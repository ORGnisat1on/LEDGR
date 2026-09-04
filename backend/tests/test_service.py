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


def test_trace_unknown_address_404():
    client = make_client()
    assert client.post("/trace", json={"address": "nope", "hop_depth": 2}).status_code == 404
    assert client.post("/rules", json={"address": "nope", "hop_depth": 2}).status_code == 404


def test_trace_invalid_hop_422():
    client = make_client()
    r = client.post("/trace", json={"address": "tx000000", "hop_depth": 0})
    assert r.status_code == 422
