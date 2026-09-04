# Roadmap

**Submission deadline:** 20 September 2026
**Kickoff:** ~24 August 2026 (date of this document)
**Total runway:** ~27 days

Milestones are scoped against `SCOPE.md`'s MVP list only. Stretch items (Ethereum, expanded heuristics, LLM report text, watchlist monitoring, bulk wallet tracing) are not scheduled below — they're only attempted if a milestone finishes early with runway to spare. The one exception is the time-boxed GNN attempt folded into Phase 4 below, since it's cheapest to try immediately after the baseline while the same context is fresh, rather than deferred to Phase 9.

---

## Phase 1 — Data Pipeline (Days 1–5, ~Aug 24–28)

- Acquire Elliptic + Elliptic++ from Kaggle; verify integrity against published dataset stats (203,769 transactions / 234,355 edges / 822,000 addresses). **Do this first, day 1** — Elliptic++'s actor/address extension has historically needed separate author access rather than a direct download (see `DATA.md`), and Modules 2/5 depend on it. If access is delayed, fall back to deriving address-level structure from base Elliptic alone rather than blocking the phase.
- Build Module 1 (Data Ingestion): normalized transaction record format, static-dataset loader.
- Implement and verify the **entity-based train/test split** (see `DATA.md`, `METHODOLOGY.md`) — this must be correct before any model work starts, since it invalidates every downstream metric if wrong.
- **Milestone check:** can load Elliptic++ into the normalized format and produce a leakage-free entity split with a documented verification method.

## Phase 2 — Graph Construction (Days 6–8, ~Aug 29–31)

- Build Module 2: local subgraph extraction around a given wallet address, bounded hop-depth parameter.
- Sanity-check subgraph construction against a handful of known Elliptic entities.
- **Milestone check:** given any wallet address in the dataset, produce its local transaction subgraph as a NetworkX/PyG object.

## Phase 3 — Rule-Based Signal (Days 9–11, ~Sep 1–3)

- Implement Module 3a: peel-chain detection, rapid fan-out detection, mixer-adjacent-hop detection.
- Source a known-Bitcoin-mixer address list/validation set for the mixer-adjacent-hop heuristic early in this phase — these lists are sparser for Bitcoin than the Ethereum-side equivalent, so this needs sourcing rather than assuming it's readily available (see `SCOPE.md`).
- Validate each heuristic independently against known-pattern examples (manual or literature-sourced test cases) before wiring into the pipeline.
- **Milestone check:** rule-based engine flags wallets with per-heuristic, auditable output (which rule fired and why).

## Phase 4 — Learned Signal (Days 12–16, ~Sep 4–8)

- **Committed MVP learned signal:** random forest on Elliptic's 166 handcrafted features, trained and evaluated on the entity-safe split from Phase 1. This alone satisfies the phase milestone — the GNN below is explicitly a time-boxed stretch attempt, not a Phase 4 requirement (matches `SCOPE.md`, which already lists "a more sophisticated learned-signal model (e.g., GNN)" under stretch goals).
- **Time-boxed GNN attempt (only if baseline + eval finish early):** if the random forest is trained, evaluated, and logged by day 14, spend the remaining Phase 4 days (up to day 16) attempting a graph ML model (e.g., GCN) on the same split, compared against the baseline. If it isn't converging or eating into buffer time by day 16, stop and keep the random forest as the shipped learned signal — do not let this slip into Phase 5.
- **Milestone check:** learned signal produces per-wallet risk scores, evaluated honestly on held-out entities, with metrics logged.

## Phase 5 — Correlation Layer (Days 17–18, ~Sep 9–10)

- Implement Module 4: confirmed vs. watch verdict logic combining 3a and 3b outputs.
- Validate that confirmed-flag wallets are a strict subset of either individual signal's flagged set, and that the logic never invents a flag neither signal raised.
- **Milestone check:** given a subgraph, produce per-wallet verdicts with contributing-signal traceability.

## Phase 6 — Clustering / Attribution (Days 19–21, ~Sep 11–13)

- Implement Module 5: entity clustering over verdict-tagged wallets.
- Integrate supplementary named-exchange sources (hot-wallet lists, community tagging), tagged at lower confidence, kept separate from Elliptic-derived clustering.
- **Milestone check:** wallet clusters produced with confidence tiers correctly attached and visibly distinguishable in output.

## Phase 7 — Visualization / Reporting (Days 22–24, ~Sep 14–16)

- Implement Module 6: fund-flow graph visualization, standardized investigation report export.
- Build the lightweight dashboard (Streamlit or minimal React) for querying a wallet and viewing results end-to-end.
- Wire up the mocked complaint-intake interface and the live-demo block-explorer tracing path.
- **Milestone check:** a wallet address entered in the dashboard produces a full trace → verdicts → cluster → visualization → exportable report, end to end.

## Phase 8 — Integration, Testing, Hardening (Days 25–26, ~Sep 17–18)

- End-to-end test on multiple wallet addresses, including edge cases (isolated wallets, very large subgraphs, wallets with no illicit signal).
- Confirm every scope boundary in `SCOPE.md` is reflected accurately in the dashboard/report UI text — no accidental overclaiming in labels or copy.
- Fix issues found; do not add new features at this stage.

## Phase 9 — Submission Packaging (Day 27, ~Sep 19–20)

- Finalize README, architecture diagrams, demo script, and any required SIH submission artifacts (presentation, video, etc., per official SIH submission requirements — not covered by this handoff).
- Freeze scope. Any stretch-goal work only happens here if all MVP milestones above are complete with time still remaining.
- Submit by 20 September 2026.

---

## Notes on this roadmap

- Each phase's milestone check is a hard gate — don't start the next phase's core work until the current phase's check passes, since later modules (Correlation, Clustering, Reporting) all depend on earlier ones producing correct, honestly-evaluated output.
- If a phase runs over, the first thing to cut is stretch scope (Phase 9), not MVP milestones (Phases 1–7) or the entity-safe split (Phase 1) — an on-time system with an invalid evaluation methodology is worse than a slightly later one with a defensible one.
