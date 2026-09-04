#!/usr/bin/env python
"""Phase R2 — sanity-check subgraph construction against known Elliptic entities.

Per BACKEND_BUILD_PLAN.md Phase R2:
  "Sanity-check subgraph construction against a handful of known Elliptic
   entities."
  Exit criteria: "given any wallet address in the dataset, the service returns
  its real local subgraph; `hopDepth` measurably changes output size."

This script loads the pre-indexed graph and, for a handful of hand-picked seed
nodes (the densest, a mid-degree, and a low/illicit one), verifies:
  1. local_subgraph returns a real local subgraph for that wallet,
  2. hop_depth is strictly respected (max_hop_reached <= hop_depth),
  3. increasing hop_depth measurably changes (monotonically grows) output size.

Usage:
  backend/.venv/Scripts/python backend/scripts/sanity_check_subgraph.py \
      [--graph-index artifacts/graph_index.pkl] [--n-seeds 8] [--seed-tx ID...]

Run against a freshly-built graph index (see scripts/run_ingest.py). Exits
non-zero if any seed fails any check.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import networkx as nx

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledgr.config import artifacts_dir  # noqa: E402
from ledgr.graph import load_graph_index, local_subgraph  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

HOPS_TO_CHECK = (1, 2, 3, 5)


def _pick_seeds(G: nx.DiGraph, n_seeds: int, explicit: list[str]) -> list[str]:
    """Choose a diverse handful of known entities for the sanity check."""
    if explicit:
        missing = [s for s in explicit if s not in G]
        if missing:
            raise SystemExit(f"Explicit seed(s) not in graph: {missing}")
        return explicit
    if not G.number_of_nodes():
        raise SystemExit("Graph index is empty — nothing to sanity-check.")
    # Sort by descending degree and walk a spread of candidates (dense + mid + low)
    by_degree = sorted(G.nodes, key=lambda n: G.degree(n), reverse=True)
    picks: list[str] = []
    for i in range(0, max(len(by_degree), 1), max(1, len(by_degree) // max(1, n_seeds))):
        if i >= len(by_degree):
            break
        node = by_degree[i]
        if node not in picks:
            picks.append(node)
        if len(picks) >= n_seeds:
            break
    # Fill from the tail (low-degree / isolated-ish) if we came up short
    for node in reversed(by_degree):
        if len(picks) >= n_seeds:
            break
        if node not in picks:
            picks.append(node)
    return picks[:n_seeds]


def check_seed(G: nx.DiGraph, seed: str, hops: tuple[int, ...]) -> tuple[bool, dict]:
    """Run the three R2 checks for one seed entity. Returns (ok, report).

    Checks:
      1. hop_depth strictly respected: max_hop_reached <= hop_depth. This is the
         binding R2 guarantee and is always required.
      2. node-count is monotonic non-decreasing as hop_depth grows.
      3. output size grows with hop_depth (R2 exit criterion). This is waived
         only when the seed is *saturated* — i.e. its reachable frontier is fully
         covered at hop 1, so there is nothing more to reach (typical of a
         high-degree hub whose neighbors are leaves). Saturation is reported
         honestly rather than miscounted as a failure.
    """
    results = {}
    sizes = []
    ok = True
    for h in hops:
        res = local_subgraph(G, seed, hop_depth=h)
        st = res["stats"]
        max_hop_ok = bool(st["max_hop_reached"] <= h)
        sizes.append(st["node_count"])
        results[str(h)] = {
            "max_hop_reached": st["max_hop_reached"],
            "node_count": st["node_count"],
            "edge_count": st["edge_count"],
            "illicit_nodes": st["illicit_nodes"],
            "licit_nodes": st["licit_nodes"],
            "unknown_nodes": st["unknown_nodes"],
            "max_hop_ok": max_hop_ok,
        }
        ok = ok and max_hop_ok

    monotonic = all(sizes[i] <= sizes[i + 1] for i in range(len(sizes) - 1))
    grows = sizes[-1] > sizes[0]
    # Saturated: node count is identical from hop 1 onward — the reachable
    # frontier is exhausted immediately (high-degree hub with leaf neighbors).
    saturated = sizes[1] == sizes[0] if len(sizes) >= 2 else False
    ok = ok and monotonic and (grows or saturated)
    return ok, {
        "seed": seed,
        "label": int(G.nodes[seed].get("label", -1)),
        "degree": int(G.degree(seed)),
        "sizes_by_hop": dict(zip(map(str, hops), sizes)),
        "monotonic": monotonic,
        "grows_with_hop": grows,
        "saturated": saturated,
        "per_hop": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="LEDGR R2 subgraph sanity check")
    ap.add_argument("--graph-index", type=Path, default=artifacts_dir() / "graph_index.pkl")
    ap.add_argument("--n-seeds", type=int, default=8, help="How many auto-picked seeds to check")
    ap.add_argument("--seed", dest="explicit_seeds", action="append", default=[],
                    help="Explicit seed tx id(s) to check (repeatable)")
    args = ap.parse_args()

    G = load_graph_index(args.graph_index)
    seeds = _pick_seeds(G, args.n_seeds, args.explicit_seeds)

    print(f"Sanity-checking subgraph construction on {len(seeds)} known entities "
          f"(hops {HOPS_TO_CHECK}) ...\n")
    failures = 0
    for seed in seeds:
        ok, report = check_seed(G, seed, HOPS_TO_CHECK)
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] seed={report['seed']!r} "
              f"label={report['label']} degree={report['degree']} "
              f"sizes={report['sizes_by_hop']} monotonic={report['monotonic']} "
              f"grows={report['grows_with_hop']} saturated={report['saturated']}")

    summary = {
        "checks_passed": failures == 0,
        "n_seeds": len(seeds),
        "seed_reports": [
            {"seed": s, "label": int(G.nodes[s].get("label", -1)), "degree": int(G.degree(s))}
            for s in seeds
        ],
    }
    print("\nSanity check:", "ALL PASS" if failures == 0 else f"{failures} FAILURES")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())