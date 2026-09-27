"""Phase R9 tests — live address tracing, fixture-based (no live network in CI).

Covers BACKEND_BUILD_PLAN.md R9's required cases:
- a high-tx-volume address (pagination/cap logic: > LIVE_MAX_TXS_PER_ADDRESS txs)
- a low-tx address
- a nonexistent address (no on-chain history -> honest not-found-on-chain)
- live-API failure (both sources raise -> LiveSourceError -> 503, distinct from not-found)
- the correlation cap: a live-looked-up wallet with rules FIRING is capped at `watch`
"""

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr import live_graph  # noqa: E402
from ledgr.live_graph import (  # noqa: E402
    SOURCE_NOT_FOUND_ON_CHAIN,
    LiveSourceError,
    build_live_graph,
    extract_addresses_from_summary,
    live_subgraph_payload,
    trace_live,
)
from ledgr.rules import run_rules  # noqa: E402
from ledgr import service as svc  # noqa: E402

# --- fixture helpers (synthetic Blockstream-format tx summaries) -------------


def _tx(txid: str, ins: list[str], outs: list[str], block_time: int) -> dict:
    return {
        "txid": txid,
        "status": {"block_time": block_time, "block_height": 800000},
        "vin": [{"prevout": {"scriptpubkey_address": a, "value": 1000}} for a in ins],
        "vout": [{"scriptpubkey_address": a, "value": 900} for a in outs],
    }


T0 = 1_700_000_000  # fixed epoch for reproducible time steps

# Fixture seeds must be format-valid MAINNET addresses (the local format gate in
# trace_live rejects anything else before it would touch a fetcher — that is the
# point of the gate; see tests/test_address_format.py for the full vector set).
# Counterparties inside fixtures are explorer-supplied data, not user input, so
# they are deliberately not validated. The genesis address is a genuine P2PKH
# mainnet address whose checksum the validator independently verifies.
SEED_P2PKH = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
SEED_P2SH = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"

# A peel-chain-like structure: seed receives funding, then forwards onward —
# each hop one input address → one output address, out-degree exactly 1.
PEEL_TXS = {
    "genesis": [_tx("t1", ["miner"], [SEED_P2PKH], T0)],
    SEED_P2PKH: [_tx("t2", [SEED_P2PKH], ["a1"], T0 + 3600)],
    "a1": [_tx("t3", ["a1"], ["a2"], T0 + 7200)],
    "a2": [_tx("t4", ["a2"], ["a3"], T0 + 10800)],
    "a3": [],
    "funding": [],
}


def test_extract_addresses_excludes_coinbase_and_op_return():
    tx = {
        "vin": [{"prevout": None}, {"prevout": {"scriptpubkey_address": "in1", "value": 1}}],
        "vout": [{"scriptpubkey_address": None}, {"scriptpubkey_address": "out1", "value": 1}],
    }
    ins, outs = extract_addresses_from_summary(tx)
    assert ins == {"in1"} and outs == {"out1"}


def test_build_live_graph_structure_and_attrs():
    G = build_live_graph(SEED_P2PKH, PEEL_TXS)
    assert SEED_P2PKH in G and G.has_edge(SEED_P2PKH, "a1")
    assert G.has_edge("a1", "a2") and G.has_edge("a2", "a3")
    # labels are always unknown (-1) for live addresses; time_step mapped from block time
    assert all(G.nodes[n]["label"] == -1 for n in G.nodes)
    assert G.nodes["a1"]["time_step"] == (T0 + 7200) // live_graph.LIVE_TIME_STEP_SECONDS


def test_rules_engine_runs_on_live_graph():
    """R3 heuristics run unchanged on the ad-hoc live graph (they need no training data)."""
    G = build_live_graph(SEED_P2PKH, PEEL_TXS)
    out = run_rules(G, SEED_P2PKH, mixer_ids=set(), hop_depth=2)
    assert out["rule_score"] >= 0
    assert set(out["rules_fired"]) <= {"peel_chain", "rapid_fan_out", "mixer_adjacent"}


def test_trace_live_low_tx_address():
    calls = []

    def fetcher(addr):
        calls.append(addr)
        return PEEL_TXS.get(addr, [])

    out = trace_live(SEED_P2PKH, hop_depth=1, fetcher=fetcher)
    assert out["source"] == live_graph.SOURCE_LIVE
    assert calls == [SEED_P2PKH]  # hop_depth=1 -> no counterparty fetches
    assert out["meta"]["capped"] is False


def test_trace_live_high_volume_address_capped():
    """A Binance-scale address (60 txs) is truncated to the documented cap — honestly flagged."""
    many = [_tx(f"t{i}", ["funder"], [SEED_P2PKH, f"out{i}"], T0) for i in range(60)]

    def fetcher(addr):
        return many

    out = trace_live(SEED_P2PKH, hop_depth=1, fetcher=fetcher, max_txs=10)
    assert out["meta"]["txs_by_address_fetched"][SEED_P2PKH] == 10
    assert out["meta"]["capped"] is True


def test_trace_live_fetch_cap_respected():
    """hop_depth>1 expands counterparties but never exceeds the fetch cap."""
    # seed fans out to 40 counterparties, each with one tx back to new addresses
    fmt_seed = SEED_P2SH
    txs = {
        fmt_seed: [
            _tx(f"s{i}", ["funding"], [fmt_seed, f"c{i:02d}"], T0) for i in range(40)
        ],
    }
    for i in range(40):
        c = f"c{i:02d}"
        txs[c] = [_tx(f"c{i:02d}tx", [fmt_seed], [f"d{i:02d}"], T0)]

    calls = []

    def fetcher(addr):
        calls.append(addr)
        return txs.get(addr, [])

    out = trace_live(fmt_seed, hop_depth=3, fetcher=fetcher, max_fetches=5)
    assert len(calls) <= 5  # hard cap enforced (1 seed + up to 4 counterparties)
    assert out["meta"]["capped"] is True


def test_trace_live_nonexistent_address_is_not_found_on_chain():
    # BIP-173's mainnet P2WPKH example: FORMAT-valid, but the injected fetcher
    # returns zero txs, so the honest outcome is "no on-chain history". An
    # invalid-format string never gets this far (see test_live_failure_modes.py).
    VALID_NO_HISTORY = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"

    def fetcher(addr):
        return []

    out = trace_live(VALID_NO_HISTORY, hop_depth=2, fetcher=fetcher)
    assert out["source"] == SOURCE_NOT_FOUND_ON_CHAIN
    assert "no on-chain" in out["note"]


def test_trace_live_api_failure_raises_live_source_error():
    import requests

    def fetcher(addr):
        raise requests.ConnectionError("both explorers down")

    with pytest.raises(LiveSourceError) as exc_info:
        trace_live(SEED_P2PKH, hop_depth=1, fetcher=fetcher)
    # A connection failure is operational (unknown-cause), never "bad address".
    assert exc_info.value.kind == "api-error"


# --- service-level (fetcher monkeypatched; TestClient against real artifacts) ---

from fastapi.testclient import TestClient  # noqa: E402

import ledgr.service as svc  # noqa: E402


def _make_client(monkeypatch):
    import pickle

    from ledgr.graph import build_graph, save_graph_index
    from ledgr.ingest import load_elliptic

    fixture = BACKEND / "tests" / "fixtures" / "synthetic"
    index = BACKEND / "tests" / "fixtures" / "graph_index.pkl"
    if not index.exists():
        save_graph_index(build_graph(load_elliptic(fixture)), index.parent)
    with open(index, "rb") as f:
        svc._G = pickle.load(f)
    # Live tracing OFF by default in service tests so old offline expectations hold;
    # individual live tests flip it on.
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "0")
    return TestClient(svc.app)


def test_service_trace_live_lookup(monkeypatch):
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    def fake_trace_live(address, hop_depth, **kwargs):
        # Build the ad-hoc graph around whatever address was requested.
        txs = {
            "funder": [_tx("t0", [], [address], T0)],
            address: [_tx("t1", [address], ["a1"], T0 + 3600)],
            "a1": [_tx("t2", ["a1"], ["a2"], T0 + 7200)],
        }
        return {"source": live_graph.SOURCE_LIVE,
                "graph": build_live_graph(address, txs),
                "txs_by_address": txs,
                "meta": {"capped": False, "fetch_count": 1, "fetch_cap": 25,
                         "tx_cap": 50, "hop_depth": hop_depth,
                         "txs_by_address_fetched": {address: 1}}}

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    r = client.post("/trace", json={"address": "bc1qoutofdataset", "hop_depth": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "live-lookup"
    assert body["stats"]["unknown_nodes"] == body["stats"]["node_count"]


def test_service_trace_not_found_on_chain(monkeypatch):
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    def fake_trace_live(address, hop_depth, **kwargs):
        return {"source": SOURCE_NOT_FOUND_ON_CHAIN, "note": "Address has no on-chain transaction history"}

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    r = client.post("/trace", json={"address": "bc1qunused", "hop_depth": 2})
    assert r.status_code == 200
    assert r.json()["source"] == "not-found-on-chain"


def test_service_verdict_live_capped_at_watch(monkeypatch):
    """THE R9 correlation cap: rules fire hard on a live wallet, verdict stays `watch`."""
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    # Build a live graph where the seed sits in a qualifying peel chain (rule fires).
    chain = {
        "genesis": [_tx("t0", ["miner"], ["seedLive"], T0)],
        "seedLive": [_tx("t1", ["seedLive"], ["a1"], T0 + 3600)],
        "a1": [_tx("t2", ["a1"], ["a2"], T0 + 7200)],
        "a2": [_tx("t3", ["a2"], ["a3"], T0 + 10800)],
    }
    G = build_live_graph("seedLive", chain)
    rules_out = run_rules(G, "seedLive", mixer_ids=set(), hop_depth=3)
    assert rules_out["rules_fired"], "fixture must make a rule fire for the cap test"

    def fake_trace_live(address, hop_depth, **kwargs):
        return {"source": live_graph.SOURCE_LIVE, "graph": G,
                "txs_by_address": chain, "meta": {"capped": False}}

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    # hop_depth=3 so the peel chain's terminal node is inside run_rules' local subgraph
    r = client.post("/verdict", json={"address": "seedLive", "hop_depth": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "watch", "live-lookup verdicts must be capped at watch"
    assert body["source"] == "live-lookup"
    assert body["contributing_signals"]["learned_signal"]["classified"] is False
    assert "watch" in body["correlation_cap"] or "capped" in body["correlation_cap"]


def test_service_live_bad_address_is_invalid_answer_not_503(monkeypatch):
    """An explorer-side rejection (both sources 400/404) is an honest answer
    about the INPUT — 200 with its own source — never a 503 and never the
    'no on-chain history' bucket. (Updated from the pre-hardening contract,
    where this answered not-found-on-chain.)"""
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    def fake_trace_live(address, hop_depth, **kwargs):
        raise LiveSourceError("explorer rejected the address", kind="bad-address")

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    r = client.post("/trace", json={"address": "not-a-valid-address", "hop_depth": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "invalid-address-format"
    assert body["network_attempted"] is True


def test_service_live_api_failure_is_503(monkeypatch):
    """A live-API failure is distinct from not-found: 503 with a STRUCTURED
    detail so the caller can map the failure mode (kind + retryable) instead of
    collapsing it. (Updated: detail is now a machine-readable dict.)"""
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    def fake_trace_live(address, hop_depth, **kwargs):
        raise LiveSourceError("both live sources failed")

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    r = client.post("/trace", json={"address": "bc1qanything", "hop_depth": 1})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert detail["kind"] == "api-error"
    assert detail["retryable"] is True
    assert "NOTHING about the address" in detail["message"]
    # The whole point: the message must never claim the address is the problem.
    assert "address is not" not in detail["message"].lower()


# --- /clusters/live endpoint (R10 wiring) ------------------------------------


def test_service_clusters_live_endpoint(monkeypatch):
    """GET /clusters/live returns TIER_LIVE_UTXO clusters built from InternalTx.

    Monkeypatches BlockstreamClient.iter_address_internal_txs so no live network
    is needed.  The fixture has two inputs in the same tx (co-spend) so they
    must land in one cluster — this confirms the full path:
      iter_address_internal_txs -> build_live_clusters -> endpoint response.
    """
    from ledgr.live_types import InternalTx, TxIn, TxOut
    from ledgr.cluster import TIER_LIVE_UTXO, TIER_ELLIPTIC, TIER_SUPPLEMENTARY

    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    # Two inputs co-spending in one tx: addr_a and addr_b should cluster together.
    fake_internal_txs = [
        InternalTx(
            tx_hash="a" * 64,
            timestamp=1_700_000_000,
            block_height=800_000,
            inputs=(
                TxIn(txid="b" * 64, vout=0, address="addr_a", amount_sats=500),
                TxIn(txid="c" * 64, vout=0, address="addr_b", amount_sats=300),
            ),
            outputs=(TxOut(address="addr_out", amount_sats=800),),
        )
    ]

    monkeypatch.setattr(
        "ledgr.service.BlockstreamClient.iter_address_internal_txs",
        lambda self, address, max_txs=None: iter(fake_internal_txs),
    )

    # The query must be a format-valid mainnet address: clusters_live checks the
    # format gate before touching the network, so a synthetic id like "addr_a"
    # would be rejected with a 400 before the monkeypatched client is called.
    SEED_CLUSTER = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    r = client.get("/clusters/live", params={"address": SEED_CLUSTER})
    assert r.status_code == 200, r.text
    body = r.json()

    # Top-level envelope fields
    assert body["source"] == "live-traced-utxo"
    assert body["confidence_tier"] == "live-traced-utxo"
    assert body["confidence_tier"] == TIER_LIVE_UTXO
    assert isinstance(body["n_clusters"], int)
    assert body["n_clusters"] >= 1

    # All clusters carry TIER_LIVE_UTXO — never elliptic-derived or supplementary-source
    for c in body["clusters"]:
        assert c["confidence_tier"] == TIER_LIVE_UTXO
        assert c["confidence_tier"] != TIER_ELLIPTIC
        assert c["confidence_tier"] != TIER_SUPPLEMENTARY

    # Co-spend: addr_a and addr_b must be in the same cluster
    cospend = next(
        (c for c in body["clusters"] if "addr_a" in c["members_sample"]),
        None,
    )
    assert cospend is not None, "addr_a must appear in some cluster"
    assert "addr_b" in cospend["members_sample"], (
        "addr_a and addr_b co-spent in the same tx — must be in the same cluster"
    )

    # Cost note is present and mentions the tx cap
    assert "cost_note" in body
    assert "50" in body["cost_note"]  # LIVE_MAX_TXS_PER_ADDRESS


def test_service_clusters_live_disabled(monkeypatch):
    """/clusters/live returns 503 when LEDGR_LIVE_TRACING=0."""
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "0")
    r = client.get("/clusters/live", params={"address": SEED_P2PKH})
    assert r.status_code == 503
    assert "disabled" in r.json()["detail"].lower()


def test_service_clusters_live_bad_format_is_400_not_503(monkeypatch):
    """Malformed input to /clusters/live is a 400 (client problem), never the
    previous 'explorer fetch failed' 503 — it never reaches the network."""
    from unittest.mock import MagicMock

    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")
    spy = MagicMock(side_effect=AssertionError("network must not be touched"))
    monkeypatch.setattr(
        "ledgr.service.BlockstreamClient.iter_address_internal_txs", spy
    )
    r = client.get("/clusters/live", params={"address": "not-an-address!!"})
    assert r.status_code == 400
    # Canonical vocabulary: the same string the 200 answer body uses, so a
    # malformed paste is named identically wherever it surfaces.
    assert r.json()["detail"]["kind"] == "invalid-address-format"
    spy.assert_not_called()
