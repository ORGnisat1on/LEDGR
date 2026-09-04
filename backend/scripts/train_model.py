#!/usr/bin/env python
"""Phase R4 entrypoint — train the learned-signal baseline (Module 3b).

Loads the Elliptic dataset -> entity-safe split -> random-forest baseline ->
honest evaluation on held-out entities (recall/precision/F1 on illicit, per
METHODOLOGY.md §2) -> writes artifacts/{learned_model.joblib, feature_lookup.pkl,
model_eval.json}.

Usage:
  backend/.venv/Scripts/python backend/scripts/train_model.py [--data-dir data/raw]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledgr.config import artifacts_dir, data_dir  # noqa: E402
from ledgr.entity_split import build_entities, split_entities, verify_no_leakage  # noqa: E402
from ledgr.ingest import load_address_map, load_elliptic  # noqa: E402
from ledgr.learn import train_and_evaluate  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> int:
    ap = argparse.ArgumentParser(description="LEDGR R4 learned-signal trainer")
    ap.add_argument("--data-dir", type=Path, default=data_dir())
    ap.add_argument("--artifacts-dir", type=Path, default=artifacts_dir())
    ap.add_argument("--n-estimators", type=int, default=None,
                    help="Override the committed RF_N_ESTIMATORS (tests use small values).")
    args = ap.parse_args()

    print(f"[1/5] Loading Elliptic from {args.data_dir} ...")
    ds = load_elliptic(args.data_dir)
    ds.address_map = load_address_map(args.data_dir)

    print("[2/5] Building entities (hub-safeguarded connected components) ...")
    ents = build_entities(ds)

    print("[3/5] Splitting entities and verifying no leakage ...")
    split_df = split_entities(ents)
    report = verify_no_leakage(ds, split_df)
    print(f"      entities={report['n_entities']} leakage_free={report['leakage_free']}")

    print(f"[4/5] Training random-forest baseline (n_estimators={args.n_estimators}) ...")
    result = train_and_evaluate(ds, split_df, out_dir=args.artifacts_dir,
                                n_estimators=args.n_estimators
                                if args.n_estimators else 200)

    print("[5/5] Evaluation report:")
    m = result["metrics"]
    print(f"      illicit recall={m['illicit_recall']:.3f} "
          f"precision={m['illicit_precision']:.3f} f1={m['illicit_f1']:.3f} "
          f"(n_test={m['n_test_entities_txids']}, n_illicit_test={m['n_illicit_test']})")
    print(f"      accuracy={m['accuracy']:.3f} (secondary metric only, per METHODOLOGY.md §2)")
    print(f"Artifacts -> {args.artifacts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())