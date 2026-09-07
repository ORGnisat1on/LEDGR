# Build & Test Verification Report

**Date:** 2026-09-07 · Node v24 · macOS · Python 3.14

---

## Build checks

| Command | Result | Detail |
|---|---|---|
| `npx tsc --noEmit` | ✅ Pass | Zero type errors |
| `npm run build` | ✅ Pass | Vite: 1687 modules → 341.95 kB JS / 52.85 kB CSS; esbuild server: 9.1 kB ESM bundle |
| Dev server (`npx tsx server.ts`, port 3000) | ✅ Pass | Boots, serves SPA, proxies to Python backend |
| `GET /api/health` | ✅ Pass | `{"status":"ok",...}` |
| `POST /api/generate-brief` without API key | ✅ Pass | Graceful fallback message, HTTP 200 |
| `GET /api/mempool/address/:addr` | ✅ Pass | Proxies to mempool.space; degrades gracefully when offline (`live:false` + note) |

## Test suites

### Node (TypeScript)

**Command:** `npx tsx --test test/pipeline-fallback.test.ts`

| # | Test | Status |
|---|---|---|
| 1 | returns `source:fallback` with NO trace when backend returns service-down envelope | ✅ |
| 2 | returns `source:fallback` when Node server returns HTTP 500 | ✅ |
| 3 | returns `source:fallback` when payload has `source:pipeline` but missing data field | ✅ |
| 4 | returns `source:pipeline` WITH trace when backend responds successfully | ✅ |
| 5 | fallback note is a non-empty descriptive string | ✅ |

**Result:** 5 passed, 0 failed.

### Python (`backend/`)

**Command:** `cd backend && python -m pytest -v`

| Module | Tests | Status |
|---|---|---|
| `test_cluster.py` | 5 | ✅ All pass |
| `test_correlate.py` | 10 | ✅ All pass |
| `test_graph.py` | 4 | ✅ All pass |
| `test_ingest_split.py` | 6 | ✅ All pass |
| `test_learn.py` | 7 | ✅ All pass |
| `test_live_clients.py` | 2 | ✅ All pass |
| `test_live_trace.py` | 12 | ✅ All pass |
| `test_rules.py` | 11 | ✅ All pass |
| `test_service.py` | 9 | ✅ All pass |
| **Total** | **79** | ✅ **79 passed, 0 failed** |

6 deprecation warnings (FastAPI `on_event`, httpx/anyio upstream) — none from project code.

## Pipeline status vs. documentation

| Capability (`SCOPE.md`) | Status |
|---|---|
| Graph ML trained on Elliptic/Elliptic++ (entity-safe split) | ✅ Implemented — `backend/ledgr/learn.py`, validated in `test_learn.py` and `test_ingest_split.py` |
| Rule-based signal (peel chain, fan-out, mixer proximity) | ✅ Implemented — `backend/ledgr/rules.py`, validated in `test_rules.py` (11 tests) |
| Correlation layer (confirmed/watch/none) | ✅ Implemented — `backend/ledgr/correlate.py`, validated in `test_correlate.py` (10 tests including subset property) |
| Live blockchain tracing (Blockstream + BlockCypher) | ✅ Implemented — `backend/ledgr/live_trace.py`, validated in `test_live_trace.py` (12 tests) |
| Wallet clustering (co-spend + change-address heuristics) | ✅ Implemented — `backend/ledgr/cluster.py`, validated in `test_cluster.py` (5 tests) |
| Watchlist mempool monitoring (stretch) | ✅ Live polling via `useMempoolPolling.ts` → `WatchlistMonitor.tsx`, proxied through `server.ts` |
| Bulk tracing / cross-wallet convergence (stretch) | ⚠️ `BulkConvergenceView.tsx` — live pipeline path implemented; falls back to labeled mock data when backend unavailable |
| LLM narrative generation (stretch) | ✅ Implemented, optional, degrades gracefully |
| Complaint intake / report export | ✅ Components implemented (mocked NCRP interface, per scope) |

## Deleted artifacts

- **`test/engine-smoke.ts`** — Deleted. This file tested the former `ForensicEngine` class which generated fabricated traces from address hashes. The `ForensicEngine` class and its import have been fully removed from the codebase; `src/services/analyzer.ts` now calls the live Python pipeline via `runPipelineTrace()` and does not fabricate data. The replacement test suite is `test/pipeline-fallback.test.ts`, which validates the real fallback contract (backend unreachable → honest error, no fabrication).

## Known issues

1. **Production server bundle:** `npm start` (`node dist/server.mjs`) may fail on systems where `import.meta.url` resolution differs between esbuild's ESM output and the Node runtime. Dev mode (`npx tsx server.ts`) is unaffected and is the supported run path.

---

## History

> Prior to Phase R7 (circa 2026-09-03), the frontend used a `ForensicEngine` class (`src/services/analyzer.ts`) that either replayed pre-built traces from `mockCases.ts` or deterministically fabricated trace data from an address hash — no real graph analysis, no Elliptic dataset, no Python backend. Verdicts were hardcoded to `confirmed` with fixed scores. The only test was an ad-hoc smoke script (`test/engine-smoke.ts`). This was replaced during Phases R5–R8 with a live Python pipeline (ingestion, graph construction, rule-based heuristics, learned signal, correlation, clustering, live blockchain tracing) and a proper test suite (79 Python tests + 5 Node tests). The previous TEST_REPORT.md (dated 2026-09-03) documented the mock-era state and is preserved in git history.
