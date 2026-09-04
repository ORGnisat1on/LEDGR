"""
Main ingestion pipeline for Module 1.

Per ARCHITECTURE.md Module 1:
- Ingests static dataset once (batch, at training time)
- Queries live APIs only on-demand for a specific reported address at query time
- MVP intake accepts one reported address per submission
- Produces two artifacts:
  1. Normalized record stream (downstream interface for Modules 2, 3a, 3b)
  2. Internal transaction index (for Module 5 clustering) - ONLY from live Bitcoin sources
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator

from .types import NormalizedRecord, InternalTx, SourceType
from .elliptic_ingest import EllipticIngestor, ingest_elliptic_dataset
from .blockstream_client import BlockstreamClient, fetch_address_data_blockstream, BlockstreamConfig
from .blockcypher_client import BlockCypherClient, fetch_address_data_blockcypher, BlockCypherConfig


class DataSource(Enum):
    """Data source selection for ingestion."""
    ELLIPTIC = "elliptic"      # Static dataset for training/evaluation
    BLOCKSTREAM = "blockstream"  # Live API for demo-time tracing
    BLOCKCYPHER = "blockcypher"  # Live API for demo-time tracing (fallback/alternative)


@dataclass(frozen=True, slots=True)
class IngestionConfig:
    """Configuration for the ingestion pipeline."""
    # Static dataset
    elliptic_data_dir: str | Path | None = None

    # Live API configs
    blockstream_config: BlockstreamConfig | None = None
    blockcypher_config: BlockCypherConfig | None = None

    # Query limits
    max_txs_per_address: int | None = 100  # Limit for live API queries

    # Source preference for live queries (try in order)
    live_source_preference: tuple[DataSource, ...] = (DataSource.BLOCKSTREAM, DataSource.BLOCKCYPHER)


class IngestionPipeline:
    """
    Main ingestion pipeline coordinating all data sources.

    Per ARCHITECTURE.md:
    - Batch ingestion of Elliptic dataset at training time
    - On-demand live API queries for reported addresses at demo/query time
    - Produces normalized records from all sources
    - Produces internal transaction index ONLY from live Bitcoin sources (Blockstream, BlockCypher)
      because Elliptic lacks genuine UTXO structure
    """

    def __init__(self, config: IngestionConfig | None = None):
        self.config = config or IngestionConfig()
        self._elliptic_ingestor: EllipticIngestor | None = None

    def _get_elliptic_ingestor(self) -> EllipticIngestor:
        """Lazy initialization of Elliptic ingestor."""
        if self._elliptic_ingestor is None:
            if not self.config.elliptic_data_dir:
                raise ValueError("elliptic_data_dir must be set in config for Elliptic ingestion")
            self._elliptic_ingestor = EllipticIngestor(self.config.elliptic_data_dir)
        return self._elliptic_ingestor

    def ingest_elliptic_batch(self) -> list[NormalizedRecord]:
        """
        Ingest the full Elliptic dataset (batch, at training time).

        Returns:
            normalized_records - list in memory

        Note: Elliptic does NOT produce InternalTx records because it lacks
        genuine UTXO structure (prev_txid, vout, amounts). InternalTx is only
        available from live Bitcoin data sources.
        """
        ingestor = self._get_elliptic_ingestor()
        return ingest_elliptic_dataset(self.config.elliptic_data_dir)

    def iter_elliptic_normalized_records(self) -> Iterator[NormalizedRecord]:
        """Iterate normalized records from Elliptic dataset (memory efficient)."""
        ingestor = self._get_elliptic_ingestor()
        yield from ingestor.iter_normalized_records()

    def get_elliptic_address_tx_mapping(self) -> dict[str, list[str]]:
        """
        Get Elliptic++ address -> txId mapping for Module 5 clustering.

        This provides the static Elliptic transaction/address relationships
        from AddrTx_edgelist.csv for common-input clustering without
        misrepresenting them as UTXO data.
        """
        ingestor = self._get_elliptic_ingestor()
        return ingestor.get_address_tx_mapping()

    def get_elliptic_txid_address_mapping(self) -> dict[str, list[str]]:
        """
        Get Elliptic++ txId -> address mapping for Module 5 clustering.

        This provides the static Elliptic transaction/address relationships
        from TxAddr_edgelist.csv.
        """
        ingestor = self._get_elliptic_ingestor()
        return ingestor.get_txid_address_mapping()

    def ingest_live_address(
        self,
        address: str,
        source: DataSource | None = None,
        max_txs: int | None = None
    ) -> tuple[list[NormalizedRecord], list[InternalTx]]:
        """
        Ingest transaction data for a specific address from live API (on-demand).

        Per ARCHITECTURE.md: MVP intake accepts one reported address per submission.

        Args:
            address: Bitcoin address to trace
            source: Specific source to use (None = use preference order)
            max_txs: Maximum transactions to fetch (default from config)

        Returns:
            (normalized_records, internal_txs) - both from live Bitcoin data with genuine UTXO structure

        Raises:
            ValueError: If no live source is configured or all sources fail
        """
        max_txs = max_txs or self.config.max_txs_per_address

        sources_to_try = [source] if source else list(self.config.live_source_preference)

        last_error: Exception | None = None
        for src in sources_to_try:
            try:
                if src == DataSource.BLOCKSTREAM:
                    if not self.config.blockstream_config:
                        # Use defaults
                        return fetch_address_data_blockstream(address, max_txs)
                    return fetch_address_data_blockstream(address, max_txs, self.config.blockstream_config)
                elif src == DataSource.BLOCKCYPHER:
                    if not self.config.blockcypher_config:
                        return fetch_address_data_blockcypher(address, max_txs)
                    return fetch_address_data_blockcypher(address, max_txs, self.config.blockcypher_config)
                elif src == DataSource.ELLIPTIC:
                    raise ValueError("Elliptic is a batch source, not for live address queries")
            except Exception as e:
                last_error = e
                continue

        raise ValueError(f"All live sources failed for address {address}. Last error: {last_error}")

    def iter_live_normalized_records(
        self,
        address: str,
        source: DataSource | None = None,
        max_txs: int | None = None
    ) -> Iterator[NormalizedRecord]:
        """Iterate normalized records for a live address (memory efficient)."""
        records, _ = self.ingest_live_address(address, source, max_txs)
        yield from records

    def iter_live_internal_txs(
        self,
        address: str,
        source: DataSource | None = None,
        max_txs: int | None = None
    ) -> Iterator[InternalTx]:
        """Iterate internal transactions for a live address (memory efficient)."""
        _, internal_txs = self.ingest_live_address(address, source, max_txs)
        yield from internal_txs


def create_pipeline(
    elliptic_data_dir: str | Path | None = None,
    blockcypher_token: str | None = None,
    max_txs_per_address: int = 100
) -> IngestionPipeline:
    """
    Factory function to create a configured ingestion pipeline.

    Args:
        elliptic_data_dir: Path to Elliptic dataset (for training)
        blockcypher_token: Optional BlockCypher API token for higher rate limits
        max_txs_per_address: Max transactions to fetch per live address query

    Returns:
        Configured IngestionPipeline instance
    """
    blockstream_cfg = BlockstreamConfig()
    blockcypher_cfg = BlockCypherConfig(token=blockcypher_token) if blockcypher_token else BlockCypherConfig()

    config = IngestionConfig(
        elliptic_data_dir=elliptic_data_dir,
        blockstream_config=blockstream_cfg,
        blockcypher_config=blockcypher_cfg,
        max_txs_per_address=max_txs_per_address,
    )
    return IngestionPipeline(config)


# Convenience functions for the two main use cases per ARCHITECTURE.md

def ingest_training_data(data_dir: str | Path) -> list[NormalizedRecord]:
    """
    Ingest Elliptic dataset for training/evaluation (batch, one-time).

    Per ARCHITECTURE.md: "ingests the static dataset once (batch, at training time)"

    Returns:
        normalized_records only (Elliptic has no UTXO data for InternalTx)
    """
    return ingest_elliptic_dataset(data_dir)


def ingest_reported_address(
    address: str,
    prefer_source: str = "blockstream",
    max_txs: int = 100,
    blockcypher_token: str | None = None
) -> tuple[list[NormalizedRecord], list[InternalTx]]:
    """
    Ingest transaction data for a reported wallet address (on-demand, query time).

    Per ARCHITECTURE.md: "queries live APIs only on-demand for a specific reported
    address at query time. MVP intake accepts one reported address per submission"

    Args:
        address: Bitcoin address from complaint-intake interface (Module 6)
        prefer_source: "blockstream" or "blockcypher"
        max_txs: Maximum transactions to fetch
        blockcypher_token: Optional API token for BlockCypher

    Returns:
        (normalized_records, internal_txs) for downstream modules
    """
    source = DataSource.BLOCKSTREAM if prefer_source == "blockstream" else DataSource.BLOCKCYPHER
    pipeline = create_pipeline(
        blockcypher_token=blockcypher_token,
        max_txs_per_address=max_txs
    )
    return pipeline.ingest_live_address(address, source=source, max_txs=max_txs)