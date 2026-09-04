# Entity-Based Train/Validation/Test Split — Revised Implementation Plan

**Phase 1 deliverable.** Implements `METHODOLOGY.md §1` exactly. Not Module 2 graph construction.

---

## Files Created / Modified

```
module1/
  entity_split.py                  [NEW] main implementation
  test_entity_split.py             [NEW] test suite
  requirements.txt                 [MODIFY] add networkx>=3.2.0, scikit-learn>=1.4.0
  data_ingestion/
    test_fixtures/                 ← untouched; Module 1 tests rely on exact row counts
  entity_split_fixtures/           [NEW] separate fixtures for entity split tests only
    elliptic_txs_classes.csv       ~30 txIds; licit/illicit/unknown rows
    elliptic_txs_edgelist.csv      edges forming distinct components + one hub node
    elliptic_txs_features.csv      time_step column for all txIds
    actor_mapping_fixture.csv      minimal actor_id→txId fixture (known schema, hand-built)
```

**The existing `module1/data_ingestion/test_fixtures/` directory is not touched.**  
The existing 72 Module 1 tests are not touched.

---

## Named Constants

```python
HUB_DEGREE_THRESHOLD: int   = 1000   # METHODOLOGY.md §1: "degree threshold = 1000"
TRAIN_FRACTION:       float = 0.70   # METHODOLOGY.md §1: "70% train"
VAL_FRACTION:         float = 0.15   # METHODOLOGY.md §1: "15% validation"
TEST_FRACTION:        float = 0.15   # METHODOLOGY.md §1: "15% test"
RANDOM_SEED:          int   = 42     # fixed for reproducibility; logged in every split output
```

All referenced by name everywhere — no bare literals in logic.

---

## Output Type

```python
@dataclass(frozen=True)
class EntitySplit:
    # Core split sets — every txId in the dataset appears in exactly one
    train_txids: frozenset[str]
    val_txids:   frozenset[str]
    test_txids:  frozenset[str]

    # Audit metadata (logged on every call; required for METHODOLOGY.md §1 step 3 reporting)
    split_method:       str            # "actor_id" | "connected_component_proxy" | "mixed"
    n_entities_total:   int
    n_hub_nodes:        int            # count of nodes excluded by hub-node safeguard
    hub_node_ids:       frozenset[str] # the excluded node IDs for reproducible audit
    leakage_verified:   bool           # True only if verify_no_leakage() ran and passed
    time_order_median:  dict           # {"train": float, "val": float, "test": float}
    time_order_ok:      bool | None    # diagnostic flag; None if time_step unavailable
    split_stats:        dict           # per-split entity and txId counts + label fractions

    # Supervised-training eligibility is NOT the same as split membership.
    # train_txids contains licit + illicit + unknown. For supervised training,
    # callers must filter to licit/illicit. This set is the full split membership.
    # "unknown" entities are assigned to splits to prevent data leakage but are
    # not used as labelled examples during model training.

    def verify_no_leakage(self) -> None:
        """
        Per METHODOLOGY.md §1 step 3: confirm no txId appears in more than one set.
        Raises ValueError with overlap counts if any intersection is non-empty.
        Called automatically inside build_entity_split(); returned EntitySplit.leakage_verified
        is True only if this passed.
        """
```

> [!IMPORTANT]
> **Split membership ≠ supervised training eligibility.**  
> `train_txids` contains *all* txIds assigned to train, including `"unknown"` label ones. Downstream module (Module 3b) must filter to `class in {"licit", "illicit"}` before using as labelled training examples. This module produces the split; it does not filter it. The distinction is documented here and in code docstrings — it must not be collapsed.

---

## Algorithm — Step by Step

### Step 1: Discover and load raw data

Read these files from `data_dir`:

| File (base Elliptic) | Columns used | Required? |
|---|---|---|
| `elliptic_txs_edgelist.csv` | `txId1, txId2` | Yes — for connected-component fallback |
| `elliptic_txs_classes.csv` | `txId, class` (`1`=illicit, `2`=licit, `unknown`) | Yes — for labelling and stratification |
| `elliptic_txs_features.csv` | columns 0 (`txId`) and 1 (`time_step`) only | Yes — for time-awareness check |

For Elliptic++ actor mapping: **do not assume filename or columns.**

At runtime, probe `data_dir` for any CSV file whose header contains both an actor identifier column and a transaction/address column. The probing logic:
1. List all `.csv` files in `data_dir`.
2. For each, read the header row only.
3. Accept it as the actor mapping if **all** of the following hold:
   - It has exactly two columns.
   - One column name matches a known actor-id pattern (e.g. contains `actor`) and the other matches a known txId/address pattern (e.g. contains `tx` or `addr` or `id`).
   - It has at least one data row.
4. If zero files qualify → fallback to connected-component proxy (logged explicitly).
5. If multiple files qualify → log a warning, use none of them, fall back to proxy. Ambiguous actor-mapping input is treated as unavailable rather than silently guessing.

This inspection is done at import time of the split builder, not at test time. Tests that exercise the actor-id path provide a fixture at a known path explicitly passed in.

---

### Step 2: Entity identification

**Path A — Actor-id (if actor mapping discovered and unambiguous):**

- Build `actor_id → set[txId]` from the mapping file.
- Each distinct `actor_id` is one entity.
- txIds not appearing in the actor mapping are processed by Path B below.
- `split_method` = `"actor_id"` (all txIds covered) or `"mixed"` (some txIds via actor, rest via proxy).

**Path B — Connected-component proxy (fallback or for uncovered txIds):**

The connected-component result is a **conservative entity proxy**, not a claim that each component represents a real-world entity. A component groups txIds that are tightly connected in the transaction graph; in the absence of actor-level ground truth, treating a component as a single entity for split purposes is the safest way to prevent leakage — it errs toward over-grouping rather than risking splitting a real entity across train and test.

`split_method` = `"connected_component_proxy"` when all txIds are covered this way.

---

### Step 3: Hub-node safeguard

> `METHODOLOGY.md §1`: *"Before computing components, identify and exclude/cap known high-degree hub addresses (degree threshold = 1000) from the component-forming step so one hub doesn't merge thousands of unrelated entities into one blob."*

**Policy: hub nodes are removed from the graph before components are computed, then assigned as singleton entities.**

Precise procedure:
1. Build an undirected NetworkX graph from `elliptic_txs_edgelist.csv`.
2. Identify all nodes with `degree >= HUB_DEGREE_THRESHOLD`. Call this set `H`.
3. **Remove all nodes in `H` from the graph.** This severs all edges connecting through them.
   - This is what prevents hub nodes from merging otherwise-separate components — they are physically absent from the graph when `connected_components()` runs.
   - Crucially: removing a hub node also removes its edges, so no two components that were only connected through a hub will merge.
4. Run `networkx.connected_components()` on the hub-stripped graph. Each component is one proxy entity.
5. **Each hub node in `H` is assigned as its own singleton entity** (one entity per hub node), independently of the components above.
   - Rationale: hub nodes have real transaction data and real labels. Discarding them entirely would silently lose labelled training examples. Treating each as a singleton is the most data-preserving interpretation of "exclude from component-forming" that is consistent with METHODOLOGY.md's stated goal (preventing merging, not discarding data).
   - Alternative considered: exclude hub nodes entirely from the split. Rejected because METHODOLOGY.md says "exclude/cap from the component-forming step" — the step, not from the split. The step is component computation; the hub nodes are still in the dataset.
6. Log `n_hub_nodes = |H|` and `hub_node_ids = H` in `EntitySplit`.

> [!NOTE]
> The singleton policy means hub nodes compete for split slots individually, not as part of any large component. A hub node labelled illicit will be assigned to train/val/test independently of any other entity, which is correct — it does not drag unrelated entities into its split bucket.

---

### Step 4: Entity labelling

For each entity (a set of txIds from either path):

```
if any txId in entity has class "illicit"  → entity label = "illicit"
elif any txId in entity has class "licit"  → entity label = "licit"
else                                        → entity label = "unknown"
```

This is conservative: a mixed entity (some illicit, some licit) is classified as illicit. It will not contaminate the licit training set. No assumptions are made about why an entity is mixed — it is treated as potentially illicit in full.

---

### Step 5: Stratified entity-level split

1. Partition entities into three buckets: `illicit_entities`, `licit_entities`, `unknown_entities`.
2. For `illicit_entities` and `licit_entities` together (labelled entities): apply two-stage stratified split.
   - Stage 1: `train` (70%) vs `temp` (30%), `stratify` by entity label, `random_state=RANDOM_SEED`.
   - Stage 2: `temp` → `val` (50% of temp) vs `test` (50% of temp), `stratify` by entity label, `random_state=RANDOM_SEED`.
3. For `unknown_entities`: same two-stage split, no `stratify` argument, same seed.
4. Final entity sets: `train_entities = labeled_train ∪ unknown_train`, similarly for val and test.
5. Expand to txIds: for each entity in `train_entities`, add all its txIds to `train_txids`. Same for val and test. Result is three `frozenset[str]`.

> [!IMPORTANT]
> `sklearn.train_test_split` is applied to **entity IDs**, not to individual txIds. The txId expansion happens *after* the entity-level assignment is complete. Tests must verify that all txIds belonging to one entity land in the same split — this is the core correctness property.

---

### Step 6: Leakage verification

```python
def verify_no_leakage(self) -> None:
    train_val  = self.train_txids & self.val_txids
    train_test = self.train_txids & self.test_txids
    val_test   = self.val_txids   & self.test_txids
    if train_val or train_test or val_test:
        raise ValueError(
            f"Entity split leakage detected — "
            f"train∩val: {len(train_val)}, "
            f"train∩test: {len(train_test)}, "
            f"val∩test: {len(val_test)}"
        )
```

Called inside `build_entity_split()` before returning. `EntitySplit.leakage_verified` is set to `True` only on pass. A split with `leakage_verified=False` must never be used for model training — callers should check this field.

---

### Step 7: Time-awareness secondary check

Per `METHODOLOGY.md §1 step 4`: *"entity-safety takes priority."*

1. Load `time_step` for each txId from `elliptic_txs_features.csv`.
2. Compute `median(time_step)` for all txIds in each split.
3. Record `time_order_median = {"train": M_train, "val": M_val, "test": M_test}`.
4. Set `time_order_ok = True` if `M_train <= M_val <= M_test`, else `False`.
   - If time_step data is unavailable: `time_order_ok = None`.
5. Log the medians and the flag. **Do not alter the split in any way based on this result.**

This check reports whether the entity-based split *happens to* roughly respect time ordering. It is a transparency metric. Calling it "temporal disjointness" would overclaim — the splits are not guaranteed to be time-disjoint, and they are not required to be. The entity-safe property is what matters; the time check is informational.

---

## Public API

```python
def build_entity_split(
    data_dir: str | Path,
    hub_degree_threshold: int = HUB_DEGREE_THRESHOLD,
    random_seed: int = RANDOM_SEED,
) -> EntitySplit:
    """
    Build a leakage-free entity-based 70/15/15 train/val/test split from the Elliptic dataset.

    Implements METHODOLOGY.md §1 exactly:
    - Attempts Elliptic++ actor_id grouping (discovered at runtime, not assumed by filename).
    - Falls back to connected-component clustering as a conservative entity proxy for
      txIds not covered by actor-id mapping (or when actor mapping is unavailable/ambiguous).
    - Applies hub-node safeguard: nodes with degree >= hub_degree_threshold are removed
      from the graph before component computation, then assigned as singleton entities.
    - Stratifies by licit/illicit entity label where possible; unknown entities split separately.
    - Calls verify_no_leakage() before returning; raises ValueError if leakage found.
    - Logs split stats, hub-node count, split method, and time-order diagnostic.

    Split membership (train/val/test_txids) includes all txIds, including "unknown" class.
    Callers training supervised models MUST filter to licit/illicit — this function does not.

    This split is entity-safe. It is NOT guaranteed to be time-disjoint; the time_order_ok
    field reports whether it approximately respects time ordering, for transparency only.

    Args:
        data_dir: Directory containing Elliptic CSV files.
        hub_degree_threshold: Nodes at or above this degree are excluded from component-forming.
        random_seed: RNG seed. Logged in output for reproducibility.

    Returns:
        EntitySplit with leakage_verified=True.

    Raises:
        FileNotFoundError: If required base Elliptic files are missing.
        ValueError: If leakage is detected post-split (should not occur under normal operation).
    """
```

---

## Test Plan (`test_entity_split.py`)

All tests use `entity_split_fixtures/` only. The existing `data_ingestion/test_fixtures/` is not referenced.

### Fixture design (`entity_split_fixtures/`)

The fixture must have enough **entities** (not just txIds) for the 70/15/15 split fractions to be meaningful. A fixture of ~55 txIds organized into ~30 entities achieves this — some entities contain a single txId, others contain 2–4 txIds, so that entity-level grouping (the core correctness property) is actually exercised.

- `elliptic_txs_classes.csv`: ~55 txIds; mix of illicit/licit/unknown labels, with at least one multi-txId entity containing both illicit and licit txIds (for the mixed-entity label test).
- `elliptic_txs_edgelist.csv`: edges forming exactly **28 connected components** from the non-hub txIds (2–4 txIds each for the larger components, singletons for the smaller ones), plus **one hub node** with edges to nodes in at least two otherwise-disconnected components. The hub node brings the total entity count to ~30 (28 components + 1 hub singleton + actor-covered entities where applicable). This structure is what makes test #9 work: the two components the hub connects must be separately nameable (e.g. component A = txIds starting with `aa...`, component B = txIds starting with `bb...`).
- `elliptic_txs_features.csv`: time_step values for all ~55 txIds; first ~60% of txIds get lower time_steps and last ~20% get higher time_steps, so that `time_order_ok=True` is the expected outcome for a chronologically-arranged split.
- `actor_mapping_fixture.csv`: 2 columns with names matching the discovery heuristic (one containing `actor`, one containing `tx`), covering 3 actor IDs → 9 txIds total — a subset of the ~55 txIds. Used only in actor-id path tests; the main fixture tests use the directory without this file.

### Test cases

| # | Test | What it verifies |
|---|---|---|
| 1 | `test_output_is_entity_split_dataclass` | Return type, all fields present and typed correctly |
| 2 | `test_split_fractions_approximate` | train/val/test fractions ≈ 70/15/15 (±5%) on the 30-entity fixture |
| 3 | `test_all_txids_accounted_for` | `len(train) + len(val) + len(test) == total txIds` — no txId lost or duplicated |
| 4 | `test_no_leakage_verify_passes` | `verify_no_leakage()` completes without exception on a valid split |
| 5 | `test_verify_no_leakage_raises_on_injected_overlap` | Construct `EntitySplit` with manufactured overlap; confirm `ValueError` raised |
| 6 | `test_leakage_verified_true` | `EntitySplit.leakage_verified == True` on all valid outputs |
| 7 | `test_entity_level_split_not_transaction_level` | All txIds belonging to the same connected component appear in one split only — never split across two sets |
| 8 | `test_actor_id_entities_never_cross_splits` | **With actor mapping fixture**: all txIds sharing the same `actor_id` appear in exactly one of train/val/test; none of an actor's txIds appear in more than one set |
| 9 | `test_hub_node_does_not_merge_components` | **Core hub-node test**: the fixture contains a hub node whose edges connect to nodes in two otherwise-disconnected components (A and B). With the safeguard applied, A and B remain separate entities and the hub is a singleton — total entity count matches the expected value. Without the safeguard (tested by calling the component routine on the *un-stripped* graph), A and B collapse into one component. The test asserts the safeguarded output, not the unsafeguarded one. |
| 10 | `test_hub_node_audit_metadata` | `n_hub_nodes`, `hub_node_ids`, and the hub txId's split assignment are all populated and internally consistent: count matches the size of the ids set, and the hub txId appears in exactly one of train/val/test. This single test covers the metadata assertions from the previous four; no additional hub tests. |
| 11 | `test_reproducibility_same_seed` | Two calls with `random_seed=42` produce identical `frozenset`s |
| 12 | `test_different_seeds_differ` | Calls with seeds 42 and 43 produce different splits (fixture has ≥30 entities, making collision negligible) |
| 13 | `test_conservative_label_mixed_entity` | Entity containing both illicit and licit txIds is labelled `"illicit"` for stratification purposes |
| 14 | `test_unknown_entities_included_in_splits` | `"unknown"`-label entities appear across all three splits; none are excluded |
| 15 | `test_supervised_eligibility_not_enforced` | `train_txids` contains `"unknown"`-label txIds (split membership ≠ supervised eligibility); callers must filter |
| 16 | `test_stratification_preserves_illicit_fraction` | illicit-labelled entity fraction in each split approximately matches overall fraction (within ±10%) |
| 17 | `test_time_order_ok_field_present` | `time_order_median` dict has keys `"train"`, `"val"`, `"test"`; `time_order_ok` is `bool` or `None` |
| 18 | `test_time_order_diagnostic_does_not_alter_split` | Two calls identical except one has shuffled time_steps (forcing `time_order_ok=False`) produce the same three `frozenset`s — proving the diagnostic is read-only |
| 19 | `test_fallback_when_no_actor_mapping` | Directory without actor mapping file → `split_method == "connected_component_proxy"` |
| 20 | `test_split_method_when_mapping_present` | With actor fixture → `split_method in {"actor_id", "mixed"}` |
| 21 | `test_ambiguous_actor_mapping_triggers_fallback` | Two qualifying candidate files in same directory → fallback, warning logged, `split_method == "connected_component_proxy"` |
| 22 | `test_missing_required_file_raises` | Missing `elliptic_txs_edgelist.csv` → `FileNotFoundError` |
| 23 | `test_split_stats_populated` | `split_stats` contains entity counts, txId counts, label fractions per split |
| 24 | `test_split_method_is_documented_value` | `split_method` is one of `{"actor_id", "connected_component_proxy", "mixed"}` |

---

## What This Does NOT Do

- **Not graph construction.** The NetworkX graph built here is used only to compute connected components as a conservative entity proxy for the train/val/test split. It is not the per-address subgraph that Module 2 will build — that is a different graph, built from normalized records at query time.
- **Not loading 166 Elliptic features.** Only `time_step` (column index 1) is read from the features file.
- **Not assuming Elliptic++ availability.** Actor mapping is discovered at runtime from what actually exists in `data_dir`. If nothing qualifies, the fallback runs silently with a log entry.
- **Not LEARNED_THRESHOLD tuning.** That is Phase 4 work.
- **Not marking Phase 1 complete.** The milestone check (`ROADMAP.md` Phase 1) is a separate human decision.
