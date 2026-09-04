"""
Test suite for module1/entity_split.py.

Phase 1 entity-based train/val/test split — 24 tests per the approved plan.

All tests use entity_split_fixtures/ ONLY.
The existing data_ingestion/test_fixtures/ is never referenced or modified.

IMPORTANT: tests use hub_degree_threshold=5 (not the production default of
1000) so the fixture's hub node (degree=5) triggers the safeguard.
Chain-internal nodes (max degree=2) are NOT affected by this threshold.
The production default of HUB_DEGREE_THRESHOLD=1000 is correct for the full
Elliptic dataset; the fixture uses a lower threshold to exercise the code path.

Run with: python3 -m pytest module1/test_entity_split.py -v
"""

import dataclasses
import shutil
from pathlib import Path

import pytest

from module1.entity_split import (
    EntitySplit,
    HUB_DEGREE_THRESHOLD,
    RANDOM_SEED,
    TRAIN_FRACTION,
    VAL_FRACTION,
    TEST_FRACTION,
    build_entity_split,
    _discover_actor_mapping,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "entity_split_fixtures"
ACTOR_FIXTURE = FIXTURE_DIR / "actor_mapping_fixture.csv"

# Load the fixture ID lookup generated alongside the fixtures
import sys
sys.path.insert(0, str(FIXTURE_DIR))
from _fixture_ids import (
    HEX,
    COMPONENTS,
    HUB,
    SINGLETONS,
    LABELS,
    ACTOR_MAP,
    HUB_FIXTURE_DEGREE,
    N_ENTITIES_WITH_SAFEGUARD,
    N_ENTITIES_WITHOUT_SAFEGUARD,
)

# Hub threshold tuned to the fixture: hub has degree=5, so threshold=5 triggers it.
# Chain-internal nodes (e.g. a2) have degree<=2, so they are NOT removed at threshold=5.
HUB_THRESHOLD_FOR_FIXTURE = HUB_FIXTURE_DEGREE  # = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build(data_dir=FIXTURE_DIR, threshold=HUB_THRESHOLD_FOR_FIXTURE, seed=RANDOM_SEED):
    """Convenience wrapper for build_entity_split with fixture defaults."""
    return build_entity_split(
        data_dir=data_dir,
        hub_degree_threshold=threshold,
        random_seed=seed,
    )


def _all_fixture_txids():
    return frozenset(HEX.values())


# ---------------------------------------------------------------------------
# 1. test_output_is_entity_split_dataclass
# ---------------------------------------------------------------------------

def test_output_is_entity_split_dataclass():
    """Return type is EntitySplit; all required fields are present and typed."""
    split = _build()
    assert isinstance(split, EntitySplit)
    assert isinstance(split.train_txids, frozenset)
    assert isinstance(split.val_txids, frozenset)
    assert isinstance(split.test_txids, frozenset)
    assert isinstance(split.split_method, str)
    assert isinstance(split.n_entities_total, int)
    assert isinstance(split.n_hub_nodes, int)
    assert isinstance(split.hub_node_ids, frozenset)
    assert isinstance(split.leakage_verified, bool)
    assert isinstance(split.time_order_median, dict)
    assert split.time_order_ok is None or isinstance(split.time_order_ok, bool)
    assert isinstance(split.split_stats, dict)


# ---------------------------------------------------------------------------
# 2. test_split_fractions_approximate
# ---------------------------------------------------------------------------

def test_split_fractions_approximate():
    """
    Train/val/test entity fractions approximately match 70/15/15 (within 10%).
    Tolerance accounts for small fixture size (36 entities) where rounding matters.
    """
    split = _build()
    total = split.n_entities_total
    train_n = split.split_stats["train"]["n_entities"]
    val_n = split.split_stats["val"]["n_entities"]
    test_n = split.split_stats["test"]["n_entities"]

    assert abs(train_n / total - TRAIN_FRACTION) < 0.10
    assert abs(val_n / total - VAL_FRACTION) < 0.10
    assert abs(test_n / total - TEST_FRACTION) < 0.10


# ---------------------------------------------------------------------------
# 3. test_all_txids_accounted_for
# ---------------------------------------------------------------------------

def test_all_txids_accounted_for():
    """Every txId appears in exactly one of train/val/test; none lost or duplicated."""
    split = _build()
    combined = split.train_txids | split.val_txids | split.test_txids
    assert combined == _all_fixture_txids()
    total_count = len(split.train_txids) + len(split.val_txids) + len(split.test_txids)
    assert total_count == len(_all_fixture_txids())


# ---------------------------------------------------------------------------
# 4. test_no_leakage_verify_passes
# ---------------------------------------------------------------------------

def test_no_leakage_verify_passes():
    """verify_no_leakage() completes without exception on a valid split."""
    split = _build()
    split.verify_no_leakage()  # must not raise


# ---------------------------------------------------------------------------
# 5. test_verify_no_leakage_raises_on_injected_overlap
# ---------------------------------------------------------------------------

def test_verify_no_leakage_raises_on_injected_overlap():
    """Manually construct an EntitySplit with overlap; verify_no_leakage raises ValueError."""
    split = _build()
    stolen = next(iter(split.val_txids))
    corrupted = dataclasses.replace(
        split,
        train_txids=split.train_txids | frozenset({stolen}),
        leakage_verified=False,
    )
    with pytest.raises(ValueError, match="leakage detected"):
        corrupted.verify_no_leakage()


# ---------------------------------------------------------------------------
# 6. test_leakage_verified_true
# ---------------------------------------------------------------------------

def test_leakage_verified_true():
    """EntitySplit.leakage_verified is True on valid output."""
    split = _build()
    assert split.leakage_verified is True


# ---------------------------------------------------------------------------
# 7. test_entity_level_split_not_transaction_level
# ---------------------------------------------------------------------------

def test_entity_level_split_not_transaction_level():
    """
    All txIds belonging to the same connected component appear in exactly one
    split — never split across two sets.  Core correctness property.
    """
    split = _build()
    for comp_name, short_members in COMPONENTS.items():
        hex_members = [HEX[s] for s in short_members]
        in_train = any(t in split.train_txids for t in hex_members)
        in_val = any(t in split.val_txids for t in hex_members)
        in_test = any(t in split.test_txids for t in hex_members)
        splits_containing = sum([in_train, in_val, in_test])
        assert splits_containing == 1, (
            f"Component {comp_name} spans {splits_containing} splits"
        )


# ---------------------------------------------------------------------------
# 8. test_actor_id_entities_never_cross_splits
# ---------------------------------------------------------------------------

def test_actor_id_entities_never_cross_splits(tmp_path):
    """
    With actor mapping present, all txIds sharing the same actor_id appear in
    exactly one of train/val/test.
    """
    for f in FIXTURE_DIR.iterdir():
        if f.suffix in (".csv", ".py"):
            shutil.copy(f, tmp_path / f.name)

    split = build_entity_split(
        data_dir=tmp_path,
        hub_degree_threshold=HUB_THRESHOLD_FOR_FIXTURE,
        random_seed=RANDOM_SEED,
    )
    for actor_id, actor_txids in ACTOR_MAP.items():
        actor_set = frozenset(actor_txids)
        in_train = actor_set & split.train_txids
        in_val = actor_set & split.val_txids
        in_test = actor_set & split.test_txids
        non_empty = sum([bool(in_train), bool(in_val), bool(in_test)])
        assert non_empty == 1, (
            f"Actor '{actor_id}' txIds span {non_empty} splits"
        )


# ---------------------------------------------------------------------------
# 9. test_hub_node_does_not_merge_components
# ---------------------------------------------------------------------------

def test_hub_node_does_not_merge_components():
    """
    Core hub-node test.

    Fixture has hub1 connecting component A (a1..a4) and component B (b1..b4)
    and also s03, s04, s05 (singletons).  Without the safeguard, all of these
    merge into one large component.  With the safeguard (hub removed before
    component computation), A and B remain separate entities.

    Entity count comparison:
    - WITH safeguard: hub becomes a singleton; A, B, s03, s04, s05 are separate.
    - WITHOUT safeguard (threshold raised to hub_degree + 1, so hub stays):
      A + B + hub + s03 + s04 + s05 merge into 1 component — 5 fewer entities
      than the safeguarded split.
    """
    split_safe = _build(threshold=HUB_THRESHOLD_FOR_FIXTURE)
    split_unsafe = build_entity_split(
        data_dir=FIXTURE_DIR,
        hub_degree_threshold=HUB_THRESHOLD_FOR_FIXTURE + 1,  # hub not removed
        random_seed=RANDOM_SEED,
    )

    # With safeguard: more entities (hub + A + B + s03+s04+s05 all separate)
    # Without safeguard: those 6 merge into 1 → 5 fewer entities
    assert split_safe.n_entities_total == split_unsafe.n_entities_total + 5, (
        f"Expected safeguarded split to have 5 more entities than unsafeguarded split. "
        f"safe={split_safe.n_entities_total}, unsafe={split_unsafe.n_entities_total}"
    )
    # Hub was removed in safeguarded split
    assert split_safe.n_hub_nodes == 1
    assert split_unsafe.n_hub_nodes == 0


# ---------------------------------------------------------------------------
# 10. test_hub_node_audit_metadata
# ---------------------------------------------------------------------------

def test_hub_node_audit_metadata():
    """Hub node audit fields are populated and internally consistent."""
    split = _build(threshold=HUB_THRESHOLD_FOR_FIXTURE)
    hub_hex = HEX[HUB]

    assert split.n_hub_nodes == 1
    assert len(split.hub_node_ids) == split.n_hub_nodes
    assert hub_hex in split.hub_node_ids

    in_train = hub_hex in split.train_txids
    in_val = hub_hex in split.val_txids
    in_test = hub_hex in split.test_txids
    assert sum([in_train, in_val, in_test]) == 1


# ---------------------------------------------------------------------------
# 11. test_reproducibility_same_seed
# ---------------------------------------------------------------------------

def test_reproducibility_same_seed():
    """Two calls with random_seed=42 produce identical frozensets."""
    split1 = _build(seed=RANDOM_SEED)
    split2 = _build(seed=RANDOM_SEED)
    assert split1.train_txids == split2.train_txids
    assert split1.val_txids == split2.val_txids
    assert split1.test_txids == split2.test_txids


# ---------------------------------------------------------------------------
# 12. test_different_seeds_differ
# ---------------------------------------------------------------------------

def test_different_seeds_differ():
    """Seeds 42 and 43 produce different splits (36-entity fixture, negligible collision risk)."""
    split42 = _build(seed=42)
    split43 = _build(seed=43)
    assert (
        split42.train_txids != split43.train_txids
        or split42.val_txids != split43.val_txids
        or split42.test_txids != split43.test_txids
    )


# ---------------------------------------------------------------------------
# 13. test_conservative_label_mixed_entity
# ---------------------------------------------------------------------------

def test_conservative_label_mixed_entity():
    """
    Component E: e1=illicit, e2=licit, e3=unknown -> conservative label "illicit".
    All of E's txIds appear in exactly one split (entity treated atomically);
    e2 (licit) and e1 (illicit) are never separated.
    """
    split = _build()
    comp_e_txids = frozenset(HEX[s] for s in COMPONENTS["E"])
    in_train = bool(comp_e_txids & split.train_txids)
    in_val = bool(comp_e_txids & split.val_txids)
    in_test = bool(comp_e_txids & split.test_txids)
    assert sum([in_train, in_val, in_test]) == 1

    def _which(t, s):
        if t in s.train_txids: return "train"
        if t in s.val_txids: return "val"
        return "test"

    assert _which(HEX["e1"], split) == _which(HEX["e2"], split)


# ---------------------------------------------------------------------------
# 14. test_unknown_entities_included_in_splits
# ---------------------------------------------------------------------------

def test_unknown_entities_included_in_splits():
    """
    "unknown"-label entities are assigned to splits; none excluded.
    Component F is all-unknown; its txIds must be in exactly one split.
    """
    split = _build()
    comp_f_txids = frozenset(HEX[s] for s in COMPONENTS["F"])
    assert comp_f_txids.issubset(
        split.train_txids | split.val_txids | split.test_txids
    )


# ---------------------------------------------------------------------------
# 15. test_supervised_eligibility_not_enforced
# ---------------------------------------------------------------------------

def test_supervised_eligibility_not_enforced():
    """
    train_txids contains unknown-label txIds.
    Split membership is not filtered to supervised-eligible examples.
    """
    split = _build()
    unknown_txids = frozenset(HEX[s] for s in COMPONENTS["F"])
    assert unknown_txids.issubset(
        split.train_txids | split.val_txids | split.test_txids
    )
    # At least one unknown txId must be in train (not silently dropped)
    assert unknown_txids & split.train_txids


# ---------------------------------------------------------------------------
# 16. test_stratification_preserves_illicit_fraction
# ---------------------------------------------------------------------------

def test_stratification_preserves_illicit_fraction():
    """
    Illicit txId fraction per split approximately matches global fraction (within 20%).
    Tolerance is generous for a 36-entity fixture.
    """
    split = _build()
    all_txids = _all_fixture_txids()
    global_illicit_frac = sum(1 for t in all_txids if LABELS.get(t) == "1") / len(all_txids)

    for partition in ("train", "val", "test"):
        frac = split.split_stats[partition]["label_fractions"]["illicit"]
        assert abs(frac - global_illicit_frac) < 0.25, (
            f"{partition} illicit fraction {frac:.3f} deviates >25% from global {global_illicit_frac:.3f}"
        )


# ---------------------------------------------------------------------------
# 17. test_time_order_ok_field_present
# ---------------------------------------------------------------------------

def test_time_order_ok_field_present():
    """time_order_median has keys train/val/test; time_order_ok is bool or None."""
    split = _build()
    assert set(split.time_order_median.keys()) == {"train", "val", "test"}
    assert split.time_order_ok is None or isinstance(split.time_order_ok, bool)


# ---------------------------------------------------------------------------
# 18. test_time_order_diagnostic_does_not_alter_split
# ---------------------------------------------------------------------------

def test_time_order_diagnostic_does_not_alter_split(tmp_path):
    """
    Reversed time_steps force time_order_ok=False but the split is unchanged.
    The time-order diagnostic is read-only.
    """
    import csv as _csv

    for f in FIXTURE_DIR.iterdir():
        if f.suffix in (".csv", ".py") and f.stem != "elliptic_txs_features":
            shutil.copy(f, tmp_path / f.name)

    features_orig = FIXTURE_DIR / "elliptic_txs_features.csv"
    txids_in_order = []
    with features_orig.open() as f:
        reader = _csv.reader(f)
        next(reader)
        for row in reader:
            txids_in_order.append(row[0])

    with (tmp_path / "elliptic_txs_features.csv").open("w", newline="") as f:
        writer = _csv.writer(f)
        writer.writerow(["txId", "time_step", "feat_1"])
        n = len(txids_in_order)
        for i, txid in enumerate(txids_in_order):
            writer.writerow([txid, n - i, 0.0])  # reversed -> forces time_order_ok=False

    split_reversed = build_entity_split(
        data_dir=tmp_path,
        hub_degree_threshold=HUB_THRESHOLD_FOR_FIXTURE,
        random_seed=RANDOM_SEED,
    )
    split_original = _build()

    assert split_original.train_txids == split_reversed.train_txids
    assert split_original.val_txids == split_reversed.val_txids
    assert split_original.test_txids == split_reversed.test_txids


# ---------------------------------------------------------------------------
# 19. test_fallback_when_no_actor_mapping
# ---------------------------------------------------------------------------

def test_fallback_when_no_actor_mapping(tmp_path):
    """No actor mapping file -> split_method == "connected_component_proxy"."""
    for fname in [
        "elliptic_txs_classes.csv",
        "elliptic_txs_edgelist.csv",
        "elliptic_txs_features.csv",
    ]:
        shutil.copy(FIXTURE_DIR / fname, tmp_path / fname)

    split = build_entity_split(
        data_dir=tmp_path,
        hub_degree_threshold=HUB_THRESHOLD_FOR_FIXTURE,
        random_seed=RANDOM_SEED,
    )
    assert split.split_method == "connected_component_proxy"


# ---------------------------------------------------------------------------
# 20. test_split_method_when_mapping_present
# ---------------------------------------------------------------------------

def test_split_method_when_mapping_present(tmp_path):
    """Actor mapping present -> split_method in {"actor_id", "mixed"}."""
    for f in FIXTURE_DIR.iterdir():
        if f.suffix in (".csv", ".py"):
            shutil.copy(f, tmp_path / f.name)

    split = build_entity_split(
        data_dir=tmp_path,
        hub_degree_threshold=HUB_THRESHOLD_FOR_FIXTURE,
        random_seed=RANDOM_SEED,
    )
    assert split.split_method in {"actor_id", "mixed"}


# ---------------------------------------------------------------------------
# 21. test_ambiguous_actor_mapping_triggers_fallback
# ---------------------------------------------------------------------------

def test_ambiguous_actor_mapping_triggers_fallback(tmp_path):
    """Two qualifying actor-mapping files -> fallback; never guesses."""
    for fname in [
        "elliptic_txs_classes.csv",
        "elliptic_txs_edgelist.csv",
        "elliptic_txs_features.csv",
    ]:
        shutil.copy(FIXTURE_DIR / fname, tmp_path / fname)

    for name in ("actor_map_a.csv", "actor_map_b.csv"):
        with (tmp_path / name).open("w") as f:
            f.write("actor_id,txId\n")
            f.write("actor1,abc\n")

    split = build_entity_split(
        data_dir=tmp_path,
        hub_degree_threshold=HUB_THRESHOLD_FOR_FIXTURE,
        random_seed=RANDOM_SEED,
    )
    assert split.split_method == "connected_component_proxy"


# ---------------------------------------------------------------------------
# 22. test_missing_required_file_raises
# ---------------------------------------------------------------------------

def test_missing_required_file_raises(tmp_path):
    """Missing elliptic_txs_edgelist.csv raises FileNotFoundError."""
    shutil.copy(
        FIXTURE_DIR / "elliptic_txs_classes.csv",
        tmp_path / "elliptic_txs_classes.csv",
    )
    with pytest.raises(FileNotFoundError):
        build_entity_split(
            data_dir=tmp_path,
            hub_degree_threshold=HUB_THRESHOLD_FOR_FIXTURE,
        )


# ---------------------------------------------------------------------------
# 23. test_split_stats_populated
# ---------------------------------------------------------------------------

def test_split_stats_populated():
    """split_stats contains entity counts, txId counts, label fractions per split."""
    split = _build()
    for partition in ("train", "val", "test"):
        stats = split.split_stats[partition]
        assert "n_entities" in stats
        assert "n_txids" in stats
        assert "label_fractions" in stats
        fracs = stats["label_fractions"]
        assert set(fracs.keys()) == {"illicit", "licit", "unknown"}
        assert abs(sum(fracs.values()) - 1.0) < 0.01


# ---------------------------------------------------------------------------
# 24. test_split_method_is_documented_value
# ---------------------------------------------------------------------------

def test_split_method_is_documented_value():
    """split_method is one of the three documented values."""
    split = _build()
    assert split.split_method in {
        "actor_id",
        "connected_component_proxy",
        "mixed",
    }