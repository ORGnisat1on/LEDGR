"""Phase R1 (rebuilt as R3 prerequisite) — Entity-safe train/test split (METHODOLOGY.md §1).

Entity = connected-component clustering on the transaction graph with the
mandatory hub-node safeguard (edges through high-degree hub nodes do not merge
components), whole entities go to train or test, and a programmatic
no-leakage check runs post-split with its result logged.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict

import numpy as np
import pandas as pd

from .config import HUB_DEGREE_THRESHOLD, SPLIT_SEED, TRAIN_FRACTION, artifacts_dir
from .ingest import NormalizedDataset

logger = logging.getLogger(__name__)


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

def build_entities(ds: NormalizedDataset, hub_threshold: int = HUB_DEGREE_THRESHOLD) -> pd.DataFrame:
    """Assign every tx id an entity_id. Returns DataFrame [tx_id, entity_id, is_hub]."""
    degree: dict[str, int] = defaultdict(int)
    for src, dst in ds.edges.itertuples(index=False):
        degree[src] += 1
        degree[dst] += 1
    hubs = {n for n, d in degree.items() if d > hub_threshold}

    uf = _UnionFind()
    n_merged = 0
    for src, dst in ds.edges.itertuples(index=False):
        if src in hubs or dst in hubs:
            continue
        uf.union(src, dst)
        n_merged += 1

    comp_ids: dict[str, str] = {}
    rows = []
    for tx in ds.tx_ids:
        tx = str(tx)
        if tx in hubs:
            entity = f"hub::{tx}"
        else:
            root = uf.find(tx)
            entity = comp_ids.setdefault(root, f"entity::{len(comp_ids)}")
        rows.append((tx, entity, tx in hubs))

    df = pd.DataFrame(rows, columns=["tx_id", "entity_id", "is_hub"])
    logger.info("Entity construction: %d txs -> %d entities (hub threshold %d, %d hubs)",
                len(df), df["entity_id"].nunique(), hub_threshold, len(hubs))
    return df


def split_entities(entities: pd.DataFrame, train_fraction: float = TRAIN_FRACTION,
                   seed: int = SPLIT_SEED) -> pd.DataFrame:
    """Assign whole entities to train/test. Returns [tx_id, entity_id, is_hub, split]."""
    rng = np.random.default_rng(seed)
    entity_ids = sorted(entities["entity_id"].unique())
    shuffled = rng.permutation(entity_ids)
    n_train = int(round(len(shuffled) * train_fraction))
    assignment = {e: ("train" if i < n_train else "test") for i, e in enumerate(shuffled)}
    out = entities.copy()
    out["split"] = out["entity_id"].map(assignment)
    logger.info("Entity split (seed=%d): %d train / %d test entities", seed,
                sum(1 for v in assignment.values() if v == "train"),
                sum(1 for v in assignment.values() if v == "test"))
    return out

def verify_no_leakage(ds: NormalizedDataset, split_df: pd.DataFrame) -> dict:
    """Programmatic post-split leakage check (METHODOLOGY.md §1 step 3). Writes
    artifacts/split_verification.{json,log}; raises on leakage."""
    train_txs = set(split_df.loc[split_df["split"] == "train", "tx_id"])
    test_txs = set(split_df.loc[split_df["split"] == "test", "tx_id"])
    tx_overlap = train_txs & test_txs
    train_ents = set(split_df.loc[split_df["split"] == "train", "entity_id"])
    test_ents = set(split_df.loc[split_df["split"] == "test", "entity_id"])
    entity_overlap = train_ents & test_ents

    split_of = dict(zip(split_df["tx_id"], split_df["split"]))
    cross_edges = sum(1 for s, d in ds.edges.itertuples(index=False)
                      if split_of.get(str(s)) and split_of.get(str(d))
                      and split_of[str(s)] != split_of[str(d)])

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "hub_degree_threshold": HUB_DEGREE_THRESHOLD,
        "train_fraction": TRAIN_FRACTION,
        "split_seed": SPLIT_SEED,
        "n_entities": len(train_ents | test_ents),
        "n_train_txs": len(train_txs),
        "n_test_txs": len(test_txs),
        "tx_overlap_count": len(tx_overlap),
        "entity_overlap_count": len(entity_overlap),
        "cross_split_edge_count": cross_edges,
        "leakage_free": len(tx_overlap) == 0 and len(entity_overlap) == 0,
    }

    out_dir = artifacts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "split_verification.json").write_text(json.dumps(report, indent=2))
    with open(out_dir / "split_verification.log", "a", encoding="utf-8") as f:
        f.write(f"{report['generated_at']} leakage_free={report['leakage_free']} "
                f"tx_overlap={report['tx_overlap_count']} "
                f"entity_overlap={report['entity_overlap_count']} "
                f"cross_split_edges={report['cross_split_edge_count']}\n")
    logger.info("No-leakage verification: %s", "PASS" if report["leakage_free"] else "FAIL")
    if not report["leakage_free"]:
        raise RuntimeError(f"Entity leakage detected: tx_overlap={len(tx_overlap)}, "
                           f"entity_overlap={len(entity_overlap)}")
    return report


