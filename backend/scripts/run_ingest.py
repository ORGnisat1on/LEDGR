#!/usr/bin/env python
"""Phase R1/R2 (rebuilt as R3 prerequisite) entrypoint: load raw Elliptic CSVs
-> normalized artifacts -> entity-safe split -> no-leakage verification ->
pre-indexed graph.

Usage:
  backend/.venv/Scripts/python backend/scripts/run_ingest.py [--data-dir data/raw]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledgr.config import artifacts_dir, data_dir  # noqa: E402
from ledgr.entity_split import build_entities, split_entities, verify_no_leakage  # noqa: E402
from ledgr.graph import build_graph, save_graph_index  # noqa: E402
from ledgr.ingest import load_address_map, load_elliptic  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> int:
    ap = argparse.ArgumentParser(description="LEDGR R1/R2 pipeline runner")
    ap.add_argument("--data-dir", type=Path, default=data_dir())
    ap.add_argument("--artifacts-dir", type=Path, default=artifacts_dir())
    args = ap.parse_args()

    print(f"[1/5] Loading Elliptic from {args.data_dir} ...")
    ds = load_elliptic(args.data_dir)
    ds.address_map = load_address_map(args.data_dir)

    out = args.artifacts_dir
    out.mkdir(parents=True, exist_ok=True)
    print(f"[2/5] Writing normalized artifacts to {out} ...")
    import pandas as pd
    pd.DataFrame({"tx_id": ds.tx_ids, "label": ds.tx_labels, "time_step": ds.tx_time_steps}).to_csv(
        out / "txs.csv", index=False)
    ds.edges.to_csv(out / "edges.csv", index=False)

    print("[3/5] Building entities (hub-safeguarded connected components) ...")
    ents = build_entities(ds)

    print("[4/5] Splitting entities and verifying no leakage ...")
    split_df = split_entities(ents)
    report = verify_no_leakage(ds, split_df)
    split_df.to_csv(out / "entity_split.csv", index=False)

    print("[5/5] Building and saving pre-indexed graph ...")
    save_graph_index(build_graph(ds), out)

    print("\nDone. Integrity:", {k: v["ok"] for k, v in ds.source_stats["integrity"].items()})
    print(f"Entities: {report['n_entities']} | leakage_free: {report['leakage_free']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
