import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr.graph import build_graph, local_subgraph  # noqa: E402

FIXTURE = BACKEND / "tests" / "fixtures" / "synthetic"


@pytest.fixture(scope="module")
def graph():
    from ledgr.ingest import load_elliptic
    return build_graph(load_elliptic(FIXTURE))


def test_hop_depth_actually_respected(graph):
    """Exit criterion R2: hopDepth measurably changes output size."""
    seed_int = next(n for n, d in graph.nodes(data=True) if d["label"] == 1)
    seed = str(graph.graph["idx_to_tx"][seed_int]) if "idx_to_tx" in graph.graph else str(seed_int)
    sizes = []
    for hop in (1, 2, 4):
        res = local_subgraph(graph, seed, hop_depth=hop)
        assert res["stats"]["max_hop_reached"] <= hop
        sizes.append(res["stats"]["node_count"])
    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1], "hopDepth had no effect on subgraph size"


def test_unknown_seed_raises(graph):
    with pytest.raises(KeyError):
        local_subgraph(graph, "tx_not_present", hop_depth=2)


def test_invalid_hop_depth(graph):
    seed = str(graph.graph["idx_to_tx"][0]) if "idx_to_tx" in graph.graph else next(iter(graph.nodes))
    with pytest.raises(ValueError):
        local_subgraph(graph, seed, hop_depth=0)




def test_subgraph_stats_consistent(graph):
    seed = str(graph.graph["idx_to_tx"][0]) if "idx_to_tx" in graph.graph else next(iter(graph.nodes))
    res = local_subgraph(graph, seed, hop_depth=3)
    assert res["stats"]["node_count"] == len(res["nodes"])
    assert res["stats"]["edge_count"] == len(res["edges"])
    assert res["stats"]["illicit_nodes"] + res["stats"]["licit_nodes"] \
        + res["stats"]["unknown_nodes"] == res["stats"]["node_count"]
