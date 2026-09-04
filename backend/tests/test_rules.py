import sys
from pathlib import Path

import networkx as nx
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr.rules import (  # noqa: E402
    RULE_FANOUT, RULE_MIXER, RULE_PEEL, detect_mixer_adjacency,
    detect_peel_chains, detect_rapid_fan_out, load_mixer_ids, run_rules,
)


def chain_graph(length: int) -> nx.DiGraph:
    G = nx.DiGraph()
    nodes = [f"chain{i}" for i in range(length + 1)]
    for i, n in enumerate(nodes):
        G.add_node(n, label=-1, time_step=10 + i)
    G.add_edges_from(zip(nodes, nodes[1:]))
    return G


def fanout_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_node("src", label=-1, time_step=5)
    G.add_node("burst", label=-1, time_step=6)
    for i in range(8):
        G.add_node(f"out{i}", label=-1, time_step=7)
        G.add_edge("burst", f"out{i}")
    G.add_edge("src", "burst")
    return G


def merchant_graph() -> nx.DiGraph:
    """Clearly-licit: many inputs AND many outputs, spread over time."""
    G = nx.DiGraph()
    G.add_node("merchant", label=0, time_step=10)
    for i in range(12):
        G.add_node(f"cust{i}", label=0, time_step=5 + i)
        G.add_node(f"vendor{i}", label=0, time_step=12 + i)
        G.add_edge(f"cust{i}", "merchant")
        G.add_edge("merchant", f"vendor{i}")
    return G

def test_peel_chain_detected():
    G = chain_graph(5)
    ev = detect_peel_chains(G, min_hops=3, max_time_gap=1)
    assert "chain2" in ev, "mid-chain node must be flagged"
    assert ev["chain2"]["chain_length_hops"] >= 3
    assert "chain0" not in ev  # source with no funding input is not a chain internal


def test_short_chain_not_flagged():
    G = chain_graph(2)  # only 2 hops < min_hops 3
    ev = detect_peel_chains(G, min_hops=3, max_time_gap=1)
    assert not ev, "chain shorter than min_hops must not fire"


def test_time_gap_breaks_chain():
    G = chain_graph(5)
    for i in range(3, 6):  # big time jump mid-chain breaks the pattern
        G.nodes[f"chain{i}"]["time_step"] = 50 + i
    ev = detect_peel_chains(G, min_hops=3, max_time_gap=1)
    assert not ev


def test_fan_out_detected():
    G = fanout_graph()
    ev = detect_rapid_fan_out(G, min_out=5, max_in=2, window=2)
    assert "burst" in ev
    assert ev["burst"]["out_degree"] == 8


def test_fan_out_spread_over_time_not_flagged():
    G = fanout_graph()
    for i in range(8):  # outputs spread over 20 steps — not a burst
        G.nodes[f"out{i}"]["time_step"] = 7 + i * 3
    ev = detect_rapid_fan_out(G, min_out=5, max_in=2, window=2)
    assert "burst" not in ev


def test_merchant_wallet_not_flagged():
    """FP check: high-volume licit merchant (many in AND out) fires nothing."""
    G = merchant_graph()
    assert not detect_rapid_fan_out(G, min_out=5, max_in=2, window=2)
    assert not detect_peel_chains(G, min_hops=3, max_time_gap=1)


def test_mixer_adjacency_hops():
    G = merchant_graph()
    G.add_node("mixer", label=-1, time_step=1)
    G.add_edge("mixer", "mixer_out")
    G.add_edge("mixer_out", "cust0")  # cust0 at hop 2, merchant at hop 3
    ev = detect_mixer_adjacency(G, {"mixer"}, max_hops=2)
    assert "cust0" in ev and ev["cust0"]["hops_from_mixer"] == 2
    assert "mixer_out" in ev and ev["mixer_out"]["hops_from_mixer"] == 1
    assert "merchant" not in ev, "hop 3 exceeds max_hops 2"
    assert "mixer" not in ev

def test_run_rules_peel_auditable():
    G = chain_graph(5)
    res = run_rules(G, "chain2", mixer_ids=set(), hop_depth=6)
    assert res["rules_fired"] == [RULE_PEEL]
    assert res["rule_score"] == 40 and res["rule_flag"] == "medium"
    ev = res["contributing_signals"][RULE_PEEL]["evidence"]
    assert ev["chain_length_hops"] >= 3
    assert "engine_params" in res, "parameters must be logged for auditability"


def test_run_rules_composite_score_and_tiers():
    G = fanout_graph()
    G.add_node("mixer", label=-1, time_step=1)
    G.add_edge("mixer", "src")
    res = run_rules(G, "burst", mixer_ids={"mixer"}, hop_depth=6)
    assert set(res["rules_fired"]) == {RULE_FANOUT, RULE_MIXER}
    assert res["rule_score"] == 60 and res["rule_flag"] == "high"


def test_run_rules_no_hardcoded_scores():
    """Different graphs must produce different scores (mock returned fixed 94/96/98)."""
    r1 = run_rules(chain_graph(5), "chain2", mixer_ids=set(), hop_depth=6)
    r2 = run_rules(merchant_graph(), "merchant", mixer_ids=set(), hop_depth=6)
    assert r1["rule_score"] != r2["rule_score"]
    assert r2["rule_flag"] == "none" and r2["rule_score"] == 0


def test_run_rules_unknown_seed_raises():
    with pytest.raises(KeyError):
        run_rules(chain_graph(5), "nope", mixer_ids=set())


def test_mixer_list_missing_file_returns_empty(tmp_path):
    assert load_mixer_ids(tmp_path / "does_not_exist.txt") == set()


def test_mixer_list_parsing_with_comments(tmp_path):
    f = tmp_path / "mixers.txt"
    f.write_text("# comment\nabc\n\n  def  \n# another\n", encoding="utf-8")
    assert load_mixer_ids(f) == {"abc", "def"}


def test_run_rules_without_mixer_list_reports_it():
    G = fanout_graph()
    res = run_rules(G, "burst", mixer_ids=set(), hop_depth=6)
    assert res["mixer_list_loaded"] is False


