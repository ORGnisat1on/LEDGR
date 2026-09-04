# LEDGR — Real Backend Build Plan

**Baseline:** Sept 3 2026 build verification report — frontend/API shell real, analytical engine (`ForensicEngine`) fully mocked.
**Today:** Sept 4 2026. **Deadline:** Sept 20 2026. **Runway:** 16 days.
**Goal:** replace the mock engine with the real pipeline `ROADMAP.md`/`ARCHITECTURE.md` describe, without breaking the existing frontend/API contract.

This plan supersedes `ROADMAP.md`'s Phases 1–7 for scheduling purposes (those assumed a clean start; you're now starting the *real* pipeline from an existing UI/API shell). `ROADMAP.md` stays the reference for *what* each module must do — this plan is the reference for *what's left and in what order*, from today.

---

## Architecture decision (make this first, day 1)

The docs specify Python + NetworkX/PyTorch Geometric for graph construction and ML; the shipped backend is Node/Express. Don't port graph ML to TypeScript — it's not necessary and burns days you don't have.

**Recommended split:**
- **Python side (offline + a small inference service):** data ingestion, entity-safe split, graph construction, rule heuristics, RF/GNN training. Runs mostly offline, producing versioned artifacts (trained model, validated heuristic thresholds, a pre-indexed graph/lookup structure). A thin **FastAPI** service exposes one or two endpoints (`POST /trace`, `POST /score`) for query-time inference against those artifacts.
- **Node side (unchanged contract):** `server.ts` keeps its existing routes (`/api/generate-brief`, `/api/mempool/...`, and the trace endpoint the frontend already calls) but proxies the trace/score logic to the FastAPI service instead of calling `ForensicEngine`'s mock. The frontend doesn't need to change.

This keeps your working UI and API surface intact and confines the real engineering risk to one new, isolated Python service.

---

## Phase R1 — Real Data Foundation (Days 1–3, Sept 4–6)

- Acquire Elliptic + Elliptic++ from Kaggle; verify integrity against published stats (203,769 tx / 234,355 edges / 822,000 addresses). Confirm Elliptic++ actor/address access works today — it's the one dependency with real access risk (`DATA.md`). Fallback: derive address-level structure from base Elliptic alone if blocked.
- Build the Python ingestion module: normalized transaction record format, static-dataset loader.
- Implement the entity-based split (entity ID where labeled, connected-component proxy with the hub-node exclusion safeguard otherwise — `METHODOLOGY.md` §1).
- Implement and run the automated no-leakage verification check; log its result.
- **Replaces:** nothing yet (net-new — this layer doesn't exist at all currently).
- **Exit criteria:** Elliptic++ loads into normalized format; leakage-free entity split produced with a logged verification result.

## Phase R2 — Graph Construction Service (Days 4–5, Sept 7–8)

- Build local subgraph extraction (NetworkX/PyG `Data` object) around a given wallet address, bounded hop-depth parameter — actually respected this time (current mock ignores it).
- Stand up the FastAPI service skeleton; wire one working endpoint (`POST /trace` → subgraph + basic stats) that the Node backend can call.
- Sanity-check subgraph construction against a handful of known Elliptic entities.
- **Replaces:** the fixed-size, hash-fabricated trace in `analyzer.ts`.
- **Exit criteria:** given any wallet address in the dataset, the service returns its real local subgraph; `hopDepth` measurably changes output size.

## Phase R3 — Rule-Based Signal (Days 6–7, Sept 9–10)

- Implement the three heuristics for real: peel chains, rapid fan-out, mixer-adjacent hops.
- Source a Bitcoin mixer-address validation set (thin ground truth — start early, per `SCOPE.md`).
- Validate each heuristic independently against synthetic/literature test cases; check false-positive rate against clearly-licit wallets (e.g. confirm the genesis address no longer comes back flagged).
- **Replaces:** the hash/modulo-based flag selection currently standing in for this module.
- **Exit criteria:** rule engine flags wallets with per-heuristic, auditable output (which rule fired and why) — no hardcoded scores.

## Phase R4 — Learned Signal (Days 8–10, Sept 11–13)

- Train the random forest baseline on Elliptic's 166 features, entity-safe split. This is the **committed MVP learned signal** (`ROADMAP.md` Phase 4 decision) — not the GNN.
- Evaluate honestly: recall/precision/F1 on the illicit class, logged per `METHODOLOGY.md` §2.
- Time-boxed GNN attempt **only if** the baseline is trained, evaluated, and logged by day 9 — stop by day 10 regardless of result.
- **Replaces:** the hardcoded `mlScore: 0.942` / `mlPrediction: 'illicit'`.
- **Exit criteria:** real per-wallet risk scores, evaluated on held-out entities, metrics logged (not just claimed).

## Phase R5 — Correlation Layer (Days 11, Sept 14)

- Implement real confirmed/watch/none logic combining R3 and R4 outputs, per the threshold defined and logged in `METHODOLOGY.md` §4.
- Verify the confirmed set is a strict subset of both individual flagged sets, and that "neither fires" never gets upgraded to a flag.
- **Replaces:** the always-`confirmed` verdict.
- **Exit criteria:** verdicts vary honestly by wallet (confirmed/watch/none all reachable) with contributing-signal traceability.

## Phase R6 — Clustering / Attribution (Days 12–13, Sept 15–16)

- Entity clustering over verdict-tagged wallets (Elliptic-derived, higher confidence).
- Wire in supplementary named-exchange sources (hot-wallet lists, community tagging), tagged `supplementary-source`, kept visibly separate from `elliptic-derived`.
- Connect `BulkConvergenceView.tsx` to real cluster output instead of mock data.
- **Replaces:** mock attribution/clustering.
- **Exit criteria:** wallet clusters produced with confidence tiers correctly attached and visibly distinguishable in the UI.

## Phase R7 — Integration + Production Fix (Day 14, Sept 17)

- Point `server.ts`'s trace endpoint at the FastAPI service; remove the `ForensicEngine` mock path from the live flow (keep `mockCases.ts` only as an explicitly-labeled offline fallback if the Python service is down, never silently).
- Fix the production crash: `fileURLToPath(import.meta.url)` returning `undefined` in the esbuild CJS bundle — either switch the production entry to an ESM-compatible build target or resolve the path with a CJS-safe equivalent (`__dirname` shim) instead of `import.meta.url`.
- **Exit criteria:** `npm start` boots and serves the app; a wallet entered in the dashboard runs the real pipeline end to end.

## Phase R8 — Testing & Hardening (Day 15, Sept 18)

- Expand beyond the smoke test: known-licit wallets, isolated wallets, very large subgraphs, wallets with no illicit signal.
- Confirm every `SCOPE.md` boundary is reflected accurately in the UI/report copy — no leftover "100% operational" or similar overclaiming.
- Fix issues found; no new features at this stage.

## Phase R9 — Submission Packaging (Day 16, Sept 19–20)

- Final README pass reflecting the real (not mocked) pipeline status.
- Demo script, submission artifacts per SIH requirements.
- Freeze scope. Submit.

---

## Hard gate (unchanged from ROADMAP.md)

Don't start R4 before R1's entity-safe split is verified. Don't start R5 before R3 and R4 both produce real, independent output. A late system with a defensible pipeline beats an on-time one with a mock behind real-looking UI.
