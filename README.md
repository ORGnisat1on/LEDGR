# Crypto Fraud Attribution System (SIH26183)

**Problem Statement:** SIH26183 — Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses through Automated Blockchain Analytics
**Organisation:** Ministry of Home Affairs — Indian Cyber Crime Coordination Centre (I4C), CIS Division
**Category:** Software | **Theme:** Blockchain & Cybersecurity

## What this is

Cyber fraud victims report suspect crypto wallet addresses to investigators. Manually tracing where those funds end up — which exchange or VASP received them, whether they passed through mixers or intermediary "burner" wallets — takes real blockchain-forensics expertise and time investigators often don't have.

This project builds a system that takes a reported wallet address, traces its transaction graph, flags laundering-pattern activity, and surfaces the most likely destination exchange/VASP cluster — producing an investigator-readable report instead of a manual trace.

## Current status

Early-stage build. See [`ROADMAP.md`](./ROADMAP.md) for milestones and current phase.

## How it works (short version)

1. Take a wallet address as input (single address for MVP; batch/bulk address ingestion is a stretch goal — see `SCOPE.md`).
2. Build a local transaction subgraph around it (from the Elliptic/Elliptic++ dataset for training/eval, and optionally live block-explorer APIs for demo-time tracing).
3. Run two independent risk signals against that subgraph:
   - a **rule-based** signal (known laundering heuristics — peel chains, rapid fan-out, mixer-adjacent hops)
   - a **learned** signal (a graph ML model trained on Elliptic/Elliptic++)
4. A wallet is only marked **confirmed risk** when both signals agree. A hit from only one signal is a lower-confidence **watch** flag. (This two-signal-agreement principle is deliberate — see [`ARCHITECTURE.md`](./ARCHITECTURE.md).)
5. Cluster wallets likely controlled by the same exchange/entity, and generate a fund-flow visualization and a standardized investigation report.

Full module breakdown is in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## What this is *not* (read before assuming more than it does)

This system is built to a real ₹0, ~20-day, no-government-access constraint. To keep every claim honest:

- **No live SAHYOG/NCRP integration.** These are real government cybercrime-reporting platforms this project has no access path to. The input format is designed to be *compatible* with what such platforms would need, and the demo runs against a mocked complaint-intake interface — not a real one.
- **No full multi-chain coverage.** MVP scope is **Bitcoin only**, built on the Elliptic/Elliptic++ dataset. Ethereum is a stretch goal, not a committed feature. DeFi protocols, cross-chain bridges, and privacy-chain tracing are explicitly out of scope for this build — the architecture is designed to extend to them later, but they are not implemented.
- **"Real-time" means query-time speed against a pre-indexed graph**, not continuous live ingestion of the blockchain. Continuous ingestion is an infrastructure-scale problem outside this project's budget and timeline.
- **Named-exchange attribution is best-effort, not guaranteed.** The Elliptic dataset gives licit/illicit labels, not named-exchange identity. Named-exchange attribution (when present) comes from supplementary, lower-confidence public sources (known hot-wallet lists, community tagging), documented separately from the core Elliptic-derived labels.

See [`SCOPE.md`](./SCOPE.md) for the full MVP / stretch / out-of-scope breakdown.

## Dataset

Primary dataset: **Elliptic / Elliptic++** (Bitcoin transaction graph + actor/address dataset, Kaggle). Full documentation, structure, and the entity-based train/test split methodology (needed to avoid a known label-leakage issue in this dataset) are in [`DATA.md`](./DATA.md).

## Tech stack

- Python (core pipeline)
- NetworkX / PyTorch Geometric (graph construction + graph ML)
- Elliptic/Elliptic++ (Kaggle) for training/eval
- Blockstream.info / BlockCypher free-tier Bitcoin APIs for live demo tracing (Etherscan is Ethereum-specific and is only relevant if the Ethereum stretch goal in `SCOPE.md` is attempted)
- Streamlit or a minimal React app for the analytics dashboard
- No paid infrastructure. No hosted-LLM dependency for the core detection pipeline — an LLM may optionally generate natural-language report text later, but the core graph analysis never depends on one.

## Running it

Setup and run instructions will be added here once the data pipeline milestone (see `ROADMAP.md`) is complete.

## Docs index

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — module boundaries, inputs/outputs
- [`DATA.md`](./DATA.md) — dataset structure, leakage caveat, split methodology
- [`SCOPE.md`](./SCOPE.md) — MVP vs. stretch vs. out-of-scope
- [`ROADMAP.md`](./ROADMAP.md) — phased build plan to submission
- [`METHODOLOGY.md`](./METHODOLOGY.md) — evaluation methodology and metrics
