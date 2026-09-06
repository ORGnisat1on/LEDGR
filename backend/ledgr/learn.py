"""Phase R4 — Learned Signal (ARCHITECTURE.md Module 3b).

Random-forest baseline trained on Elliptic's 166 handcrafted features using the
entity-safe train split, and evaluated honestly on held-out test entities.
Metrics (recall / precision / F1 on the illicit class) are logged per
METHODOLOGY.md §2 and written to `artifacts/model_eval.json`.

This **replaces** the hardcoded `mlScore: 0.942` / `mlPrediction: 'illicit'` in
the mock analyzer with a real per-wallet risk score.

Notes on honesty (AGENTS.md / METHODOLOGY.md §2):
  - Elliptic's class imbalance means raw accuracy is NOT reported as a headline
    metric; the headline metrics are illicit recall / precision / F1.
  - Training uses ONLY licit/illicit txIds. The entity split includes
    'unknown'-label txIds, but they are excluded from supervised training
    exactly as the split documentation requires.
  - This is the committed MVP learned signal (ROADMAP.md Phase 4 decision), the
    GNN is explicitly out of scope for the committed build.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import joblib
import numpy as np

from .config import (
    FEATURE_LOOKUP_FILE,
    LABEL_ILlicit,
    LABEL_LICIT,
    LABEL_UNKNOWN,
    LEARNED_FLAG_THRESHOLD,
    LEARNED_MODEL_FILE,
    MODEL_SEED,
    RF_N_ESTIMATORS,
    artifacts_dir,
    model_eval_report,
)
from .ingest import NormalizedDataset

logger = logging.getLogger(__name__)

# The positive class for every metric reported. Elliptic encodes illicit as 1.
POS_LABEL = LABEL_ILlicit


# ---------------------------------------------------------------------------
# Data preparation: entity-safe, supervised-eligible train/test subsets
# ---------------------------------------------------------------------------


def _label_index(ds: NormalizedDataset) -> dict[str, int]:
    """Map tx_id -> integer label (1 illicit / 0 licit / -1 unknown)."""
    return {str(t): int(l) for t, l in zip(ds.tx_ids, ds.tx_labels.tolist())}


def split_labeled(ds: NormalizedDataset, split_df) -> tuple[list[str], list[str]]:
    """Return `(train_ids, test_ids)` limited to supervised-eligible txIds.

    The entity split assigns *every* txId (including 'unknown'-label ones) to a
    partition; supervised training must only use licit/illicit txIds. We keep the
    split membership intact but filter to labeled txIds here, exactly as the split
    documentation instructs callers to do.
    """
    split_of = {str(t): s for t, s in zip(split_df["tx_id"].astype(str), split_df["split"])}
    label_of = _label_index(ds)
    train_ids: list[str] = []
    test_ids: list[str] = []
    for tx in ds.tx_ids:
        tx = str(tx)
        if label_of.get(tx) not in (LABEL_ILlicit, LABEL_LICIT):
            continue  # unknown -> not a supervised example
        s = split_of.get(tx)
        if s == "train":
            train_ids.append(tx)
        elif s == "test":
            test_ids.append(tx)
    return train_ids, test_ids


def features_for_ids(ds: NormalizedDataset, ids: list[str]) -> np.ndarray:
    """Assemble the feature matrix for the given txIds (row order preserved)."""
    idx = {str(t): i for i, t in enumerate(ds.tx_ids)}
    n_feat = ds.tx_features.shape[1]
    rows = [ds.tx_features[idx[t]] for t in ids]
    if not rows:
        return np.zeros((0, n_feat), dtype=np.float32)
    return np.vstack(rows)


def _labels_for_ids(ds: NormalizedDataset, ids: list[str]) -> np.ndarray:
    label_of = _label_index(ds)
    return np.array([label_of[t] for t in ids], dtype=np.int64)


def build_feature_lookup(ds: NormalizedDataset) -> dict[str, np.ndarray]:
    """tx_id -> 166-dim feature row, for query-time scoring of any known wallet."""
    return {str(t): ds.tx_features[i].astype(np.float32) for i, t in enumerate(ds.tx_ids)}
# ---------------------------------------------------------------------------
# Training / evaluation
# ---------------------------------------------------------------------------


def _pos_index(model) -> int:
    """Column index of the illicit class in model.classes_ / predict_proba."""
    return list(model.classes_).index(POS_LABEL)


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    n_estimators: int = RF_N_ESTIMATORS,
    seed: int = MODEL_SEED,
):
    """Train the random-forest baseline. class_weight='balanced' counters the
    severe illicit imbalance (METHODOLOGY.md §2) so the model does not just
    predict the majority (licit) class."""
    from sklearn.ensemble import RandomForestClassifier

    model = RandomForestClassifier(
        n_estimators=n_estimators,
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    logger.info(
        "Trained RF baseline: n_estimators=%d seed=%d n_train=%d classes=%s",
        n_estimators, seed, len(y_train), list(model.classes_),
    )
    return model


def evaluate_model(model, X_test: np.ndarray, y_test: np.ndarray,
                   flag_threshold: float = LEARNED_FLAG_THRESHOLD) -> dict:
    """Honest evaluation on held-out entities (METHODOLOGY.md §2).

    Headline metrics are illicit recall / precision / F1. Accuracy is reported
    only as a secondary number and never presented as the headline result.
    The positive-class decision uses the *configured* LEARNED_FLAG_THRESHOLD
    (not sklearn's implicit argmax default), so the eval threshold always
    matches the one /score serves — audit finding 2026-09-06: the two happened
    to coincide at 0.5, but the code now guarantees it instead of assuming it.
    The raw confusion matrix is logged per the same audit request.
    """
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
    )

    probs = predict_risk(model, X_test)
    y_pred = (probs >= flag_threshold).astype(np.int64)
    tp = int(np.sum((y_pred == POS_LABEL) & (y_test == POS_LABEL)))
    fp = int(np.sum((y_pred == POS_LABEL) & (y_test != POS_LABEL)))
    fn = int(np.sum((y_pred != POS_LABEL) & (y_test == POS_LABEL)))
    tn = int(np.sum((y_pred != POS_LABEL) & (y_test != POS_LABEL)))
    n = int(len(y_test))
    n_illicit = int(np.sum(y_test == POS_LABEL))
    zero = {"zero_division": 0}
    metrics = {
        "n_test_entities_txids": n,
        "n_illicit_test": n_illicit,
        "illicit_recall": float(recall_score(y_test, y_pred, pos_label=POS_LABEL, **zero)),
        "illicit_precision": float(precision_score(y_test, y_pred, pos_label=POS_LABEL, **zero)),
        "illicit_f1": float(f1_score(y_test, y_pred, pos_label=POS_LABEL, **zero)),
        "accuracy": float(accuracy_score(y_test, y_pred)),  # secondary only
        "n_illicit_predicted": int(np.sum(y_pred == POS_LABEL)),
        # Raw confusion matrix (audit 2026-09-06): reported, not just derived rates
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "flag_threshold_applied": flag_threshold,
    }
    logger.info(
        "Eval on held-out entities: illicit recall=%.3f precision=%.3f f1=%.3f "
        "(n_test=%d, n_illicit_test=%d, thr=%.2f, TP=%d FP=%d FN=%d TN=%d) "
        "— accuracy=%.3f reported as secondary only",
        metrics["illicit_recall"], metrics["illicit_precision"], metrics["illicit_f1"],
        n, n_illicit, flag_threshold, tp, fp, fn, tn, metrics["accuracy"],
    )
    return metrics


def predict_risk(model, X: np.ndarray) -> np.ndarray:
    """Return P(illicit) for each row, in 0..1."""
    probs = model.predict_proba(X)  # shape (n, n_classes)
    return probs[:, _pos_index(model)].astype(float)
# ---------------------------------------------------------------------------
# Artifact persistence
# ---------------------------------------------------------------------------


def save_learned_model(model, out_dir: Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else artifacts_dir()
    out.mkdir(parents=True, exist_ok=True)
    path = out / LEARNED_MODEL_FILE
    joblib.dump(model, path)
    logger.info("Learned model saved: %s", path)
    return path


def load_learned_model(path: Path | None = None):
    path = Path(path) if path else artifacts_dir() / LEARNED_MODEL_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"Learned model not found at {path}. Run `python scripts/train_model.py` first."
        )
    model = joblib.load(path)
    logger.info("Learned model loaded: %s", path)
    return model


def save_feature_lookup(lookup: dict[str, np.ndarray], out_dir: Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else artifacts_dir()
    out.mkdir(parents=True, exist_ok=True)
    path = out / FEATURE_LOOKUP_FILE
    joblib.dump(lookup, path)
    logger.info("Feature lookup saved: %s (%d wallets)", path, len(lookup))
    return path


def load_feature_lookup(path: Path | None = None) -> dict[str, np.ndarray]:
    path = Path(path) if path else artifacts_dir() / FEATURE_LOOKUP_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"Feature lookup not found at {path}. Run `python scripts/train_model.py` first."
        )
    lookup = joblib.load(path)
    logger.info("Feature lookup loaded: %s (%d wallets)", path, len(lookup))
    return lookup
# ---------------------------------------------------------------------------
# End-to-end training run (used by scripts/train_model.py)
# ---------------------------------------------------------------------------


def train_and_evaluate(
    ds: NormalizedDataset,
    split_df,
    out_dir: Path | None = None,
    n_estimators: int = RF_N_ESTIMATORS,
    seed: int = MODEL_SEED,
) -> dict:
    """Train the baseline on the entity-safe train split, evaluate on the held-out
    test entities, persist the model + feature lookup + evaluation report.

    Returns a summary dict of the artifacts written (paths + metrics).
    """
    out = Path(out_dir) if out_dir else artifacts_dir()
    out.mkdir(parents=True, exist_ok=True)

    train_ids, test_ids = split_labeled(ds, split_df)
    X_train = features_for_ids(ds, train_ids)
    y_train = _labels_for_ids(ds, train_ids)
    X_test = features_for_ids(ds, test_ids)
    y_test = _labels_for_ids(ds, test_ids)

    start = time.time()
    model = train_model(X_train, y_train, n_estimators=n_estimators, seed=seed)
    metrics = evaluate_model(model, X_test, y_test)
    train_seconds = round(time.time() - start, 2)

    # Effective per-class weights implied by class_weight="balanced"
    # (n_samples / (n_classes * class_count)) — recorded so audits can verify
    # balancing actually reached the fit, not just the config (audit 2026-09-06).
    counts = np.bincount(y_train)
    effective_weights = {
        int(c): round(len(y_train) / (len(counts) * int(counts[c])), 6)
        for c in range(len(counts)) if counts[c] > 0
    }

    # Persist artifacts
    model_path = save_learned_model(model, out)
    lookup_path = save_feature_lookup(build_feature_lookup(ds), out)

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "split": "entity_safe",
        "model": "random_forest_elliptic_166feat",
        "parameters": {
            "n_estimators": n_estimators,
            "class_weight": "balanced",
            "effective_class_weights": effective_weights,
            "seed": seed,
            "n_train_txids": len(train_ids),
            "n_test_txids": len(test_ids),
            "flag_threshold": LEARNED_FLAG_THRESHOLD,
        },
        "train_seconds": train_seconds,
        "metrics": metrics,
        "artifacts": {
            "model": str(model_path),
            "feature_lookup": str(lookup_path),
        },
        # Explicit honesty caveat required by METHODOLOGY.md §4
        "note": "risk_score/P(illicit) is a model output, not a determination of "
                "guilt; confirmed/watch correlation is Phase R5.",
    }
    report_path = model_eval_report(out)
    report_path.write_text(json.dumps(report, indent=2))
    logger.info("R4 evaluation report written: %s", report_path)
    return report


# ---------------------------------------------------------------------------
# Query-time scoring (Module 3b handoff to service)
# ---------------------------------------------------------------------------


def predict_wallet(model, feature_lookup: dict[str, np.ndarray], address: str) -> dict:
    """Return the learned-signal output for a single wallet address.

    If the address is not in the feature lookup (it was never in Elliptic), the
    wallet is honestly reported as `classified: False` with no fabricated risk —
    a fresh/out-of-dataset wallet cannot be scored by a model trained on Elliptic.
    """
    address = str(address)
    if address not in feature_lookup:
        return {
            "wallet": address,
            "classified": False,
            "risk_score": None,
            "prediction": None,
            "learned_flag": False,
            "note": "address not in Elliptic feature set; model cannot score it "
                    "and no risk is fabricated.",
        }
    risk = float(predict_risk(model, feature_lookup[address].reshape(1, -1))[0])
    flagged = risk >= LEARNED_FLAG_THRESHOLD
    return {
        "wallet": address,
        "classified": True,
        "risk_score": round(risk, 6),
        "prediction": "illicit" if flagged else "licit",
        "learned_flag": flagged,
        "flag_threshold": LEARNED_FLAG_THRESHOLD,
    }
    return {str(t): int(l) for t, l in zip(ds.tx_ids, ds.tx_labels.tolist())}