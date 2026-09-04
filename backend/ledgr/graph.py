"""Phase R2 (rebuilt as R3 prerequisite) — Graph Construction Service.

Builds a NetworkX DiGraph from the normalized dataset and extracts a local
subgraph around a given tx id / wallet, with the hop-depth bound actually
respected (unlike the mock it replaces).
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import networkx as nx
import pandas as pd

from .config import artifacts_dir
from .ingest import NormalizedDataset

logger = logging.getLogger(__name__)


def build_graph(ds: NormalizedDataset) -> nx.DiGraph:
    """Build a DiGraph with per-node attrs: label (1/0/-1), time_step."""
    G = nx.DiGraph()
    label_of = dict(zip(map(str, ds.tx_ids), ds.tx_labels.tolist()))
    ts_of = dict(zip(map(str, ds.tx_ids), ds.tx_time_steps.tolist()))
    G.add_nodes_from((tx, {"label": label_of.get(tx, -1), "time_step": ts_of.get(tx, -1)})
                     for tx in map(str, ds.tx_ids))
    G.add_edges_from((str(s), str(d)) for s, d in ds.edges.itertuples(index=False))
    logger.info("Graph built: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())
    return G

def local_subgraph(G: nx.DiGraph, seed_node: str, hop_depth: int = 2) -> dict:
    """Extract the bounded local subgraph around seed_node (hop_depth strictly enforced)."""
    seed_node = str(seed_node)
    if seed_node not in G:
        raise KeyError(f"Seed node not in graph: {seed_node}")
    if hop_depth < 1:
        raise ValueError(f"hop_depth must be >= 1, got {hop_depth}")

    G_und = G.to_undirected(as_view=True)
    lengths = nx.single_source_shortest_path_length(G_und, seed_node, cutoff=hop_depth)
    nodes = set(lengths)

    sub = G.subgraph(nodes)
    edges = [
        {"src": u, "dst": v,
         "src_label": int(G.nodes[u]["label"]), "dst_label": int(G.nodes[v]["label"])}
        for u, v in sub.edges()
    ]
    node_list = [
        {"id": n, "hop": int(lengths[n]),
         "label": int(G.nodes[n]["label"]), "time_step": int(G.nodes[n]["time_step"])}
        for n in nodes
    ]
    stats = {
        "seed": seed_node,
        "hop_depth_requested": hop_depth,
        "max_hop_reached": int(max(lengths.values())),
        "node_count": len(node_list),
        "edge_count": len(edges),
        "illicit_nodes": sum(1 for n in node_list if n["label"] == 1),
        "licit_nodes": sum(1 for n in node_list if n["label"] == 0),
        "unknown_nodes": sum(1 for n in node_list if n["label"] == -1),
    }
    logger.info("Local subgraph %s hop=%d: %d nodes / %d edges",
                seed_node, hop_depth, stats["node_count"], stats["edge_count"])
    return {"nodes": node_list, "edges": edges, "stats": stats}


def save_graph_index(G: nx.DiGraph, out_dir: Path | None = None) -> Path:
    """Persist the pre-indexed graph (query-time speed = pre-indexed lookup, not live ingestion)."""
    out_dir = Path(out_dir) if out_dir else artifacts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "graph_index.pkl"
    with open(path, "wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Graph index saved: %s (%d nodes)", path, G.number_of_nodes())
    return path


def load_graph_index(path: Path | None = None) -> nx.DiGraph:
    path = Path(path) if path else artifacts_dir() / "graph_index.pkl"
    if not path.exists():
        raise FileNotFoundError(
            f"Graph index not found at {path}. Run `python scripts/run_ingest.py` first."
        )
    with open(path, "rb") as f:
        G = pickle.load(f)
    logger.info("Graph index loaded: %s (%d nodes)", path, G.number_of_nodes())
    return G

