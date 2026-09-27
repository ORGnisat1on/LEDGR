"""Mainnet Bitcoin address format validation — LOCAL, no network call ever.

Why this module exists (hardening pass, 2026-09-26): explorer HTTP statuses are
*ambiguous evidence*. Blockstream returns 400 for a malformed address, but it
also returns 429 when we are rate-limited — and 429 is a 4xx too. Before this
module, `_default_fetcher` classified "both sources 4xx'd" as `bad-address`, so
a rate-limited lookup was reported to the user as *"address not valid"* — a
confident wrong state, the exact defect class this pass exists to eliminate.

Format validity is decidable locally, so it is decided locally, BEFORE any
block-explorer request:

  - Base58Check : P2PKH (`1…`, version 0x00) and P2SH (`3…`, version 0x05)
                  with the truncated double-SHA256 checksum verified.
  - Bech32/m    : `bc1…` witness v0 (BIP-173 bech32) and witness v1+ (BIP-350
                  bech32m), program length 2..40, v0 restricted to 20/32 bytes.
  - Mainnet only: testnet (`tb1…`, versions 0x6f/0xc4) and regtest (`bcrt1…`)
                  are rejected as `wrong-network`, never as "malformed" — they
                  are valid addresses, just not on the network we trace.

The verdict vocabulary (`reason`) is deliberately small and stable — asserted by
`backend/tests/test_address_format.py` and echoed verbatim in the user note:

    empty | too-long | non-ascii-or-whitespace | malformed | bad-checksum | wrong-network

Contract: this function never raises and never guesses. A string it accepts may
still be rejected by the explorers (that is `LiveSourceError kind 'bad-address'`,
which requires BOTH sources to agree); a string it rejects never generates a
network request at all.

Test vectors live in `backend/tests/test_address_format.py` and come from the
BIP-173 / BIP-350 specifications and bitcoin/bitcoin's `key_io_valid.json` /
`key_io_invalid.json` — not invented here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .config import MAX_ADDRESS_INPUT_LENGTH

# --- rejection vocabulary (stable; asserted by tests, echoed to the user) ---
REASON_EMPTY = "empty"
REASON_TOO_LONG = "too-long"
REASON_NON_ASCII = "non-ascii-or-whitespace"
REASON_MALFORMED = "malformed"
REASON_BAD_CHECKSUM = "bad-checksum"
REASON_WRONG_NETWORK = "wrong-network"

# --- accepted kinds (logged so callers can record what matched) -------------
KIND_P2PKH = "p2pkh"
KIND_P2SH = "p2sh"
KIND_P2WPKH = "p2wpkh"
KIND_P2WSH = "p2wsh"
KIND_WITNESS_V1_PLUS = "witness-v1-plus"

# --- Base58Check -----------------------------------------------------------
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {ch: i for i, ch in enumerate(_BASE58_ALPHABET)}
_VERSION_P2PKH = 0x00   # mainnet pay-to-pubkey-hash ('1…')
_VERSION_P2SH = 0x05    # mainnet pay-to-script-hash ('3…')

# --- Bech32 / Bech32m (BIP-173, BIP-350) -----------------------------------
_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_GEN = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
_BECH32_CONST = 1
_BECH32M_CONST = 0x2BC830A3
_MAINNET_HRP = "bc"
_MAX_BECH32_LENGTH = 90   # BIP-173 hard maximum


@dataclass(frozen=True, slots=True)
class AddressFormat:
    """Result of a local format check. Never partial, never guessed."""

    valid: bool
    reason: str = ""    # "" when valid, else one of the REASON_* constants
    detail: str = ""    # human-readable specifics for the user-facing note
    kind: str = ""      # KIND_* when valid


def _invalid(reason: str, detail: str) -> AddressFormat:
    return AddressFormat(valid=False, reason=reason, detail=detail)


def _valid(kind: str) -> AddressFormat:
    return AddressFormat(valid=True, kind=kind)


# ---------------------------------------------------------------------------
# Base58Check
# ---------------------------------------------------------------------------

def _base58check_decode(s: str) -> bytes:
    """Decode a Base58Check string → version byte + payload. Raises ValueError."""
    value = 0
    for ch in s:
        idx = _BASE58_INDEX.get(ch)
        if idx is None:
            raise ValueError(f"invalid Base58 character {ch!r}")
        value = value * 58 + idx
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""
    # Leading '1's encode leading zero bytes.
    leading_ones = len(s) - len(s.lstrip("1"))
    raw = b"\x00" * leading_ones + raw
    # Base58Check: version + payload must be exactly 25 bytes (1 + 20 + 4).
    # Anything else that "checksums" (e.g. an over-long extended key) must never
    # be reported as a checksum problem — it is a structural mismatch.
    if len(raw) != 25:
        raise ValueError(
            f"decoded to {len(raw)} bytes; a mainnet address is exactly 25 bytes "
            "(version + 20-byte hash + 4-byte checksum) — checksum not evaluated"
        )
    payload, checksum = raw[:-4], raw[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected:
        raise ValueError("Base58Check checksum mismatch (double-SHA256)")
    return payload


def _classify_base58(s: str) -> AddressFormat:
    try:
        decoded = _base58check_decode(s)
    except ValueError as exc:
        msg = str(exc)
        if "checksum mismatch" in msg:
            return _invalid(REASON_BAD_CHECKSUM, msg)
        return _invalid(REASON_MALFORMED, msg)
    version = decoded[0]
    if version == _VERSION_P2PKH:
        return _valid(KIND_P2PKH)
    if version == _VERSION_P2SH:
        return _valid(KIND_P2SH)
    return _invalid(
        REASON_WRONG_NETWORK,
        f"Base58 version byte 0x{version:02x} is not mainnet (0x00 P2PKH / 0x05 P2SH) "
        "— testnet/regtest/signet addresses are rejected",
    )


# ---------------------------------------------------------------------------
# Bech32 / Bech32m
# ---------------------------------------------------------------------------

def _polymod(values: list[int]) -> int:
    chk = 1
    for v in values:
        b = (chk >> 25) & 0x1FFFFFF
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            if (b >> i) & 1:
                chk ^= _BECH32_GEN[i]
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convertbits(data, frombits: int, tobits: int) -> list[int]:
    """Base-convert with an explicit zero-padding check (BIP-173 reference)."""
    acc = 0
    bits = 0
    out: list[int] = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise ValueError("invalid value during base conversion")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & maxv)
    if bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("non-zero padding bits")
    return out


def _bech32_decode(s: str) -> tuple[str, int, bytes, str]:
    """→ (hrp, witness_version, program, encoding). Raises ValueError."""
    if s.lower() != s and s.upper() != s:
        raise ValueError("mixed case is not allowed in bech32")
    s = s.lower()
    if len(s) > _MAX_BECH32_LENGTH:
        raise ValueError(f"longer than the {_MAX_BECH32_LENGTH}-character bech32 maximum")
    pos = s.rfind("1")
    if pos < 1:
        raise ValueError("missing separator '1'")
    hrp, data = s[:pos], s[pos + 1:]
    if len(data) < 6:
        raise ValueError("data part shorter than the 6-character checksum")
    try:
        parts = [_BECH32_CHARSET.index(c) for c in data]
    except ValueError as exc:
        raise ValueError("invalid bech32 data character") from exc
    checksum = _polymod(_hrp_expand(hrp) + parts)
    if checksum == _BECH32_CONST:
        encoding = "bech32"
    elif checksum == _BECH32M_CONST:
        encoding = "bech32m"
    else:
        raise ValueError("bech32/bech32m checksum mismatch")
    witver = parts[0]
    if witver > 16:
        raise ValueError("witness version above 16")
    if witver == 0 and encoding != "bech32":
        raise ValueError("witness version 0 must use bech32, not bech32m")
    if witver > 0 and encoding != "bech32m":
        raise ValueError("witness version 1+ must use bech32m, not bech32")
    program = bytes(_convertbits(parts[1:-6], 5, 8))
    if not 2 <= len(program) <= 40:
        raise ValueError(f"witness program length {len(program)} outside 2..40 bytes")
    if witver == 0 and len(program) not in (20, 32):
        raise ValueError("witness v0 program must be 20 (P2WPKH) or 32 (P2WSH) bytes")
    return hrp, witver, program, encoding


def _classify_bech32(s: str) -> AddressFormat:
    try:
        hrp, witver, program, _encoding = _bech32_decode(s)
    except ValueError as exc:
        msg = str(exc)
        if "checksum" in msg:
            return _invalid(REASON_BAD_CHECKSUM, msg)
        if "invalid bech32 data character" in msg or "missing separator" in msg:
            # Not a segwit string at all — fall through to Base58 so a base58
            # string containing a '1' is judged by its own encoding.
            base58 = _classify_base58(s)
            if base58.valid or base58.reason != REASON_MALFORMED:
                return base58
            return _invalid(REASON_MALFORMED, msg)
        if "witness" in msg:
            return _invalid(REASON_MALFORMED, msg)
        return _invalid(REASON_MALFORMED, msg)
    if hrp != _MAINNET_HRP:
        return _invalid(
            REASON_WRONG_NETWORK,
            f"human-readable part {hrp!r} is not mainnet 'bc' — testnet/regtest addresses are rejected",
        )
    if witver == 0:
        return _valid(KIND_P2WPKH if len(program) == 20 else KIND_P2WSH)
    return _valid(KIND_WITNESS_V1_PLUS)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def classify_address(raw) -> AddressFormat:
    """Classify user input as a mainnet Bitcoin address or not. Never raises.

    Pure and synchronous: no socket is opened and no client is constructed, so
    the verdict costs O(length) and is available before any rate-limit budget
    is spent. Surrounding whitespace is tolerated (a pasted address often
    carries a trailing newline); whitespace *inside* the string, control
    characters and non-ASCII characters are rejected — a real address never
    contains them, so this is a statement about the input, not a guess.
    """
    if not isinstance(raw, str):
        return _invalid(REASON_MALFORMED, f"input is {type(raw).__name__}, not a string")
    s = raw.strip()
    if not s:
        return _invalid(REASON_EMPTY, "the address is empty")
    if len(s) > MAX_ADDRESS_INPUT_LENGTH:
        return _invalid(
            REASON_TOO_LONG,
            f"{len(s)} characters exceeds the {MAX_ADDRESS_INPUT_LENGTH}-character maximum "
            "for a Bitcoin address",
        )
    if any(not 33 <= ord(ch) <= 126 for ch in s):
        return _invalid(
            REASON_NON_ASCII,
            "the input contains whitespace, control or non-ASCII characters "
            "(a Bitcoin address never does)",
        )
    lowered = s.lower()
    if lowered.startswith(("bc1", "tb1", "bcrt1")):
        return _classify_bech32(s)
    return _classify_base58(s)

    return out
