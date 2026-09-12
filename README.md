# Crypto Fraud Attribution System (SIH26183)

**Problem Statement:** SIH26183 — Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses through Automated Blockchain Analytics
**Organisation:** Ministry of Home Affairs — Indian Cyber Crime Coordination Centre (I4C), CIS Division
**Category:** Software | **Theme:** Blockchain & Cybersecurity

## What this is

Cyber fraud victims report suspect crypto wallet addresses to investigators. Manually tracing where those funds end up — which exchange or VASP received them, whether they passed through mixers or intermediary "burner" wallets — takes real blockchain-forensics expertise and time investigators often don't have.

This project builds a system that takes a reported wallet address, traces its transaction graph, flags laundering-pattern activity, and surfaces the most likely destination exchange/VASP cluster — producing an investigator-readable report instead of a manual trace.

## Current status

Working end-to-end demo build: live tracing, rule + ML scoring, entity clustering, multi-address (bulk) convergence view, and AI-generated investigation briefs are all implemented. See [`ROADMAP.md`](./ROADMAP.md) for milestone history and what's still ahead.

## How it works (short version)

1. Take a wallet address as input — either a single address, or multiple addresses at once via the bulk convergence view, which correlates them to surface shared downstream entities.
2. Build a local transaction subgraph around it (from the Elliptic/Elliptic++ dataset for training/eval, and live block-explorer APIs for demo-time tracing).
3. Run two independent risk signals against that subgraph:
   - a **rule-based** signal (known laundering heuristics — peel chains, rapid fan-out, mixer-adjacent hops)
   - a **learned** signal (a scikit-learn classifier trained on Elliptic/Elliptic++ transaction features)
4. A wallet is only marked **confirmed risk** when both signals agree. A hit from only one signal is a lower-confidence **watch** flag. (This two-signal-agreement principle is deliberate — see [`ARCHITECTURE.md`](./ARCHITECTURE.md).)
5. Cluster wallets likely controlled by the same exchange/entity, and generate a fund-flow visualization and a standardized investigation report, including an AI-generated natural-language investigation brief ("Dossier").

Full module breakdown is in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## What this is *not* (read before assuming more than it does)

This system is built to a real ₹0, ~20-day, no-government-access constraint. To keep every claim honest:

- **No live SAHYOG/NCRP integration.** These are real government cybercrime-reporting platforms this project has no access path to. The input format is designed to be *compatible* with what such platforms would need, and the demo runs against a mocked complaint-intake interface — not a real one.
- **No full multi-chain coverage.** MVP scope is **Bitcoin only**, built on the Elliptic/Elliptic++ dataset. Ethereum is a stretch goal, not a committed feature. DeFi protocols, cross-chain bridges, and privacy-chain tracing are explicitly out of scope for this build — the architecture is designed to extend to them later, but they are not implemented.
- **"Real-time" means query-time speed against a pre-indexed graph**, not continuous live ingestion of the blockchain. Continuous ingestion is an infrastructure-scale problem outside this project's budget and timeline.
- **Named-exchange attribution is best-effort, not guaranteed.** The Elliptic dataset gives licit/illicit labels, not named-exchange identity. Named-exchange attribution (when present) comes from supplementary, lower-confidence public sources (known hot-wallet lists, community tagging), documented separately from the core Elliptic-derived labels.
- **Live tracing runs on free-tier infrastructure and a fixed ~200K-transaction dataset snapshot**, not a live/continuously-updated blockchain index — a direct consequence of the ₹0 budget constraint above.

See [`SCOPE.md`](./SCOPE.md) for the full MVP / stretch / out-of-scope breakdown.

## Dataset

Primary dataset: **Elliptic / Elliptic++** (Bitcoin transaction graph + actor/address dataset, Kaggle). Full documentation, structure, and the entity-based train/test split methodology (needed to avoid a known label-leakage issue in this dataset) are in [`DATA.md`](./DATA.md).

## Tech stack

- **Python (FastAPI)** — core analysis pipeline: graph construction/traversal (NetworkX), the rule-based signal, and the learned signal (a **scikit-learn** classifier trained on Elliptic/Elliptic++ features — not a graph neural network).
- **Node.js / Express** — an aggregation layer sitting in front of the Python service. It fans out to the Python endpoints (`/trace`, `/rules`, `/score`, `/verdict`, `/clusters`) and stitches the results into one payload for the frontend, and hosts the AI investigation-brief generation (see below) so its API key never reaches the client.
- **React (Vite)** — the analytics dashboard: fund-flow graph, verdict panels, bulk convergence view, and investigation Dossier view.
- Elliptic/Elliptic++ (Kaggle) for training/eval.
- Blockstream.info / BlockCypher free-tier Bitcoin APIs for live demo tracing (Etherscan is Ethereum-specific and is only relevant if the Ethereum stretch goal in `SCOPE.md` is attempted).
- **Gemini API** generates the natural-language investigation brief ("Dossier"). This is implemented, not optional — the core graph/rule/ML detection pipeline itself never depends on it, so detection still works if this integration is unavailable.
- No paid infrastructure — deployed on free tiers throughout (see "What this is not" above for the real-world limitations that come with that).

## Running it

Requires the Python backend and the Node/frontend running together locally.

**1. Start the Python backend** (from repo root, in a terminal with the backend virtualenv activated):
```bash
uvicorn backend.ledgr.service:app --reload --port 8000
```
Confirm it's healthy by opening `http://localhost:8000/docs`.

**2. Start the frontend + Node aggregation layer** (in a second terminal, from repo root):
```bash
npm run dev
```
This runs Express and Vite together in one process on `http://localhost:3000`.

**3. Environment variables** — a local `.env` file is required with:
```
VITE_API_URL=""
```
This must stay empty so the browser calls the app's own same-origin `/api/*` routes (handled by the Express aggregation layer) rather than trying to reach the Python backend directly.

Open `http://localhost:3000` once both are running.

## Docs index

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — module boundaries, inputs/outputs
- [`DATA.md`](./DATA.md) — dataset structure, leakage caveat, split methodology
- [`SCOPE.md`](./SCOPE.md) — MVP vs. stretch vs. out-of-scope
- [`ROADMAP.md`](./ROADMAP.md) — phased build plan to submission
- [`METHODOLOGY.md`](./METHODOLOGY.md) — evaluation methodology and metrics
