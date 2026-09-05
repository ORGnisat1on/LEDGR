import sys
from pathlib import Path

import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr.config import artifacts_dir  # noqa: E402
from ledgr.entity_split import build_entities, split_entities, verify_no_leakage  # noqa: E402
from ledgr.ingest import load_elliptic  # noqa: E402

FIXTURE = BACKEND / "tests" / "fixtures" / "synthetic"


@pytest.fixture(scope="module")
def dataset():
    return load_elliptic(FIXTURE)


def test_fixture_integrity(dataset):
    """Fixture loads into the normalized format with expected shape."""
    assert dataset.source_stats["n_features"] == 166
    assert dataset.source_stats["tx_count"] > 0
    assert set(dataset.tx_labels.tolist()) <= {1, 0, -1}


def test_features_align_with_classes(dataset):
    ids = list(map(str, dataset.tx_ids))
    assert len(ids) == len(set(ids))
    assert 1 <= dataset.tx_time_steps.min() and dataset.tx_time_steps.max() <= 49


def test_entity_split_is_leakage_free(dataset, tmp_path, monkeypatch):
    """METHODOLOGY §1: no tx or entity may appear in both train and test."""
    monkeypatch.setattr("ledgr.entity_split.artifacts_dir", lambda: tmp_path)
    ents = build_entities(dataset)
    split_df = split_entities(dataset, ents)
    train = set(split_df.loc[split_df["split"] == "train", "tx_id"])
    test = set(split_df.loc[split_df["split"] == "test", "tx_id"])
    assert not (train & test), "tx id leaked across split"
    # require_span_zero=False: the synthetic fixture is a random graph whose
    # components legitimately span multiple time steps; only the no-leakage
    # mechanics are under test here. Span-0 is strictly enforced (default) on
    # real pipeline runs (scripts/train_model.py) — see METHODOLOGY.md §1 step 2.
    report = verify_no_leakage(dataset, split_df, require_span_zero=False)
    assert report["leakage_free"] is True
    assert "entity_time_span_violations" in report  # span audit logged on every run
    assert (tmp_path / "split_verification.json").exists()


def test_hub_safeguard(dataset, tmp_path, monkeypatch):
    """The exchange-like hub must not merge everything into one giant entity."""
    monkeypatch.setattr("ledgr.entity_split.artifacts_dir", lambda: tmp_path)
    ents = build_entities(dataset, hub_threshold=50)
    hub_rows = ents[ents["is_hub"]]
    assert len(hub_rows) == 1
    n_entities = ents["entity_id"].nunique()
    assert n_entities > 10, f"hub safeguard failed: only {n_entities} entities"


def test_split_reproducible(dataset):
    ents = build_entities(dataset)
    s1 = split_entities(dataset, ents)
    s2 = split_entities(dataset, ents)
    pd.testing.assert_frame_equal(s1, s2)


def test_artifact_dir_default():
    assert artifacts_dir().name == "artifacts"
