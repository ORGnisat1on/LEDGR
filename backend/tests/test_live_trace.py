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

# A peel-chain-like structure: seed receives funding, then forwards onward —
# each hop one input address → one output address, out-degree exactly 1.
PEEL_TXS = {
    "genesis": [_tx("t1", ["miner"], ["seedAddr"], T0)],
    "seedAddr": [_tx("t2", ["seedAddr"], ["a1"], T0 + 3600)],
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
    G = build_live_graph("seedAddr", PEEL_TXS)
    assert "seedAddr" in G and G.has_edge("seedAddr", "a1")
    assert G.has_edge("a1", "a2") and G.has_edge("a2", "a3")
    # labels are always unknown (-1) for live addresses; time_step mapped from block time
    assert all(G.nodes[n]["label"] == -1 for n in G.nodes)
    assert G.nodes["a1"]["time_step"] == (T0 + 7200) // live_graph.LIVE_TIME_STEP_SECONDS


def test_rules_engine_runs_on_live_graph():
    """R3 heuristics run unchanged on the ad-hoc live graph (they need no training data)."""
    G = build_live_graph("seedAddr", PEEL_TXS)
    out = run_rules(G, "seedAddr", mixer_ids=set(), hop_depth=2)
    assert out["rule_score"] >= 0
    assert set(out["rules_fired"]) <= {"peel_chain", "rapid_fan_out", "mixer_adjacent"}


def test_trace_live_low_tx_address():
    calls = []

    def fetcher(addr):
        calls.append(addr)
        return PEEL_TXS.get(addr, [])

    out = trace_live("seedAddr", hop_depth=1, fetcher=fetcher)
    assert out["source"] == live_graph.SOURCE_LIVE
    assert calls == ["seedAddr"]  # hop_depth=1 -> no counterparty fetches
    assert out["meta"]["capped"] is False


def test_trace_live_high_volume_address_capped():
    """A Binance-scale address (60 txs) is truncated to the documented cap — honestly flagged."""
    many = [_tx(f"t{i}", ["funder"], ["seedAddr", f"out{i}"], T0) for i in range(60)]

    def fetcher(addr):
        return many

    out = trace_live("seedAddr", hop_depth=1, fetcher=fetcher, max_txs=10)
    assert out["meta"]["txs_by_address_fetched"]["seedAddr"] == 10
    assert out["meta"]["capped"] is True


def test_trace_live_fetch_cap_respected():
    """hop_depth>1 expands counterparties but never exceeds the fetch cap."""
    # seed fans out to 40 counterparties, each with one tx back to new addresses
    txs = {
        "seed": [
            _tx(f"s{i}", ["funding"], ["seed", f"c{i:02d}"], T0) for i in range(40)
        ],
    }
    for i in range(40):
        c = f"c{i:02d}"
        txs[c] = [_tx(f"c{i:02d}tx", ["seed"], [f"d{i:02d}"], T0)]

    calls = []

    def fetcher(addr):
        calls.append(addr)
        return txs.get(addr, [])

    out = trace_live("seed", hop_depth=3, fetcher=fetcher, max_fetches=5)
    assert len(calls) <= 5  # hard cap enforced (1 seed + up to 4 counterparties)
    assert out["meta"]["capped"] is True


def test_trace_live_nonexistent_address_is_not_found_on_chain():
    def fetcher(addr):
        return []

    out = trace_live("bc1qnonexistent", hop_depth=2, fetcher=fetcher)
    assert out["source"] == SOURCE_NOT_FOUND_ON_CHAIN
    assert "no on-chain" in out["note"]


def test_trace_live_api_failure_raises_live_source_error():
    import requests

    def fetcher(addr):
        raise requests.ConnectionError("both explorers down")

    with pytest.raises(LiveSourceError):
        trace_live("seedAddr", hop_depth=1, fetcher=fetcher)


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


def test_service_live_bad_address_is_not_found_not_503(monkeypatch):
    """An invalid address (explorer 4xx) is an honest bad-address result (200), never a 503."""
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    def fake_trace_live(address, hop_depth, **kwargs):
        raise LiveSourceError("explorer rejected the address", kind="bad-address")

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    r = client.post("/trace", json={"address": "not-a-valid-address", "hop_depth": 1})
    assert r.status_code == 200
    assert r.json()["source"] == "not-found-on-chain"


def test_service_live_api_failure_is_503(monkeypatch):
    """A live-API failure is distinct from not-found: 503 with a live-specific detail."""
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    def fake_trace_live(address, hop_depth, **kwargs):
        raise LiveSourceError("both live sources failed")

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    r = client.post("/trace", json={"address": "bc1qanything", "hop_depth": 1})
    assert r.status_code == 503
    assert "Live block-explorer API failed" in r.json()["detail"]
