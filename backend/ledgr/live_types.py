"""
Core data types for Module 1 — Data Ingestion.

Following ARCHITECTURE.md exactly:
- NormalizedRecord: one record per address-per-transaction (downstream interface)
- InternalTx: transaction-level map keyed by tx_hash (for Module 5 clustering)
- TxIn / TxOut: UTXO structure for InternalTx
"""

from dataclasses import dataclass
from typing import Literal
import re


# Valid source identifiers for normalized records
SourceType = Literal["elliptic", "blockstream", "blockcypher"]
DirectionType = Literal["in", "out"]

# Bitcoin tx hash regex: 64 hex characters
BITCOIN_TX_HASH_PATTERN = re.compile(r'^[0-9a-f]{64}$')


def _validate_bitcoin_tx_hash(tx_hash: str) -> None:
    """Validate that tx_hash is a valid 64-char lowercase hex string (Bitcoin transaction hash)."""
    if not isinstance(tx_hash, str) or not BITCOIN_TX_HASH_PATTERN.match(tx_hash):
        raise ValueError(f"tx_hash must be 64-char lowercase hex (Bitcoin hash), got: {tx_hash}")


def _validate_elliptic_id(elliptic_id: str) -> None:
    """Validate that elliptic_id is a non-empty string (Elliptic dataset anonymized ID)."""
    if not isinstance(elliptic_id, str) or len(elliptic_id) == 0:
        raise ValueError(f"elliptic_id must be non-empty string, got: {elliptic_id}")


@dataclass(frozen=True, slots=True)
class NormalizedRecord:
    """
    Normalized transaction record — downstream interface for Modules 2, 3a, 3b.

    Schema per ARCHITECTURE.md Module 1:
    - tx_hash: string (64-char hex) — Bitcoin transaction hash (live sources only)
    - elliptic_id: string | None — Elliptic dataset anonymized transaction ID (Elliptic source only)
    - address: string (Bitcoin address, base58/bech32)
    - timestamp: integer | None (Unix epoch seconds, None if unknown)
    - amount_sats: integer (satoshis, > 0)
    - direction: "in" | "out" (relative to the address)
    - source: "elliptic" | "blockstream" | "blockcypher"
    - block_height: integer | null (optional, live data only)
    """
    tx_hash: str | None = None
    elliptic_id: str | None = None
    address: str = ""
    timestamp: int | None = None
    amount_sats: int = 0
    direction: DirectionType = "in"
    source: SourceType = "elliptic"
    block_height: int | None = None

    def __post_init__(self):
        """Validate record invariants."""
        # Source-specific validation
        if self.source == "elliptic":
            if self.elliptic_id is None:
                raise ValueError("Elliptic records must have elliptic_id")
            _validate_elliptic_id(self.elliptic_id)
            if self.tx_hash is not None:
                raise ValueError("Elliptic records must not have tx_hash (use elliptic_id)")
        else:
            # blockstream or blockcypher - must have Bitcoin tx hash
            if self.tx_hash is None:
                raise ValueError(f"{self.source} records must have tx_hash")
            _validate_bitcoin_tx_hash(self.tx_hash)
            if self.elliptic_id is not None:
                raise ValueError(f"{self.source} records must not have elliptic_id")

        if not isinstance(self.address, str) or len(self.address) == 0:
            raise ValueError(f"address must be non-empty string, got: {self.address}")
        if self.timestamp is not None and (not isinstance(self.timestamp, int) or self.timestamp <= 0):
            raise ValueError(f"timestamp must be positive integer or None, got: {self.timestamp}")
        if not isinstance(self.amount_sats, int) or self.amount_sats <= 0:
            raise ValueError(f"amount_sats must be positive integer, got: {self.amount_sats}")
        if self.direction not in ("in", "out"):
            raise ValueError(f"direction must be 'in' or 'out', got: {self.direction}")
        if self.source not in ("elliptic", "blockstream", "blockcypher"):
            raise ValueError(f"source must be elliptic/blockstream/blockcypher, got: {self.source}")
        if self.block_height is not None and (not isinstance(self.block_height, int) or self.block_height < 0):
            raise ValueError(f"block_height must be non-negative integer or None, got: {self.block_height}")

    @property
    def tx_identifier(self) -> str:
        """Return the transaction identifier appropriate for this record's source."""
        if self.source == "elliptic":
            return self.elliptic_id or ""
        return self.tx_hash or ""


@dataclass(frozen=True, slots=True)
class TxIn:
    """
    Transaction input — part of InternalTx UTXO structure.

    Per ARCHITECTURE.md:
    {txid: str, vout: int, address: str, amount_sats: int}

    All fields must be populated from genuine UTXO data (live Bitcoin sources only).
    Coinbase inputs have no prevout - they are excluded from InternalTx.
    """
    txid: str | None = None
    vout: int | None = None
    address: str | None = None
    amount_sats: int | None = None

    def __post_init__(self):
        if self.txid is not None:
            _validate_bitcoin_tx_hash(self.txid)
        if self.vout is not None and (not isinstance(self.vout, int) or self.vout < 0):
            raise ValueError(f"vout must be non-negative integer, got: {self.vout}")
        if self.amount_sats is not None and (not isinstance(self.amount_sats, int) or self.amount_sats < 0):
            raise ValueError(f"amount_sats must be non-negative integer, got: {self.amount_sats}")


@dataclass(frozen=True, slots=True)
class TxOut:
    """
    Transaction output — part of InternalTx UTXO structure.

    Per ARCHITECTURE.md:
    {address: str, amount_sats: int}

    OP_RETURN outputs (no address) are excluded from InternalTx.
    """
    address: str | None = None
    amount_sats: int | None = None

    def __post_init__(self):
        if self.amount_sats is not None and (not isinstance(self.amount_sats, int) or self.amount_sats < 0):
            raise ValueError(f"amount_sats must be non-negative integer, got: {self.amount_sats}")


@dataclass(frozen=True, slots=True)
class InternalTx:
    """
    Internal transaction index entry — for Module 5 clustering only.

    Per ARCHITECTURE.md Module 1:
    - tx_hash: str (64-char hex, Bitcoin transaction hash)
    - timestamp: int | None (Unix epoch seconds, None if unknown)
    - block_height: int | None
    - inputs: list[TxIn] (genuine UTXO inputs only; coinbase excluded)
    - outputs: list[TxOut] (genuine UTXO outputs only; OP_RETURN excluded)

    This is NOT passed to Modules 2/3a/3b — stored alongside normalized stream
    and made available only to Module 5 for common-input / change-address clustering.

    InternalTx is ONLY constructed from live Bitcoin data sources (blockstream, blockcypher)
    where genuine UTXO structure is available. Elliptic dataset does NOT provide UTXO data
    and therefore does NOT produce InternalTx records.
    """
    tx_hash: str
    timestamp: int | None
    block_height: int | None
    inputs: tuple[TxIn, ...]
    outputs: tuple[TxOut, ...]

    def __post_init__(self):
        _validate_bitcoin_tx_hash(self.tx_hash)
        if self.timestamp is not None and (not isinstance(self.timestamp, int) or self.timestamp <= 0):
            raise ValueError(f"timestamp must be positive integer or None, got: {self.timestamp}")
        if self.block_height is not None and (not isinstance(self.block_height, int) or self.block_height < 0):
            raise ValueError(f"block_height must be non-negative integer or None, got: {self.block_height}")
        if not isinstance(self.inputs, tuple):
            raise ValueError("inputs must be tuple[TxIn, ...]")
        if not isinstance(self.outputs, tuple):
            raise ValueError("outputs must be tuple[TxOut, ...]")
        for inp in self.inputs:
            if not isinstance(inp, TxIn):
                raise ValueError(f"All inputs must be TxIn, got: {type(inp)}")
        for out in self.outputs:
            if not isinstance(out, TxOut):
                raise ValueError(f"All outputs must be TxOut, got: {type(out)}")

    @property
    def input_list(self) -> list[TxIn]:
        """Return inputs as list (for mutation if needed)."""
        return list(self.inputs)

    @property
    def output_list(self) -> list[TxOut]:
        """Return outputs as list (for mutation if needed)."""
        return list(self.outputs)