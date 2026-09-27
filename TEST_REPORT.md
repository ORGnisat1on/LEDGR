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

**Command:** `npx tsx --test test/pipeline-sequenced-traces.test.ts` (added 2026-09-26, regression for the "second trace fails" bug)

| # | Test | Status |
|---|---|---|
| 1 | traces two different indexed addresses back-to-back in the same process | ✅ |
| 2 | indexed trace followed by a non-indexed address returns `source:empty` instead of throwing | ✅ |
| 3 | keeps working after an empty answer — a third call in the same process still returns `pipeline` | ✅ |
| 4 | a subgraph without a complete signal set returns `source:incomplete` (no fabricated rule/ML values) | ✅ |
| 5 | the proxy 404 branch (`found:false`) returns `source:empty` with the backend note, never a throw | ✅ |
| 6 | an unmappable response is reported honestly as a fallback naming the failure | ✅ |
| 7 | `mapPipelineEnvelope` returns `fallback` (no trace) when the envelope carries no pipeline data | ✅ |
| 8 | passes the backend note through verbatim for an empty outcome | ✅ |
| 9 | falls back to a descriptive note naming the traced address when the backend sends none | ✅ |

**Result:** 9 passed, 0 failed. Unlike `pipeline-fallback.test.ts`, this suite imports the real `runPipelineTrace` / `mapPipelineEnvelope` from `src/services/analyzer.ts` (no re-implementation) and replays the exact proxy payload shapes captured from the live server, sequentially, in a single process — the reuse pattern a fresh-process-per-case test cannot exercise. No network access is used.

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
2. ~~Live-lookup rate limiting is reported as "address not valid"~~ **FIXED 2026-09-26** (see addendum at the end of this report). Original finding: when Blockstream *and* BlockCypher both answer HTTP 429, `backend/ledgr/live_graph.py` `_default_fetcher` classifies "both 4xx" as `kind='bad-address'`, so `/trace` answers `not-found-on-chain` ("nothing to trace / not recognised") rather than a rate-limit failure. The UI no longer crashes on that response (see the 2026-09-26 `STATUS.md` entry), but the message is misleading. **Status: fixed on 2026-09-26** — HTTP 429 from either source is now classified `rate-limited` (a throttled source is not a validity verdict, so 429 + 404 is `rate-limited`, not `bad-address`) and surfaces as a retryable 503 all the way to the UI. The original finding is retained above for history; the current implementation and its tests are in the 2026-09-26 addendum at the end of this report.
3. **`npx tsc --noEmit` was red at HEAD before 2026-09-26** (`Property 'env' does not exist on type 'ImportMeta'` in four `import.meta.env` call sites, no ambient Vite type declaration in the repo). The same optional-access form is now used everywhere, so lint is green; adding `src/vite-env.d.ts` (`/// <reference types="vite/client" />`) would be the pukka fix if the Vite-typed form is preferred.

---

## History

> Prior to Phase R7 (circa 2026-09-03), the frontend used a `ForensicEngine` class (`src/services/analyzer.ts`) that either replayed pre-built traces from `mockCases.ts` or deterministically fabricated trace data from an address hash — no real graph analysis, no Elliptic dataset, no Python backend. Verdicts were hardcoded to `confirmed` with fixed scores. The only test was an ad-hoc smoke script (`test/engine-smoke.ts`). This was replaced during Phases R5–R8 with a live Python pipeline (ingestion, graph construction, rule-based heuristics, learned signal, correlation, clustering, live blockchain tracing) and a proper test suite (79 Python tests + 5 Node tests; 14 Node tests as of 2026-09-26). The previous TEST_REPORT.md (dated 2026-09-03) documented the mock-era state and is preserved in git history.

---

## 2026-09-26 — Live/arbitrary-address failure-mode hardening (addendum)

**Context:** close-out of the open item in the previous report — a live lookup that both block explorers *rate-limited* (HTTP 429) was reported to the user as a 200 "address not valid / not found on chain". This addendum records the new suites and the current build state.

### Build checks (re-run after the hardening pass)

| Command | Result | Detail |
|---|---|---|
| `npx tsc --noEmit` | ✅ Pass | Zero type errors (new: `proxyOutcome.ts`, `test/pipeline-failure-modes.test.ts`) |
| `npm run build` | ✅ Pass | Vite: 1687 modules → 346.61 kB JS / 53.51 kB CSS; esbuild server bundle: 14.7 kB |
| `cd backend && python -m pytest tests -q` | ✅ Pass | **119 passed**, 6 warnings (was 79) |
| `cd backend && HTTPS_PROXY=http://127.0.0.1:9 python -m pytest tests -q` | ✅ Pass | 119 passed with the network black-holed — proves the suite makes no live network calls |
| `npx tsx --test test/pipeline-failure-modes.test.ts test/pipeline-sequenced-traces.test.ts test/pipeline-fallback.test.ts` | ✅ Pass | 44 tests, 7 suites, 0 fail (was 14 + 5) |

### New Python suites

**`backend/tests/test_address_format.py`** — the local, offline mainnet format gate: P2PKH/P2SH base58, SegWit v0/v1+ bech32, checksum and network validation, plus the empty / overlong / non-ASCII / internal-whitespace / malformed / wrong-network distinctions.

**`backend/tests/test_live_failure_modes.py`** (33 tests) — the single-source classifier (429 → `rate-limited`, timeout → `timeout`, 5xx/connection → `api-error`, 401/403 → `api-error` and *not* a validity verdict); the **two-source** matrix driven through the real `_default_fetcher` with patched client methods (both 429; 429+404 in both orders → `rate-limited`; both 400, 400+404 → `bad-address`; 400+timeout → `timeout`; both 500, 500+400 → `api-error`); failover (one source throttled/hung/500 while the other answers ⇒ **succeeds**; primary 429 + fallback 200-with-zero-txs ⇒ `not-found-on-chain`, not an error); the local gate (a spy fetcher that raises if called, across 7 malformed inputs, and a whitespace-padded real address that must still reach the fetcher); 24 concurrent traces in one process (no cross-talk between malformed / rate-limited / valid); and the service contract (`/trace` returns 503 `{kind, retryable}` for rate-limited/timeout/api-error, 200 for the local format gate, and never phrases an operational failure as a claim about the address).

**`backend/tests/test_service.py`** (2 new) — `/clusters/live` answers a malformed address with a local **400** and makes no network call, and answers a throttled explorer with a structured retryable **503**.

### New Node suite

**`test/pipeline-failure-modes.test.ts`** (24 tests) — exercises the real `mapProxyFailure` / `mapMempoolFailure` (extracted to `proxyOutcome.ts` precisely because `server.ts` starts a listener on import) and the real `mapPipelineEnvelope` / `runPipelineTrace`:

- 404 → honest dataset-miss answer; own `AbortError` → `retryable/timeout`; 429 → `retryable/rate-limited`; 503 + structured detail → the pipeline's own kind; 400/422 → `invalid-input`; 500 → `service-error` (explicitly *not* "unreachable"); no response → `unreachable`.
- No operational envelope carries a trace, and **no operational note contains an address-claiming phrase** ("not a valid", "no on-chain history", …) — an explicit `assertNoAddressClaim` helper enforces this.
- The backend's `invalid-address-format` answer maps to a clear "invalid input" note; a `rate-limited` source inside a 200 envelope (older backend shape) can never read as "empty"; a failed cluster lookup is not reported as "no sourced exchange match", while a completed lookup with no match still is.
- The full interleaved sequence **valid → rate-limited → malformed → valid** through the real `runPipelineTrace` in one process, plus outage-recovery and a non-JSON proxy response.
- Mempool: every failure reason returns `success:false` with a machine-readable `reason` and a note stating the state is UNKNOWN — the field-level difference from a genuine "no transactions" answer (`success:true` + `txs:[]`).

### Two real bugs this pass caught in its own new code

1. `except ... as bs_exc` unbinds the name after the handler, so the two-source message raised `UnboundLocalError`, which was classified as `api-error` and hid the real failure kind. Caught by the pair-classification matrix; now regression-covered.
2. `analyzer.ts` had no guard for an operational failure source arriving inside a 200 pipeline envelope — it still mapped to "empty". Caught by the older-shape fixture test; guard added.

### Still open (unchanged honesty statement)

- ~~Live-explorer success paths are not verified end-to-end~~ **CLOSED 2026-09-27**: with the stack running, `34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo` @ hop 1 traced live for real — `trace.source: live-lookup`, 500 nodes / 241 edges, `max_hop_reached: 2`, rules/labels/verdict all honestly empty, `attribution_status: matched`; the malformed-input gate also confirmed live (`network_attempted: false`); and `/api/mempool/address/34xp4v…` returned a genuine `success:true, txs:0`. The retryable states (`rate-limited` / `timeout` / `api-error`) remain fixture-tested only, since the explorers are currently healthy.
- **No browser-level visual confirmation** in this environment — the new banners and the "check failed (reason) — status unknown" cell are verified at the module/HTTP level plus `tsc` and `vite build`, not by clicking through the SPA.
- Known issue 2 from the previous report ("rate limiting reported as address not valid") is now **fixed**; it is superseded by this addendum. Known issues 1 and 3 are unchanged.

---

## 2026-09-27 — Module 1b addendum: 429/alert-clearing invariant now directly tested

A task reported Module 1b (watchlist mempool monitoring) as removed. **It was not** — `git log --all --diff-filter=D` shows no deletion in any ref, and both `useMempoolPolling.ts` (7,701 B) and `WatchlistMonitor.tsx` (17,870 B) are present in `HEAD`. It was added by `9b9494f` (2026-09-07) and hardened in uncommitted working-tree work from the prior session. Restoring from `HEAD` would have reverted the 429 fix, so nothing was restored.

The real gap was **test coverage**: the 429 invariant lived in the hook body with no test asserting it (existing mempool tests only covered the proxy envelope). The decision point is now a pure, exported `applyMempoolPoll` in `src/hooks/useMempoolPolling.ts` that the hook itself calls, covered by `test/mempool-poll.test.ts`.

| Check | Result |
|---|---|
| `npx tsx --test test/mempool-poll.test.ts` | ✅ 9 passed, 0 failed |
| Negative control: pre-hardening behaviour injected | ✅ 6 of 9 fail (alert cleared + timestamp advanced) — the tests are not vacuous |
| `npx tsc --noEmit` | ✅ zero errors |
| `npx tsx --test test/mempool-poll.test.ts test/pipeline-failure-modes.test.ts test/pipeline-sequenced-traces.test.ts test/pipeline-fallback.test.ts` | ✅ 53 passed / 9 suites, 0 failed (was 44; 9 mempool-specific) |
| `cd backend && python -m pytest tests -q` | ✅ 119 passed (unchanged) |
| `npm run build` | ✅ Vite + esbuild clean |
| Dev server serves the refactored modules | ✅ hook HTTP 200 (31,501 B), WatchlistMonitor HTTP 200 (77,213 B) |
| Live mempool endpoint | ✅ `success:true, 14 txs` for `1A1zP1eP5…` (genuine answer, unchanged by the refactor) |
| Rate-limit math for the current watchlist | ✅ 4 addresses × 30 s = 8 req/min = 11,520 req/day — matches the original figure, within free tier |
| Fabricated alert data in the render path | ✅ none — `mockCases.ts` holds no alert data (removal from `9b9494f` intact); there is no simulated-alert code path anywhere in `src/` |

**Flagged:** `proxyOutcome.ts` (which holds `mapMempoolFailure`, the server-side half of the 429 fix) is still **untracked/uncommitted** — the mempool fix currently has no durable restore point in git history.

---

## 2026-09-27 — Module 1b browser verification addendum (rendering/integration gap)

Code existed and unit tests passed, but the feature never reached the screen. Root causes: (1) the "Mempool" trigger in `Header.tsx` was commented out, so `isWatchlistOpen` was never set and `WatchlistMonitor` always returned `null`; (2) the crash hidden behind that comment was real — three React defects (unstable per-address poller callbacks restarting the 30 s poll loop, a state-building effect that depended on the state it set, and a `useMemo` keyed on that same state), plus a rules-of-hooks early return.

| Check | Result |
|---|---|
| Browser | ✅ Headless Chrome 153 driven over CDP (zero dependencies) against the running dev server |
| Before fix | ✅ Probe: `watchlistTriggerInDom: false`; header buttons = intake / convergence / methodology / report; screenshot shows no Mempool button; console clean (never an error boundary) |
| Button re-enabled, loop not yet fixed | ✅ Reproduced `Error: Too many re-renders…` + `An error occurred in the <WatchlistMonitor> component`; modal did not open |
| After fix — page errors | ✅ **0** |
| After fix — console errors/warnings | ✅ **0** (only Vite/React devtools notices) |
| After fix — visual | ✅ Screenshot: modal open, 4 rows, live `URGENT MEMPOOL BROADCAST INTERCEPTED (1 UNCONFIRMED EVENT)`, INCOMING 0.00003672 BTC to `1A1zP1eP5…` from `14skJjCJ7R2Y…`, other rows `Idle / Monitoring` |
| Loop is gone (network proof) | ✅ 5 `/api/mempool/address/*` requests in a ~28 s window (4 initial + 1 at the 30 s boundary), all HTTP 200 — a live loop would produce hundreds |
| Honest failure state (visual) | ✅ With `Network.setBlockedURLs` on the mempool endpoint, all 4 rows show `CHECK FAILED (unreachable) — STATUS UNKNOWN`, never `Idle / Monitoring` |
| Stale build? | ✅ No — Vite served both modules HTTP 200 throughout; `Header.tsx` was hidden since 2026-09-24, dev server started after all source edits |
| `npx tsc --noEmit` | ✅ clean |
| Node suites | ✅ 53 passed / 9 suites (incl. 9 mempool-poll tests) |
| `cd backend && python -m pytest tests -q` | ✅ 119 passed |
| `npm run build` | ✅ clean |

**Flagged:** no error boundary exists anywhere in the app, so any future render throw blanks the entire page — that is why this class of bug was hard to diagnose. Adding one is out of scope here but worth considering.

---

## 2026-09-27 — Render deployability addendum

Three areas investigated; **two were genuine bugs, one was already correct** (plus a third bug found while investigating it).

| Area | Verdict | Evidence |
|---|---|---|
| Hardcoded port | **Genuine bug, fixed** | `const PORT = 3000` → `Number(process.env.PORT) \|\| 3000`. Render injects `PORT` (documented default 10000). Prod boot with `PORT=5000` → "listening on 5000"; netstat confirmed :5000. |
| `demo_cache.json` path | **Genuine bug, fixed** | `npm start` runs `dist/server.mjs` so `__dirname` = `<root>/dist` → old lookup `<root>/dist/src/data/demo_cache.json`; `ls` proved it does not exist and `dist/` holds only index.html/assets/server.mjs. Cache silently empty in production. Now resolved via 3 candidates; prod boot logged "Loaded demo_cache.json (4 presets)" and `[CACHE HIT]` returned 500 nodes for preset `1A1zP1eP5…`. |
| `NODE_ENV` switch | **Already correct — left untouched** | Prod: `mode=production (serving dist/)`, `GET /` returns the built hashed bundle (`assets/index-Bph5OwlM.js`). Dev: `mode=development (Vite middleware)`. The code's check matches Render, which documents `NODE_ENV=production` as **runtime only**. |
| *(found while investigating)* top-level `vite` import | **Genuine bug, fixed** | The bundle had `import { createServer as createViteServer } from "vite"` at line 6 — a devDependency evaluated at boot, so `npm ci --omit=dev` died with `ERR_MODULE_NOT_FOUND` in a mode that never uses Vite. Now `await import("vite")` inside the dev branch; the built bundle has no top-level vite import. |

**Additional verifications**

| Check | Result |
|---|---|
| `NODE_ENV=production PORT=5000 npm run build` | ✅ clean; bundle no longer statically imports vite |
| Non-preset address in production mode | ✅ `230425980` → `source:pipeline`, `trace.source=elliptic-indexed`, 5 nodes, verdict `watch`; uvicorn log shows /trace /rules /score /verdict 200 |
| Missing demo cache must not crash | ✅ Bundle run outside the repo (node_modules junction, unlinked with `rmdir` afterwards): warns with all 3 tried paths, `demo_cache entries=0`, **still listens**; preset address then returned a real `live-lookup` (85 nodes) with 0 cache hits |
| Any other hardcoded port in code | ✅ none — only the intentional `\|\| 3000` fallback and one test comment |
| `npx tsc --noEmit` | ✅ clean |
| Node suites | ✅ 53 passed / 9 suites |
| `cd backend && python -m pytest tests -q` | ✅ 119 passed |
| Dev mode after making the import dynamic | ✅ `mode=development (Vite middleware)`, Vite boots |

**New file:** `DEPLOY.md` — env vars for both Render services (with `PORT`/`NODE_ENV` marked "do not set"), the demo-cache path logic, and a copy-pasteable production-mode smoke test.

**Not verifiable locally:** whether Render applies *dashboard-set* env vars at build time (docs confirm the default `NODE_ENV` is runtime-only but not the user-set case); git-LFS artifact pulls on Render; cold-start timing.
