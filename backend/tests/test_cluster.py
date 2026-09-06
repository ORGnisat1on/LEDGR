import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr.cluster import (  # noqa: E402
    TIER_ELLIPTIC,
    TIER_SUPPLEMENTARY,
    TIER_LIVE_UTXO,
    attach_verdicts,
    build_cluster_report,
    build_entity_clusters,
    build_live_clusters,
    load_cluster_report,
    load_exchange_tags,
    save_cluster_report,
    wallet_to_cluster_map,
)
from ledgr.entity_split import build_entities  # noqa: E402
from ledgr.ingest import load_elliptic  # noqa: E402
from ledgr.live_types import InternalTx, TxIn, TxOut  # noqa: E402

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


def test_build_live_clusters_cospend():
    tx1 = InternalTx(
        tx_hash="a" * 64,
        timestamp=1000,
        block_height=100,
        inputs=(TxIn(txid="b"*64, vout=0, address="addr1", amount_sats=100), TxIn(txid="c"*64, vout=0, address="addr2", amount_sats=200)),
        outputs=(TxOut(address="addr3", amount_sats=300),)
    )
    clusters = build_live_clusters([tx1])
    # The graph nodes are addr1, addr2, addr3. Co-spend links addr1 and addr2.
    c = next(c for c in clusters if len(c["members_sample"]) > 1)
    assert c["confidence_tier"] == TIER_LIVE_UTXO
    assert set(c["members_sample"]) == {"addr1", "addr2"}


def test_build_live_clusters_change_address():
    # tx1 sends to addr3, change to addr4 (addr4 is novel globally)
    # tx2 spends from addr3 to addr5 (addr5 novel globally, but tx2 only has 1 output so guard prevents change heuristic)
    tx1 = InternalTx(
        tx_hash="a" * 64,
        timestamp=1000,
        block_height=100,
        inputs=(TxIn(txid="d"*64, vout=0, address="addr1", amount_sats=1000),),
        outputs=(TxOut(address="addr3", amount_sats=700), TxOut(address="addr4", amount_sats=300))
    )
    tx2 = InternalTx(
        tx_hash="b" * 64,
        timestamp=1001,
        block_height=100,
        inputs=(TxIn(txid="a"*64, vout=0, address="addr3", amount_sats=700),),
        outputs=(TxOut(address="addr5", amount_sats=700),)
    )
    clusters = build_live_clusters([tx1, tx2])
    
    addr1_cluster = next(c for c in clusters if "addr1" in c["members_sample"])
    assert "addr4" in addr1_cluster["members_sample"]
    assert "addr3" not in addr1_cluster["members_sample"]
    
    addr3_cluster = next(c for c in clusters if "addr3" in c["members_sample"])
    assert len(addr3_cluster["members_sample"]) == 1
    
    addr5_cluster = next(c for c in clusters if "addr5" in c["members_sample"])
    assert len(addr5_cluster["members_sample"]) == 1


def test_live_clusters_are_live_utxo_tier():
    tx = InternalTx(
        tx_hash="a" * 64,
        timestamp=1000,
        block_height=100,
        inputs=(TxIn(txid="b"*64, vout=0, address="addr1", amount_sats=100),),
        outputs=(TxOut(address="addr2", amount_sats=100),)
    )
    clusters = build_live_clusters([tx])
    for c in clusters:
        assert c["confidence_tier"] == TIER_LIVE_UTXO


# ---------------------------------------------------------------------------
# Adversarial cases (verification task — added 2026-09-06)
# ---------------------------------------------------------------------------


def test_single_output_tx_does_not_trigger_change_heuristic():
    """A transaction with exactly ONE output must never have change detected.

    The guard in build_live_clusters() is ``len(tx_outputs) >= 2``.
    Even if the single output is a fresh (frequency-1) address, no edge
    should be added between the input and that output via the change-address
    heuristic.
    """
    # tx1: addr_in → addr_single (1 output only, addr_single is global freq=1)
    tx1 = InternalTx(
        tx_hash="a" * 64,
        timestamp=1000,
        block_height=100,
        inputs=(TxIn(txid="b" * 64, vout=0, address="addr_in", amount_sats=500),),
        outputs=(TxOut(address="addr_single", amount_sats=500),),
    )
    clusters = build_live_clusters([tx1])

    # addr_in and addr_single must be in SEPARATE singleton clusters — no change edge.
    addr_in_cluster = next(c for c in clusters if "addr_in" in c["members_sample"])
    addr_single_cluster = next(c for c in clusters if "addr_single" in c["members_sample"])

    assert addr_in_cluster["cluster_id"] != addr_single_cluster["cluster_id"], (
        "addr_single must NOT be merged with addr_in via change heuristic "
        "when the tx has only 1 output"
    )
    assert addr_in_cluster["n_wallets"] == 1, "addr_in must be a singleton cluster"
    assert addr_single_cluster["n_wallets"] == 1, "addr_single must be a singleton cluster"


def test_reused_address_disqualified_from_change_heuristic():
    """An address that appears as an output in one tx and as an input in another
    must NOT qualify as a change address: its global_freq across the traced subgraph
    will be >= 2, so ``global_freq[addr] == 1`` is False.

    This tests the widened novelty check described in the build_live_clusters docstring.
    """
    # tx1: addr_source → addr_reused (first touch as output)
    # tx2: addr_reused → addr_dest  (addr_reused is now also an input → global_freq >= 2)
    # tx1 also outputs addr_change which is truly novel (freq=1).
    # Layout:
    #   tx1 inputs: [addr_source]
    #   tx1 outputs: [addr_reused, addr_change]   ← 2 outputs so guard passes
    #   tx2 inputs: [addr_reused]
    #   tx2 outputs: [addr_dest]                  ← 1 output so guard blocks change on tx2
    tx1 = InternalTx(
        tx_hash="a" * 64,
        timestamp=1000,
        block_height=100,
        inputs=(TxIn(txid="b" * 64, vout=0, address="addr_source", amount_sats=1000),),
        outputs=(
            TxOut(address="addr_reused", amount_sats=700),
            TxOut(address="addr_change", amount_sats=300),
        ),
    )
    tx2 = InternalTx(
        tx_hash="c" * 64,
        timestamp=1001,
        block_height=101,
        inputs=(TxIn(txid="a" * 64, vout=0, address="addr_reused", amount_sats=700),),
        outputs=(TxOut(address="addr_dest", amount_sats=700),),
    )
    clusters = build_live_clusters([tx1, tx2])

    # -- Global frequencies --
    # addr_source:  appears as input in tx1           → freq 1
    # addr_reused:  appears as output in tx1 AND input in tx2 → freq 2  ← disqualified
    # addr_change:  appears as output in tx1 only     → freq 1  ← the true change candidate
    # addr_dest:    appears as output in tx2 only     → freq 1

    # addr_change should be linked to addr_source via change heuristic on tx1
    # (tx1 has 2 outputs; addr_reused has freq 2 → disqualified; addr_change has freq 1 → sole candidate)
    source_cluster = next(c for c in clusters if "addr_source" in c["members_sample"])
    assert "addr_change" in source_cluster["members_sample"], (
        "addr_change (freq=1, sole candidate in tx1) must be merged with addr_source"
    )

    # addr_reused must NOT be in the same cluster as addr_source (not a change address)
    assert "addr_reused" not in source_cluster["members_sample"], (
        "addr_reused (freq=2 across subgraph) must be disqualified as a change address"
    )