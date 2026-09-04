# AGENTS.md

Instructions for any AI coding agent (Claude Code, Codex, or similar) working in this repository. Read this before making changes. If something here conflicts with a prompt from a user in a given session, treat that as a deliberate override — but flag the conflict rather than silently picking one.

---

## Project in one paragraph

SIH26183: a system that takes a victim-reported crypto wallet address, traces its transaction graph (Bitcoin, via the Elliptic/Elliptic++ dataset), runs a rule-based heuristic signal and a learned graph-ML signal independently, flags a wallet as "confirmed" risk only when both agree, clusters wallets by likely controlling entity, and produces an investigator-readable fund-flow report. ₹0 budget, no paid infra, no hosted-LLM dependency in the core pipeline, ~20-day build window to a 20 September 2026 submission.

Full context: [`SIH26183_HANDOFF.md`](./SIH26183_HANDOFF.md) (original problem statement and scoping rationale — read this first if anything below is ambiguous). Working docs: `README.md`, `ARCHITECTURE.md`, `DATA.md`, `SCOPE.md`, `ROADMAP.md`, `METHODOLOGY.md`.

---

## Before doing anything

1. Check `SCOPE.md` before adding any feature. If it's not on the "in scope" list, don't build it without an explicit human decision first — see "Scope discipline" below.
2. Check `ROADMAP.md` for the current phase. Don't start Phase N+1 core work before Phase N's milestone check (stated in `ROADMAP.md`) is actually met.
3. If a task touches the train/test split or any evaluation metric, read `METHODOLOGY.md` first. The entity-based split is a hard constraint, not a suggestion — see below.

---

## Hard constraints (never violate these without an explicit, current instruction to do so)

- **No random transaction-level train/test split, ever.** All learned-signal evaluation must use the entity-based split described in `METHODOLOGY.md`. If you write or modify any training/eval code, verify the split is entity-safe before reporting metrics from it. Never take a naive `sklearn.train_test_split` and consider it acceptable for this dataset.
- **No accuracy-only reporting on the illicit-classification task.** Class imbalance makes accuracy misleading here. Always report recall/precision/F1 for the illicit class (see `METHODOLOGY.md` §2).
- **No real SAHYOG/NCRP API calls or client code that assumes real access exists.** Any complaint-intake code is against a mocked interface. If you're tempted to add a "TODO: connect to real SAHYOG API," don't — document the format-compatibility intent in comments instead.
- **No paid infrastructure, no paid API keys, no hosted-LLM call in the core detection pipeline** (ingestion, graph construction, rule-based signal, learned signal, correlation, clustering). An LLM call is only acceptable for optional, non-critical report-text generation (a stretch goal), and must be clearly isolated so the core pipeline runs without it.
- **No silent scope expansion.** Don't add Ethereum support, DeFi/mixer/bridge tracing, or continuous live-chain ingestion as if they were already in scope — these are explicitly out-of-scope or stretch-only per `SCOPE.md`. If a task seems to require one of these, stop and flag it rather than building it.
- **Don't claim capabilities in code comments, docstrings, README text, or UI copy that the system doesn't actually have.** E.g., never write "integrates with SAHYOG" — write "SAHYOG-compatible input format, demoed against a mock." This project's documentation was deliberately written to avoid overclaiming; new code and docs should match that standard.

- **No ghost dependencies.** Every import in the codebase must correspond to a package explicitly declared (with a version) in `requirements.txt` / `pyproject.toml` / equivalent — never rely on a library being present because it happened to be available in a given sandbox or was pulled in transitively by something else. Conversely, don't leave declared dependencies that nothing actually imports — if you remove the last usage of a package, remove it from the dependency file in the same change. Before considering a module done, the dependency file and the actual imports must match exactly in both directions.

- **No placeholders or mocks standing in for real implementation, outside the two explicitly sanctioned mocks** (the SAHYOG/NCRP complaint-intake interface per `SCOPE.md`, and test fixtures for unit tests). This means: no stub functions returning hardcoded/fake-but-plausible data, no `pass  # TODO` left in a function that's referenced elsewhere as if complete, no silently-mocked model/API call presented as a real result. If something genuinely can't be implemented yet, make that visible — `raise NotImplementedError("...")`, a clearly-labeled `# TODO(reason)` comment, or an explicit "not yet implemented" flag in output — never a fake value that could pass for a real one. Before marking any roadmap milestone complete, search the relevant module for placeholder patterns (`mock`, `stub`, `TODO`, `FIXME`, hardcoded return values that don't derive from actual input) and resolve or explicitly flag every hit.

- **No metric chasing.** Tune hyperparameters, thresholds, and heuristic parameters against a validation set — never against the test set. The test set is touched once, at the end, to report a result; if a number looks disappointing, the fix is to improve the method or report the honest limitation in `METHODOLOGY.md`, not to re-split the data, adjust the entity-split ratio, or cherry-pick which wallets/examples get evaluated or demoed until the number improves. This applies to the confirmed/watch confidence threshold too — it gets tuned once on validation data and documented, not adjusted after seeing test results to make the confirmed-tier look more precise. A mediocre, honestly-reported metric is acceptable; an inflated one isn't, even under deadline pressure.

---

## Scope discipline

`SCOPE.md` is the source of truth for what's in/out of scope. If asked to build something not listed there:
1. Check whether it's a natural extension of an in-scope module (per `ARCHITECTURE.md`'s "Extensibility notes") — if so, it may still need an explicit go-ahead before building, since scope creep is the main risk this project is guarding against (see the handoff doc, Section 3).
2. If genuinely ambiguous, ask rather than assume. A wrong guess here costs more than a clarifying question, given the fixed deadline.

---

## Repo conventions

- **Language:** Python for the core pipeline. Graph work uses NetworkX and/or PyTorch Geometric. Frontend, if built, is Streamlit or a minimal React app — don't introduce a third frontend framework without reason.
- **Module boundaries follow `ARCHITECTURE.md` exactly** — data ingestion, graph construction, rule-based signal, learned signal, correlation layer, clustering/attribution, reporting/visualization. Keep these as separable modules/packages, not one monolithic script — the two-signal-independence property (see below) depends on 3a and 3b being genuinely separate code paths.
- **Rule-based and learned signals must remain independently runnable and independently testable.** Don't let the learned model's output leak into the rule-based heuristics or vice versa — the correlation layer's validity depends on this separation (`METHODOLOGY.md` §3).
- **Any heuristic or model threshold** (e.g., the confirmed/watch confidence cutoff) must be a named, documented constant — not a bare magic number in the middle of logic. Log where/why it was tuned.
- **Confidence tiers are always carried through to output.** Elliptic-derived labels vs. supplementary-source named attribution must remain visibly distinguishable at every layer that touches them (graph construction → clustering → reporting) — don't collapse them into a single "confidence" field that loses which tier it came from.

---

## Working with the dataset

- Elliptic/Elliptic++ files are large — don't commit raw dataset files to the repo. Use a `.gitignore`'d data directory and document the download/setup step in `README.md`'s "Running it" section as it gets filled in.
- Any new evaluation script must state explicitly, in its own output, that it used an entity-safe split (or flag clearly if it's a quick non-safe sanity check that shouldn't be treated as a real result — see `METHODOLOGY.md`).
- Live block-explorer API calls (Etherscan, Blockchain.com) are for demo-time tracing of a small, fixed set of example wallets only — don't wire them into the training/eval pipeline, and don't add code that would hit rate limits at scale (this stays free-tier).

---

## Verification expectations

Before considering a module "done":
- **Rule-based heuristics:** validated against known-pattern test cases (synthetic or literature-sourced), with false-positive rate checked against clearly-licit wallets, per `METHODOLOGY.md` §3.
- **Learned model:** evaluated on the entity-safe split, compared against a stated baseline (e.g., random forest on the 166 Elliptic features), with recall/precision/F1 reported per `METHODOLOGY.md` §2 — not just accuracy.
- **Correlation layer:** verified that "confirmed" flags are a strict subset of wallets flagged by at least one individual signal — the correlation layer should never invent a flag neither input signal raised.
- Each `ROADMAP.md` phase has a stated milestone check — treat that as the acceptance criterion for work in that phase.

---

## Docs maintenance

If a change affects scope, architecture, dataset handling, or methodology, update the corresponding doc (`SCOPE.md`, `ARCHITECTURE.md`, `DATA.md`, `METHODOLOGY.md`) in the same change — don't let code and docs drift apart. These docs exist specifically to prevent scope drift and overclaiming (per the handoff doc); an agent letting them go stale defeats their purpose.
