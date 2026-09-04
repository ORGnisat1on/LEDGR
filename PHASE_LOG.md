# LEDGR Phase Log

Append-only. Newest entries at the bottom. One entry per meaningful state change (phase start, phase done, blocker hit) — not every commit.
See `PROJECT_MEMORY.md` for the current overall project snapshot; this file is the detailed history behind it.

## R0 — baseline (2026-09-03, from build verification report)

- **Summary:** Frontend (React/TS), Express dev server, and API endpoints confirmed working. Forensic engine confirmed to be a deterministic mock: known addresses replay canned cases from `mockCases.ts`, unknown addresses get a hash-fabricated trace, every verdict hardcoded to `confirmed` with fixed scores. `hopDepth` accepted but ignored. Production build (`npm start`) crashes on `fileURLToPath(import.meta.url)`.
- **Still mock / remaining:** everything in `ROADMAP.md` Phases 1–5 (real data ingestion, entity-safe split, real graph construction, real rule heuristics, trained ML model, real correlation logic, real clustering/attribution). See `BACKEND_BUILD_PLAN.md` for the phase-by-phase plan to close this gap.
