"""Phase R9 — Live Address Tracing (out-of-dataset wallets).

Real-world Bitcoin addresses (a victim-pasted wallet, a rich-list cold wallet)
will essentially never match Elliptic's anonymized node ids, so the indexed
lookup alone can only ever answer "not classified" for the case that matters
most. This module closes that gap, per BACKEND_BUILD_PLAN.md Phase R9:

- Live source: the existing Module-1 clients (`blockstream_client.py` primary,
  `blockcypher_client.py` fallback) fetch a bounded window of real transaction
  history for ONE reported address, on demand (SCOPE.md: demo-time tracing of a
  small fixed set — never bulk, never continuous, free-tier rate limits).
- `build_live_graph` constructs an ad-hoc address-level DiGraph from the fetched
  summaries with the same node-attribute conventions as `graph.build_graph`
  (label / time_step), so the R3 rule engine runs on it unchanged.
- Failure modes are distinct and never collapse: an address with no on-chain
  history is `not-found-on-chain`; a live-API failure raises `LiveSourceError`
  (surfaced as 503, never as a silent "unavailable").

The learned signal (R4) has no feature vector for a live-fetched address and
stays honestly `classified: false` — the verdict for any live-looked-up wallet
is therefore CAPPED AT `watch` (enforced in service.correlate_live, not just
assumed), because `confirmed` requires two independent signals and only one
can exist here.
"""

from __future__ import annotations

import functools
import logging

import networkx as nx

from .config import (
    LIVE_MAX_COUNTERPARTY_FETCHES,
    LIVE_MAX_NODES,
    LIVE_MAX_TXS_PER_ADDRESS,
    LIVE_TIME_STEP_SECONDS,
)

logger = logging.getLogger(__name__)

SOURCE_LIVE = "live-lookup"
SOURCE_NOT_FOUND_ON_CHAIN = "not-found-on-chain"


class LiveSourceError(Exception):
    """A live block-explorer API failure (timeout/rate-limit/bad response).

    Distinct from 'address has no on-chain history' — that is an honest result
    (SOURCE_NOT_FOUND_ON_CHAIN), not an error. `kind` separates failure modes
    so they never collapse into one message:
      - 'api-error': the live source itself failed (timeout/5xx/network)
      - 'bad-address': the explorers rejected the address as invalid (4xx)
    """

    def __init__(self, message: str, cause: Exception | None = None, kind: str = "api-error"):
        super().__init__(message)
        self.cause = cause
        self.kind = kind


def extract_addresses_from_summary(tx: dict) -> tuple[set[str], set[str]]:
    """Extract input/output addresses from one Blockstream tx summary.

    Coinbase inputs (no prevout) and OP_RETURN outputs (no scriptpubkey_address)
    yield no address and are excluded — same UTXO hygiene as Module 1.
    """
    in_addrs: set[str] = set()
    out_addrs: set[str] = set()
    for vin in tx.get("vin", []) or []:
        prevout = vin.get("prevout")
        addr = (prevout or {}).get("scriptpubkey_address")
        if addr:
            in_addrs.add(addr)
    for vout in tx.get("vout", []) or []:
        addr = vout.get("scriptpubkey_address")
        if addr:
            out_addrs.add(addr)
    return in_addrs, out_addrs


def _tx_time_step(tx: dict) -> int:
    """Map a tx's block time onto Elliptic-granularity time steps (-1 if unconfirmed)."""
    block_time = (tx.get("status") or {}).get("block_time")
    if not block_time or block_time <= 0:
        return -1
    return int(block_time) // LIVE_TIME_STEP_SECONDS


def build_live_graph(seed: str, txs_by_address: dict[str, list[dict]]) -> nx.DiGraph:
    """Build an ad-hoc address-level DiGraph from fetched tx summaries.

    Pure function (no network) so it is directly testable against recorded
    fixtures. Node attrs follow `graph.build_graph` conventions:
    label=-1 (live addresses carry no Elliptic label), time_step mapped from
    block time at Elliptic's ~2-week granularity. Each tx contributes directed
    edges from every input address to every output address (the standard UTXO
    flow heuristic).
    """
    G = nx.DiGraph()
    seed = str(seed)

    for addr, txs in txs_by_address.items():
        for tx in txs:
            ts = _tx_time_step(tx)
            in_addrs, out_addrs = extract_addresses_from_summary(tx)
            nodes_here = (in_addrs | out_addrs) | {addr}
            for n in nodes_here:
                if n not in G:
                    G.add_node(n, label=-1, time_step=ts)
                elif ts >= 0 and int(G.nodes[n]["time_step"]) < 0:
                    G.nodes[n]["time_step"] = ts
            for i in in_addrs:
                for o in out_addrs:
                    if i != o:
                        G.add_edge(i, o)

    if seed not in G:
        # Seed had txs but none with usable addresses (rare) — still give it a node.
        G.add_node(seed, label=-1, time_step=-1)

    if G.number_of_nodes() > LIVE_MAX_NODES:
        keep = {seed}
        for n in list(G.nodes):
            if len(keep) >= LIVE_MAX_NODES:
                break
            keep.add(n)
        G = G.subgraph(keep).copy()
        logger.warning("Live graph hard-capped at %d nodes", LIVE_MAX_NODES)

    logger.info("Live graph for %s: %d nodes / %d edges",
                seed, G.number_of_nodes(), G.number_of_edges())
    return G


def live_subgraph_payload(G: nx.DiGraph, seed: str, meta: dict) -> dict:
    """Shape the live graph exactly like `graph.local_subgraph`'s output.

    Keeping the same node/edge/stats schema means the frontend renders live
    traces without caring where the graph came from; `meta` carries the
    live-specific honesty fields (fetch caps, source, learned-signal note).
    """
    seed = str(seed)
    if seed not in G:
        raise KeyError(f"Seed node not in live graph: {seed}")
    sub = G
    und = sub.to_undirected(as_view=True)
    lengths = nx.single_source_shortest_path_length(und, seed)
    nodes = [
        {"id": n, "hop": int(lengths.get(n, -1)),
         "label": int(sub.nodes[n].get("label", -1)),
         "time_step": int(sub.nodes[n].get("time_step", -1))}
        for n in sub.nodes
    ]
    edges = [
        {"src": u, "dst": v,
         "src_label": int(sub.nodes[u].get("label", -1)),
         "dst_label": int(sub.nodes[v].get("label", -1))}
        for u, v in sub.edges
    ]
    stats = {
        "seed": seed,
        "max_hop_reached": int(max(lengths.values())) if lengths else 0,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "illicit_nodes": 0,  # live addresses have no Elliptic labels — never implied otherwise
        "licit_nodes": 0,
        "unknown_nodes": len(nodes),
    }
    return {"nodes": nodes, "edges": edges, "stats": stats, "source": SOURCE_LIVE, **meta}


@functools.lru_cache(maxsize=32)
def _default_fetcher(address: str) -> list[dict]:
    """Fetch tx summaries for one address: Blockstream primary, BlockCypher fallback.

    Raises LiveSourceError (api-error kind) only when BOTH sources fail — a
    single-source failure must degrade, not abort. Raises LiveSourceError with
    kind 'not-found-on-chain' is NOT used here: an empty tx list is returned as-is.
    """
    import requests

    from .blockcypher_client import BlockCypherClient
    from .blockstream_client import BlockstreamClient

    try:
        return BlockstreamClient().get_address_txs(address)
    except requests.HTTPError as bs_err:
        status = bs_err.response.status_code if bs_err.response is not None else 0
        try:
            return BlockCypherClient().get_address_full(address).get("txs", [])
        except Exception as bc_err:
            # Both sources 4xx'd => the address itself is invalid (bad-address);
            # anything else is a genuine api-error. Never collapse the two.
            bc_resp = getattr(bc_err, "response", None)
            both_4xx = 400 <= status < 500 and (
                bc_resp is not None and bc_resp.status_code < 500
            )
            raise LiveSourceError(
                f"Both live sources rejected/failed for {address} "
                f"(blockstream: {bs_err}; blockcypher: {bc_err})",
                cause=bc_err,
                kind="bad-address" if both_4xx else "api-error",
            ) from bc_err
    except requests.RequestException as bs_err:
        logger.warning("Blockstream fetch failed for %s (%s) — falling back to BlockCypher",
                       address, bs_err)
        try:
            return BlockCypherClient().get_address_full(address).get("txs", [])
        except Exception as bc_err:  # both sources down — a genuine api-error
            raise LiveSourceError(
                f"Both live sources failed for {address} "
                f"(blockstream: {bs_err}; blockcypher: {bc_err})",
                cause=bc_err,
            ) from bc_err


def has_onchain_history(address: str) -> bool:
    """Cheap pre-check: does this address have ANY on-chain txs?

    Uses the stats endpoint (1 request) so an unused/unknown address is
    reported honestly without spending calls on its tx list. Falls back to
    checking the fetched tx list if the stats call is unsupported upstream.
    """
    import requests

    from .blockstream_client import BlockstreamClient

    try:
        return BlockstreamClient().get_address_stats(address)["tx_count"] > 0
    except requests.RequestException as e:
        raise LiveSourceError(f"Live source stats check failed for {address}: {e}", cause=e) from e


def trace_live(address: str, hop_depth: int,
               fetcher=None, max_txs: int = LIVE_MAX_TXS_PER_ADDRESS,
               max_fetches: int = LIVE_MAX_COUNTERPARTY_FETCHES) -> dict:
    """Orchestrate a live lookup for one out-of-dataset address.

    Returns {"graph": nx.DiGraph, "txs_by_address": ..., "meta": {...}} where
    meta reports every cap honestly (capped flags + counts). Raises
    LiveSourceError on live-API failure; an address with zero on-chain txs
    returns source=not-found-on-chain instead of a graph.
    """
    address = str(address)
    fetcher = fetcher or _default_fetcher

    def _fetch(addr: str) -> list[dict]:
        try:
            return list(fetcher(addr))
        except LiveSourceError:
            raise
        except Exception as e:
            # A 4xx from the explorer means the address itself is invalid —
            # an honest 'bad address' result, not a service outage.
            kind = "bad-address"
            resp = getattr(e, "response", None)
            if resp is None or resp.status_code >= 500:
                kind = "api-error"
            raise LiveSourceError(f"live fetch failed for {addr}: {e}", cause=e, kind=kind) from e

    txs = _fetch(address)[:max_txs]
    if not txs:
        return {"source": SOURCE_NOT_FOUND_ON_CHAIN,
                "note": "Address has no on-chain transaction history (unknown or unused address) — nothing to trace and no signal to compute."}

    txs_by_address: dict[str, list[dict]] = {address: txs}
    fetch_count = 1
    frontier = set()
    for tx in txs:
        ins, outs = extract_addresses_from_summary(tx)
        frontier |= (ins | outs) - {address}

    # Expand outward BFS-style up to hop_depth, respecting the fetch cap.
    depth = 1
    visited = {address}
    while depth < hop_depth and frontier and fetch_count <= max_fetches:
        next_frontier = set()
        for addr in sorted(frontier):
            if fetch_count >= max_fetches:
                break
            if addr in txs_by_address:
                continue
            txs_by_address[addr] = _fetch(addr)[:max_txs]
            fetch_count += 1
            visited.add(addr)
            for tx in txs_by_address[addr]:
                ins, outs = extract_addresses_from_summary(tx)
                next_frontier |= (ins | outs) - set(txs_by_address)
        frontier = next_frontier - visited
        depth += 1

    G = build_live_graph(address, txs_by_address)
    meta = {
        "txs_by_address_fetched": {a: len(t) for a, t in txs_by_address.items()},
        "fetch_count": fetch_count,
        "fetch_cap": max_fetches,
        "tx_cap": max_txs,
        "capped": fetch_count >= max_fetches or any(
            len(t) >= max_txs for t in txs_by_address.values()
        ),
        "hop_depth": hop_depth,
    }
    return {"source": SOURCE_LIVE, "graph": G, "txs_by_address": txs_by_address, "meta": meta}


