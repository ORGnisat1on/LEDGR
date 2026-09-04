# STATUS.md — SIH26183

Living document. Each agent appends a dated entry after finishing a task.
Never overwrite a previous entry. Per AGENT_ROUTING.md §4 template.

---

## 2026-09-04 — Antigravity (implementation agent) — Phase 1 Entity Split

**What changed:**
- `module1/entity_split.py` [NEW] — complete implementation of METHODOLOGY.md §1
- `module1/test_entity_split.py` [NEW] — 24-test suite per approved plan
- `module1/entity_split_fixtures/` [NEW] — 5 files: elliptic_txs_classes.csv (55 txIds), elliptic_txs_edgelist.csv (26 edges + hub), elliptic_txs_features.csv, actor_mapping_fixture.csv (3 actors/9 txIds), _fixture_ids.py (test lookup helper)
- `module1/requirements.txt` [MODIFIED] — added `networkx>=3.2.0` and `scikit-learn>=1.4.0` with comments

**Claimed complete:**
- Entity-based 70/15/15 train/val/test split per METHODOLOGY.md §1
- Hub-node safeguard (degree threshold = HUB_DEGREE_THRESHOLD = 1000; tested with fixture threshold = 5)
- Actor-id mapping discovery at runtime (no assumed filename/columns); ambiguous → connected_component_proxy fallback; warning logged
- Connected-component proxy entity identification (conservative; documented as proxy, not proof)
- Conservative entity label rule: any illicit → illicit; else any licit → licit; else unknown
- Split membership vs. supervised training eligibility distinction: documented in EntitySplit, not enforced
- Leakage verification (verify_no_leakage()) called inside build_entity_split(); leakage_verified=True on return
- Time-order diagnostic: diagnostic only, never alters split; time_order_ok=None if unavailable
- Named constants: HUB_DEGREE_THRESHOLD, TRAIN_FRACTION, VAL_FRACTION, TEST_FRACTION, RANDOM_SEED — no bare literals
- All audit metadata in EntitySplit: split_method, n_hub_nodes, hub_node_ids, leakage_verified, time_order_median, time_order_ok, split_stats

**Verified how:**
```
$ python3 -m pytest module1/test_entity_split.py -v
24 passed in 0.72s

$ python3 -m pytest module1/ --ignore=module1/test_entity_split.py -v
72 passed in 1.38s

$ python3 -m pytest module1/ -v
96 passed in 2.04s
```
All 96 tests pass. No regressions in the existing 72 Module 1 tests.
Existing `data_ingestion/test_fixtures/` was not touched.

**Still open / unverified:**
1. **Real Elliptic++ actor mapping schema is unknown.** The runtime discovery heuristic (two-column CSV, one column containing "actor", one containing "tx"/"addr"/"id") was designed against the fixture. If the real file's column names don't match this pattern, it will fall back to connected_component_proxy. This fallback behavior is correct per the plan, but whether it triggers unnecessarily on real data cannot be verified until the dataset is downloaded. Logged as WARNING if triggered.
2. **Hub-node safeguard at threshold=1000 is untested.** The fixture uses threshold=5 (hub has degree=5). No real Bitcoin transaction graph is available. The production threshold=1000 is documented in METHODOLOGY.md and set as a named constant; its fitness for the real Elliptic graph requires runtime validation.
3. **Connected-component entity proxy with real data.** The real Elliptic edgelist has 203,769 edges. Whether the giant-component collapse problem is actually prevented by threshold=1000 can only be confirmed once the real data is available. The test proves the code path works correctly at threshold=5.
4. **Stratification balance on the real dataset.** With ~46K txIds and severe class imbalance (approx 2% illicit), stratification may encounter edge cases not present in the balanced fixture.
5. **Actor mapping covers a subset of txIds.** The plan's "mixed" split_method path (some txIds via actor, rest via proxy) is tested with the fixture but the actor-to-txId coverage ratio on real Elliptic++ is unknown. If actor coverage is very high, the "mixed" path reduces to "actor_id"; if very low, to "connected_component_proxy".

**Blocking questions, if any:**
- None. Phase 1 entity split implementation is ready for independent verification per AGENT_ROUTING.md §3.
- Do NOT mark Phase 1 complete in ROADMAP.md — that requires a different agent's independent review (AGENT_ROUTING.md §3).
