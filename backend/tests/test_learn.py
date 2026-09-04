import sys
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr.entity_split import build_entities, split_entities, verify_no_leakage  # noqa: E402
from ledgr.ingest import load_elliptic  # noqa: E402
from ledgr.learn import (  # noqa: E402
    build_feature_lookup,
    features_for_ids,
    load_feature_lookup,
    load_learned_model,
    predict_risk,
    predict_wallet,
    split_labeled,
    train_and_evaluate,
    train_model,
)

FIXTURE = BACKEND / "tests" / "fixtures" / "synthetic"

N_FEATURES = 166  # feature columns after tx id (matches load_elliptic / ingest.py)


@pytest.fixture(scope="module")
def split_ds():
    ds = load_elliptic(FIXTURE)
    split_df = split_entities(build_entities(ds))
    assert verify_no_leakage(ds, split_df)["leakage_free"]
    return ds, split_df


def _labels(ds, ids):
    lab = dict(zip(map(str, ds.tx_ids), ds.tx_labels.tolist()))
    return np.array([lab[t] for t in ids], dtype=np.int64)


def test_split_labeled_only_contains_labelled(split_ds):
    ds, split_df = split_ds
    train_ids, test_ids = split_labeled(ds, split_df)
    assert train_ids and test_ids, "fixture must produce a usable labeled split"
    lab = dict(zip(map(str, ds.tx_ids), ds.tx_labels.tolist()))
    for t in train_ids + test_ids:
        assert lab[t] in (1, 0), f"supervised eligibility violated for {t}"


def test_train_and_evaluate_writes_artifacts(split_ds, tmp_path):
    ds, split_df = split_ds
    report = train_and_evaluate(ds, split_df, out_dir=tmp_path, n_estimators=20)
    m = report["metrics"]
    # Honest evaluation report per METHODOLOGY.md §2
    for key in ("illicit_recall", "illicit_precision", "illicit_f1", "n_test_entities_txids"):
        assert key in m
    assert (tmp_path / "learned_model.joblib").exists()
    assert (tmp_path / "feature_lookup.pkl").exists()
    assert (tmp_path / "model_eval.json").exists()
    assert report["split"] == "entity_safe"


def test_model_load_roundtrip(split_ds, tmp_path):
    ds, split_df = split_ds
    train_and_evaluate(ds, split_df, out_dir=tmp_path, n_estimators=20)
    model = load_learned_model(tmp_path / "learned_model.joblib")
    lookup = load_feature_lookup(tmp_path / "feature_lookup.pkl")
    for t in map(str, ds.tx_ids):
        assert lookup[t].shape == (N_FEATURES,)


def test_predict_risk_in_unit_interval(split_ds, tmp_path):
    ds, split_df = split_ds
    train_ids, _ = split_labeled(ds, split_df)
    model = train_model(features_for_ids(ds, train_ids), _labels(ds, train_ids),
                        n_estimators=20)
    risk = predict_risk(model, features_for_ids(ds, [train_ids[0]]))
    assert 0.0 <= risk[0] <= 1.0


def test_predict_wallet_classified_and_unclassified(split_ds, tmp_path):
    ds, split_df = split_ds
    train_and_evaluate(ds, split_df, out_dir=tmp_path, n_estimators=20)
    model = load_learned_model(tmp_path / "learned_model.joblib")
    lookup = load_feature_lookup(tmp_path / "feature_lookup.pkl")

    known = str(ds.tx_ids[0])
    out = predict_wallet(model, lookup, known)
    assert out["classified"] is True
    assert 0.0 <= out["risk_score"] <= 1.0
    assert out["prediction"] in ("illicit", "licit")
    assert out["learned_flag"] in (True, False)

    unseen = predict_wallet(model, lookup, "not-a-real-elliptic-wallet")
    assert unseen["classified"] is False
    assert unseen["risk_score"] is None
    assert unseen["learned_flag"] is False


def test_all_feature_lookup_entries_present(split_ds):
    ds, _ = split_ds
    lookup = build_feature_lookup(ds)
    assert len(lookup) == len(ds.tx_ids)
    assert set(lookup.keys()) == {str(t) for t in ds.tx_ids}
