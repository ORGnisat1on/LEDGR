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
import numpy as np
import pandas as pd

from .config import artifacts_dir
from .ingest import NormalizedDataset

logger = logging.getLogger(__name__)


def build_graph(ds: NormalizedDataset) -> nx.DiGraph:
    """Build a DiGraph using integer node IDs for memory efficiency."""
    G = nx.DiGraph()
    tx_ids_str = [str(tx) for tx in ds.tx_ids]
    tx_to_idx = {tx: i for i, tx in enumerate(tx_ids_str)}
    idx_to_tx = np.array(tx_ids_str)
    
    G.add_nodes_from(range(len(tx_ids_str)))
    
    edges = [(tx_to_idx[str(s)], tx_to_idx[str(d)]) for s, d in ds.edges.itertuples(index=False) 
             if str(s) in tx_to_idx and str(d) in tx_to_idx]
    G.add_edges_from(edges)
    
    # Store attributes in contiguous arrays instead of per-node dicts to save ~200MB
    node_labels = np.full(len(tx_ids_str), -1, dtype=np.int8)
    node_time_steps = np.full(len(tx_ids_str), -1, dtype=np.int8)
    for i, tx in enumerate(ds.tx_ids):
        node_labels[i] = ds.tx_labels[i]
        node_time_steps[i] = ds.tx_time_steps[i]
        
    G.graph["tx_to_idx"] = tx_to_idx
    G.graph["idx_to_tx"] = idx_to_tx
    G.graph["node_labels"] = node_labels
    G.graph["node_time_steps"] = node_time_steps
    
    logger.info("Graph built: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())
    return G

def local_subgraph(G: nx.DiGraph, seed_node: str, hop_depth: int = 2) -> dict:
    """Extract the bounded local subgraph around seed_node (hop_depth strictly enforced)."""
    seed_node = str(seed_node)
    tx_to_idx = G.graph.get("tx_to_idx")
    idx_to_tx = G.graph.get("idx_to_tx")
    
    # Handle int-mapped graphs or raw string graphs
    if tx_to_idx is not None:
        if seed_node not in tx_to_idx:
            raise KeyError(f"Seed node not in graph: {seed_node}")
        internal_seed = tx_to_idx[seed_node]
        def to_str(n): return str(idx_to_tx[n])
    else:
        if seed_node not in G:
            raise KeyError(f"Seed node not in graph: {seed_node}")
        internal_seed = seed_node
        def to_str(n): return str(n)

    if hop_depth < 1:
        raise ValueError(f"hop_depth must be >= 1, got {hop_depth}")

    G_und = G.to_undirected(as_view=True)
    lengths = nx.single_source_shortest_path_length(G_und, internal_seed, cutoff=hop_depth)
    nodes = set(lengths)

    sub = G.subgraph(nodes)
    if tx_to_idx is not None:
        labels = G.graph["node_labels"]
        time_steps = G.graph["node_time_steps"]
        def get_label(n): return int(labels[n])
        def get_ts(n): return int(time_steps[n])
    else:
        def get_label(n): return int(G.nodes[n]["label"])
        def get_ts(n): return int(G.nodes[n]["time_step"])

    edges = [
        {"src": to_str(u), "dst": to_str(v),
         "src_label": get_label(u), "dst_label": get_label(v)}
        for u, v in sub.edges()
    ]
    node_list = [
        {"id": to_str(n), "hop": int(lengths[n]),
         "label": get_label(n), "time_step": get_ts(n)}
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

