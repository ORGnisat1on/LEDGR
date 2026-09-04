#!/usr/bin/env python
"""Generate a small synthetic dataset in Elliptic CSV format for tests/sanity
checks (NOT real data — used until the Kaggle CSVs are placed in data/raw/).

Also generates backend/tests/fixtures/mixers_test.txt (a tiny synthetic mixer
list for tests — never ship fabricated real addresses).

Writes: elliptic_txs_features.csv, elliptic_txs_edgelist.csv, elliptic_txs_classes.csv
to backend/tests/fixtures/synthetic/
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

N_FEATURES = 166
N_CLUSTERS = 40
N_CHAINS = 30
N_HUB_EDGES = 400

rng = random.Random(42)


def main() -> None:
    out = BACKEND / "tests" / "fixtures" / "synthetic"
    out.mkdir(parents=True, exist_ok=True)

    txs: list[str] = []
    edges: list[tuple[str, str]] = []
    labels: dict[str, str] = {}
    feat_idx = 0

    def new_tx(label: str) -> str:
        nonlocal feat_idx
        tx = f"tx{feat_idx:06d}"
        feat_idx += 1
        txs.append(tx)
        labels[tx] = label
        return tx

    # Dense clusters: some illicit, some licit
    for c in range(N_CLUSTERS):
        label = "1" if c % 3 == 0 else "2"
        members = [new_tx(label) for _ in range(8)]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if rng.random() < 0.5:
                    edges.append((members[i], members[j]))

    # Peel chains (time-advancing: node i gets time step based on position)
    for _ in range(N_CHAINS):
        label = rng.choice(["1", "2"])
        prev = new_tx(label)
        for _hop in range(10):
            nxt = new_tx(label)
            edges.append((prev, nxt))
            prev = nxt

    # One high-degree hub (exchange-like) — must be excluded by hub safeguard
    hub = new_tx("2")
    for _ in range(N_HUB_EDGES):
        edges.append((hub, new_tx("unknown")))

    with open(out / "elliptic_txs_edgelist.csv", "w", encoding="utf-8") as f:
        f.write("txId1,txId2\n")
        for a, b in edges:
            f.write(f"{a},{b}\n")

    with open(out / "elliptic_txs_classes.csv", "w", encoding="utf-8") as f:
        f.write("txId,class\n")
        for tx in txs:
            f.write(f"{tx},{labels[tx]}\n")

    # Features CSV (no header): txId + time_step + 165 dummy features.
    # Time step advances along each chain so peel-chain detection sees real ordering.
    chain_pos = {}
    for a, b in edges:
        chain_pos.setdefault(a, 0)
    with open(out / "elliptic_txs_features.csv", "w", encoding="utf-8") as f:
        for i, tx in enumerate(txs):
            ts = 1 + (i % 49)
            feats = [ts] + [round(rng.random(), 6) for _ in range(N_FEATURES - 1)]
            f.write(tx + "," + ",".join(map(str, feats)) + "\n")

    # Synthetic mixer list for tests only
    mixers = BACKEND / "tests" / "fixtures" / "mixers_test.txt"
    mixers.write_text(
        "# synthetic test mixer list — NOT real addresses\n"
        + "\n".join(txs[:5]) + "\n", encoding="utf-8")

    print(f"Synthetic fixture written: {len(txs)} txs, {len(edges)} edges -> {out}")


if __name__ == "__main__":
    main()
