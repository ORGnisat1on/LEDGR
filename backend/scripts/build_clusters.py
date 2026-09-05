#!/usr/bin/env python
"""Phase R6 entrypoint — entity clustering + supplementary attribution.

Builds Elliptic-derived entity clusters (hub-safeguarded connected components —
the same entity definition the entity-safe split uses), optionally tags
verdicts per wallet (when R3/R4 artifacts exist), attaches supplementary-source
named-exchange attribution from data/exchanges.txt (if sourced), and writes
artifacts/clusters.json.

Usage:
  backend/.venv/Scripts/python backend/scripts/build_clusters.py \
      [--data-dir data/raw] [--no-verdicts] [--max-verdict-wallets N]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledgr.cluster import (  # noqa: E402
    build_cluster_report,
    load_exchange_tags,
    save_cluster_report,
    wallet_to_cluster_map,
)
from ledgr.config import artifacts_dir, data_dir  # noqa: E402
from ledgr.correlate import correlate  # noqa: E402
from ledgr.entity_split import build_entities  # noqa: E402
from ledgr.graph import load_graph_index  # noqa: E402
from ledgr.ingest import load_elliptic  # noqa: E402
from ledgr.learn import load_feature_lookup, load_learned_model, predict_wallet  # noqa: E402
from ledgr.rules import load_mixer_ids, run_rules  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def compute_verdicts(ds, G, mixer_ids, max_wallets=None):
    """Per-wallet R3+R4 verdicts. Heavy at full-dataset scale — it is an offline
    batch step; `--max-verdict-wallets` bounds it and the cap is logged (never
    applied silently)."""
    try:
        model = load_learned_model()
        features = load_feature_lookup()
    except FileNotFoundError as e:
        logging.warning("Learned signal unavailable (%s) — verdicts will use the "
                        "rule signal alone (missing learned signal counts as not flagged).", e)
        model = features = None

    wallets = list(map(str, ds.tx_ids))
    capped = max_wallets is not None and len(wallets) > max_wallets
    if capped:
        logging.warning("Verdict computation capped at %d of %d wallets "
                        "(--max-verdict-wallets); remaining wallets get no verdict tag.",
                        max_wallets, len(wallets))
        wallets = wallets[:max_wallets]

    verdict_by_wallet: dict[str, str] = {}
    for w in wallets:
        if w not in G:
            continue
        rules_out = run_rules(G, w, mixer_ids=mixer_ids, hop_depth=2)
        if model is not None and features is not None and w in features:
            learned_out = predict_wallet(model, features, w)
        else:
            learned_out = {"wallet": w, "classified": False, "risk_score": None,
                           "prediction": None, "learned_flag": False}
        verdict_by_wallet[w] = correlate(rules_out, learned_out)["verdict"]
    logging.info("Computed verdicts for %d wallets", len(verdict_by_wallet))
    return verdict_by_wallet


def main() -> int:
    ap = argparse.ArgumentParser(description="LEDGR R6 clustering / attribution")
    ap.add_argument("--data-dir", type=Path, default=data_dir())
    ap.add_argument("--artifacts-dir", type=Path, default=artifacts_dir())
    ap.add_argument("--graph-index", type=Path, default=None)
    ap.add_argument("--no-verdicts", action="store_true",
                    help="Skip per-wallet verdict tagging (clusters only).")
    ap.add_argument("--max-verdict-wallets", type=int, default=None)
    args = ap.parse_args()

    print(f"[1/5] Loading Elliptic from {args.data_dir} ...")
    ds = load_elliptic(args.data_dir)

    print("[2/5] Building entity clusters (hub-safeguarded components) ...")
    entities_df = build_entities(ds)

    print("[3/5] Loading supplementary named-exchange tagging ...")
    exchange_tags = load_exchange_tags()

    verdict_by_wallet = None
    if not args.no_verdicts:
        print("[4/5] Tagging per-wallet verdicts (R3 rules + R4 learned) ...")
        G = load_graph_index(args.graph_index or (args.artifacts_dir / "graph_index.pkl"))
        verdict_by_wallet = compute_verdicts(
            ds, G, load_mixer_ids(), max_wallets=args.max_verdict_wallets
        )
    else:
        print("[4/5] Skipping per-wallet verdict tagging (--no-verdicts).")

    print("[5/5] Assembling cluster report ...")
    report = build_cluster_report(
        ds, entities_df,
        exchange_tags=exchange_tags,
        verdict_by_wallet=verdict_by_wallet,
    )
    out = save_cluster_report(report, args.artifacts_dir)

    print(f"\nClusters: {report['n_clusters']} (wallets: {report['n_wallets']})")
    print(f"Attributed via supplementary exchange list: {report['n_attributed_clusters']}")
    print(f"Supplementary matches: {len(report['supplementary_matches'])} "
          f"(unmatched tags: {len(report['supplementary_unmatched'])})")
    print(f"Report -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())