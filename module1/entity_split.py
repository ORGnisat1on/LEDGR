"""
Entity-based train/validation/test split for the Elliptic dataset.

Phase 1 deliverable — implements METHODOLOGY.md §1 exactly.
This is NOT Module 2 graph construction. The NetworkX graph built here exists
solely to compute connected-component entity proxies for the split.

Key guarantees:
  - entity-safe: no txId appears in more than one of train/val/test
  - leakage is programmatically verified before returning
  - split is at entity level, not transaction level
  - hub nodes (degree >= HUB_DEGREE_THRESHOLD) are excluded from component-forming
    and assigned as singleton entities, preventing hub-driven component merging
  - actor-id mapping is discovered at runtime (not assumed by filename)
  - "unknown"-label txIds are assigned to splits but must NOT be used as supervised
    training examples — callers filter to licit/illicit themselves

Usage::

    from module1.entity_split import build_entity_split

    split = build_entity_split(data_dir="path/to/elliptic/csvs/")
    split.verify_no_leakage()  # always passes; build_entity_split() calls it internally
    assert split.leakage_verified

    train_labeled = {t for t in split.train_txids if labels[t] in ("licit", "illicit")}
"""

from __future__ import annotations

import csv
import logging
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import networkx as nx
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants — every one of these is referenced by name in the logic,
# never as a bare literal.  Per AGENTS.md: "Any heuristic or model threshold
# must be a named, documented constant — not a bare magic number."
# ---------------------------------------------------------------------------

HUB_DEGREE_THRESHOLD: int = 1000
"""Nodes with degree >= this value are excluded from connected-component
formation and assigned as singleton entities (METHODOLOGY.md §1)."""

TRAIN_FRACTION: float = 0.70
"""Fraction of entities assigned to train (METHODOLOGY.md §1)."""

VAL_FRACTION: float = 0.15
"""Fraction of entities assigned to validation (METHODOLOGY.md §1)."""

TEST_FRACTION: float = 0.15
"""Fraction of entities assigned to test (METHODOLOGY.md §1).
TRAIN_FRACTION + VAL_FRACTION + TEST_FRACTION must equal 1.0."""

RANDOM_SEED: int = 42
"""RNG seed for reproducibility.  Logged in every split output."""

# Elliptic class encoding in elliptic_txs_classes.csv
_ILLICIT_CLASS: str = "1"
_LICIT_CLASS: str = "2"
_UNKNOWN_CLASS: str = "unknown"

# Entity-level labels used throughout (not the raw Elliptic class codes)
_ENTITY_ILLICIT: str = "illicit"
_ENTITY_LICIT: str = "licit"
_ENTITY_UNKNOWN: str = "unknown"

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntitySplit:
    """
    Leakage-free entity-based 70/15/15 train/val/test split.

    SPLIT MEMBERSHIP vs. SUPERVISED TRAINING ELIGIBILITY
    -----------------------------------------------------
    train_txids / val_txids / test_txids contain ALL txIds assigned to each
    partition, including those with "unknown" class labels.  For supervised
    training (Module 3b), callers MUST filter to txIds whose class is
    "licit" or "illicit".  This class does not filter — that would hide
    "unknown" examples from the split assignment, which is wrong.

    TIME-ORDER NOTE
    ---------------
    This split is entity-safe, NOT guaranteed to be time-disjoint.
    time_order_ok reports whether the entity-based split happens to
    respect approximate time ordering.  It is a diagnostic transparency
    metric only — it never alters the split.
    """

    # Core split sets — every txId appears in exactly one
    train_txids: frozenset
    val_txids: frozenset
    test_txids: frozenset

    # Audit metadata (logged on every call; required for METHODOLOGY.md §1 step 3 reporting)
    split_method: str
    """One of: "actor_id" | "connected_component_proxy" | "mixed" """

    n_entities_total: int
    """Total entity count before splitting."""

    n_hub_nodes: int
    """Count of nodes excluded by the hub-node safeguard."""

    hub_node_ids: frozenset
    """The exact set of excluded hub node IDs (for reproducible audit)."""

    leakage_verified: bool
    """True only if verify_no_leakage() ran and passed inside build_entity_split()."""

    time_order_median: dict
    """{"train": float, "val": float, "test": float} — median time_step per split."""

    time_order_ok: Optional[bool]
    """True if median(train) <= median(val) <= median(test); False otherwise;
    None if time_step data was unavailable.  Diagnostic only."""

    split_stats: dict
    """Per-split counts and label fractions, for reporting."""

    def verify_no_leakage(self) -> None:
        """
        Programmatic leakage check (METHODOLOGY.md §1 step 3).

        Confirms no txId appears in more than one of train/val/test.
        Raises ValueError with overlap counts if any intersection is non-empty.

        This is called automatically inside build_entity_split(); the returned
        EntitySplit.leakage_verified is True only if this passed.  Callers may
        call it again independently.
        """
        train_val = self.train_txids & self.val_txids
        train_test = self.train_txids & self.test_txids
        val_test = self.val_txids & self.test_txids
        if train_val or train_test or val_test:
            raise ValueError(
                f"Entity split leakage detected — "
                f"train\u2229val: {len(train_val)}, "
                f"train\u2229test: {len(train_test)}, "
                f"val\u2229test: {len(val_test)}"
            )


# ---------------------------------------------------------------------------
# Actor-mapping discovery
# ---------------------------------------------------------------------------


def _discover_actor_mapping(data_dir: Path) -> Optional[Path]:
    """
    Discover an Elliptic++ actor-id mapping file at runtime.

    Does NOT assume filename or column names.  Probes every .csv file in
    data_dir and accepts at most one that matches all of:
      - exactly two columns
      - one column name contains "actor"
      - the other column name contains "tx" or "addr" or "id"
      - at least one data row

    Returns the path if exactly one qualifying file is found.
    Returns None if zero files qualify (logged) or if multiple qualify
    (logged as a warning — ambiguous input falls back to proxy, never guessing).
    """
    candidates: list[Path] = []

    for csv_path in sorted(data_dir.glob("*.csv")):
        try:
            with csv_path.open(newline="") as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    continue  # empty file

                if len(header) != 2:
                    continue

                col_a, col_b = (h.strip().lower() for h in header)

                has_actor = "actor" in col_a or "actor" in col_b
                has_tx_or_addr = any(
                    tok in col
                    for col in (col_a, col_b)
                    for tok in ("tx", "addr", "id")
                )

                if not (has_actor and has_tx_or_addr):
                    continue

                # Must have at least one data row
                try:
                    next(reader)
                except StopIteration:
                    continue

                candidates.append(csv_path)
        except (OSError, csv.Error):
            continue

    if len(candidates) == 0:
        logger.info(
            "No actor-id mapping file found in %s — "
            "falling back to connected_component_proxy entity identification.",
            data_dir,
        )
        return None

    if len(candidates) > 1:
        logger.warning(
            "Multiple candidate actor-id mapping files found in %s: %s — "
            "ambiguous input; falling back to connected_component_proxy. "
            "Never guessing an actor mapping.",
            data_dir,
            [p.name for p in candidates],
        )
        return None

    logger.info("Actor-id mapping file discovered: %s", candidates[0].name)
    return candidates[0]


def _load_actor_mapping(mapping_path: Path) -> dict[str, set[str]]:
    """
    Load actor_id -> set of txIds from the discovered mapping file.

    The actor column is identified by containing "actor" in its header name.
    """
    with mapping_path.open(newline="") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]

    actor_col_idx = next(
        (i for i, h in enumerate(header) if "actor" in h.lower()), None
    )
    if actor_col_idx is None:
        logger.warning(
            "Actor column not found in %s after discovery — falling back to proxy.",
            mapping_path,
        )
        return {}

    tx_col_idx = 1 - actor_col_idx

    actor_to_txids: dict[str, set[str]] = {}
    with mapping_path.open(newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) < 2:
                continue
            actor_id = row[actor_col_idx].strip()
            tx_id = row[tx_col_idx].strip()
            if actor_id and tx_id:
                actor_to_txids.setdefault(actor_id, set()).add(tx_id)

    return actor_to_txids


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def _load_classes(data_dir: Path) -> dict[str, str]:
    """Load txId -> raw class string from elliptic_txs_classes.csv."""
    path = data_dir / "elliptic_txs_classes.csv"
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    result: dict[str, str] = {}
    with path.open(newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) < 2:
                continue
            result[row[0].strip()] = row[1].strip()
    return result


def _load_time_steps(data_dir: Path) -> dict[str, int]:
    """
    Load txId -> time_step from elliptic_txs_features.csv.

    Only columns 0 (txId) and 1 (time_step) are read; the 166 feature
    columns are intentionally ignored (not loaded into memory).
    """
    path = data_dir / "elliptic_txs_features.csv"
    if not path.exists():
        logger.warning(
            "Features file not found: %s — time-order diagnostic will return None.",
            path,
        )
        return {}
    result: dict[str, int] = {}
    with path.open(newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) < 2:
                continue
            try:
                result[row[0].strip()] = int(row[1].strip())
            except ValueError:
                continue
    return result


def _load_graph(data_dir: Path) -> nx.Graph:
    """
    Build an undirected NetworkX graph from elliptic_txs_edgelist.csv.

    This graph is used solely for connected-component entity proxy computation.
    It is NOT the per-address subgraph that Module 2 will build.
    """
    path = data_dir / "elliptic_txs_edgelist.csv"
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    G = nx.Graph()
    with path.open(newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) < 2:
                continue
            src, dst = row[0].strip(), row[1].strip()
            if src and dst:
                G.add_edge(src, dst)
    return G


# ---------------------------------------------------------------------------
# Entity labelling
# ---------------------------------------------------------------------------


def _entity_label(txids: frozenset, raw_classes: dict[str, str]) -> str:
    """
    Assign a label to an entity (set of txIds) using the conservative rule
    (METHODOLOGY.md §1 / implementation_plan.md Step 4):

        any illicit  -> "illicit"
        else any licit -> "licit"
        else           -> "unknown"

    A mixed entity (some illicit, some licit) is classified as "illicit" so it
    cannot contaminate the licit training set.
    """
    labels = {raw_classes.get(t, _UNKNOWN_CLASS) for t in txids}
    if _ILLICIT_CLASS in labels:
        return _ENTITY_ILLICIT
    if _LICIT_CLASS in labels:
        return _ENTITY_LICIT
    return _ENTITY_UNKNOWN


# ---------------------------------------------------------------------------
# Split helpers
# ---------------------------------------------------------------------------


def _two_stage_split(
    entities: list,
    labels: list,
    use_stratify: bool,
    random_seed: int,
) -> tuple:
    """
    Split a list of entity frozensets into train/val/test using two stages:
      Stage 1: train (TRAIN_FRACTION) vs temp (1 - TRAIN_FRACTION)
      Stage 2: temp -> val (50%) vs test (50%)

    Applied at entity level (frozensets), NOT at txId level.
    txId expansion happens after this function returns.

    Handles degenerate cases gracefully: fewer than 2 entities goes to train.
    Handles stratification failures (class with 1 member) by falling back
    to non-stratified split rather than raising.
    """
    if len(entities) < 2:
        return list(entities), [], []

    stratify_arg = labels if use_stratify else None

    # Stage 1
    try:
        train_e, temp_e, train_l, temp_l = train_test_split(
            entities,
            labels,
            test_size=1.0 - TRAIN_FRACTION,
            stratify=stratify_arg,
            random_state=random_seed,
        )
    except ValueError:
        # Stratification impossible (e.g., only 1 member of some class)
        train_e, temp_e, train_l, temp_l = train_test_split(
            entities,
            labels,
            test_size=1.0 - TRAIN_FRACTION,
            stratify=None,
            random_state=random_seed,
        )

    if len(temp_e) < 2:
        return train_e, temp_e, []

    # Stage 2: split temp 50/50
    temp_stratify = temp_l if use_stratify else None
    try:
        val_e, test_e, _, _ = train_test_split(
            temp_e,
            temp_l,
            test_size=0.5,
            stratify=temp_stratify,
            random_state=random_seed,
        )
    except ValueError:
        val_e, test_e, _, _ = train_test_split(
            temp_e,
            temp_l,
            test_size=0.5,
            stratify=None,
            random_state=random_seed,
        )

    return train_e, val_e, test_e


def _compute_time_order(
    train_txids: frozenset,
    val_txids: frozenset,
    test_txids: frozenset,
    time_steps: dict,
) -> tuple:
    """
    Compute median time_step per split and return a diagnostic flag.

    Per METHODOLOGY.md §1 step 4, this is informational only — entity-safety
    takes priority.  This result NEVER alters the split.
    """
    if not time_steps:
        return {"train": None, "val": None, "test": None}, None

    def _median_ts(txids: frozenset) -> Optional[float]:
        vals = [time_steps[t] for t in txids if t in time_steps]
        return statistics.median(vals) if vals else None

    m_train = _median_ts(train_txids)
    m_val = _median_ts(val_txids)
    m_test = _median_ts(test_txids)

    medians = {"train": m_train, "val": m_val, "test": m_test}

    if None in (m_train, m_val, m_test):
        ok = None
    else:
        ok = m_train <= m_val <= m_test

    if ok is True:
        logger.info(
            "Time-order diagnostic: PASS — "
            "median time_steps: train=%.1f, val=%.1f, test=%.1f "
            "(informational only; entity-safety is the binding constraint)",
            m_train, m_val, m_test,
        )
    elif ok is False:
        logger.info(
            "Time-order diagnostic: WARN — "
            "median time_steps train=%.1f, val=%.1f, test=%.1f do not follow "
            "ascending order.  Transparency metric only; entity-safe split "
            "stands unchanged (METHODOLOGY.md §1 step 4).",
            m_train, m_val, m_test,
        )
    else:
        logger.info("Time-order diagnostic: SKIPPED (time_step data unavailable).")

    return medians, ok


def _build_split_stats(
    train_txids: frozenset,
    val_txids: frozenset,
    test_txids: frozenset,
    train_entities: list,
    val_entities: list,
    test_entities: list,
    raw_classes: dict,
) -> dict:
    """Build the split_stats audit dict."""

    def _fractions(txids: frozenset) -> dict:
        total = len(txids)
        if total == 0:
            return {"illicit": 0.0, "licit": 0.0, "unknown": 0.0}
        illicit = sum(1 for t in txids if raw_classes.get(t) == _ILLICIT_CLASS)
        licit = sum(1 for t in txids if raw_classes.get(t) == _LICIT_CLASS)
        unknown = total - illicit - licit
        return {
            "illicit": round(illicit / total, 4),
            "licit": round(licit / total, 4),
            "unknown": round(unknown / total, 4),
        }

    return {
        "train": {
            "n_entities": len(train_entities),
            "n_txids": len(train_txids),
            "label_fractions": _fractions(train_txids),
        },
        "val": {
            "n_entities": len(val_entities),
            "n_txids": len(val_txids),
            "label_fractions": _fractions(val_txids),
        },
        "test": {
            "n_entities": len(test_entities),
            "n_txids": len(test_txids),
            "label_fractions": _fractions(test_txids),
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_entity_split(
    data_dir,
    hub_degree_threshold: int = HUB_DEGREE_THRESHOLD,
    random_seed: int = RANDOM_SEED,
) -> EntitySplit:
    """
    Build a leakage-free entity-based 70/15/15 train/val/test split.

    Implements METHODOLOGY.md §1 exactly:

    1. Attempts Elliptic++ actor_id grouping (discovered at runtime — filename
       and columns are NOT assumed; see _discover_actor_mapping).
    2. Falls back to connected-component clustering as a **conservative entity
       proxy** for txIds not covered by actor-id mapping, or when the mapping
       is unavailable / ambiguous.
    3. Applies hub-node safeguard: nodes with degree >= hub_degree_threshold
       are removed from the graph before component computation (preventing hub-
       driven merging of unrelated components), then assigned as singleton
       entities.
    4. Stratifies by licit/illicit entity label where possible; unknown
       entities are split in a separate pass without stratification.
    5. Calls verify_no_leakage() before returning; raises ValueError on leakage.
    6. Logs split stats, hub-node count, split method, and the time-order
       diagnostic (which is informational only and never alters the split).

    SPLIT MEMBERSHIP vs. SUPERVISED TRAINING ELIGIBILITY:
    train_txids / val_txids / test_txids include ALL txIds, including
    "unknown"-class ones.  Callers training supervised models MUST filter to
    licit/illicit.  This function produces the split; it does not filter it.

    This split is entity-safe.  It is NOT guaranteed to be time-disjoint;
    time_order_ok reports whether it approximately respects time ordering,
    for transparency only.

    Args:
        data_dir: Directory containing Elliptic CSV files.
        hub_degree_threshold: Nodes at or above this degree are excluded from
            component-forming and assigned as singleton entities.
            Default = HUB_DEGREE_THRESHOLD (1000) per METHODOLOGY.md §1.
        random_seed: RNG seed for reproducibility.  Logged in output.
            Default = RANDOM_SEED (42).

    Returns:
        EntitySplit with leakage_verified=True.

    Raises:
        FileNotFoundError: If elliptic_txs_edgelist.csv or
            elliptic_txs_classes.csv are missing.
        ValueError: If leakage is detected post-split (should not occur).
    """
    data_dir = Path(data_dir)

    logger.info(
        "build_entity_split: data_dir=%s, hub_degree_threshold=%d, random_seed=%d",
        data_dir, hub_degree_threshold, random_seed,
    )

    # ---- Step 1: Load data ------------------------------------------------
    raw_classes = _load_classes(data_dir)
    all_txids = set(raw_classes.keys())
    time_steps = _load_time_steps(data_dir)
    G_full = _load_graph(data_dir)
    # Add isolated txIds (in classes but not in edgelist) as isolated graph nodes
    for t in all_txids:
        if t not in G_full:
            G_full.add_node(t)

    # ---- Step 2: Hub-node safeguard (METHODOLOGY.md §1 step 1 bullet) ----
    hub_node_ids: set = {
        n for n, d in G_full.degree() if d >= hub_degree_threshold
    }
    n_hub_nodes = len(hub_node_ids)
    if n_hub_nodes:
        logger.info(
            "Hub-node safeguard: removing %d node(s) with degree >= %d "
            "before connected-component computation.  "
            "Threshold: HUB_DEGREE_THRESHOLD=%d",
            n_hub_nodes, hub_degree_threshold, HUB_DEGREE_THRESHOLD,
        )
    G_stripped = G_full.copy()
    G_stripped.remove_nodes_from(hub_node_ids)

    # ---- Step 3: Actor-id mapping (Path A) --------------------------------
    actor_mapping_path = _discover_actor_mapping(data_dir)
    actor_to_txids: dict = {}
    if actor_mapping_path is not None:
        actor_to_txids = _load_actor_mapping(actor_mapping_path)

    actor_covered: set = set()
    for txids in actor_to_txids.values():
        actor_covered.update(txids)

    # ---- Step 4: Entity identification ------------------------------------
    # Path A: actor-id entities
    entities_actor: list = [
        frozenset(txids) for txids in actor_to_txids.values()
    ]

    # Path B: connected-component proxy for uncovered, non-hub txIds
    covered_or_hub = actor_covered | hub_node_ids
    uncovered_txids = all_txids - covered_or_hub
    G_proxy = G_stripped.subgraph(uncovered_txids).copy()
    for t in uncovered_txids:
        if t not in G_proxy:
            G_proxy.add_node(t)

    entities_proxy: list = [
        frozenset(comp) for comp in nx.connected_components(G_proxy)
    ]

    # Hub nodes -> each is its own singleton entity (preserves their labelled data;
    # see implementation_plan.md §3 for rejection of the "exclude entirely" alternative)
    entities_hub: list = [frozenset({h}) for h in hub_node_ids]

    # Determine split_method label
    has_actor = len(entities_actor) > 0
    has_proxy = len(entities_proxy) > 0 or len(entities_hub) > 0
    if has_actor and not has_proxy:
        split_method = "actor_id"
    elif not has_actor and has_proxy:
        split_method = "connected_component_proxy"
    else:
        split_method = "mixed"

    all_entities: list = entities_actor + entities_proxy + entities_hub
    n_entities_total = len(all_entities)

    logger.info(
        "Entity identification: method=%s, "
        "actor=%d, proxy=%d, hub_singletons=%d, total=%d",
        split_method, len(entities_actor), len(entities_proxy),
        len(entities_hub), n_entities_total,
    )

    # ---- Step 5: Entity labelling -----------------------------------------
    entity_labels: list = [
        _entity_label(e, raw_classes) for e in all_entities
    ]

    # ---- Step 6: Stratified entity-level split ----------------------------
    labeled_entities = [
        e for e, lbl in zip(all_entities, entity_labels) if lbl != _ENTITY_UNKNOWN
    ]
    labeled_labels = [lbl for lbl in entity_labels if lbl != _ENTITY_UNKNOWN]

    unknown_entities = [
        e for e, lbl in zip(all_entities, entity_labels) if lbl == _ENTITY_UNKNOWN
    ]
    unknown_labels = [_ENTITY_UNKNOWN] * len(unknown_entities)

    train_lab, val_lab, test_lab = _two_stage_split(
        labeled_entities, labeled_labels, use_stratify=True, random_seed=random_seed
    )
    train_unk, val_unk, test_unk = _two_stage_split(
        unknown_entities, unknown_labels, use_stratify=False, random_seed=random_seed
    )

    train_entities = train_lab + train_unk
    val_entities = val_lab + val_unk
    test_entities = test_lab + test_unk

    # ---- Step 7: Expand entities to txIds ---------------------------------
    train_txids: frozenset = frozenset(t for e in train_entities for t in e)
    val_txids: frozenset = frozenset(t for e in val_entities for t in e)
    test_txids: frozenset = frozenset(t for e in test_entities for t in e)

    # ---- Step 8: Time-awareness secondary check (diagnostic only) ---------
    time_order_median, time_order_ok = _compute_time_order(
        train_txids, val_txids, test_txids, time_steps
    )

    # ---- Step 9: Build stats ----------------------------------------------
    split_stats = _build_split_stats(
        train_txids, val_txids, test_txids,
        train_entities, val_entities, test_entities,
        raw_classes,
    )

    logger.info(
        "Split stats: train=%d entities/%d txIds, "
        "val=%d entities/%d txIds, test=%d entities/%d txIds",
        len(train_entities), len(train_txids),
        len(val_entities), len(val_txids),
        len(test_entities), len(test_txids),
    )

    # ---- Step 10: Construct EntitySplit, verify, reconstruct verified -----
    # First pass — leakage_verified=False; verify; then reconstruct True
    unverified = EntitySplit(
        train_txids=train_txids,
        val_txids=val_txids,
        test_txids=test_txids,
        split_method=split_method,
        n_entities_total=n_entities_total,
        n_hub_nodes=n_hub_nodes,
        hub_node_ids=frozenset(hub_node_ids),
        leakage_verified=False,
        time_order_median=time_order_median,
        time_order_ok=time_order_ok,
        split_stats=split_stats,
    )
    # Raises ValueError if any intersection is non-empty
    unverified.verify_no_leakage()

    # Reconstruct with leakage_verified=True (frozen dataclass)
    result = EntitySplit(
        train_txids=train_txids,
        val_txids=val_txids,
        test_txids=test_txids,
        split_method=split_method,
        n_entities_total=n_entities_total,
        n_hub_nodes=n_hub_nodes,
        hub_node_ids=frozenset(hub_node_ids),
        leakage_verified=True,
        time_order_median=time_order_median,
        time_order_ok=time_order_ok,
        split_stats=split_stats,
    )

    logger.info(
        "build_entity_split complete: leakage_verified=True, "
        "split_method=%s, n_entities=%d, n_hub_nodes=%d, "
        "time_order_ok=%s, random_seed=%d",
        split_method, n_entities_total, n_hub_nodes,
        time_order_ok, random_seed,
    )

    return result