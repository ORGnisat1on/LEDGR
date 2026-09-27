"""Failure-mode hardening tests — fixture-based (no live network anywhere).

Every test here constructs failures (synthetic requests exceptions) and feeds
them to the REAL functions (trace_live / _default_fetcher / service endpoints
via TestClient with monkeypatched clients). No scenario is re-implemented.

The invariant under test, per defect class (STATUS.md 2026-09-26 follow-up):
no external-response class may be silently reported as another. Concretely:
  - both sources 429            -> LiveSourceError kind 'rate-limited'
  - Blockstream 429 + BlockCypher 404 (mixed) -> 'rate-limited' (NOT bad-address)
  - both sources 400/404        -> 'bad-address' (this and ONLY this)
  - timeout anywhere            -> 'timeout' (distinct from a fast 429)
  - 5xx / connection failure    -> 'api-error'
  - one source down + other OK  -> data flows through (failover works)
  - malformed seed              -> invalid-address-format answer, fetcher NEVER called
  - valid seed + empty txs      -> not-found-on-chain (an answer, not an error)

Monty by orders-of-magnitude: repeated requests are cheap — the gate is local.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr import live_graph  # noqa: E402
from ledgr.live_graph import (  # noqa: E402
    KIND_API_ERROR,
    KIND_BAD_ADDRESS,
    KIND_RATE_LIMITED,
    KIND_TIMEOUT,
    SOURCE_INVALID_ADDRESS_FORMAT,
    SOURCE_NOT_FOUND_ON_CHAIN,
    LiveSourceError,
    classify_live_failure,
    trace_live,
)
from ledgr import service as svc  # noqa: E402

# Format-valid seeds (must pass address_format — the gate is the point).
SEED = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"


def _http_error(status: int, url: str = "https://example.invalid/x") -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    resp.url = url
    err = requests.HTTPError(f"{status} Client Error for url: {url}")
    err.response = resp
    return err


def test_single_429_is_rate_limited_not_bad_address():
    err = _http_error(429)
    assert classify_live_failure(err) == KIND_RATE_LIMITED


def test_single_timeout_is_timeout_not_api_error_and_not_bad_address():
    for exc in (
        requests.Timeout("timed out"),
        requests.ConnectTimeout("connect timed out"),
        requests.ReadTimeout("read timed out"),
    ):
        assert classify_live_failure(exc) == KIND_TIMEOUT


def test_single_connection_failure_is_api_error():
    assert classify_live_failure(requests.ConnectionError("down")) == KIND_API_ERROR


def test_single_500_is_api_error():
    assert classify_live_failure(_http_error(500)) == KIND_API_ERROR


def test_401_403_are_api_error_not_validity_verdicts():
    # Auth/quota statuses must never feed the "both sources say invalid" rule —
    # they describe the SERVERS, not the address.
    assert classify_live_failure(_http_error(401)) == KIND_API_ERROR
    assert classify_live_failure(_http_error(403)) == KIND_API_ERROR

# --- pair classification (the 429 -> bad-address mislabel lives HERE) -------
# The real _default_fetcher is exercised with patched CLIENT METHODS, so the
# failover path and the pair rules run for real; only the HTTP layer is faked.

def _patch_sources(monkeypatch, bs_side, bc_side):
    """bs_side/bc_side: a list to return, or an exception instance to raise."""
    def _make(side):
        def _impl(*_args, **_kwargs):
            if isinstance(side, BaseException):
                raise side
            return side
        return _impl

    monkeypatch.setattr(
        "ledgr.blockstream_client.BlockstreamClient.get_address_txs", _make(bs_side))
    monkeypatch.setattr(
        "ledgr.blockcypher_client.BlockCypherClient.get_address_full", _make(bc_side))


def _kind_from(monkeypatch, bs_side, bc_side) -> str:
    _patch_sources(monkeypatch, bs_side, bc_side)
    with pytest.raises(LiveSourceError) as exc_info:
        trace_live(SEED, hop_depth=1)   # no custom fetcher -> real _default_fetcher
    return exc_info.value.kind


BOTH_429 = (_http_error(429), _http_error(429))
MIXED_429_404 = (_http_error(429), _http_error(404))      # <- the mixed case
MIXED_404_429 = (_http_error(404), _http_error(429))      # <- and the mirror
BOTH_400 = (_http_error(400), _http_error(400))
MIXED_400_404 = (_http_error(400), _http_error(404))      # both verdicts, different codes
MIXED_400_TIMEOUT = (_http_error(400), requests.Timeout("hung"))
MIXED_429_TIMEOUT = (_http_error(429), requests.Timeout("hung"))
BOTH_TIMEOUT = (requests.Timeout("hung"), requests.Timeout("hung"))
BOTH_500 = (_http_error(500), _http_error(500))
MIXED_500_400 = (_http_error(500), _http_error(400))      # outage + verdict


@pytest.mark.parametrize(
    "bs_side, bc_side, expected, why",
    [
        (BOTH_429[0], BOTH_429[1], KIND_RATE_LIMITED,
         "both throttled: retryable, says nothing about the address"),
        (MIXED_429_404[0], MIXED_429_404[1], KIND_RATE_LIMITED,
         "a throttled source is NOT a validity verdict (the 2026-09-26 bug)"),
        (MIXED_404_429[0], MIXED_404_429[1], KIND_RATE_LIMITED,
         "same, mirror order: order must not matter"),
        (MIXED_429_TIMEOUT[0], MIXED_429_TIMEOUT[1], KIND_RATE_LIMITED,
         "rate limit outranks a hung source"),
        (BOTH_400[0], BOTH_400[1], KIND_BAD_ADDRESS,
         "both sources independently rejected the address"),
        (MIXED_400_404[0], MIXED_400_404[1], KIND_BAD_ADDRESS,
         "two independent verdicts, different status codes"),
        (MIXED_400_TIMEOUT[0], MIXED_400_TIMEOUT[1], KIND_TIMEOUT,
         "one verdict + one hang is NOT two verdicts -> unknown cause"),
        (BOTH_TIMEOUT[0], BOTH_TIMEOUT[1], KIND_TIMEOUT,
         "hangs are timeouts, not invalid addresses and not outages"),
        (BOTH_500[0], BOTH_500[1], KIND_API_ERROR, "explorer outage"),
        (MIXED_500_400[0], MIXED_500_400[1], KIND_API_ERROR,
         "outage + verdict is not a verdict -> retryable outage"),
    ],
)
def test_pair_failure_classification(monkeypatch, bs_side, bc_side, expected, why):
    assert _kind_from(monkeypatch, bs_side, bc_side) == expected, why


def _tx(vout_addr: str) -> dict:
    return {
        "txid": "t1",
        "status": {"block_time": 1_700_000_000, "block_height": 800_000},
        "vin": [{"prevout": {"scriptpubkey_address": "funder", "value": 1000}}],
        "vout": [{"scriptpubkey_address": vout_addr, "value": 900}],
    }


def test_failover_succeeds_when_only_one_source_is_down(monkeypatch):
    """One source down/throttled, the other answers -> the lookup SUCCEEDS.
    Case (d) of the hardening brief: implied by the primary/fallback design but
    never previously asserted directly."""
    tx = [_tx(SEED)]
    for bs_side, bc_side, label in (
        (_http_error(429), {"txs": tx}, "blockstream throttled"),
        (requests.Timeout("hung"), {"txs": tx}, "blockstream hung"),
        (tx, _http_error(429), "blockcypher throttled"),
        (tx, _http_error(500), "blockcypher 500"),
    ):
        _patch_sources(monkeypatch, bs_side, bc_side)
        out = trace_live(SEED, hop_depth=1)
        assert out["source"] == live_graph.SOURCE_LIVE, label
        assert out["meta"]["txs_by_address_fetched"][SEED] == 1, label


def test_failover_empty_from_fallback_is_not_found_not_an_error(monkeypatch):
    """Primary 429, fallback answers 200 with ZERO txs -> a real answer
    (valid address, no history), not a service failure and not 'invalid'."""
    _patch_sources(monkeypatch, _http_error(429), {"txs": []})
    out = trace_live(SEED, hop_depth=1)
    assert out["source"] == SOURCE_NOT_FOUND_ON_CHAIN
    assert "no on-chain" in out["note"]


# --- local format gate: malformed input never reaches a fetcher --------------

@pytest.mark.parametrize(
    "raw",
    [
        "not-a-valid-address",
        "1InvalidAddressThatDoesNotExist123",   # DEMO.md walkthrough case
        "230425980",                             # an Elliptic tx-id, not a BTC address
        "bc1qnonexistent",
        "1" * 400,                               # absurdly long paste
        "  ",                                    # whitespace only
        "١A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",   # non-ASCII
    ],
)
def test_malformed_input_answers_locally_and_never_fetches(raw):
    """The local gate answers for malformed input and never touches a fetcher —
    so it cannot be rate-limited, time out, or be called at all."""
    spy = MagicMock(side_effect=AssertionError("fetcher must not be called"))
    out = trace_live(raw, hop_depth=1, fetcher=spy)
    assert out["source"] == SOURCE_INVALID_ADDRESS_FORMAT
    assert out["network_attempted"] is False
    assert out["format_reason"]
    assert "no block-explorer request" in out["note"]
    spy.assert_not_called()


def test_malformed_input_is_not_reported_as_no_history():
    """The two 'nothing to show' answers must stay distinct: a malformed paste is
    not a claim about the chain, and a valid address with no history is."""
    malformed = trace_live("nonsense", hop_depth=1, fetcher=lambda a: [])
    empty = trace_live(SEED, hop_depth=1, fetcher=lambda a: [])
    assert malformed["source"] != empty["source"]
    assert malformed["source"] == SOURCE_INVALID_ADDRESS_FORMAT
    assert empty["source"] == SOURCE_NOT_FOUND_ON_CHAIN
    assert empty.get("network_attempted") is True


def test_whitespace_padded_real_address_still_reaches_the_fetcher():
    calls = []

    def fetcher(addr):
        calls.append(addr)
        return []

    out = trace_live(f"  {SEED}\n", hop_depth=1, fetcher=fetcher)
    assert calls == [f"  {SEED}\n"]      # trailing newline must not break a real paste
    assert out["source"] == SOURCE_NOT_FOUND_ON_CHAIN


# --- concurrency: the gate and the classifier hold under parallel load -------
# The watchlist (Module 1b) polls mempool.space on a timer while an on-demand
# trace runs, so requests can be in flight together. Each call must reach its
# own correct state with no shared mutable state between them.

def test_concurrent_traces_do_not_cross_talk():
    from concurrent.futures import ThreadPoolExecutor

    def throttled(addr):
        err = _http_error(429)
        raise err

    def valid_no_history(addr):
        return []

    def scenario(i):
        if i % 3 == 0:
            return trace_live(f"malformed-input-{i}", hop_depth=1, fetcher=valid_no_history)
        if i % 3 == 1:
            try:
                trace_live(SEED, hop_depth=1, fetcher=throttled)
                return {"unexpected": "no error"}
            except LiveSourceError as e:
                return {"kind": e.kind}
        return trace_live(SEED, hop_depth=1, fetcher=valid_no_history)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(scenario, range(24)))

    assert len(results) == 24
    for i, res in enumerate(results):
        if i % 3 == 0:
            assert res["source"] == SOURCE_INVALID_ADDRESS_FORMAT, i
        elif i % 3 == 1:
            # fetcher raises a bare HTTPError; the classifier reads its status.
            assert res.get("kind") == KIND_RATE_LIMITED, (i, res)
        else:
            assert res["source"] == SOURCE_NOT_FOUND_ON_CHAIN, i

# --- service endpoints: the states must survive the HTTP boundary -----------

from fastapi.testclient import TestClient  # noqa: E402


def _make_client(monkeypatch):
    """Same fixture as test_live_trace.py: real (synthetic) graph index, live off
    by default so each test opts in."""
    import pickle

    from ledgr.graph import build_graph, save_graph_index
    from ledgr.ingest import load_elliptic

    fixture = BACKEND / "tests" / "fixtures" / "synthetic"
    index = BACKEND / "tests" / "fixtures" / "graph_index.pkl"
    if not index.exists():
        save_graph_index(build_graph(load_elliptic(fixture)), index.parent)
    with open(index, "rb") as f:
        svc._G = pickle.load(f)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "0")
    return TestClient(svc.app)


@pytest.mark.parametrize("kind", [KIND_RATE_LIMITED, KIND_TIMEOUT, KIND_API_ERROR])
def test_service_maps_operational_kinds_to_structured_503(monkeypatch, kind):
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    def fake_trace_live(address, hop_depth, **kwargs):
        raise LiveSourceError(f"simulated {kind}", kind=kind)

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    r = client.post("/trace", json={"address": SEED, "hop_depth": 1})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert detail["kind"] == kind
    assert detail["retryable"] is True
    # An operational failure must NEVER be phrased as a statement about the
    # address — that phrasing is the defect this pass removes.
    msg = detail["message"].lower()
    for forbidden in ("not valid", "not recognised", "not recognized", "no on-chain history"):
        assert forbidden not in msg, detail["message"]


def test_service_reports_rate_limit_distinctly_from_invalid(monkeypatch):
    """The 2026-09-26 bug, end to end: a throttled lookup is a retryable 503 —
    never the 200 'invalid address' answer the pre-hardening code returned."""
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    def fake_trace_live(address, hop_depth, **kwargs):
        raise LiveSourceError("both live sources failed (rate-limited)", kind=KIND_RATE_LIMITED)

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    r = client.post("/trace", json={"address": SEED, "hop_depth": 1})
    assert r.status_code == 503
    assert r.json()["detail"]["kind"] == KIND_RATE_LIMITED


def test_service_local_format_gate_returns_200_invalid_answer(monkeypatch):
    """Through the real endpoint (no monkeypatching of trace_live): malformed
    input is answered locally, without any explorer request."""
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")
    spy = MagicMock(side_effect=AssertionError("no network call may happen"))
    monkeypatch.setattr("ledgr.blockstream_client.BlockstreamClient.get_address_txs", spy)
    monkeypatch.setattr("ledgr.blockcypher_client.BlockCypherClient.get_address_full", spy)

    r = client.post("/trace", json={"address": "1InvalidAddressThatDoesNotExist123", "hop_depth": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == SOURCE_INVALID_ADDRESS_FORMAT
    assert body["network_attempted"] is False
    spy.assert_not_called()


def test_service_explorer_rejection_is_invalid_answer_not_503(monkeypatch):
    client = _make_client(monkeypatch)
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "1")

    def fake_trace_live(address, hop_depth, **kwargs):
        raise LiveSourceError("both sources 400", kind=KIND_BAD_ADDRESS)

    monkeypatch.setattr(svc, "trace_live", fake_trace_live)
    r = client.post("/trace", json={"address": SEED, "hop_depth": 1})
    assert r.status_code == 200
    assert r.json()["source"] == SOURCE_INVALID_ADDRESS_FORMAT
