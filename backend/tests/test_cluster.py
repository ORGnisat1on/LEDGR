import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr.cluster import (  # noqa: E402
    TIER_ELLIPTIC,
    TIER_SUPPLEMENTARY,
    attach_verdicts,
    build_cluster_report,
    build_entity_clusters,
    load_cluster_report,
    load_exchange_tags,
    save_cluster_report,
    wallet_to_cluster_map,
)
from ledgr.entity_split import build_entities  # noqa: E402
from ledgr.ingest import load_elliptic  # noqa: E402

FIXTURE = BACKEND / "tests" / "fixtures" / "synthetic"


@pytest.fixture(scope="module")
def ds_ents():
    ds = load_elliptic(FIXTURE)
    return ds, build_entities(ds)


def test_clusters_are_elliptic_derived_and_complete(ds_ents):
    ds, ents = ds_ents
    clusters = build_entity_clusters(ds, ents)
    assert clusters, "fixture must produce clusters"
    assert all(c["confidence_tier"] == TIER_ELLIPTIC for c in clusters)
    # Every wallet appears in exactly one cluster (entity grouping is a partition)
    assert sum(c["n_wallets"] for c in clusters) == len(ds.tx_ids)
    assert all(set(c["label_counts"]) == {"illicit", "licit", "unknown"} for c in clusters)
    # label counts must sum to n_wallets per cluster
    for c in clusters:
        assert sum(c["label_counts"].values()) == c["n_wallets"]


def test_hub_is_singleton_cluster(ds_ents):
    """The hub safeguard must prevent hub-driven mega-clusters (same as the split)."""
    ds, ents = ds_ents
    clusters = build_entity_clusters(ds, ents)
    hubs = ents.loc[ents["is_hub"] == True, "entity_id"].unique()  # noqa: E712
    assert len(hubs) >= 1
    for h in hubs:
        c = next(c for c in clusters if c["cluster_id"] == h)
        assert c["n_wallets"] == 1, "hub must be its own singleton cluster"


def test_member_sample_bounded(ds_ents):
    ds, ents = ds_ents
    clusters = build_entity_clusters(ds, ents, max_members_sample=5)
    big = [c for c in clusters if c["n_wallets"] > 5]
    assert big, "fixture should have clusters larger than the sample"
    for c in big:
        assert len(c["members_sample"]) == 5
        assert c["n_members_truncated"] == c["n_wallets"] - 5


def test_missing_exchange_file_means_no_supplementary(ds_ents, tmp_path):
    ds, ents = ds_ents
    tags = load_exchange_tags(tmp_path / "does_not_exist.txt")
    assert tags == [], "missing list must yield zero tags, never fabricated"
    report = build_cluster_report(ds, ents, exchange_tags=tags)
    assert report["exchange_list_loaded"] is False
    assert report["n_attributed_clusters"] == 0
    assert report["supplementary_matches"] == []


def test_supplementary_match_and_tier_separation(ds_ents, tmp_path):
    ds, ents = ds_ents
    target_wallet = str(ds.tx_ids[0])
    list_file = tmp_path / "exchanges.txt"
    list_file.write_text(
        "# sourced test list (synthetic)\n"
        f"{target_wallet},TestExchange,unit-test-fixture,SG\n"
        "not_in_graph_wallet,OtherExchange,unit-test-fixture,US\n",
        encoding="utf-8",
    )
    tags = load_exchange_tags(list_file)
    assert len(tags) == 2
    report = build_cluster_report(ds, ents, exchange_tags=tags)
    assert report["exchange_list_loaded"] is True
    assert report["n_attributed_clusters"] == 1
    matched = report["supplementary_matches"]
    assert len(matched) == 1 and matched[0]["address"] == target_wallet
    # Attribution tier is supplementary-source; cluster tier stays elliptic-derived
    cluster = next(c for c in report["clusters"] if c["attribution"] is not None)
    assert cluster["attribution"]["confidence_tier"] == TIER_SUPPLEMENTARY
    assert cluster["confidence_tier"] == TIER_ELLIPTIC
    assert cluster["attribution"]["name"] == "TestExchange"
    assert cluster["attribution"]["source_name"] == "unit-test-fixture"
    # The unmatched tag is reported, not silently dropped
    assert len(report["supplementary_unmatched"]) == 1
    assert report["supplementary_unmatched"][0]["name"] == "OtherExchange"


def test_verdict_counts_attach(ds_ents):
    ds, ents = ds_ents
    clusters = build_entity_clusters(ds, ents)
    w2c = wallet_to_cluster_map(ents)
    first_wallet = str(ds.tx_ids[0])
    verdicts = {first_wallet: "confirmed", str(ds.tx_ids[1]): "watch"}
    attach_verdicts(clusters, verdicts, w2c)
    cid = w2c[first_wallet]
    c = next(c for c in clusters if c["cluster_id"] == cid)
    assert c["verdict_counts"]["confirmed"] >= 1
    # Wallets with no verdict simply don't add counts
    assert all(set(c2["verdict_counts"]) == {"confirmed", "watch", "none"} for c2 in clusters)


def test_report_roundtrip(ds_ents, tmp_path):
    ds, ents = ds_ents
    report = build_cluster_report(ds, ents)
    save_cluster_report(report, tmp_path)
    loaded = load_cluster_report(tmp_path / "clusters.json")
    assert loaded["n_clusters"] == report["n_clusters"]
    assert loaded["confidence_tiers"]["elliptic_derived"] == TIER_ELLIPTIC
    assert loaded["confidence_tiers"]["supplementary_source"] == TIER_SUPPLEMENTARY