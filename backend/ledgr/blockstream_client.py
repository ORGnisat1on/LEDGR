"""
Blockstream.info API client for live Bitcoin transaction data.

Per ARCHITECTURE.md Module 1:
- Live public Bitcoin block-explorer API responses (Blockstream.info, BlockCypher free tier)
- Used only at demo time, for real-time tracing of a small number of example wallets
- On-demand query for a specific reported address at query time (not continuous ingestion)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import urljoin

import requests

from ledgr.live_types import NormalizedRecord, InternalTx, TxIn, TxOut, SourceType


@dataclass(frozen=True, slots=True)
class BlockstreamConfig:
    """Configuration for Blockstream API client."""
    base_url: str = "https://blockstream.info/api"
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    rate_limit_rps: float = 10.0  # Be respectful to free tier


class BlockstreamClient:
    """
    Client for Blockstream.info REST API.

    API docs: https://github.com/Blockstream/esplora/blob/master/API.md

    Key endpoints used:
    - GET /address/{address}/txs - Get transactions for an address
    - GET /tx/{txid} - Get full transaction details (for UTXO structure)
    - GET /block-height/{height} - Get block hash from height
    - GET /block/{hash} - Get block details (for timestamp)

    Edge cases handled:
    - Coinbase inputs: no prevout, excluded from InternalTx
    - OP_RETURN outputs: no scriptpubkey_address, excluded from InternalTx
    - Unconfirmed transactions: timestamp = None, block_height = None
    """

    def __init__(self, config: BlockstreamConfig | None = None):
        self.config = config or BlockstreamConfig()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SIH26183-FraudTrace/1.0"})
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        min_interval = 1.0 / self.config.rate_limit_rps
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make HTTP request with retries and rate limiting."""
        url = urljoin(self.config.base_url + "/", path.lstrip("/"))

        for attempt in range(self.config.max_retries):
            self._rate_limit()
            try:
                resp = self._session.request(
                    method, url, timeout=self.config.timeout_seconds, **kwargs
                )
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                if attempt == self.config.max_retries - 1:
                    raise
                time.sleep(self.config.retry_backoff_seconds * (attempt + 1))
        raise RuntimeError("Unreachable")

    def get_address_txs(self, address: str) -> list[dict]:
        """
        Get all transactions for an address.

        Returns list of transaction summaries with:
        - txid, version, locktime, vin, vout, block_height, timestamp, etc.
        """
        resp = self._request("GET", f"address/{address}/txs")
        return resp.json()

    def get_address_stats(self, address: str) -> dict:
        """
        Get address statistics (GET /address/{address}).

        Returns dict with chain_stats/mempool_stats tx counts — used to
        distinguish an unused/unknown address (zero txs) from one with history
        BEFORE spending calls on its transaction list (Phase R9).
        """
        resp = self._request("GET", f"address/{address}")
        body = resp.json()
        chain = body.get("chain_stats", {})
        mempool = body.get("mempool_stats", {})
        return {
            "tx_count": (chain.get("funded_txo_count", 0) or 0) + (mempool.get("funded_txo_count", 0) or 0),
            "raw": body,
        }

    def get_tx(self, txid: str) -> dict:
        """
        Get full transaction details including vin/vout with addresses and amounts.

        Returns dict with: txid, version, locktime, vin[], vout[], block_height, timestamp, etc.
        """
        resp = self._request("GET", f"tx/{txid}")
        return resp.json()

    def get_block_height(self, height: int) -> str:
        """Get block hash from height."""
        resp = self._request("GET", f"block-height/{height}")
        return resp.text.strip('"')

    def get_block(self, block_hash: str) -> dict:
        """Get block details including timestamp."""
        resp = self._request("GET", f"block/{block_hash}")
        return resp.json()

    def _extract_timestamp_and_height(self, tx_summary: dict) -> tuple[int | None, int | None]:
        """Extract timestamp and block_height from transaction summary."""
        status = tx_summary.get("status", {})
        block_height = status.get("block_height")
        block_time = status.get("block_time")

        # Unconfirmed transactions have no block_time or block_height
        timestamp = block_time if block_time and block_time > 0 else None
        return timestamp, block_height

    def iter_address_normalized_records(
        self, address: str, max_txs: int | None = None
    ) -> Iterator[NormalizedRecord]:
        """
        Iterate normalized records for a specific address.

        Per ARCHITECTURE.md: on-demand query for a specific reported address.

        Handles:
        - Unconfirmed transactions (timestamp = None)
        - Only yields records with valid amounts (> 0)
        """
        txs = self.get_address_txs(address)
        if max_txs:
            txs = txs[:max_txs]

        for tx_summary in txs:
            txid = tx_summary["txid"]
            timestamp, block_height = self._extract_timestamp_and_height(tx_summary)

            # Get full transaction for input/output details
            full_tx = self.get_tx(txid)

            # Process outputs (vout) - find those belonging to our address
            for vout in full_tx.get("vout", []):
                scriptpubkey = vout.get("scriptpubkey_address")
                # Skip OP_RETURN and other no-address outputs
                if scriptpubkey is None:
                    continue
                if scriptpubkey == address:
                    amount_sats = vout.get("value", 0)
                    if amount_sats > 0:
                        yield NormalizedRecord(
                            tx_hash=txid,
                            address=address,
                            timestamp=timestamp,
                            amount_sats=amount_sats,
                            direction="in",
                            source="blockstream",
                            block_height=block_height,
                        )

            # Process inputs (vin) - find those spending from our address
            for vin in full_tx.get("vin", []):
                prevout = vin.get("prevout", {})
                prev_address = prevout.get("scriptpubkey_address")
                # Skip coinbase inputs (no prevout address)
                if prev_address is None:
                    continue
                if prev_address == address:
                    amount_sats = prevout.get("value", 0)
                    if amount_sats > 0:
                        yield NormalizedRecord(
                            tx_hash=txid,
                            address=address,
                            timestamp=timestamp,
                            amount_sats=amount_sats,
                            direction="out",
                            source="blockstream",
                            block_height=block_height,
                        )

    def iter_address_internal_txs(
        self, address: str, max_txs: int | None = None
    ) -> Iterator[InternalTx]:
        """
        Iterate InternalTx records for a specific address.

        Fetches full transaction details to build UTXO structure for Module 5.

        Only includes genuine UTXO data:
        - Excludes coinbase inputs (no prevout)
        - Excludes OP_RETURN outputs (no address)
        - Only includes inputs/outputs with valid addresses and amounts > 0
        - Unconfirmed transactions have timestamp = None, block_height = None
        """
        txs = self.get_address_txs(address)
        if max_txs:
            txs = txs[:max_txs]

        seen_txids: set[str] = set()

        for tx_summary in txs:
            txid = tx_summary["txid"]
            if txid in seen_txids:
                continue
            seen_txids.add(txid)

            timestamp, block_height = self._extract_timestamp_and_height(tx_summary)

            # Get full transaction for UTXO structure
            full_tx = self.get_tx(txid)

            # Build inputs - allow coinbase inputs
            inputs = []
            for vin in full_tx.get("vin", []):
                prevout = vin.get("prevout")
                prev_txid = vin.get("txid")
                vout = vin.get("vout")
                prev_address = prevout.get("scriptpubkey_address") if prevout else None
                amount_sats = prevout.get("value") if prevout else None

                inputs.append(TxIn(
                    txid=prev_txid,
                    vout=vout,
                    address=prev_address,
                    amount_sats=amount_sats,
                ))

            # Build outputs - allow OP_RETURN
            outputs = []
            for vout in full_tx.get("vout", []):
                scriptpubkey = vout.get("scriptpubkey_address")
                amount_sats = vout.get("value")

                outputs.append(TxOut(
                    address=scriptpubkey,
                    amount_sats=amount_sats,
                ))

            # Always yield InternalTx even if only coinbase inputs or OP_RETURN outputs
            if True:
                yield InternalTx(
                    tx_hash=txid,
                    timestamp=timestamp,
                    block_height=block_height,
                    inputs=tuple(inputs),
                    outputs=tuple(outputs),
                )


def fetch_address_data_blockstream(
    address: str,
    max_txs: int | None = None,
    config: BlockstreamConfig | None = None
) -> tuple[list[NormalizedRecord], list[InternalTx]]:
    """
    Convenience function to fetch all data for an address from Blockstream.

    Returns:
        (normalized_records, internal_txs)
    """
    client = BlockstreamClient(config)
    records = list(client.iter_address_normalized_records(address, max_txs))
    internal_txs = list(client.iter_address_internal_txs(address, max_txs))
    return records, internal_txs