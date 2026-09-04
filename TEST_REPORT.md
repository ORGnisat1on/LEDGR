# Build Verification Report

**Date:** 2026-09-03 · Node v24.19.0 · Windows

## ✅ What works

| Check | Result |
|---|---|
| `npm install` | ✅ Clean install, all 18 deps resolve |
| `npm run lint` (`tsc --noEmit`) | ✅ Zero type errors |
| `npm run build` (Vite client bundle) | ✅ 1685 modules, 340 kB JS / 49 kB CSS |
| Dev server (`npx tsx server.ts`, port 3000) | ✅ Boots, serves SPA (HTTP 200) |
| `GET /api/health` | ✅ `{"status":"ok",...}` in dev |
| `POST /api/generate-brief` without API key | ✅ Graceful fallback message, HTTP 200 |
| `GET /api/mempool/address/:addr` | ✅ Graceful degradation (`live:false` + note) |
| ForensicEngine case-study lookup | ✅ All 3 indexed addresses return full traces |
| ForensicEngine synthetic path | ✅ Deterministic (identical output for same address) |
| Complaint override (scamCategory/amount) | ✅ Correctly drives typology + mixer heuristic |
| `hopDepth` parameter | ✅ Echoed through to result |

## ❌ What doesn't work

1. **Production server is broken.** `npm start` (`node dist/server.cjs`) **crashes instantly** with `ERR_INVALID_ARG_TYPE` — `fileURLToPath(import.meta.url)` yields `undefined` in the esbuild CJS bundle (the build warned about exactly this). The production path has never worked as shipped. Dev mode is unaffected (tsx runs ESM).
2. **The core "detection pipeline" is a mock, not real analysis.** `src/services/analyzer.ts` does **no real graph analysis**: it (a) replays pre-built traces from `mockCases.ts` for known addresses, or (b) **fabricates** a trace deterministically from a hash of the address string. It never touches the Elliptic dataset or any block-explorer API.
3. **Verdicts are hardcoded.** Every trace returns `verdict:'confirmed'`, `ruleScore:94/96/98`, `mlScore:0.942`, `mlPrediction:'illicit'` — violating `METHODOLOGY.md` §4 (confirmed requires both signals independently flagging) and `ARCHITECTURE.md` Module 4 ("never invents evidence"). A known-licit address (e.g. the genesis address `1A1zP1...`, Satoshi's wallet) comes back **"confirmed illicit."**
4. **`hopDepth` is not actually respected** in graph construction — requesting 5 hops still yields 6 edges; subgraph size is fixed by the template, not the parameter.
5. **None of the documented data/ML pipeline exists in this repo.** No Python, no NetworkX/PyTorch Geometric, no Elliptic dataset, no entity-based split, no model training — Phases 1–5 of `ROADMAP.md` are unbuilt. Only a simulation of Modules 3a–6 exists.
6. **No test framework** (`package.json` has no test script); this smoke test lives in `test/engine-smoke.ts` (run with `npx tsx test/engine-smoke.ts`).

## Doc-vs-build deltas (`SCOPE.md`)

| Claimed | Reality |
|---|---|
| Graph ML trained on Elliptic/Elliptic++ | ❌ Hardcoded score (0.942) |
| Rule-based signal (3 heuristics) | ⚠️ Present but flag selection is hash/modulo-based, not heuristic-derived |
| Correlation layer (confirmed/watch/none) | ❌ Always `confirmed`; no watch/none path exercised |
| Watchlist mempool monitoring (stretch) | ⚠️ UI component exists; live API proxy degrades gracefully |
| Bulk tracing / cross-wallet convergence (stretch) | ⚠️ `BulkConvergenceView.tsx` exists against mock data |
| LLM narrative generation (stretch) | ✅ Implemented, optional, degrades gracefully |
| Report export / intake modal | ✅ Components implemented (mocked, per scope) |

## Bottom line

The **frontend demo, dev server, and all API endpoints work**; the **production build does not run**; and the **forensic engine is a deterministic simulation**, consistent with the project being at the "Phase 7 visualization mock" stage while the roadmap's data/ML phases (1–5) remain unbuilt. The docs are honest about mock status ("mocked complaint intake", "no live integration") but the UI's "100% operational" classification claims are not backed by real analysis code.
