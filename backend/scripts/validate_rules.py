#!/usr/bin/env python
"""Phase R3 — independent validation of each heuristic (METHODOLOGY.md §3).

For each rule, builds documented synthetic known-pattern graphs (literature
laundering patterns) and checks:
  * the rule FIRES on the known-pattern case,
  * the rule does NOT fire on clearly-licit comparison wallets (FP check —
    e.g. a busy merchant wallet with many inputs AND many outputs, and a
    wallet nowhere near any mixer).

Writes artifacts/rule_validation.json with the full result; exits non-zero on
any failure. This is the R3 exit criterion: per-heuristic, auditable output.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledgr.config import artifacts_dir, rule_params  # noqa: E402
from ledgr.rules import (  # noqa: E402
    RULE_FANOUT, RULE_MIXER, RULE_PEEL, run_rules,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
P = rule_params()


def chain_graph(length: int) -> nx.DiGraph:
    """Known peel-chain pattern: seed -> n1 -> ... -> nk, one output each, time-advancing."""
    G = nx.DiGraph()
    nodes = [f"chain{i}" for i in range(length + 1)]
    for i, n in enumerate(nodes):
        G.add_node(n, label=-1, time_step=10 + i)
    G.add_edges_from(zip(nodes, nodes[1:]))
    return G


def fanout_graph() -> nx.DiGraph:
    """Known rapid fan-out pattern: 1 funding input -> burst to 8 outputs, tight window."""
    G = nx.DiGraph()
    G.add_node("src", label=-1, time_step=5)
    G.add_node("burst", label=-1, time_step=6)
    G.add_node("unused", label=-1, time_step=6)
    for i in range(11):
        G.add_node(f"out{i}", label=-1, time_step=7)
        G.add_edge("unused", f"out{i}")
    G.add_edge("src", "burst")
    G.add_edges_from(("burst", f"out{i}") for i in range(11))
    return G


def merchant_graph() -> nx.DiGraph:
    """Clearly-licit: busy merchant — many inputs AND many outputs, spread over time."""
    G = nx.DiGraph()
    G.add_node("merchant", label=0, time_step=10)
    for i in range(12):
        G.add_node(f"cust{i}", label=0, time_step=5 + i)
        G.add_node(f"vendor{i}", label=0, time_step=12 + i)
        G.add_edge(f"cust{i}", "merchant")
        G.add_edge("merchant", f"vendor{i}")
    return G


def isolated_graph() -> nx.DiGraph:
    """Clearly-licit: single wallet, one in, one out, no chain (out-degree 1)."""
    G = nx.DiGraph()
    for n, ts in (("a", 1), ("wallet", 2), ("b", 3)):
        G.add_node(n, label=0, time_step=ts)
    G.add_edge("a", "wallet")
    G.add_edge("wallet", "b")
    return G


def mixer_far_graph() -> nx.DiGraph:
    """Clearly-licit w.r.t. mixers: active wallet, but known mixer is 5 hops away."""
    G = chain_graph(6)  # includes a >3-hop chain, so peel will fire — that's fine
    G.add_node("mixer_known", label=-1, time_step=1)
    G.add_node("far_wallet", label=0, time_step=9)
    prev = "mixer_known"
    for i in range(5):
        nxt = f"bridge{i}"
        G.add_node(nxt, label=-1, time_step=2 + i)
        G.add_edge(prev, nxt)
        prev = nxt
    G.add_edge(prev, "far_wallet")
    return G


def run() -> int:
    cases = []
    failures = 0

    def check(name: str, graph: nx.DiGraph, seed: str, mixers: set[str],
              expect_fired: list[str], expect_not_fired: list[str]) -> None:
        nonlocal failures
        res = run_rules(graph, seed, mixer_ids=mixers, hop_depth=6)
        fired = set(res["rules_fired"])
        ok = all(r in fired for r in expect_fired) and not (fired & set(expect_not_fired))
        failures += 0 if ok else 1
        cases.append({
            "case": name, "seed": seed, "fired": sorted(fired),
            "expected_fired": sorted(expect_fired),
            "expected_not_fired": sorted(expect_not_fired),
            "rule_score": res["rule_score"], "rule_flag": res["rule_flag"],
            "evidence": {r: v["evidence"] for r, v in res["contributing_signals"].items()},
            "pass": ok,
        })
        logging.info("%-28s fired=%s %s", name, sorted(fired), "PASS" if ok else "FAIL")

    mixers = {"mixer_known"}
    check("peel_chain: known pattern", chain_graph(5), "chain2", set(),
          expect_fired=[RULE_PEEL], expect_not_fired=[RULE_FANOUT, RULE_MIXER])
    check("fan_out: known pattern", fanout_graph(), "burst", set(),
          expect_fired=[RULE_FANOUT], expect_not_fired=[RULE_PEEL, RULE_MIXER])
    check("mixer: adjacent hop-2", mixer_far_graph(), "bridge1", mixers,
          expect_fired=[RULE_MIXER], expect_not_fired=[])
    check("FP check: merchant wallet", merchant_graph(), "merchant", set(),
          expect_fired=[], expect_not_fired=[RULE_PEEL, RULE_FANOUT, RULE_MIXER])
    check("FP check: isolated wallet", isolated_graph(), "wallet", set(),
          expect_fired=[], expect_not_fired=[RULE_PEEL, RULE_FANOUT, RULE_MIXER])
    check("FP check: far from mixer", mixer_far_graph(), "far_wallet", mixers,
          expect_fired=[], expect_not_fired=[RULE_MIXER])

    out = artifacts_dir() / "rule_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "engine_params": P,
        "all_passed": failures == 0,
        "cases": cases,
    }, indent=2))
    logging.info("Validation report: %s (%s)", out, "ALL PASS" if failures == 0 else f"{failures} FAILURES")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
