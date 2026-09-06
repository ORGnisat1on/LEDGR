# LEDGR Phase Log

Append-only. Newest entries at the bottom. One entry per meaningful state change (phase start, phase done, blocker hit) — not every commit.
See `PROJECT_MEMORY.md` for the current overall project snapshot; this file is the detailed history behind it.

## R0 — baseline (2026-09-03, from build verification report)

- **Summary:** Frontend (React/TS), Express dev server, and API endpoints confirmed working. Forensic engine confirmed to be a deterministic mock: known addresses replay canned cases from `mockCases.ts`, unknown addresses get a hash-fabricated trace, every verdict hardcoded to `confirmed` with fixed scores. `hopDepth` accepted but ignored. Production build (`npm start`) crashes on `fileURLToPath(import.meta.url)`.
- **Still mock / remaining:** everything in `ROADMAP.md` Phases 1–5 (real data ingestion, entity-safe split, real graph construction, real rule heuristics, trained ML model, real correlation logic, real clustering/attribution). See `BACKEND_BUILD_PLAN.md` for the phase-by-phase plan to close this gap.
# LEDGR Phase Log

Append-only. Newest entries at the bottom. One entry per meaningful state change (phase start, phase done, blocker hit) — not every commit.
See `PROJECT_MEMORY.md` for the current overall project snapshot; this file is the detailed history behind it.

## R1 — started (2026-09-04 15:31 UTC)

- **Summary:** Phase R1 started: building Python ingestion module, entity-safe split, and no-leakage verification (dataset acquisition pending Kaggle credentials)
- **Still mock / remaining:** Elliptic CSVs not yet in data/raw/

## R1 — in-progress (2026-09-04 15:42 UTC)

- **Summary:** R1 code complete: Python ingestion module (normalized tx format, integrity check vs published stats), entity-safe split with hub-exclusion safeguard, automated no-leakage verification writing artifacts/split_verification.{json,log}; 15 pytest tests pass on synthetic Elliptic-format fixture
- **Still mock / remaining:** Real Kaggle Elliptic/Elliptic++ CSVs not yet downloaded (needs Kaggle credentials + terms acceptance) - exit criteria unmet until data lands in data/raw/

## R2 — in-progress (2026-09-04 15:42 UTC)

- **Summary:** R2 code complete: NetworkX graph construction with pre-indexed graph_index.pkl artifact; local subgraph extraction with strictly-enforced hop_depth (test proves output size scales with hopDepth); FastAPI service with /health + POST /trace verified live (404 unknown seed, 422 bad hop)
- **Still mock / remaining:** Sanity-check against real Elliptic entities pending R1 dataset; Node server.ts proxy wiring deferred to R7 per plan


## R2 — rolled-back (2026-09-04 15:53 UTC)

- **Summary:** Python backend/ (R1 ingestion + entity split + no-leakage verification, R2 graph construction + FastAPI /trace service, 15 passing tests) deleted at user direction on 2026-09-04; repo cleaned
- **Still mock / remaining:** Back to R0 baseline: analytical engine is still the ForensicEngine mock; all of R1-R9 unbuilt. Phase plan (BACKEND_BUILD_PLAN.md) unchanged - next session restarts from R1

## R3 — started (2026-09-04 15:57 UTC)

- **Summary:** Phase R3 (rule-based signal) started - prerequisite: rebuilding minimal R1/R2 foundation (deleted earlier same day) since the plan hard gates require it before signal work
- **Still mock / remaining:** mixer-address validation set not yet sourced

## R3 — done (2026-09-04 16:06 UTC)

- **Summary:** Rule-based signal (Module 3a) real: peel-chain, rapid fan-out, mixer-adjacency heuristics with per-rule auditable evidence, weighted rule_score (40/30/30, thresholds in config, env-tunable) and rule_flag tiers - no hardcoded scores. R1/R2 foundation rebuilt as prerequisite (ingest, entity split + no-leakage check, graph + hop_depth enforcement). Independent validation script passes all known-pattern + false-positive cases (merchant wallet, isolated wallet, far-from-mixer stay unflagged), report at artifacts/rule_validation.json. FastAPI exposes POST /rules alongside /trace. 29 pytest tests pass; /rules verified live
- **Still mock / remaining:** Real Elliptic CSVs still needed for dataset-scale validation; mixer-address validation set still a synthetic-format placeholder (data/mixers.example.txt) - must be sourced per SCOPE.md

## R7 — done (2026-09-05 13:02 UTC)

- **Summary:** Integration + Production Fix complete. Express `server.ts` proxy routes `/api/trace` and `/api/clusters` linked to Python FastAPI backend (`http://localhost:8000`). Fixed TS2304 variable error in `App.tsx`. Verified end-to-end trace flow returning live pipeline data (`source: "pipeline"`, `available: true`). Verified production build (`npm run build`) and ESM server bundle (`dist/server.mjs`) start cleanly without crashes. All 56 backend tests pass.
- **Still mock / remaining:** R8 testing & hardening and R9 submission packaging.

