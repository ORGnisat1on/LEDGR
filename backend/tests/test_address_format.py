"""Format-validation vectors — grounded in specifications, not invented.

Sources (all retrieved 2026-09-26, see STATUS.md for the grounding trail):
  - BIP-173 §Examples + §Test vectors: mainnet P2WPKH / P2WSH, uppercase forms,
    testnet forms, over-length and mixed-case rejections.
  - BIP-350 §Test vectors: valid v1 (taproot), v2 and v16 segwit addresses on
    mainnet; the `tc1…` wrong-HRP rejection.
  - bitcoin/bitcoin `src/test/data/key_io_valid.json`: mainnet P2PKH/P2SH/
    taproot vectors and testnet/regtest cases for the wrong-network bucket.
  - bitcoin/bitcoin `src/test/data/key_io_invalid.json`: an authoritative
    non-address string.
  - The Bitcoin genesis address `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`: a real,
    funded mainnet P2PKH address (checksum-verified by the code under test —
    a valid-format MUST pass, or the gate itself becomes the mislabeller).

No network access: every case is pure and runs offline.
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr.address_format import (  # noqa: E402
    KIND_P2PKH,
    KIND_P2SH,
    KIND_P2WPKH,
    KIND_P2WSH,
    KIND_WITNESS_V1_PLUS,
    REASON_BAD_CHECKSUM,
    REASON_EMPTY,
    REASON_MALFORMED,
    REASON_NON_ASCII,
    REASON_TOO_LONG,
    REASON_WRONG_NETWORK,
    classify_address,
)

# --- valid mainnet vectors (address, expected kind) --------------------------

VALID = [
    # bitcoin-core key_io_valid.json, chain=main
    ("1FsSia9rv4NeEwvJ2GvXrX7LyxYspbN2mo", KIND_P2PKH),
    ("1G9A9j6W8TLuh6dEeVwWeyibK1Uc5MfVFV", KIND_P2PKH),
    ("36j4NfKv6Akva9amjWrLG6MuSQym1GuEmm", KIND_P2SH),
    ("33GA3ZXbw5o5HeUrBEaqkWXFYYZmdxGRRP", KIND_P2SH),
    ("bc1p83n3au0rjylefxq2nc2xh2y4jzz4pm6zxj4mw5pagdjjr2a9f36s6jjnnu", KIND_WITNESS_V1_PLUS),
    ("bc1pve739yap4uxjvfk0jrey69078u0gasm2nwvv483ec6zkzulgw9xqu4w9fd", KIND_WITNESS_V1_PLUS),
    # The genesis address — real, funded, P2PKH. Must pass: a valid-format
    # MUST never be rejected, or the gate itself becomes the mislabeller.
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", KIND_P2PKH),
    # Well-known P2SH example from the Bitcoin wiki — checksum verified.
    ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", KIND_P2SH),
    # BIP-173 mainnet examples written for pubkey 0279BE66…
    ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", KIND_P2WPKH),
    ("bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3", KIND_P2WSH),
    # BIP-350 mainnet vectors (bech32m, witness v1+)
    ("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0", KIND_WITNESS_V1_PLUS),
    ("bc1pw508d6qejxtdg4y5r3zarvary0c5xw7kw508d6qejxtdg4y5r3zarvary0c5xw7kt5nd6y", KIND_WITNESS_V1_PLUS),
    ("bc1zw508d6qejxtdg4y5r3zarvaryvaxxpcs", KIND_WITNESS_V1_PLUS),
    ("BC1SW50QGDZ25J", KIND_WITNESS_V1_PLUS),  # v16, all-uppercase per BIP rules
    ("BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4", KIND_P2WPKH),  # BIP-350 all-upper v0
]


def test_valid_mainnet_vectors():
    for addr, kind in VALID:
        out = classify_address(addr)
        assert out.valid, f"{addr} must be accepted: {out}"
        assert out.kind == kind, f"{addr}: kind {out.kind} != {kind}"


def test_surrounding_whitespace_tolerated():
    # A trailing newline from a paste must not turn a real address invalid.
    out = classify_address("  1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa \n")
    assert out.valid and out.kind == KIND_P2PKH


# --- invalid inputs (input, expected reason) ---------------------------------

INVALID = [
    # empty / nothing there
    ("", REASON_EMPTY),
    ("   ", REASON_EMPTY),
    ("\t\n ", REASON_EMPTY),
    # non-strings can never be addresses
    (None, REASON_MALFORMED),
    (12345, REASON_MALFORMED),
    (b"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", REASON_MALFORMED),
    # over-long input never reaches decoding or the network
    ("1" * 129, REASON_TOO_LONG),
    ("a" * 1000, REASON_TOO_LONG),
    # anything non-ASCII, or whitespace/control *inside* the string
    ("1A1z P1eP5QGefi2DMPTfTL5SLmv7DivfNa", REASON_NON_ASCII),
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\u0661", REASON_NON_ASCII),
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf\tNa", REASON_NON_ASCII),
    # bad checksum: valid-shape strings whose 4-byte checksum does not verify.
    # (An xpub decodes to 78 payload bytes; a valid P2PKH/P2SH address decodes
    # to exactly 25: version + 20-byte hash + 4-byte checksum. Anything else is
    # reported as a structural mismatch, never as an address with a bad checksum.)
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb", REASON_BAD_CHECKSUM),
    ("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj1", REASON_BAD_CHECKSUM),
    # an xpub: valid Base58Check of a *different payload type* (78 bytes, version
    # 0x0488b21e) — not an address, and must NOT be reported as bad-checksum.
    ("xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1RWDYmw5", REASON_MALFORMED),
    # wrong network: VALID addresses, just not mainnet (SCOPE: mainnet only)
    ("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", REASON_WRONG_NETWORK),   # BIP-173 testnet
    ("tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3q0sl5k7", REASON_WRONG_NETWORK),
    ("bcrt1q65nhlm4hf2ptg3t264al57p7wjxj2c3s6kyt83", REASON_WRONG_NETWORK),  # regtest
    ("mzK2FFDEhxqHcmrJw1ysqFkVyhUULo45hZ", REASON_WRONG_NETWORK),             # core testnet4 P2PKH
    ("2NC2hEhe28ULKAJkW5MjZ3jtTMJdvXmByvK", REASON_WRONG_NETWORK),            # core testnet4 P2SH
    ("tc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq5zuyut", REASON_MALFORMED),
    # malformed: decodes under neither encoding
    ("seedAddr", REASON_MALFORMED),             # not a Base58/Bech32 address at all
    ("addr_a", REASON_MALFORMED),
    ("230425980", REASON_MALFORMED),            # an Elliptic tx-id is not a BTC address
    ("bc1qnonexistent", REASON_MALFORMED),      # unusable as bech32 AND base58
    ("not-a-valid-address", REASON_MALFORMED),
    ("1InvalidAddressThatDoesNotExist123", REASON_MALFORMED),  # DEMO.md case: capital I excluded
    ("xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1RWDYmw5", REASON_MALFORMED),
    ("bc1QW508D6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", REASON_MALFORMED),  # mixed-case bech32
]


def test_invalid_inputs():
    for raw, reason in INVALID:
        out = classify_address(raw)
        assert not out.valid, f"{raw!r} must be rejected"
        assert out.reason == reason, f"{raw!r}: reason {out.reason!r} != {reason!r}"
        assert len(out.detail) > 0, "every rejection must carry a human-readable detail"


def test_classifier_never_raises():
    import math

    for raw in (None, 0, 1.5, float("nan"), b"", [], {}, object()):
        classify_address(raw)  # must return a verdict, never raise
    for raw in ("", "x", "1", "bc1", "1" * 1000, "٣٣٣", "\x00" * 10):
        classify_address(raw)

    out = classify_address("  1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa \n")
    assert out.valid and out.kind == KIND_P2PKH
