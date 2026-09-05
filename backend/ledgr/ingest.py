"""Module 1 — Data Ingestion (BACKEND_BUILD_PLAN.md Phase R1, rebuilt as R3 prerequisite).

Loads the Elliptic (and optionally Elliptic++) Kaggle CSVs into a normalized
format common to downstream modules, so nothing below this layer needs to know
where a record came from. No live blockchain ingestion happens here — static
dataset only (DATA.md).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .config import LABEL_UNKNOWN, RAW_LABEL_MAP

logger = logging.getLogger(__name__)

# Expected feature count per Elliptic spec: 1 tx id + 166 features
N_ELLIPTIC_FEATURES = 166
# Elliptic transaction count / edge count — used for integrity verification
EXPECTED_TX_COUNT = 203_769
EXPECTED_EDGE_COUNT = 234_355


@dataclass
class NormalizedDataset:
    """Normalized transaction-graph dataset common to static (and future live) sources."""

    tx_ids: np.ndarray                      # shape (N,), str
    tx_labels: np.ndarray                   # shape (N,), int: 1 illicit / 0 licit / -1 unknown
    tx_time_steps: np.ndarray               # shape (N,), int (Elliptic time step, 1..49)
    tx_features: np.ndarray                 # shape (N, 166), float32
    edges: pd.DataFrame                     # columns: src (str), dst (str) — tx id pairs
    address_map: pd.DataFrame | None = None  # columns: address, tx_id, actor_id (Elliptic++ optional)
    source_stats: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        n = len(self.tx_ids)
        assert self.tx_labels.shape == (n,)
        assert self.tx_time_steps.shape == (n,)
        assert self.tx_features.shape[0] == n
        self.source_stats["tx_count"] = n
        self.source_stats["edge_count"] = len(self.edges)
        self.source_stats["n_features"] = self.tx_features.shape[1]

    @property
    def labeled_mask(self) -> np.ndarray:
        return self.tx_labels != LABEL_UNKNOWN

def _find_file(directory: Path, *keywords: str) -> Path:
    """Locate a dataset file by keyword match on the filename (Kaggle zip layouts vary)."""
    if not directory.is_dir():
        raise FileNotFoundError(f"Data directory does not exist: {directory}")
    candidates = [
        p for p in sorted(directory.rglob("*.csv"))
        if all(k.lower() in p.name.lower() for k in keywords) and "actors dataset" not in str(p).lower()
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No CSV matching keywords {keywords} found under {directory}. "
            "Download the Elliptic dataset from Kaggle and place the CSVs in data/raw/."
        )
    return candidates[0]


def load_elliptic(data_dir: Path) -> NormalizedDataset:
    """Load base Elliptic CSVs into the normalized format."""
    features_path = _find_file(data_dir, "features")
    edges_path = _find_file(data_dir, "edgelist")
    classes_path = _find_file(data_dir, "classes")

    logger.info("Loading features: %s", features_path)
    feats = pd.read_csv(features_path, header=None, dtype={0: str})
    if feats.shape[1] != N_ELLIPTIC_FEATURES + 1:
        raise ValueError(
            f"{features_path}: expected {N_ELLIPTIC_FEATURES + 1} columns "
            f"(txId + 166 features), got {feats.shape[1]}"
        )

    logger.info("Loading classes: %s", classes_path)
    classes = pd.read_csv(classes_path, dtype=str)
    classes.columns = ["tx_id", "class"]
    label_series = classes["class"].str.strip().str.lower().map(RAW_LABEL_MAP)
    if label_series.isna().any():
        bad = sorted(classes.loc[label_series.isna(), "class"].unique())
        raise ValueError(f"Unrecognized class labels in {classes_path}: {bad}")

    logger.info("Loading edgelist: %s", edges_path)
    edges_raw = pd.read_csv(edges_path, dtype=str)
    edges_raw.columns = ["src", "dst"]

    # Align feature rows to class rows by tx id (Kaggle files may differ in order)
    ids = feats[0].astype(str).to_numpy()
    tx_ids = classes["tx_id"].astype(str).to_numpy()
    if set(ids) != set(tx_ids):
        raise ValueError("Feature and class files contain different tx id sets — dataset integrity failure")
    order = {tx: i for i, tx in enumerate(ids)}
    row_idx = np.array([order[t] for t in tx_ids])

    tx_features = feats.iloc[row_idx, 1:].to_numpy(dtype=np.float32)
    tx_time_steps = tx_features[:, 0].astype(np.int64)  # feature 1 is the time step (Elliptic spec)

    ds = NormalizedDataset(
        tx_ids=tx_ids,
        tx_labels=label_series.to_numpy(dtype=np.int64),
        tx_time_steps=tx_time_steps,
        tx_features=tx_features,
        edges=edges_raw,
    )
    _verify_integrity(ds, expected_tx=EXPECTED_TX_COUNT, expected_edges=EXPECTED_EDGE_COUNT)
    return ds


def load_address_map(data_dir: Path) -> pd.DataFrame | None:
    """Load Elliptic++ actor/address data if present (optional; DATA.md fallback allows absence)."""
    candidates = [
        p for p in sorted(data_dir.rglob("*.csv"))
        if ("addr" in p.name.lower() or "actor" in p.name.lower())
    ]
    if not candidates:
        logger.warning("No Elliptic++ actor/address files under %s — base-Elliptic-only fallback.", data_dir)
        return None
    df = pd.read_csv(candidates[0], dtype=str)
    logger.info("Loaded Elliptic++ address data: %s (%d rows)", candidates[0], len(df))
    return df


def _verify_integrity(ds: NormalizedDataset, expected_tx: int, expected_edges: int) -> None:
    """Verify dataset integrity against published stats; log PASS/FAIL (never silently skip)."""
    stats = ds.source_stats
    stats["integrity"] = {}
    for name, actual, expected in (
        ("tx_count", stats["tx_count"], expected_tx),
        ("edge_count", stats["edge_count"], expected_edges),
    ):
        ok = actual == expected
        stats["integrity"][name] = {"actual": actual, "expected": expected, "ok": ok}
        (logger.info if ok else logger.warning)(
            "Integrity %s: %d (expected %d) -> %s", name, actual, expected, "PASS" if ok else "FAIL"
        )

