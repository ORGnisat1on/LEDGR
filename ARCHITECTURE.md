# Architecture

## Core design principle

A wallet's fraud-risk classification is more defensible when two **independent** signals agree than when either fires alone. This mirrors a principle from an earlier personal project (a C profiler that only labels something a "confirmed hotspot" when a static/structural signal and a real/dynamic measurement independently agree). Here, the two independent signals are a rule-based heuristic engine and a learned graph ML model. A hit from both is a **confirmed** flag; a hit from only one is a **watch** flag. This is the load-bearing design decision of the whole system — every module below exists to feed it cleanly.

## Pipeline overview

```
Victim-reported wallet address (input)
                │
                ▼
    [1. Data Ingestion]
                │
                ▼
    [2. Graph Construction]
                │
        ┌───────┴────────┐
        │                 │
[3a. Rule-Based Signal] [3b. Learned Signal]
        │                 │
        └───────┬─────────┘
                │
                ▼
    [4. Correlation Layer] ──────► [1b. Watchlist Monitoring]
                │                   (stretch goal — persists confirmed/
                ▼                    watch wallets, polls mempool feed
    [5. Clustering / Attribution]    for new unconfirmed activity,
                │                    pushes early-warning alerts)
                ▼
    [6. Reporting & Visualization]
```

---

## Module 1 — Data Ingestion

**Purpose:** get transaction graph data into a common internal format, from two distinct sources with two distinct roles.

**Inputs:**
- Elliptic/Elliptic++ static dataset (CSV/Parquet, Kaggle) — used for training and evaluation.
- Live public block-explorer API responses (Etherscan / Blockchain.com free tier) — used only at demo time, for real-time tracing of a small number of example wallets layered on top of the static training graph.
- A wallet address string, arriving from the (mocked) complaint-intake interface — see Module 6 for the SAHYOG/NCRP-compatibility note.

**Outputs:** a normalized transaction record format (address, tx hash, timestamp, amount, direction, source) common to both static and live data, so downstream modules don't need to know which source a record came from.

**Explicit boundary:** this module does not continuously ingest the live blockchain. It ingests the static dataset once (batch, at training time) and queries live APIs only on-demand for a specific reported address at query time. MVP intake accepts one reported address per submission; accepting a batch of addresses in one submission (bulk tracing, `SCOPE.md` stretch goal) is a straightforward extension of this same on-demand query path run in a loop — it does not change the ingestion format.

---

## Module 1b — Watchlist Monitoring (IMPLEMENTED 2026-09-07)

**Purpose:** give investigators an early warning when a wallet already flagged by this system shows new activity — specifically, before that activity confirms on-chain.

**Inputs:** verdict records from Module 4 (`confirmed` or `watch` wallets are added to a persistent watchlist); mempool.space free API via `/api/mempool/address/:address` proxy endpoint for unconfirmed-transaction data.

**Logic:** polls mempool.space at 30-second intervals per watchlisted address (respecting public API rate limits). For each address, fetches unconfirmed transactions from `/api/address/{address}/txs/mempool`, filters to transactions involving the watched address, derives direction (incoming/outgoing) by comparing watched address against vin/vout, calculates amount from satoshi values, determines counterparty from the opposite side of the transaction, computes fee rate (sat/vB) from fee/weight. No new inference — pure lookup against known list.

**Outputs:** per-address alert state (`{wallet, prior_verdict, tx_hash, direction, amount_btc, amount_inr, detected_at, fee_rate_sat_vb, counterparty_address, status: unconfirmed_mempool}`) with three distinct UI states: "monitoring, no activity" (normal), "error fetching" (network/rate-limit), "alert detected" (live unconfirmed tx). Relative timestamps update live while modal is open.

**Explicit boundary:** this module only watches addresses already on the watchlist (i.e., previously run through Modules 2–4 at least once). It does not ingest the full mempool or the full chain, and it does not predict that a wallet is *about to* transact before any transaction exists — it detects a broadcast transaction before confirmation, which is a materially different and much smaller claim. See `SCOPE.md` for why true predictive forecasting is logged separately as future work, not part of this module.

**Rate limiting:** 30s interval per address. With N=4 watchlist addresses: 4 req/30s = 8 req/min = 480 req/hr. Well within mempool.space free tier limits (thousands/day). For demo with judges, this is safe.

---

## Module 2 — Graph Construction

**Purpose:** build the local transaction subgraph a reported wallet actually needs to be evaluated against — not the whole chain.

**Inputs:** normalized transaction records from Module 1, a target wallet address, a hop-depth parameter (how many transaction hops out from the target to include).

**Outputs:** a directed graph object (NetworkX / PyTorch Geometric `Data` object) representing the local neighborhood around the target wallet — nodes are addresses, edges are transactions with amount/timestamp attributes.

**Explicit boundary:** MVP builds this graph over Bitcoin transaction data only. Ethereum support (different address/UTXO model) is a stretch goal and, if attempted, is a separate code path, not a drop-in extension.

---

## Module 3a — Rule-Based Signal

**Purpose:** flag structurally suspicious patterns using known laundering heuristics, independent of any learned model.

**Inputs:** the local subgraph from Module 2.

**Heuristics (initial set):**
- **Peel chains** — a wallet repeatedly sending most of its balance onward while "peeling off" small amounts, a common laundering pattern.
- **Rapid fan-out** — one wallet distributing funds to many new wallets in a short time window.
- **Mixer-adjacent hops** — proximity (within N hops) to addresses matching known mixer/tumbler patterns or lists.

**Outputs:** a per-wallet boolean-or-scored flag (`rule_flag: {none, low, high}`) plus which heuristic(s) triggered it, for auditability.

**Explicit boundary:** this is a heuristic engine, not a model — it should be interpretable enough that an investigator can see *why* a wallet was flagged.

---

## Module 3b — Learned Signal

**Purpose:** flag suspicious wallets using a graph ML model trained on labeled data, independent of the rule-based engine.

**Inputs:** the local subgraph from Module 2, converted to model input features (the 166 handcrafted Elliptic features where available, plus any engineered graph-structural features).

**Model approach:** node classification / clustering (e.g., GCN or similar graph neural network, or a simpler baseline like a random forest over graph-derived features as a fallback) trained on the Elliptic/Elliptic++ licit/illicit labels.

**Outputs:** a per-wallet risk score or class prediction (`model_flag: {licit, illicit, unknown}` plus confidence).

**Explicit boundary:** trained and evaluated using the entity-based split described in `DATA.md` and `METHODOLOGY.md` — never evaluated with a naive random transaction split, which would leak entity identity between train and test sets.

---

## Module 4 — Correlation Layer

**Purpose:** implement the core design principle. Combine Module 3a and 3b outputs into a single, defensible risk verdict.

**Inputs:** `rule_flag` from 3a, `model_flag`/confidence from 3b, for each wallet in the subgraph.

**Logic:**
- Both signals agree (illicit) → **Confirmed** risk.
- Only one signal fires → **Watch** (lower-confidence).
- Neither fires → no flag.

**Outputs:** a per-wallet verdict record: `{wallet, verdict: confirmed|watch|none, contributing_signals, confidence}`. Confirmed/watch verdicts are also written to the watchlist store consumed by Module 1b (stretch goal).

**Explicit boundary:** this layer never overrides a "neither fires" case into a flag — it only combines, never invents new evidence.

---

## Module 5 — Clustering / Attribution

**Purpose:** group wallets likely controlled by the same entity/exchange, and attempt to name that entity where possible.

**Inputs:** verdict records from Module 4, the transaction graph from Module 2, and supplementary label sources (known exchange hot-wallet address lists, community-sourced tagging services).

**Outputs:** wallet clusters with an optional entity/exchange name attached, tagged with a confidence tier: `elliptic-derived` (higher confidence, licit/illicit only, no name) vs. `supplementary-source` (named, lower confidence).
Note: Live-traced UTXO clustering (common-input and change-address heuristics) runs on a separate `live-traced-utxo` tier. "The dataset" for these heuristics means the locally-traced, hop-bounded subgraph, not the full blockchain. A change address could have real prior history outside the traced radius that this check structurally cannot see, which is a known scope limitation.

**Explicit boundary:** named-exchange attribution is only ever presented with its confidence tier visible — the system never presents a supplementary-source name with the same confidence as an Elliptic-derived licit/illicit label. Additionally, Elliptic-derived (hub-safeguarded connected components) and live-traced UTXO clustering are distinct paths due to the unavailability of the Elliptic++ actor dataset.

**Stretch extension — cross-wallet convergence (bulk tracing):** when multiple wallets are traced in one batch (see `SCOPE.md` bulk wallet tracing), Module 5 can additionally check whether independently reported wallets converge on the same cluster/exchange, surfacing that several victims' funds landed with the same actor. This reuses the existing per-wallet cluster output — it does not require a new inference model, only comparing cluster assignments across multiple Module 4 verdict sets instead of one.

---

## Module 6 — Reporting & Visualization

**Purpose:** turn Module 5's output into something an investigator can actually use.

**Inputs:** clustered, verdict-tagged wallet graph from Module 5.

**Outputs:**
- A fund-flow visualization (graph view: target wallet → intermediary hops → attributed cluster).
- A standardized, exportable investigation report (structured fields: reported wallet, trace summary, confirmed/watch flags with contributing evidence, attributed cluster/exchange if any, confidence tiers throughout).
- Report field structure is designed to be *compatible* with what a SAHYOG/NCRP intake would need, and is demoed against a mocked complaint-intake interface — not connected to either real platform.

**Explicit boundary:** no real SAHYOG/NCRP API calls anywhere in this module. Any "integration" language in the demo refers to format compatibility, not a live connection.

---

## Extensibility notes (explicitly not current scope)

The module boundaries above are drawn so that later extension doesn't require a rewrite:
- **More chains:** Module 1 and 2 would need chain-specific ingestion/graph-construction logic; Modules 3–6 are largely chain-agnostic if fed a normalized graph.
- **Mixers/bridges/DeFi tracing:** would primarily extend Module 3a's heuristic set and Module 2's graph-construction depth.
- **Real SAHYOG/NCRP integration:** would replace the mocked intake in Module 1/6 with a real API client — the internal data format is already designed for this.
- **True predictive forecasting** (predicting a wallet will transact before any transaction is broadcast, as opposed to Module 1b's unconfirmed-transaction detection) would require a time-series/behavioral model over historical wallet activity — a different model class from the current static node classifier, with a substantially different evaluation methodology. Not attempted in this build; logged as future work only.

None of the above are implemented in this build.
