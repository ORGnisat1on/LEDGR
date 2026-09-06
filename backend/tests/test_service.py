import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

FIXTURE = BACKEND / "tests" / "fixtures" / "synthetic"
INDEX = BACKEND / "tests" / "fixtures" / "graph_index.pkl"


def make_client():
    from ledgr.graph import build_graph, save_graph_index
    from ledgr.ingest import load_elliptic
    import ledgr.service as svc
    import pickle

    if not INDEX.exists():
        save_graph_index(build_graph(load_elliptic(FIXTURE)), INDEX.parent)
    with open(INDEX, "rb") as f:
        svc._G = pickle.load(f)
    return TestClient(svc.app)


def _any_seed():
    import pickle
    with open(INDEX, "rb") as f:
        G = pickle.load(f)
    return next(iter(G.nodes))


def test_health():
    client = make_client()
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "ledgr-inference"
    assert body["graph_loaded"] is True


def test_trace_endpoint():
    client = make_client()
    seed = _any_seed()
    r = client.post("/trace", json={"address": seed, "hop_depth": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["seed"] == seed
    assert body["stats"]["max_hop_reached"] <= 2


def test_rules_endpoint():
    """Phase R3: the rule-based signal is exposed via the service, auditable."""
    client = make_client()
    seed = _any_seed()
    r = client.post("/rules", json={"address": seed, "hop_depth": 2})
    assert r.status_code == 200
    body = r.json()
    assert set(body["rules_fired"]) <= {"peel_chain", "rapid_fan_out", "mixer_adjacent"}
    assert 0 <= body["rule_score"] <= 100
    assert body["rule_flag"] in {"high", "medium", "low", "none"}
    assert "engine_params" in body


def test_trace_unknown_address_404(monkeypatch):
    """With live tracing disabled, an unknown address is a loud 404 (never fabricated)."""
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "0")
    client = make_client()
    assert client.post("/trace", json={"address": "nope", "hop_depth": 2}).status_code == 404
    assert client.post("/rules", json={"address": "nope", "hop_depth": 2}).status_code == 404


def test_trace_invalid_hop_422():
    client = make_client()
    r = client.post("/trace", json={"address": "tx000000", "hop_depth": 0})
    assert r.status_code == 422


def test_score_endpoint_learned_signal():
    """Phase R4: /score returns a real per-wallet risk score, not a hardcoded value."""
    import numpy as np

    from ledgr.entity_split import build_entities, split_entities
    from ledgr.ingest import load_elliptic
    from ledgr.learn import load_feature_lookup, load_learned_model, train_and_evaluate
    import ledgr.service as svc

    ds = load_elliptic(FIXTURE)
    split_df = split_entities(ds, build_entities(ds))
    tmp = BACKEND / "tests" / "fixtures" / "_r4tmp"
    train_and_evaluate(ds, split_df, out_dir=tmp, n_estimators=20)
    svc._MODEL = load_learned_model(tmp / "learned_model.joblib")
    svc._FEATURES = load_feature_lookup(tmp / "feature_lookup.pkl")

    client = TestClient(svc.app)
    known = str(ds.tx_ids[0])
    r = client.post("/score", json={"address": known})
    assert r.status_code == 200
    body = r.json()
    assert body["classified"] is True
    assert 0.0 <= body["risk_score"] <= 1.0
    assert body["prediction"] in ("illicit", "licit")

    r2 = client.post("/score", json={"address": "wallet-not-in-dataset"})
    assert r2.status_code == 200
    assert r2.json()["classified"] is False

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


def test_score_endpoint_503_without_artifacts():
    """Without a trained model loaded, /score must fail loudly (503), never fabricate."""
    import ledgr.service as svc

    prev_model, prev_feat = svc._MODEL, svc._FEATURES
    svc._MODEL, svc._FEATURES = None, None
    try:
        client = TestClient(svc.app)
        r = client.post("/score", json={"address": "anything"})
        assert r.status_code == 503
    finally:
        svc._MODEL, svc._FEATURES = prev_model, prev_feat


def test_verdict_endpoint():
    """Phase R5: /verdict combines rule + learned signals into confirmed/watch/none
    with traceability, and can reach more than one verdict across wallets."""
    import ledgr.service as svc
    from ledgr.correlate import VERDICT_CONFIRMED, VERDICT_NONE, VERDICT_WATCH

    from ledgr.entity_split import build_entities, split_entities
    from ledgr.ingest import load_elliptic
    from ledgr.learn import load_feature_lookup, load_learned_model, train_and_evaluate

    # Ensure graph index is loaded
    client = make_client()

    # Train a tiny model + feature lookup so the learned signal is available.
    tmp = BACKEND / "tests" / "fixtures" / "_r5tmp"
    ds = load_elliptic(FIXTURE)
    split_df = split_entities(ds, build_entities(ds))
    train_and_evaluate(ds, split_df, out_dir=tmp, n_estimators=20)
    svc._MODEL = load_learned_model(tmp / "learned_model.joblib")
    svc._FEATURES = load_feature_lookup(tmp / "feature_lookup.pkl")

    verdicts = set()
    for s in list(svc._G.nodes)[:40]:
        r = client.post("/verdict", json={"address": s, "hop_depth": 2})
        assert r.status_code == 200, f"{s}: {r.status_code}"
        body = r.json()
        assert body["verdict"] in (VERDICT_CONFIRMED, VERDICT_WATCH, VERDICT_NONE)
        assert "contributing_signals" in body
        verdicts.add(body["verdict"])

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    assert verdicts, "expected at least one verdict computed"
    # R5 exit criterion: verdicts vary honestly by wallet (not always 'confirmed')
    assert not (verdicts == {VERDICT_CONFIRMED}), "must not be always-confirmed across wallets"


def test_verdict_404_unknown_address(monkeypatch):
    monkeypatch.setenv("LEDGR_LIVE_TRACING", "0")
    client = make_client()
    r = client.post("/verdict", json={"address": "wallet-not-in-graph", "hop_depth": 2})
    assert r.status_code == 404
