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

---

---

## 2026-09-05 — Cline (verification agent) — temporal-leakage fix verified + hardening fixes

**What changed:**
- `backend/requirements.txt` — added `requests>=2.31` (ghost-dependency fix: `blockstream_client.py` / `blockcypher_client.py` import it; live BTC tracing is MVP per SCOPE.md and must fail loudly if missing, not degrade)
- `backend/tests/test_rules.py` — `fanout_graph()` fixture bumped 8 → 11 outputs to match the tuned `FANOUT_MIN_OUT=10` (was silently diverged; `test_run_rules_composite_score_and_tiers` could never pass at current config). Fixture docstring now warns against future divergence. Broad sweep found no other stale-threshold fixtures (all other detector tests parameterize thresholds explicitly; `test_correlate.py`/`test_service.py`/`test_cluster.py` are threshold-agnostic or match current config).
- `backend/ledgr/entity_split.py` — `verify_no_leakage()` now **enforces the span-0 property** (METHODOLOGY §1 step 2): every entity's txs must fall in one time step; violations are logged to `split_verification.json` on every run and raise a hard `RuntimeError` under the strict default. Only the two synthetic-fixture unit tests (`test_ingest_split.py`, `test_learn.py`) opt out with documented justification (random fixture legitimately spans steps). Real-data run: 14,270/14,270 entities span-0, PASS.
- `METHODOLOGY.md` — §1 step 2 rewritten to describe the now-real enforcement; concept-drift section's "cleanly places the train/val boundary at time-step 42" qualified (clean per *entity*; adjacent splits share boundary steps 42 and 45 at the raw step level).
- `implementation_plan.md` — marked HISTORICAL ARTIFACT: its `HUB_DEGREE_THRESHOLD=1000`, `module1/` `EntitySplit`, actor mapping, and stratification no longer match code (live: 50, `backend/ledgr/entity_split.py`).

**Independently verified (by direct re-execution, not prior summaries):** time-respecting split confirmed live (train ts 1–42 / val 42–45 / test 45–49, zero overlap, 100% entities span-0); RF baseline reproduced exactly (TP=2/FN=114/TN=2391/FP=2, illicit recall 0.017241, precision 0.500000, 2,509 labeled of 14,084 test txs, 116 illicit); rule-vs-ML union recall 4/116 = 0.0345 with rule engine adding exactly 2 peel-chain catches beyond ML's 2.

**Verified how:**
```
$ python3 -m pytest tests -q            # system python: 58 passed
$ # fresh venv from backend/requirements.txt only:
58 passed, 6 warnings in 10.30s          # genuinely clean venv, incl. test_live_clients.py
```

**Still open / unverified:**
1. ROADMAP.md contains no entry for the temporal-leakage fix or the honesty-layer UI proposal — nothing to mark resolved there yet; tracking location needs a human decision.
2. Honesty-layer UI implementation is a separate, not-yet-started task.
3. Mixer-address validation set still a format placeholder (`data/mixers.txt` absent → `mixer_adjacent` cannot fire; union-recall numbers above computed under that condition).

---

## 2026-09-05 — Antigravity (implementation agent) — Phase R7 Integration & Production Fix

**What changed:**
- `src/App.tsx` [MODIFIED] — Fixed TS2304 bug in `handleTraceAddress` by adding `const result = outcome.trace;` definition before evaluating verdict and updating watchlist.
- `server.ts` [VERIFIED] — Node/Express proxy endpoints `/api/trace` and `/api/clusters` verified communicating with Python FastAPI inference backend (`http://localhost:8000`).
- `dist/server.mjs` [VERIFIED] — Production build compiled cleanly with `npm run build` and booted without CJS/ESM module crashes.

**Claimed complete:**
- Express server proxying to FastAPI backend with graceful fallback.
- Live end-to-end trace flow returning real pipeline output (`source: "pipeline"`, `available: true`).
- 56 Python backend unit tests passing cleanly.
- TypeScript build check (`tsc --noEmit`) passing with 0 errors.

**Verified how:**
```
$ backend/.venv/Scripts/python -m pytest backend/tests/
56 passed in 3.65s

$ cmd /c npx tsc --noEmit
Passed (0 errors)

$ cmd /c npm run build
dist/server.mjs generated cleanly

Live API Test:
POST http://localhost:3000/api/trace -> returned source: "pipeline", available: true, data: { address, trace, rules, score, verdict }
GET http://localhost:3000/api/clusters -> returned source: "pipeline"
```

**Still open / unverified:**
- Real Kaggle dataset download pending user credentials; synthetic dataset currently used for local pipeline verification.
- Phase R8 testing & hardening scheduled next per `BACKEND_BUILD_PLAN.md`.


---

## 2026-09-06 — Cline (implementation agent) — Phase R8 Testing & Hardening

**What changed:**
- `backend/scripts/hardening_check.py` [NEW] — R8 hardening check over the real ingested dataset (service in-process, real graph index + real model); writes `artifacts/hardening_report.json`. Covers: known-licit, known-illicit, isolated/low-degree, hub subgraph boundedness, out-of-dataset behavior, R5 correlation invariant. Explicitly NOT a model evaluation — reports no accuracy/recall.
- `src/components/MethodologyModal.tsx` [MODIFIED] — honesty-layer UI per ROADMAP R6.5 spec: replaced stale pre-correction metrics (89.4%/81.2%/0.851/78.6% from the banned random split) with the honest time-respecting-split numbers (illicit recall 1.7% / precision 50.0% / F1 0.033; accuracy 95.4% secondary-only); §1 split description corrected to time-respecting 70/15/15 with span-0 enforcement (14,270/14,270 PASS); confirmed definition corrected to P(illicit) ≥ 0.5 (LEARNED_FLAG_THRESHOLD); added concept-drift limitation callout and out-of-dataset `classified: false` disclosure.
- `src/App.tsx` [MODIFIED] — standing footer honesty banner (validated-regime + "confirmed ≠ proof of guilt").
- `artifacts/model_eval.json` [REGENERATED] — prior on-disk artifact still carried the 0.9366-recall leakage-signature numbers; re-trained with the corrected split (recall 0.017 / precision 0.500 / F1 0.033).
- `backend/README.md` [MODIFIED] — added hardening_check to the Run section.

**Verified how:**
```
$ backend/.venv/Scripts/python -m pytest backend/tests -q      # 59 passed
$ npx tsc --noEmit                                             # 0 errors
$ backend/.venv/Scripts/python backend/scripts/hardening_check.py
  all 6 checks PASS (see artifacts/hardening_report.json)
```

**Still open / unverified:**
- Phase R9 submission packaging (README pass, demo script, scope freeze).
- Mixer-address validation set still a placeholder (`data/mixers.txt` present but unsourced) — `mixer_adjacent` remains silent on real data.

---

## 2026-09-06 — Cline (implementation agent) — Phase R9 Live Address Tracing

**What changed:**
- `backend/ledgr/live_graph.py` [NEW] — R9 live tracing: Blockstream-primary/BlockCypher-fallback fetching (reuses Module-1 clients), pure `build_live_graph` over fetched summaries, bounded orchestrator (`trace_live`) with named caps in config (`LIVE_MAX_TXS_PER_ADDRESS=50`, `LIVE_MAX_COUNTERPARTY_FETCHES=25`, `LIVE_MAX_NODES=500`, `LIVE_TIME_STEP_SECONDS`), `LiveSourceError` with distinct `kind` (api-error vs bad-address), toggle `live_tracing_enabled()` (LEDGR_LIVE_TRACING env).
- `backend/ledgr/service.py` [MODIFIED] — /trace, /rules, /verdict: indexed fast path then live fallback; response `source` field (elliptic-indexed | live-lookup | not-found-on-chain); learned signal honestly unavailable on live wallets (`ml_signal` note); correlation cap enforced in code (live verdicts can never be confirmed).
- `backend/ledgr/blockstream_client.py` [MODIFIED] — added `get_address_stats()` (cheap has-history pre-check support).
- `backend/ledgr/config.py` [MODIFIED] — R9 named constants + toggle.
- `backend/tests/test_live_trace.py` [NEW] — 12 fixture-based tests: high-tx cap, low-tx, nonexistent, api-failure, bad-address, correlation cap, service-level live paths. No live network in CI.
- `backend/scripts/hardening_check.py` [MODIFIED] — pins LEDGR_LIVE_TRACING=0 so its out-of-dataset 404 assertions stay deterministic/offline.
- `backend/README.md` [MODIFIED] — live-tracing documented.

**Verified how:**
```
$ backend/.venv/Scripts/python -m pytest backend/tests -q   # 72 passed
$ # live smoke (single addresses, demo-time per SCOPE.md):
POST /trace 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -> live-lookup, real counterparties
POST /trace 34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo -> live-lookup (Binance cold wallet)
POST /verdict 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -> capped at watch ceiling, learned classified:false
POST /trace <invalid address> -> 200 not-found-on-chain (honest, not a 503)
POST /trace 232629023 -> elliptic-indexed fast path unchanged
```

**Still open / unverified:**
- Phase R10 submission packaging (README pass, demo script, scope freeze).
- Live fetches are Blockstream free-tier: caps keep a single trace well under rate limits, but bulk tracing of many live addresses in one session would violate SCOPE.md and is not supported.

---

## 2026-09-06 — Cline (audit agent) — full R1–R9 audit: 3 findings, fixed

**Audit method:** raw test run + re-executed every phase's claim against real code/data (adversarial hop-cap check on 20 real seeds; heuristics run on the real 203,769-tx graph; model predictions diffed; 200-wallet correlation invariant sweep; cluster-connectivity spot-check; test suite run with network proxied to a dead port to prove no live calls in CI).

**Findings (all fixed in this commit):**
1. **R1 — test suite clobbered the real-data leakage artifact.** `tests/test_learn.py`'s `split_ds` fixture called `verify_no_leakage()` without redirecting `artifacts_dir()`, so every pytest run overwrote `artifacts/split_verification.json` with synthetic-fixture numbers (478 entities, `time_span_ok: false`) — the on-disk R6.5 evidence was a lie at audit time. Fixed: fixture now redirects to a throwaway dir (verified: artifact mtime unchanged across a full test run); real-data artifact regenerated (14,270/14,270 entities span-0, leakage_free=true, enforced).
2. **R8 — hardening check was broken.** `scripts/hardening_check.py` referenced `os` without importing it (broke when R9 added the live-tracing toggle) — it crashed instead of running the 6 checks. Fixed; all 6 checks PASS again.
3. **R6 — `data/exchanges.txt` contains likely-fabricated entries** (e.g. `1BitPayMerchantCommercialGateway9988` with unverifiable "Public VASP Hot-Wallet Registry" sourcing). Zero supplementary matches means no fabricated attribution reaches output today, but per SCOPE/AGENTS sourcing rules this list should be treated as unsourced and replaced with a genuinely sourced one before the R10 demo. NOT silently deleted (user data) — flagged here.

**Verified clean:** R2 hop_depth is a hard cap (adversarially recomputed distances on real graph); R3 heuristics find 55,110 peel-chain / 530 fan-out nodes on the real graph with structure-derived evidence; R4 scores derive from the real RF (per-wallet scores differ; unknown wallet `classified:false`); R5 confirmed⊆both-flagged invariant holds on a 200-wallet real sweep (0 violations); R6 cluster members are genuinely one connected component, tiers separate; R7 proxy composes real pipeline output with labeled fallback only on failure; R9 tests never touch the live network (72 passed with dead proxy).
