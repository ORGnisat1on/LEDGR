"""Phase R6 — Clustering / Attribution (ARCHITECTURE.md Module 5).

Entity clustering over verdict-tagged wallets, plus supplementary named-exchange
attribution — with the two confidence tiers kept explicitly separate:

  elliptic-derived      — clusters produced by this pipeline: hub-safeguarded
                          connected-component entities over the Elliptic
                          transaction graph (the same entity definition the
                          entity-safe split uses). Higher confidence.
  supplementary-source  — attribution matched against an externally sourced
                          named-exchange list (hot-wallet lists, community
                          tagging). Lower confidence, attached as separate
                          attribution metadata, never merged into the
                          Elliptic-derived cluster identity.

Honesty rules obeyed here (AGENTS.md / DATA.md):
  - The exchange list is loaded from data/exchanges.txt only if the user sourced
    one; a missing file means zero supplementary matches, never fabricated ones.
  - Clusters are reported with their real label composition (illicit / licit /
    unknown) — no fabricated purity or invented victim/complaint data.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .config import (
    CLUSTER_MEMBER_SAMPLE,
    CLUSTER_REPORT_FILE,
    EXCHANGE_LIST_FILE,
    artifacts_dir,
)
from .ingest import NormalizedDataset

logger = logging.getLogger(__name__)

TIER_ELLIPTIC = "elliptic-derived"
TIER_SUPPLEMENTARY = "supplementary-source"


# ---------------------------------------------------------------------------
# Elliptic-derived entity clusters
# ---------------------------------------------------------------------------


def _label_counts(members: list[str], label_of: dict[str, int]) -> dict[str, int]:
    counts = {"illicit": 0, "licit": 0, "unknown": 0}
    for m in members:
        lbl = label_of.get(m)
        if lbl == 1:
            counts["illicit"] += 1
        elif lbl == 0:
            counts["licit"] += 1
        else:
            counts["unknown"] += 1
    return counts


def build_entity_clusters(
    ds: NormalizedDataset,
    entities_df,
    max_members_sample: int = CLUSTER_MEMBER_SAMPLE,
) -> list[dict]:
    """Group wallets into Elliptic-derived clusters from the entity grouping.

    `entities_df` is the output of ledgr.entity_split.build_entities — the
    hub-safeguarded connected-component entity assignment ([tx_id, entity_id,
    is_hub]). Each entity_id becomes one cluster; hubs are their own singleton
    clusters exactly as in the split (preventing hub-driven mega-clusters).
    """
    label_of = {str(t): int(l) for t, l in zip(ds.tx_ids, ds.tx_labels.tolist())}
    groups: dict[str, list[str]] = {}
    for tx, ent in zip(entities_df["tx_id"].astype(str), entities_df["entity_id"].astype(str)):
        groups.setdefault(ent, []).append(tx)

    clusters: list[dict] = []
    for ent_id in sorted(groups):
        members = sorted(groups[ent_id])
        counts = _label_counts(members, label_of)
        total = len(members)
        clusters.append({
            "cluster_id": ent_id,
            "confidence_tier": TIER_ELLIPTIC,
            "n_wallets": total,
            "label_counts": counts,
            "illicit_fraction": round(counts["illicit"] / total, 4) if total else 0.0,
            "members_sample": members[:max_members_sample],
            "n_members_truncated": max(0, total - max_members_sample),
            "attribution": None,
        })
    logger.info("Built %d Elliptic-derived entity clusters (%d wallets total)",
                len(clusters), sum(c["n_wallets"] for c in clusters))
    return clusters


# ---------------------------------------------------------------------------
# Supplementary named-exchange sources (confidence tier: supplementary-source)
# ---------------------------------------------------------------------------


def load_exchange_tags(path: Path | None = None) -> list[dict]:
    """Load the sourced named-exchange tagging list.

    Expected CSV format (see data/exchanges.example.txt), one entry per line:
        address,name,source,jurisdiction
    Lines starting with '#' are comments. A missing file means ZERO matches —
    supplementary attribution is never fabricated (SCOPE.md / DATA.md).
    """
    path = Path(path) if path else EXCHANGE_LIST_FILE
    if not path.exists():
        logger.warning(
            "Exchange tagging list not found at %s — no supplementary-source "
            "attribution will be attached. Source a list per data/exchanges.example.txt.",
            path,
        )
        return []
    tags: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            logger.warning("Skipping malformed exchange list line %d: %r", i, line)
            continue
        tags.append({
            "address": parts[0],
            "name": parts[1],
            "source": parts[2] if len(parts) > 2 and parts[2] else "unsourced",
            "jurisdiction": parts[3] if len(parts) > 3 and parts[3] else None,
        })
    logger.info("Loaded %d supplementary exchange tags from %s", len(tags), path)
    return tags


def _address_to_txids(ds: NormalizedDataset) -> dict[str, set[str]]:
    """address -> set of tx ids, using the optional Elliptic++ address map."""
    mapping: dict[str, set[str]] = {}
    if ds.address_map is None:
        return mapping
    cols = [c.lower() for c in ds.address_map.columns]
    if "address" not in cols or "tx_id" not in cols:
        return mapping
    addr_col = ds.address_map.columns[cols.index("address")]
    tx_col = ds.address_map.columns[cols.index("tx_id")]
    for addr, tx in zip(ds.address_map[addr_col].astype(str), ds.address_map[tx_col].astype(str)):
        mapping.setdefault(addr, set()).add(tx)
    return mapping


def attach_supplementary(
    clusters: list[dict],
    exchange_tags: list[dict],
    ds: NormalizedDataset | None = None,
) -> tuple[list[dict], list[dict]]:
    """Attach supplementary-source attribution where an exchange-tagged address
    belongs to a cluster (directly, or via the Elliptic++ address map).

    Returns (clusters, supplementary_matches). Attribution is metadata on the
    cluster — the cluster's own confidence tier stays `elliptic-derived`, so the
    two sources remain visibly separate (R6 requirement).
    """
    addr_to_tx = _address_to_txids(ds) if ds is not None else {}
    matches: list[dict] = []
    tag_by_address = {t["address"]: t for t in exchange_tags}

    for cluster in clusters:
        members = set(cluster.get("members_sample", []))
        for addr, tag in tag_by_address.items():
            txs = addr_to_tx.get(addr, set())
            hit = addr in members or bool(txs & members)
            if not hit:
                continue
            cluster["attribution"] = {
                "name": tag["name"],
                "category": "VASP",
                "confidence_tier": TIER_SUPPLEMENTARY,
                "source_name": tag["source"],
                "jurisdiction": tag.get("jurisdiction"),
            }
            matches.append({
                "cluster_id": cluster["cluster_id"],
                "address": addr,
                "name": tag["name"],
                "source": tag["source"],
                "confidence_tier": TIER_SUPPLEMENTARY,
            })
    return clusters, matches

# ---------------------------------------------------------------------------
# Verdict tagging + report assembly
# ---------------------------------------------------------------------------


def wallet_to_cluster_map(entities_df) -> dict[str, str]:
    """tx_id -> cluster_id over the FULL membership (not just the sample)."""
    return {
        str(t): str(e)
        for t, e in zip(entities_df["tx_id"].astype(str), entities_df["entity_id"].astype(str))
    }


def attach_verdicts(
    clusters: list[dict],
    verdict_by_wallet: dict[str, str],
    w2c: dict[str, str] | None = None,
) -> None:
    """Attach per-cluster verdict counts (confirmed / watch / none) in place.

    `verdict_by_wallet` is keyed by wallet (tx id); `w2c` maps wallet ->
    cluster_id (wallet_to_cluster_map). If omitted, wallets are assumed to BE
    cluster ids.
    """
    for c in clusters:
        c["verdict_counts"] = {"confirmed": 0, "watch": 0, "none": 0}
    index = {c["cluster_id"]: c for c in clusters}
    for wallet, verdict in verdict_by_wallet.items():
        cid = w2c.get(wallet, wallet) if w2c else wallet
        c = index.get(cid)
        if c is not None and verdict in c["verdict_counts"]:
            c["verdict_counts"][verdict] += 1


def build_cluster_report(
    ds: NormalizedDataset,
    entities_df,
    exchange_tags: list[dict] | None = None,
    verdict_by_wallet: dict[str, str] | None = None,
    max_members_sample: int = CLUSTER_MEMBER_SAMPLE,
) -> dict:
    """Assemble the full R6 clustering/attribution report."""
    clusters = build_entity_clusters(ds, entities_df, max_members_sample)

    supplementary_matches: list[dict] = []
    if exchange_tags:
        w2c = wallet_to_cluster_map(entities_df)
        addr_to_tx = _address_to_txids(ds)
        for tag in exchange_tags:
            # Direct wallet match, or Elliptic++ address -> txId -> cluster
            target_txs = {tag["address"]} | addr_to_tx.get(tag["address"], set())
            hit_cluster = next((w2c[str(t)] for t in target_txs if str(t) in w2c), None)
            if hit_cluster is None:
                continue
            cluster = next(c for c in clusters if c["cluster_id"] == hit_cluster)
            cluster["attribution"] = {
                "name": tag["name"],
                "category": "VASP",
                "confidence_tier": TIER_SUPPLEMENTARY,
                "source_name": tag["source"],
                "jurisdiction": tag.get("jurisdiction"),
            }
            supplementary_matches.append({
                "cluster_id": hit_cluster,
                "address": tag["address"],
                "name": tag["name"],
                "source": tag["source"],
                "confidence_tier": TIER_SUPPLEMENTARY,
            })

    matched_addresses = {m["address"] for m in supplementary_matches}
    unmatched_tags = [
        t for t in (exchange_tags or []) if t["address"] not in matched_addresses
    ]

    if verdict_by_wallet:
        attach_verdicts(clusters, verdict_by_wallet, wallet_to_cluster_map(entities_df))

    n_attributed = sum(1 for c in clusters if c["attribution"] is not None)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "confidence_tiers": {
            "elliptic_derived": TIER_ELLIPTIC,
            "supplementary_source": TIER_SUPPLEMENTARY,
        },
        "exchange_list_loaded": bool(exchange_tags),
        "n_clusters": len(clusters),
        "n_attributed_clusters": n_attributed,
        "n_wallets": sum(c["n_wallets"] for c in clusters),
        "clusters": clusters,
        "supplementary_matches": supplementary_matches,
        "supplementary_unmatched": unmatched_tags,
        "note": "Clusters are Elliptic-derived (higher confidence). Supplementary "
                "named-exchange attribution is a separate, lower-confidence source "
                "and is never merged into the Elliptic-derived cluster identity.",
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_cluster_report(report: dict, out_dir: Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else artifacts_dir()
    out.mkdir(parents=True, exist_ok=True)
    path = out / CLUSTER_REPORT_FILE
    path.write_text(json.dumps(report, indent=2))
    logger.info("Cluster report saved: %s (%d clusters)", path, report["n_clusters"])
    return path


def load_cluster_report(path: Path | None = None) -> dict:
    path = Path(path) if path else artifacts_dir() / CLUSTER_REPORT_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"Cluster report not found at {path}. Run `python scripts/build_clusters.py` first."
        )
    report = json.loads(path.read_text())
    logger.info("Cluster report loaded: %s (%d clusters)", path, report.get("n_clusters", 0))
    return report