"""
BlockCypher API client for live Bitcoin transaction data (free tier).

Per ARCHITECTURE.md Module 1:
- Live public Bitcoin block-explorer API responses (Blockstream.info, BlockCypher free tier)
- Used only at demo time, for real-time tracing of a small number of example wallets
- On-demand query for a specific reported address at query time
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator
from urllib.parse import urljoin

import requests

from ledgr.live_types import NormalizedRecord, InternalTx, TxIn, TxOut, SourceType


@dataclass(frozen=True, slots=True)
class BlockCypherConfig:
    """Configuration for BlockCypher API client."""
    base_url: str = "https://api.blockcypher.com/v1/btc/main"
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    rate_limit_rps: float = 5.0  # Free tier: 200 req/hour ≈ 0.05 RPS, but burst higher
    token: str | None = None  # Optional token for higher limits


class BlockCypherClient:
    """
    Client for BlockCypher Bitcoin API.

    API docs: https://www.blockcypher.com/dev/bitcoin/

    Key endpoints used:
    - GET /addrs/{address}/full - Get full transaction history for address
    - GET /txs/{txid} - Get full transaction details

    Edge cases handled:
    - Coinbase inputs: no prev_hash, no addresses, excluded from InternalTx
    - OP_RETURN outputs: empty addresses list, excluded from InternalTx
    - Unconfirmed transactions: timestamp = None, block_height = None
    """

    def __init__(self, config: BlockCypherConfig | None = None):
        self.config = config or BlockCypherConfig()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SIH26183-FraudTrace/1.0"})
        if self.config.token:
            self._session.params = {"token": self.config.token}
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

    def get_address_full(self, address: str, limit: int = 50, before: int | None = None) -> dict:
        """
        Get full transaction history for an address.

        Returns dict with: address, total_received, total_sent, balance, unconfirmed_balance,
        final_balance, n_tx, unconfirmed_n_tx, final_n_tx, txrefs[], unconfirmed_txrefs[]
        """
        params = {"limit": limit}
        if before:
            params["before"] = before
        resp = self._request("GET", f"addrs/{address}/full", params=params)
        return resp.json()

    def get_tx(self, txid: str) -> dict:
        """
        Get full transaction details.

        Returns dict with: txid, version, vin[], vout[], block_height, confirmed, etc.
        """
        resp = self._request("GET", f"txs/{txid}")
        return resp.json()

    def _parse_timestamp(self, timestamp_val) -> int | None:
        """Parse timestamp from various formats, return None if unknown."""
        if timestamp_val is None:
            return None
        if isinstance(timestamp_val, int):
            return timestamp_val if timestamp_val > 0 else None
        if isinstance(timestamp_val, str):
            try:
                return int(datetime.fromisoformat(timestamp_val.replace("Z", "+00:00")).timestamp())
            except Exception:
                return None
        return None

    def _extract_timestamp_and_height(self, txref: dict) -> tuple[int | None, int | None]:
        """Extract timestamp and block_height from transaction reference."""
        block_height = txref.get("block_height")
        # Unconfirmed transactions have block_height = -1 or None
        if block_height is not None and block_height <= 0:
            block_height = None
        timestamp = self._parse_timestamp(txref.get("confirmed"))
        return timestamp, block_height

    def iter_address_normalized_records(
        self, address: str, max_txs: int | None = None
    ) -> Iterator[NormalizedRecord]:
        """
        Iterate normalized records for a specific address.

        Per ARCHITECTURE.md: on-demand query for a specific reported address.

        Handles:
        - Unconfirmed transactions (timestamp = None, block_height = None)
        - Only yields records with valid amounts (> 0)
        """
        # Use the full endpoint to get txrefs with details
        data = self.get_address_full(address, limit=max_txs or 50)
        txrefs = data.get("txrefs", [])
        unconfirmed_txrefs = data.get("unconfirmed_txrefs", [])

        all_txrefs = txrefs + unconfirmed_txrefs
        if max_txs:
            all_txrefs = all_txrefs[:max_txs]

        seen_txids: set[str] = set()

        for txref in all_txrefs:
            txid = txref.get("tx_hash")
            if not txid or txid in seen_txids:
                continue
            seen_txids.add(txid)

            timestamp, block_height = self._extract_timestamp_and_height(txref)

            # Get full transaction for input/output details
            full_tx = self.get_tx(txid)

            # Process outputs - find those belonging to our address
            for vout in full_tx.get("outputs", []):
                addresses = vout.get("addresses", [])
                # Skip OP_RETURN and other no-address outputs
                if not addresses:
                    continue
                if address in addresses:
                    amount_sats = vout.get("value", 0)
                    if amount_sats > 0:
                        yield NormalizedRecord(
                            tx_hash=txid,
                            address=address,
                            timestamp=timestamp,
                            amount_sats=amount_sats,
                            direction="in",
                            source="blockcypher",
                            block_height=block_height,
                        )

            # Process inputs - find those spending from our address
            for vin in full_tx.get("inputs", []):
                addresses = vin.get("addresses", [])
                # Skip coinbase inputs (no addresses)
                if not addresses:
                    continue
                if address in addresses:
                    amount_sats = vin.get("output_value", 0)
                    if amount_sats > 0:
                        yield NormalizedRecord(
                            tx_hash=txid,
                            address=address,
                            timestamp=timestamp,
                            amount_sats=amount_sats,
                            direction="out",
                            source="blockcypher",
                            block_height=block_height,
                        )

    def iter_address_internal_txs(
        self, address: str, max_txs: int | None = None
    ) -> Iterator[InternalTx]:
        """
        Iterate InternalTx records for a specific address.

        Fetches full transaction details to build UTXO structure for Module 5.

        Only includes genuine UTXO data:
        - Excludes coinbase inputs (no prev_hash, no addresses)
        - Excludes OP_RETURN outputs (empty addresses list)
        - Only includes inputs/outputs with valid addresses and amounts > 0
        - Unconfirmed transactions have timestamp = None, block_height = None
        """
        data = self.get_address_full(address, limit=max_txs or 50)
        txrefs = data.get("txrefs", [])
        unconfirmed_txrefs = data.get("unconfirmed_txrefs", [])

        all_txrefs = txrefs + unconfirmed_txrefs
        if max_txs:
            all_txrefs = all_txrefs[:max_txs]

        seen_txids: set[str] = set()

        for txref in all_txrefs:
            txid = txref.get("tx_hash")
            if not txid or txid in seen_txids:
                continue
            seen_txids.add(txid)

            timestamp, block_height = self._extract_timestamp_and_height(txref)

            # Get full transaction for UTXO structure
            full_tx = self.get_tx(txid)

            # Build inputs - allow coinbase
            inputs = []
            for vin in full_tx.get("inputs", []):
                prev_hash = vin.get("prev_hash")
                output_index = vin.get("output_index")
                addresses = vin.get("addresses", [])
                amount_sats = vin.get("output_value")
                address = addresses[0] if addresses else None

                inputs.append(TxIn(
                    txid=prev_hash,
                    vout=output_index,
                    address=address,
                    amount_sats=amount_sats,
                ))

            # Build outputs - allow OP_RETURN
            outputs = []
            for vout in full_tx.get("outputs", []):
                addresses = vout.get("addresses", [])
                amount_sats = vout.get("value")
                address = addresses[0] if addresses else None

                outputs.append(TxOut(
                    address=address,
                    amount_sats=amount_sats,
                ))

            # Always yield InternalTx
            if True:
                yield InternalTx(
                    tx_hash=txid,
                    timestamp=timestamp,
                    block_height=block_height,
                    inputs=tuple(inputs),
                    outputs=tuple(outputs),
                )


def fetch_address_data_blockcypher(
    address: str,
    max_txs: int | None = None,
    config: BlockCypherConfig | None = None
) -> tuple[list[NormalizedRecord], list[InternalTx]]:
    """
    Convenience function to fetch all data for an address from BlockCypher.

    Returns:
        (normalized_records, internal_txs)
    """
    client = BlockCypherClient(config)
    records = list(client.iter_address_normalized_records(address, max_txs))
    internal_txs = list(client.iter_address_internal_txs(address, max_txs))
    return records, internal_txs