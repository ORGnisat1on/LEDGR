"""
Elliptic/Elliptic++ static dataset ingestion.

Per ARCHITECTURE.md Module 1:
- Input: Elliptic/Elliptic++ static dataset (CSV/Parquet, Kaggle) — used for training and evaluation
- Output: NormalizedRecord stream (NO InternalTx - Elliptic lacks genuine UTXO data)

The Elliptic dataset structure (from Kaggle):
- elliptic_txs_classes.csv: txId, class (1=licit, 2=illicit, unknown)
- elliptic_txs_features.csv: txId, time_step, 166 features (94 local, 72 aggregated)
- elliptic_txs_edgelist.csv: txId1, txId2 (directed edges = transactions between addresses)
- elliptic_plus_plus_actor_mapping.csv: actor_id, address (optional, for Elliptic++)
- AddrTx_edgelist.csv: address, txId (Elliptic++ address-transaction edges)
- TxAddr_edgelist.csv: txId, address (Elliptic++ transaction-address edges)

For Elliptic++, there's also actor_id mapping for labeled addresses.

IMPORTANT: Elliptic txIds are ANONYMIZED DATASET IDs, not Bitcoin transaction hashes.
They are stored in NormalizedRecord.elliptic_id, NOT in tx_hash.
Elliptic does NOT provide UTXO structure (prev_txid, vout, amounts), so it does NOT
produce InternalTx records. InternalTx is ONLY for live Bitcoin data sources.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from .types import NormalizedRecord, SourceType


class EllipticIngestor:
    """
    Ingests the Elliptic/Elliptic++ dataset from CSV files.

    Expected file layout (Kaggle download):
    data/
      elliptic_txs_classes.csv
      elliptic_txs_features.csv
      elliptic_txs_edgelist.csv
      elliptic_plus_plus_actor_mapping.csv  # optional, for Elliptic++
      AddrTx_edgelist.csv  # optional, Elliptic++ address-transaction edges
      TxAddr_edgelist.csv  # optional, Elliptic++ transaction-address edges
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self._txid_to_timestamp: dict[str, int] = {}
        self._txid_to_blockheight: dict[str, int] = {}
        self._address_to_txids: dict[str, list[str]] = {}  # address -> list of elliptic txIds
        self._txid_to_addresses: dict[str, list[str]] = {}  # elliptic txId -> list of addresses

    def load_metadata(self) -> None:
        """Load timestamp and block height info from features file."""
        features_path = self.data_dir / "elliptic_txs_features.csv"
        if not features_path.exists():
            raise FileNotFoundError(f"Features file not found: {features_path}")

        with features_path.open() as f:
            reader = csv.reader(f)
            header = next(reader)  # txId, time_step, feat_1, ..., feat_166
            # time_step is column 1 (0-indexed)
            for row in reader:
                if len(row) < 2:
                    continue
                txid = row[0]
                time_step = int(row[1])
                # Convert time_step to approximate timestamp
                # Elliptic time_steps are 2-week intervals starting from 2009-01-03
                # Genesis block timestamp: 1230940800 (2009-01-03)
                # Each step = 2 weeks = 1209600 seconds
                genesis_ts = 1230940800
                step_seconds = 1209600
                self._txid_to_timestamp[txid] = genesis_ts + time_step * step_seconds
                # Block height approximation: ~144 blocks/day, ~2016 blocks per 2-week step
                self._txid_to_blockheight[txid] = time_step * 2016

    def load_elliptic_plus_plus_relations(self) -> None:
        """
        Load Elliptic++ address-transaction relations from AddrTx_edgelist.csv and TxAddr_edgelist.csv.

        These files provide the mapping between addresses and transaction IDs that the base
        Elliptic dataset lacks. They enable building proper address-level normalized records
        and support common-input clustering for Module 5.

        NOTE: These relationships are Elliptic-native and must NOT be misrepresented as
        prev_txid/vout UTXO data. They are stored separately for Module 5 clustering use.
        """
        # Load AddrTx_edgelist.csv: address -> txId
        addrtx_path = self.data_dir / "AddrTx_edgelist.csv"
        if addrtx_path.exists():
            with addrtx_path.open() as f:
                reader = csv.reader(f)
                header = next(reader, None)  # address, txId
                for row in reader:
                    if len(row) < 2:
                        continue
                    address, txid = row[0], row[1]
                    if address not in self._address_to_txids:
                        self._address_to_txids[address] = []
                    self._address_to_txids[address].append(txid)

        # Load TxAddr_edgelist.csv: txId -> address
        txaddr_path = self.data_dir / "TxAddr_edgelist.csv"
        if txaddr_path.exists():
            with txaddr_path.open() as f:
                reader = csv.reader(f)
                header = next(reader, None)  # txId, address
                for row in reader:
                    if len(row) < 2:
                        continue
                    txid, address = row[0], row[1]
                    if txid not in self._txid_to_addresses:
                        self._txid_to_addresses[txid] = []
                    self._txid_to_addresses[txid].append(address)

    def iter_normalized_records(self) -> Iterator[NormalizedRecord]:
        """
        Iterate over normalized records from the Elliptic dataset.

        Uses Elliptic++ address-transaction relations (AddrTx_edgelist.csv, TxAddr_edgelist.csv)
        when available to produce proper per-address-per-transaction records.
        Falls back to edgelist interpretation if Elliptic++ files are not present.

        Amount is set to 1 sat (placeholder) since actual amounts aren't in base Elliptic.
        Timestamps are derived from time_step; unknown timestamps yield None.
        """
        if not self._txid_to_timestamp:
            self.load_metadata()

        # Try to load Elliptic++ relations for proper address-level records
        if not self._address_to_txids and not self._txid_to_addresses:
            self.load_elliptic_plus_plus_relations()

        # If we have Elliptic++ address-tx relations, use them
        if self._txid_to_addresses:
            for txid, addresses in self._txid_to_addresses.items():
                timestamp = self._txid_to_timestamp.get(txid)
                block_height = self._txid_to_blockheight.get(txid)

                # We don't know direction from Elliptic++ alone; default to "in"
                # In practice, direction would need additional heuristics or data
                for address in addresses:
                    yield NormalizedRecord(
                        elliptic_id=txid,
                        address=address,
                        timestamp=timestamp,
                        amount_sats=1,  # Placeholder - Elliptic doesn't have amounts
                        direction="in",  # Default; Elliptic++ doesn't specify direction
                        source="elliptic",
                        block_height=block_height,
                    )
            return

        # Fallback: use base edgelist (tx-to-tx) - each txId treated as an address cluster
        edgelist_path = self.data_dir / "elliptic_txs_edgelist.csv"
        if not edgelist_path.exists():
            raise FileNotFoundError(f"Edgelist file not found: {edgelist_path}")

        with edgelist_path.open() as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                if len(row) < 2:
                    continue
                src_txid, dst_txid = row[0], row[1]

                timestamp = self._txid_to_timestamp.get(src_txid)
                block_height = self._txid_to_blockheight.get(src_txid)

                # Source (outgoing) - txId used as address identifier
                yield NormalizedRecord(
                    elliptic_id=src_txid,
                    address=src_txid,  # Using txId as address identifier in base Elliptic
                    timestamp=timestamp,
                    amount_sats=1,  # Placeholder - Elliptic doesn't have amounts
                    direction="out",
                    source="elliptic",
                    block_height=block_height,
                )

                # Destination (incoming)
                yield NormalizedRecord(
                    elliptic_id=dst_txid,
                    address=dst_txid,
                    timestamp=timestamp,
                    amount_sats=1,
                    direction="in",
                    source="elliptic",
                    block_height=block_height,
                )

    def get_address_tx_mapping(self) -> dict[str, list[str]]:
        """
        Get the address -> list of elliptic txIds mapping for Module 5 clustering.

        This uses Elliptic++ AddrTx_edgelist.csv when available, providing the
        static Elliptic transaction/address relationships needed for common-input
        clustering without misrepresenting them as UTXO data.
        """
        if not self._address_to_txids:
            self.load_elliptic_plus_plus_relations()
        return self._address_to_txids.copy()

    def get_txid_address_mapping(self) -> dict[str, list[str]]:
        """
        Get the elliptic txId -> list of addresses mapping for Module 5 clustering.

        This uses Elliptic++ TxAddr_edgelist.csv when available.
        """
        if not self._txid_to_addresses:
            self.load_elliptic_plus_plus_relations()
        return self._txid_to_addresses.copy()


def ingest_elliptic_dataset(data_dir: str | Path) -> list[NormalizedRecord]:
    """
    Convenience function to ingest entire Elliptic dataset into memory.

    Returns:
        normalized_records (Elliptic does NOT produce InternalTx - no UTXO data)
    """
    ingestor = EllipticIngestor(data_dir)
    records = list(ingestor.iter_normalized_records())
    return records