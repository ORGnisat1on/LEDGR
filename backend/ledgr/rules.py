"""Phase R3 — Rule-Based Signal (ARCHITECTURE.md Module 3a).

Three heuristics implemented for real, replacing the hash/modulo-based flag
selection in the mock `analyzer.ts`:

1. peel_chain       — successive nodes each forwarding onward to exactly one
                      next node, time-advancing, at least PEEL_CHAIN_MIN_HOPS
                      deep (classic layering/peel pattern).
2. rapid_fan_out    — a node funded by few inputs (<= FANOUT_MAX_IN) bursting
                      to many outputs (>= FANOUT_MIN_OUT) within a tight
                      FANOUT_TIME_WINDOW time-step window.
3. mixer_adjacent   — any node within MIXER_MAX_HOPS of a known mixer address
                      (mixer list sourced into data/mixers.txt; format in
                      data/mixers.example.txt).

Every rule returns auditable evidence (which rule fired and why). Elliptic's
static edges carry no BTC amounts, so detection is structural; amount-based
confirmation is applied when amounts are available (live/query-time data).
"""

from __future__ import annotations

import logging
from pathlib import Path

import networkx as nx

from .config import (
    MIXER_LIST_FILE,
    RULE_FLAG_THRESHOLDS,
    RULE_WEIGHTS,
    artifacts_dir,
    rule_params,
)

logger = logging.getLogger(__name__)

RULE_PEEL = "peel_chain"
RULE_FANOUT = "rapid_fan_out"
RULE_MIXER = "mixer_adjacent"


def load_mixer_ids(path: Path | None = None) -> set[str]:
    """Load the mixer-address validation set. Missing file => empty set (logged, never fabricated)."""
    path = Path(path) if path else MIXER_LIST_FILE
    if not path.exists():
        logger.warning("Mixer list not found at %s — mixer_adjacent heuristic will not fire. "
                       "Source a validation set per SCOPE.md and place it there (format: "
                       "data/mixers.example.txt).", path)
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ids.add(line)
    logger.info("Loaded %d mixer addresses from %s", len(ids), path)
    return ids

def _time_step(G: nx.DiGraph, node: str) -> int:
    return int(G.nodes[node].get("time_step", -1))


def detect_peel_chains(G: nx.DiGraph, min_hops: int, max_time_gap: int) -> dict[str, dict]:
    """Return {node -> evidence} for every node inside a qualifying peel chain.

    Structural definition: a directed path of >= min_hops edges where every
    internal node has out-degree exactly 1 (pure onward forwarding) and edge
    time steps advance monotonically with gaps <= max_time_gap.
    """
    # Nodes eligible as chain internals: exactly one onward output
    forwarding = {n for n in G.nodes if G.out_degree(n) == 1 and G.in_degree(n) >= 1}

    # Walk forward: from each forwarding node, extend while the successor is
    # also forwarding and time advances within the gap.
    chain_len: dict[str, int] = {}
    for start in forwarding:
        length = 0
        cur, prev_ts = start, _time_step(G, start)
        while True:
            nxt = next(iter(G.successors(cur)))
            if nxt not in forwarding or G.in_degree(nxt) != 1:
                break
            ts = _time_step(G, nxt)
            if prev_ts >= 0 and ts >= 0 and ts - prev_ts > max_time_gap:
                break
            length += 1
            cur, prev_ts = nxt, ts
        chain_len[start] = length

    evidence: dict[str, dict] = {}
    # A qualifying chain has >= min_hops forwarding hops. Flag every node whose
    # remaining chain length keeps it inside such a chain.
    for start, length in chain_len.items():
        if length + 1 < min_hops:
            continue
        cur, prev_ts = start, _time_step(G, start)
        hops_from_seed = 0
        while hops_from_seed <= length:
            evidence.setdefault(cur, {
                "chain_length_hops": length + 1,
                "position_from_seed": hops_from_seed,
                "time_step": prev_ts,
            })
            if hops_from_seed == length:
                break
            nxt = next(iter(G.successors(cur)))
            prev_ts = _time_step(G, nxt)
            cur = nxt
            hops_from_seed += 1
    return evidence


def detect_rapid_fan_out(G: nx.DiGraph, min_out: int, max_in: int, window: int) -> dict[str, dict]:
    """Return {node -> evidence} for nodes bursting many outputs in a tight window."""
    evidence: dict[str, dict] = {}
    for n in G.nodes:
        if G.out_degree(n) < min_out or G.in_degree(n) > max_in:
            continue
        ts = _time_step(G, n)
        succ_ts = [_time_step(G, s) for s in G.successors(n)]
        succ_ts = [t for t in succ_ts if t >= 0]
        if not succ_ts:
            continue
        spread = max(succ_ts) - min(succ_ts)
        if spread > window:
            continue
        evidence[n] = {
            "in_degree": G.in_degree(n),
            "out_degree": G.out_degree(n),
            "time_step_spread": spread,
            "seed_time_step": ts,
        }
    return evidence


def detect_mixer_adjacency(G: nx.DiGraph, mixer_ids: set[str], max_hops: int) -> dict[str, dict]:
    """Return {node -> evidence} for nodes within max_hops of any known mixer."""
    evidence: dict[str, dict] = {}
    mixers_in_graph = [m for m in mixer_ids if m in G]
    for m in mixers_in_graph:
        G_und = G.to_undirected(as_view=True)
        lengths = nx.single_source_shortest_path_length(G_und, m, cutoff=max_hops)
        for node, dist in lengths.items():
            if node == m or dist == 0:
                continue
            prev = evidence.get(node)
            if prev is None or dist < prev["hops_from_mixer"]:
                evidence[node] = {"mixer_id": m, "hops_from_mixer": dist}
    return evidence


def rule_flag_for(score: int) -> str:
    high = RULE_FLAG_THRESHOLDS["high"]
    medium = RULE_FLAG_THRESHOLDS["medium"]
    if score >= high:
        return "high"
    if score >= medium:
        return "medium"
    if score > 0:
        return "low"
    return "none"

def run_rules(G: nx.DiGraph, seed: str, mixer_ids: set[str] | None = None,
              hop_depth: int = 2, mixers_path: Path | None = None) -> dict:
    """Run the rule-based signal (Module 3a) for one wallet — auditable output.

    Heuristics are evaluated on the seed's bounded local subgraph (same
    hop_depth bound as graph construction), keeping query-time cost bounded.
    Returns which rules fired, their evidence, a composite rule_score
    (documented weights), and the rule_flag tier — no hardcoded scores.
    """
    seed = str(seed)
    if seed not in G:
        raise KeyError(f"Seed node not in graph: {seed}")
    params = rule_params()
    if mixer_ids is None:
        mixer_ids = load_mixer_ids(mixers_path)

    sub = G.to_undirected(as_view=True)
    lengths = nx.single_source_shortest_path_length(sub, seed, cutoff=hop_depth)
    local = G.subgraph(set(lengths))

    peel = detect_peel_chains(local, params["peel_chain_min_hops"], params["peel_chain_max_time_gap"])
    fanout = detect_rapid_fan_out(local, params["fanout_min_out"], params["fanout_max_in"],
                                  params["fanout_time_window"])
    mixer = detect_mixer_adjacency(local, mixer_ids, params["mixer_max_hops"])

    fired = {
        RULE_PEEL: {
            "fired": seed in peel, "weight": RULE_WEIGHTS[RULE_PEEL],
            "evidence": peel.get(seed) or ({"peers_in_chain": sorted(peel)} if peel else {}),
        },
        RULE_FANOUT: {
            "fired": seed in fanout, "weight": RULE_WEIGHTS[RULE_FANOUT],
            "evidence": fanout.get(seed) or {},
        },
        RULE_MIXER: {
            "fired": seed in mixer, "weight": RULE_WEIGHTS[RULE_MIXER],
            "evidence": mixer.get(seed) or {},
        },
    }
    rule_score = sum(r["weight"] for r in fired.values() if r["fired"])
    result = {
        "wallet": seed,
        "hop_depth": hop_depth,
        "rule_score": rule_score,
        "rule_flag": rule_flag_for(rule_score),
        "rules_fired": [r for r, v in fired.items() if v["fired"]],
        "contributing_signals": fired,
        "engine_params": params,
        "mixer_list_loaded": bool(mixer_ids),
    }
    logger.info("Rules %s: score=%d flag=%s fired=%s", seed, rule_score,
                result["rule_flag"], result["rules_fired"])
    return result


