#!/usr/bin/env python
"""Generate synthetic dataset in Elliptic CSV format for tests/demo/sanity checks.

Includes:
- Synthetic dense clusters, chains, and hubs
- The 4 SIH forensic preset cases with their real addresses:
  Case 1: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa (peel chain -> Binance 14)
  Case 2: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy (rapid fan-out -> KuCoin)
  Case 3: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq (mixer adjacent -> OKX)
  Case 4: 1BitPayMerchantCommercialGateway9988 & 1BitPayMerch498zKqw23NmKLiopQ1298as (licit merchant control)
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
    time_steps: dict[str, int] = {}
    feat_idx = 0

    def new_tx(label: str, ts: int | None = None) -> str:
        nonlocal feat_idx
        tx = f"tx{feat_idx:06d}"
        feat_idx += 1
        txs.append(tx)
        labels[tx] = label
        time_steps[tx] = ts if ts is not None else (1 + (len(txs) % 49))
        return tx

    def add_custom_tx(tx: str, label: str, ts: int) -> str:
        if tx not in labels:
            txs.append(tx)
            labels[tx] = label
            time_steps[tx] = ts
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
        prev = new_tx(label, ts=10)
        for hop in range(10):
            nxt = new_tx(label, ts=10 + hop + 1)
            edges.append((prev, nxt))
            prev = nxt

    # One high-degree hub (exchange-like) — excluded by hub safeguard
    hub = new_tx("2", ts=20)
    for _ in range(N_HUB_EDGES):
        edges.append((hub, new_tx("unknown", ts=21)))

    # ---------------------------------------------------------
    # Preset Case 1: Pig Butchering Peel Chain (Target: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa)
    # ---------------------------------------------------------
    c1_root = add_custom_tx("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1", 1)
    c1_funding = add_custom_tx("funding_input_case1", "1", 1)
    c1_hop1 = add_custom_tx("1PeelHop1xY98mQw7uRk52oKmnJ2189as1", "1", 2)
    c1_hop2 = add_custom_tx("1PeelHop2aB87xZ12mn90lkjh34567asdf", "1", 3)
    c1_hop3 = add_custom_tx("1PeelHop3cDef4567890qwertyuiopasdf", "1", 4)
    c1_vasp = add_custom_tx("1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s", "2", 5)

    edges.append((c1_funding, c1_root))
    edges.append((c1_root, c1_hop1))
    edges.append((c1_hop1, c1_hop2))
    edges.append((c1_hop2, c1_hop3))
    edges.append((c1_hop3, c1_vasp))

    # ---------------------------------------------------------
    # Preset Case 2: Telegram Task Scam Fan-Out (Target: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy)
    # ---------------------------------------------------------
    c2_root = add_custom_tx("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "1", 6)
    c2_funding = add_custom_tx("funding_input_case2", "1", 5)
    c2_vasp = add_custom_tx("3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5", "2", 8)
    edges.append((c2_funding, c2_root))

    for i in range(1, 7):
        mule = add_custom_tx(f"3MuleAddr{i}{'1'*24}", "1", 7)
        edges.append((c2_root, mule))
        edges.append((mule, c2_vasp))

    # ---------------------------------------------------------
    # Preset Case 3: Ransomware Mixer Adjacent (Target: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq)
    # ---------------------------------------------------------
    c3_root = add_custom_tx("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", "1", 10)
    c3_mixer = add_custom_tx("bc1qwasabi20coordinatorpool98234kjhsdf", "1", 11)
    c3_mule = add_custom_tx("bc1qrecombinedmulehop222222222222222", "1", 12)
    c3_vasp = add_custom_tx("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "2", 13)

    edges.append((c3_root, c3_mixer))
    edges.append((c3_mixer, c3_mule))
    edges.append((c3_mule, c3_vasp))

    # ---------------------------------------------------------
    # Preset Case 4: Licit Merchant Control (Target: 1BitPayMerchantCommercialGateway9988)
    # ---------------------------------------------------------
    for c4_addr in ["1BitPayMerchantCommercialGateway9988", "1BitPayMerch498zKqw23NmKLiopQ1298as"]:
        c4_root = add_custom_tx(c4_addr, "2", 20)
        c4_settle = add_custom_tx(f"1LicitSettlementPayroll_{c4_addr[:8]}", "2", 21)
        c4_vault = add_custom_tx(f"1KrakenLicitTreasuryVault_{c4_addr[:8]}", "2", 22)
        edges.append((c4_root, c4_settle))
        edges.append((c4_settle, c4_vault))
        for j in range(12):
            cust = add_custom_tx(f"cust_{c4_addr[:6]}_{j}", "2", 15 + j)
            vendor = add_custom_tx(f"vendor_{c4_addr[:6]}_{j}", "2", 21 + j)
            edges.append((cust, c4_root))
            edges.append((c4_root, vendor))

    # Write files
    with open(out / "elliptic_txs_edgelist.csv", "w", encoding="utf-8") as f:
        f.write("txId1,txId2\n")
        for a, b in edges:
            f.write(f"{a},{b}\n")

    with open(out / "elliptic_txs_classes.csv", "w", encoding="utf-8") as f:
        f.write("txId,class\n")
        for tx in txs:
            f.write(f"{tx},{labels[tx]}\n")

    with open(out / "elliptic_txs_features.csv", "w", encoding="utf-8") as f:
        for tx in txs:
            ts = time_steps.get(tx, 1)
            lbl = labels[tx]
            # Create feature vector with high signal for illicit vs licit
            feats = [ts]
            for feat_i in range(N_FEATURES - 1):
                if feat_i == 0:
                    # Discriminative feature for Random Forest
                    base_val = 3.5 if lbl == "1" else -3.5 if lbl == "2" else 0.0
                    val = base_val + round(rng.gauss(0, 0.3), 4)
                else:
                    val = round(rng.random(), 6)
                feats.append(val)
            f.write(tx + "," + ",".join(map(str, feats)) + "\n")

    # Synthetic mixer list for tests
    mixers = BACKEND / "tests" / "fixtures" / "mixers_test.txt"
    mixers.write_text(
        "# synthetic test mixer list\n"
        "bc1qwasabi20coordinatorpool98234kjhsdf\n"
        + "\n".join(txs[:5]) + "\n", encoding="utf-8")

    print(f"Synthetic fixture written: {len(txs)} txs, {len(edges)} edges -> {out}")


if __name__ == "__main__":
    main()
