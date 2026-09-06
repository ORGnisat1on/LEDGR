# Scope

This document is the checkable reference for scope decisions. If a feature discussion doesn't map cleanly onto one of the three lists below, it needs a scope decision before work starts on it — don't assume "future work" or "in scope" by default.

---

## In scope (MVP)

- **Chain coverage:** Bitcoin only, using the Elliptic/Elliptic++ dataset as the training/eval foundation.
- **Input:** a single victim-reported wallet address at a time, ingested via a mocked complaint-intake interface (format designed to be SAHYOG/NCRP-compatible, not actually connected to either). Batch/bulk address input is explicitly a stretch goal, not MVP — see below.
- **Tracing:** local transaction subgraph construction around a reported wallet (bounded hop-depth, not whole-chain).
- **Rule-based signal:** heuristic detection of peel chains, rapid fan-out, and mixer-adjacent hops. **Explicit Boundary:** Because the Elliptic dataset completely anonymizes node IDs as integers, there is no possible linkage to real Bitcoin mixer addresses. Therefore, the `mixer_adjacent` rule *cannot* be evaluated or tuned on historical training data. It will only be exercised on live-traced wallets (Phase R7). Note: a known-mixer validation set still needs to be sourced for the live demo. **Current status (2026-09-06 audit):** 2 of the 3 heuristics are active — `mixer_adjacent` is implemented but **dormant**. `data/mixers.txt` is intentionally empty because no citable, verifiable public source of exact mixer addresses could be found (the sources checked are documented in the file and the audit); until a real set is sourced the rule never fires rather than firing on made-up addresses.
- **Learned signal:** a graph ML model (node classification/clustering) trained on Elliptic/Elliptic++, evaluated with an entity-based train/test split.
- **Correlation layer:** confirmed-risk vs. watch-flag logic requiring agreement between the rule-based and learned signals. **Honest baseline note (2026-09-06 audit):** the committed learned signal is a random forest that, on the time-respecting entity-safe split, gets illicit recall **0.017** / precision **0.500** / F1 **0.033** (confusion matrix TP=2, FP=2, FN=114, TN=2398). Low recall is expected and correct for this honest baseline — it is precisely why the correlation layer requires *both* signals to agree for a `confirmed` verdict; neither signal alone is treated as sufficient.

- **Clustering:** grouping wallets likely controlled by the same entity, using Elliptic-derived data as the primary (higher-confidence) source. **Current implementation note:** common-input and change-address clustering currently apply to live-traced data only, because the Elliptic++ actor dataset is not available.

- **Attribution:** named-exchange attribution where supplementary public sources (hot-wallet lists, community tagging) allow it, explicitly tagged as lower-confidence and separate from Elliptic-derived clustering. **Current status (2026-09-06 audit):** this matching only works through the R9 **live-lookup** path. The indexed Elliptic graph uses anonymized transaction IDs with no address mapping, so hot-wallet-list matches can only hit real BTC addresses fetched live — an in-dataset trace shows no named attribution *by construction*, not as a silent gap.

- **Live demo tracing:** a small number of wallets traced live via free-tier Etherscan/Blockchain.com APIs, layered on top of the static training data, for demonstration purposes.
- **Output:** fund-flow graph visualization and a standardized, exportable investigation report.
- **Dashboard:** a lightweight web frontend (Streamlit or minimal React) for investigators to query a wallet and view results.

## Stretch goals (attempt only if MVP is solid and time remains)

- **Ethereum support**, as a second, separately-implemented chain path (different address model from Bitcoin — not a drop-in extension of the Bitcoin pipeline).
- Expanded rule-based heuristic set beyond the initial three (peel chains, fan-out, mixer-adjacency).
- A more sophisticated learned-signal model (e.g., moving from a baseline classifier to a full GNN) if time allows after a working baseline is evaluated.
- Optional LLM-generated natural-language summary text for the investigation report — explicitly non-critical, and never part of the core graph analysis or risk-scoring pipeline.
- **Watchlist monitoring (mempool alerts).** Once a wallet has been flagged (confirmed or watch), persist it on a watchlist and poll/subscribe to a free mempool feed (e.g. mempool.space) for any new *unconfirmed* transaction touching that address. This surfaces new activity from a known-flagged wallet before it confirms on-chain (typically a ~10+ minute window) — a genuine early-warning capability, not a forecast. Scoped narrowly to addresses already on the watchlist; it does not involve ingesting the full mempool.
- **Bulk wallet tracing.** Accept a batch of multiple victim-reported wallet addresses (e.g. CSV upload or multi-line input) in one submission, instead of one address at a time. Two sub-capabilities, in increasing order of effort:
  1. *Batch run:* run the existing single-wallet pipeline (Modules 1–4) once per address in the batch and return one report per wallet. Mostly a Module 6/dashboard loop — no new inference logic.
  2. *Cross-wallet convergence:* after batch tracing, check whether multiple independently reported wallets converge on the same downstream cluster/exchange (Module 5) — surfacing that several victims' funds landed with the same actor. This is the higher-value capability for the real I4C use case (many complainants, shared fraud infrastructure) but extends Module 5 to reason across multiple traces at once rather than a single one, so it's scoped as stretch, attempted only after batch run and the core MVP milestones are solid.

## Explicitly out of scope for this build

- **Live SAHYOG/NCRP API integration.** No real access path exists for a student team. Format compatibility only, demoed against a mock.
- **Full multi-chain coverage** beyond the stretch-goal Ethereum path — no DeFi protocol tracing, no cross-chain bridge tracing, no privacy-chain (e.g., Monero-style) tracing. Each is its own research area and is presented in `ARCHITECTURE.md` as an extensibility note, not an implemented feature.
- **Continuous, real-time blockchain ingestion.** "Real-time" in this project means fast response to a queried wallet against a pre-indexed graph — not an always-on live-ingestion pipeline. That's an infrastructure-scale problem outside a ₹0, ~20-day build. (The stretch-goal watchlist mempool monitoring above is narrower — polling for a bounded, already-flagged address list, not ingesting the full mempool or chain — and doesn't change this boundary.)
- **Predicting a transaction before it is broadcast.** The watchlist stretch goal above detects a new *unconfirmed* transaction the moment it's broadcast — it does not forecast that a wallet is about to transact before any transaction exists. True behavioral forecasting would need a different model class (time-series/sequence modeling of wallet behavior over time, not the current static node classifier) and a fundamentally different, harder-to-validate evaluation methodology. Logged here explicitly as a future-work item, not a current or stretch capability, so it doesn't get implied by demo language later.
- **Guaranteed named-exchange attribution for every flagged wallet.** Elliptic provides licit/illicit labels, not named identities. Naming is best-effort via supplementary sources only, and always confidence-tagged as such.
- **Any paid infrastructure or hardware dependency.** Budget is ₹0. Anything requiring paid infrastructure is out of scope unless explicitly logged as a "future work, money-enabled" item — and none currently are.
- **Any hosted-LLM dependency for the core detection pipeline.** An LLM may optionally generate report narrative text as a stretch goal, non-critically. The rule-based and learned signals, the correlation layer, and clustering never depend on an LLM call.

---

## How to use this file

When a scope question comes up mid-build ("should we also do X"), check it against the three lists above before deciding. If it's not listed anywhere, it needs an explicit decision — logged by adding it to the correct list here — before work starts, not after.
