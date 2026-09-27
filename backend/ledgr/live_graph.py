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
- Failure modes are distinct and never collapse (hardened 2026-09-26):
    * malformed input          -> SOURCE_INVALID_ADDRESS_FORMAT (local format
      validation, NO network call, checked before any explorer request);
    * address with no history  -> SOURCE_NOT_FOUND_ON_CHAIN (both explorers
      answered 200 with zero txs — real signal, an honest answer);
    * explorers rejected it    -> LiveSourceError kind 'bad-address' (BOTH
      sources returned a 4xx validity verdict — never inferred from one source);
    * rate-limited (HTTP 429)  -> LiveSourceError kind 'rate-limited';
    * request timed out        -> LiveSourceError kind 'timeout';
    * explorer outage (5xx etc)-> LiveSourceError kind 'api-error'.
  The last three are operational, retryable states surfaced as HTTP 503 with a
  structured detail — they are NEVER reported as "address not found/invalid"
  (the 2026-09-26 429->bad-address mislabel this pass exists to prevent).

The learned signal (R4) has no feature vector for a live-fetched address and
stays honestly `classified: false` — the verdict for any live-looked-up wallet
is therefore CAPPED AT `watch` (enforced in service.correlate_live, not just
assumed), because `confirmed` requires two independent signals and only one
can exist here.
"""

from __future__ import annotations

import logging

import networkx as nx
import requests

from .address_format import classify_address
from .config import (
    LIVE_MAX_COUNTERPARTY_FETCHES,
    LIVE_MAX_NODES,
    LIVE_MAX_TXS_PER_ADDRESS,
    LIVE_TIME_STEP_SECONDS,
)

logger = logging.getLogger(__name__)

SOURCE_LIVE = "live-lookup"
SOURCE_NOT_FOUND_ON_CHAIN = "not-found-on-chain"
# Input that fails mainnet format validation BEFORE any network call (and, via
# LiveSourceError kind 'bad-address', input both explorers independently reject).
# Distinct from NOT_FOUND: no lookup happened (or the explorers refused the
# input), so "no on-chain history" would be a claim we did not establish.
SOURCE_INVALID_ADDRESS_FORMAT = "invalid-address-format"
# Sources that describe the INPUT or its absence of history — i.e. an answer,
# not a service failure. Any outcome with one of these carries no graph.
NO_GRAPH_SOURCES = frozenset({SOURCE_NOT_FOUND_ON_CHAIN, SOURCE_INVALID_ADDRESS_FORMAT})

# LiveSourceError kinds — one per distinct external-response class. Priority
# rules when both sources fail live in _classify_pair_failure().
KIND_RATE_LIMITED = "rate-limited"   # HTTP 429 from either source (unknown-cause state)
KIND_TIMEOUT = "timeout"             # request hung/timed out (unknown-cause state)
KIND_BAD_ADDRESS = "bad-address"     # BOTH sources returned a 4xx validity verdict
KIND_API_ERROR = "api-error"         # 5xx / connection failure / anything else
# The local, offline format gate rejected the input before any network call.
# Deliberately the same string as SOURCE_INVALID_ADDRESS_FORMAT so a malformed
# paste is named identically wherever it surfaces (200 answer body and 400 detail).
KIND_INVALID_ADDRESS_FORMAT = SOURCE_INVALID_ADDRESS_FORMAT


class LiveSourceError(Exception):
    """A live block-explorer API failure (timeout/rate-limit/bad response).

    Distinct from 'address has no on-chain history' — that is an honest result
    (SOURCE_NOT_FOUND_ON_CHAIN), not an error. `kind` separates failure modes
    so they never collapse into one message:
      - 'rate-limited': HTTP 429 — the explorer throttled us; says NOTHING
        about the address. Retryable.
      - 'timeout': the request hung until the client timeout; says NOTHING
        about the address. Retryable.
      - 'bad-address': BOTH explorers returned a 4xx validity verdict —
        the address itself was rejected (not a service failure, not retryable).
      - 'api-error': 5xx / connection failure / unexpected response.
    """

    def __init__(self, message: str, cause: Exception | None = None, kind: str = KIND_API_ERROR):
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


def classify_live_failure(exc: BaseException) -> str:
    """Map ONE source's terminal failure to a LiveSourceError kind.

    Order matters: Timeout first (requests.Timeout has no .response and must
    never fall into the HTTP-status branches), then 429, then only the narrow
    statuses that constitute a validity verdict about the address (400 bad
    format / 404 unknown). 401/403 (auth/quota) and other 4xx are operational,
    never "the address is invalid".
    """
    if isinstance(exc, requests.Timeout):          # includes Connect/Read timeouts
        return KIND_TIMEOUT
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 429:
        return KIND_RATE_LIMITED
    if status in (400, 404):
        # A validity verdict in isolation — NOT yet proof of an invalid address;
        # _classify_pair_failure requires BOTH sources to agree.
        return KIND_BAD_ADDRESS
    return KIND_API_ERROR


def _classify_pair_failure(bs_kind: str, bc_kind: str) -> str:
    """Combine both sources' failure kinds when NEITHER returned data.

    Priority (the 2026-09-26 429->bad-address mislabel is fixed here):
      1. rate-limited — either source throttled us, so no verdict about the
                        address was established; NEVER report bad-address.
      2. timeout      — either source hung: also an unknown-cause state.
      3. bad-address  — ONLY if both sources independently returned a validity
                        verdict (400/404).
      4. api-error    — anything else (5xx, connection failure, mixed cases).

    Mixed cases fixed by these rules (asserted by test_live_failure_modes.py):
      429 + 404 -> rate-limited (not bad-address);
      400 + timeout -> timeout;   400 + 404 -> bad-address;
      500 + 400 -> api-error;     429 + 429 -> rate-limited.
    """
    if KIND_RATE_LIMITED in (bs_kind, bc_kind):
        return KIND_RATE_LIMITED
    if KIND_TIMEOUT in (bs_kind, bc_kind):
        return KIND_TIMEOUT
    if bs_kind == KIND_BAD_ADDRESS and bc_kind == KIND_BAD_ADDRESS:
        return KIND_BAD_ADDRESS
    return KIND_API_ERROR


def _default_fetcher(address: str) -> list[dict]:
    """Fetch tx summaries for one address: Blockstream primary, BlockCypher fallback.

    Failover contract: ONE source failing (429, timeout, 5xx, network error)
    degrades to the other — a single-source failure never aborts the request and
    never becomes a verdict about the address. Only when BOTH sources fail is
    `LiveSourceError` raised, with `kind` decided by `_classify_pair_failure`.
    An empty tx list is returned as-is (the caller maps it to not-found-on-chain).
    """
    from .blockcypher_client import BlockCypherClient
    from .blockstream_client import BlockstreamClient

    try:
        return BlockstreamClient().get_address_txs(address)
    except Exception as bs_exc:
        bs_kind = classify_live_failure(bs_exc)
        # NOTE: `except ... as bs_exc` unbinds the name when the block exits, so
        # the detail is copied out here for use after the handler. (A stray
        # UnboundLocalError in the message path would be classified as an
        # api-error and hide the real failure kind — exactly the collapse this
        # pass removes, so it is asserted by the pair-classification tests.)
        bs_detail = str(bs_exc)
        logger.warning("Blockstream failed for %s (%s: %s) — falling back to BlockCypher",
                       address, bs_kind, bs_detail)

    try:
        return BlockCypherClient().get_address_full(address).get("txs", [])
    except Exception as bc_exc:
        bc_kind = classify_live_failure(bc_exc)
        raise LiveSourceError(
            f"Both live sources failed for {address} "
            f"(blockstream: {bs_kind} — {bs_detail}; blockcypher: {bc_kind} — {bc_exc})",
            cause=bc_exc,
            kind=_classify_pair_failure(bs_kind, bc_kind),
        ) from bc_exc


def has_onchain_history(address: str) -> bool:
    """Cheap pre-check: does this address have ANY on-chain txs?

    Uses the stats endpoint (1 request) so an unused/unknown address is
    reported honestly without spending calls on its tx list. Falls back to
    checking the fetched tx list if the stats call is unsupported upstream.
    (Currently unused by the pipeline; classified like every other live call so
    a future caller cannot inherit a 429/timeout-as-api-error collapse.)
    """
    from .blockstream_client import BlockstreamClient

    try:
        return BlockstreamClient().get_address_stats(address)["tx_count"] > 0
    except requests.RequestException as e:
        raise LiveSourceError(
            f"Live source stats check failed for {address}: {e}",
            cause=e,
            kind=classify_live_failure(e),
        ) from e


def trace_live(address: str, hop_depth: int,
               fetcher=None, max_txs: int = LIVE_MAX_TXS_PER_ADDRESS,
               max_fetches: int = LIVE_MAX_COUNTERPARTY_FETCHES) -> dict:
    """Orchestrate a live lookup for one out-of-dataset address.

    Returns {"graph": nx.DiGraph, "txs_by_address": ..., "meta": {...}} where
    meta reports every cap honestly (capped flags + counts). Raises
    LiveSourceError on live-API failure; an address with zero on-chain txs
    returns source=not-found-on-chain instead of a graph; input that fails
    mainnet format validation returns source=invalid-address-format WITHOUT any
    network request (checked first — see address_format.classify_address).
    """
    address = str(address)

    # Local format gate — runs BEFORE any explorer request, so a malformed paste
    # can never be rate-limited, can never reach the network, and can never be
    # reported as "no on-chain history". Only the SEED (the user-supplied input)
    # is validated; counterparties come from the explorers' own responses and are
    # not user input, so they are not re-judged against our validator.
    fmt = classify_address(address)
    if not fmt.valid:
        logger.info("Rejecting address locally (format=%s): %s", fmt.reason, fmt.detail)
        return {
            "source": SOURCE_INVALID_ADDRESS_FORMAT,
            "note": (
                f"Not a valid mainnet Bitcoin address ({fmt.reason}): {fmt.detail}. "
                "Checked locally before any network lookup — no block-explorer request "
                "was made and no signal was computed for this input."
            ),
            "address": address,
            "format_reason": fmt.reason,
            "format_detail": fmt.detail,
            "network_attempted": False,
        }

    fetcher = fetcher or _default_fetcher

    def _fetch(addr: str) -> list[dict]:
        try:
            return list(fetcher(addr))
        except LiveSourceError:
            raise
        except Exception as e:
            # Classify instead of defaulting: a 429 or a timeout from a custom
            # fetcher must NOT become 'bad-address' (the 2026-09-26 mislabel
            # class). Only a genuine 400/404 explorer verdict qualifies.
            raise LiveSourceError(
                f"live fetch failed for {addr}: {e}",
                cause=e,
                kind=classify_live_failure(e),
            ) from e

    txs = _fetch(address)[:max_txs]
    if not txs:
        return {
            "source": SOURCE_NOT_FOUND_ON_CHAIN,
            "note": "Address has no on-chain transaction history (unknown or unused address) — nothing to trace and no signal to compute.",
            "address": address,
            "network_attempted": True,
        }

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


