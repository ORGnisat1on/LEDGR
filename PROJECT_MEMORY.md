# LEDGR — Project Memory (read this first)

One-page orientation for any agent/session picking up this project cold. Keep this file short — link out to the detailed docs rather than duplicating them. **Update this file whenever architecture, status, or scope changes** — it's meant to always reflect current reality, not history (history lives in `PHASE_LOG.md`).

---

## What this is

**LEDGR** — SIH26183, "Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses," for Ministry of Home Affairs / I4C. Takes a victim-reported Bitcoin wallet address, traces its transaction graph, flags laundering-pattern activity via two independent signals, and surfaces the likely destination exchange/VASP cluster with a standardized investigation report.

**Deadline:**  **Full doc set:** `README.md`, `SCOPE.md`, `ARCHITECTURE.md`, `DATA.md`, `METHODOLOGY.md`, `ROADMAP.md` (original plan), `BACKEND_BUILD_PLAN.md` (current from-here plan), `PHASE_LOG.md` (history).

## Core design decisions (non-negotiable, don't relitigate these)

- **Two-signal correlation:** a wallet is `confirmed` only when a rule-based heuristic engine AND a learned ML model independently agree. One signal alone → `watch`. Neither → no flag. The correlation layer never invents a flag neither signal raised.
- **Entity-safe evaluation:** all learned-signal train/test splits must be by entity (real-world actor), never by transaction — random transaction splits leak entity identity and invalidate every downstream metric. This is the one methodology point that's a hard gate; get it right before any model work.
- **Confidence-tagged attribution:** named-exchange attribution (`supplementary-source`, lower confidence) is always visually distinct from Elliptic-derived licit/illicit labels (`elliptic-derived`, higher confidence, no name).
- **"Real-time" = query-time speed against a pre-indexed graph**, not continuous blockchain ingestion. Don't build or imply an always-on ingestion pipeline.
- **Scope is Bitcoin-only for MVP.** Ethereum, DeFi, bridges, privacy chains are explicitly out of scope / stretch-only. Bitcoin ≠ Etherscan — use Blockstream.info/BlockCypher for live BTC data.
- **Budget is ₹0, no hosted-LLM dependency for the core detection pipeline.** LLM narrative generation is optional/non-critical only.

## Current status (as of 2026-09-05 — check `PHASE_LOG.md` for anything more recent)

**Real:** React/TypeScript frontend, Express server, API proxy (`/api/trace`, `/api/clusters`, `/api/health`, `/api/generate-brief`, `/api/mempool/address/:addr`), LLM report generation, complaint-intake UI, report/graph visualization UI, bulk-convergence UI. Full Python backend (R1 ingestion & entity-safe split, R2 graph extraction, R3 rule heuristics, R4 trained Random Forest ML signal, R5 correlation verdict engine, R6 entity clustering/attribution). Node server proxies trace queries to Python FastAPI service on port 8000 and maps real pipeline outputs (`source: "pipeline"`, `available: true`). Production build (`npm start` via `dist/server.mjs`) is fully functional. 56 backend tests passing.

**Still mock/missing (fallback only):** Offline case study data (`mockCases.ts`) retained purely as explicit fallback if the Python inference service is offline (labeled as fallback in UI, never presented as pipeline output). Real Kaggle Elliptic CSVs pending download (synthetic dataset currently indexed for local pipeline runs). Next phases: R8 testing & hardening, R9 submission packaging.

## Known traps (don't repeat these)

- Etherscan is Ethereum-only — irrelevant for this Bitcoin-only MVP; use Blockstream.info/BlockCypher.
- Elliptic++'s actor/address extension has historically needed separate access, unlike base Elliptic's direct Kaggle download — verify access early, don't assume it.
- Naive connected-component clustering for entity ID can collapse into one giant component via exchange hub addresses — exclude/cap high-degree hubs before clustering.
- "Confirmed" means two imperfect signals agree, not legal proof — never let report/demo language imply certainty.
- Bitcoin mixer-address ground truth is thinner than the Ethereum-side equivalent (e.g. Tornado Cash lists) — source a validation set early, don't assume one exists.

## How to update this project's shared context

- After finishing or blocking on a phase, run `./scripts/log-phase.sh <phase-id> <status> "<summary>" "<still-mock-or-remaining>"` — appends to `PHASE_LOG.md`.
- If a decision here changes (architecture split, scope, deadline), edit **this file** directly so the next agent reads current reality, not stale context.
