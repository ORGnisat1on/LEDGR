# Crypto Fraud Attribution System (SIH26183)

**Problem Statement:** SIH26183 — Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses through Automated Blockchain Analytics
**Organisation:** Ministry of Home Affairs — Indian Cyber Crime Coordination Centre (I4C), CIS Division
**Category:** Software | **Theme:** Blockchain & Cybersecurity

## What this is

Cyber fraud victims report suspect crypto wallet addresses to investigators. Manually tracing where those funds end up — which exchange or VASP received them, whether they passed through mixers or intermediary "burner" wallets — takes real blockchain-forensics expertise and time investigators often don't have.

This project builds a system that takes a reported wallet address, traces its transaction graph, flags laundering-pattern activity, and surfaces the most likely destination exchange/VASP cluster — producing an investigator-readable report instead of a manual trace.

## Current status

**R10 — final packaging and scope freeze.** All MVP milestones complete. See [`STATUS.md`](./STATUS.md) for the full audit trail and [`ROADMAP.md`](./ROADMAP.md) for the phased build history.

## What the system does (MVP — working code with passing tests)

- **Bitcoin-only** tracing using the Elliptic/Elliptic++ dataset as the training/evaluation foundation.
- **Single-wallet input** via a mocked complaint-intake interface (format designed to be SAHYOG/NCRP-compatible; no live integration with either platform).
- **Local transaction subgraph construction** around a reported wallet (bounded hop-depth, not whole-chain).
- **Two independent risk signals:**
  - **Rule-based (Module 3a):** peel-chain detection and rapid fan-out detection — both active and tested. Mixer-adjacent-hop detection is implemented but **dormant** — a completed investigation found no citable public source of exact Bitcoin mixer addresses (Europol/Chainalysis ChipMixer reporting and academic tumbler literature checked; no per-address data accessible). The heuristic never fires on made-up addresses.
  - **Learned (Module 3b):** random forest on Elliptic's 166 handcrafted features, trained and evaluated on an **entity-based, time-respecting split** (train: time-steps 1–42, val: 42–45, test: 45–49; zero entity/tx overlap; span-0 enforced per METHODOLOGY.md §1).
- **Correlation layer (Module 4):** a wallet is only **confirmed** when both signals agree; a hit from only one signal is **watch**; neither is **none**. This two-signal agreement is the load-bearing design decision — neither signal alone is treated as sufficient.
- **Clustering (Module 5):** Elliptic-derived entity clusters (licit/illicit only, higher confidence) plus live-traced UTXO clustering via common-input/change-address heuristics (exposed at `GET /clusters/live?address=<addr>`, tier `TIER_LIVE_UTXO`). The two clustering paths are separate and never merged.
- **Named-exchange attribution (Module 5):** only works through the **live-lookup** path (real BTC addresses fetched via Blockstream/BlockCypher). The indexed Elliptic graph uses anonymized transaction IDs with no address mapping, so in-dataset traces show no named attribution *by construction*, not as a silent gap. Supplementary matches are tagged `supplementary-source` (lower confidence) and kept visibly separate from `elliptic-derived` labels.
- **Live demo tracing (Module 1/R9):** a small number of wallets traced live via free-tier Blockstream/BlockCypher APIs, layered on top of the static training graph.
- **Reporting & visualization (Module 6):** fund-flow graph visualization and a standardized, exportable investigation report. Report field structure is designed for SAHYOG/NCRP format compatibility; demoed against a mocked intake — no real API calls.
- **Dashboard:** React/TypeScript frontend (Vite + Express proxy to Python FastAPI backend) for querying a wallet and viewing results end-to-end.

## What the system does NOT do (explicit boundaries — read before assuming more)

- **No live SAHYOG/NCRP integration.** No real access path exists. Format compatibility only, demoed against a mock.
- **No multi-chain coverage.** MVP is Bitcoin only. Ethereum is a stretch goal (separate code path, not a drop-in extension). DeFi protocols, cross-chain bridges, privacy-chain tracing are explicitly out of scope.
- **No continuous blockchain ingestion.** "Real-time" means fast query-time response against a pre-indexed graph — not an always-on live-ingestion pipeline.
- **No guaranteed named-exchange attribution.** Elliptic provides licit/illicit labels, not named identities. Naming is best-effort via supplementary sources (BitInfoCharts rich list, retrieved 2026-09-06), always confidence-tagged as lower-confidence.
- **No mixer-address validation set.** A genuine investigation was completed (2026-09-06) and no citable public source of exact mixer addresses was found. The `mixer_adjacent` heuristic remains dormant by design — this is a documented, closed investigation, not an open TODO.
- **No paid infrastructure or hardware dependency.** Budget is ₹0.
- **No hosted-LLM dependency for the core detection pipeline.** An LLM may optionally generate report narrative text as a stretch goal; the core graph analysis never depends on one.

## Honest capability findings (not caveats — these are documented results)

### Temporal-leakage finding and honest metrics

The original random-split evaluation produced an implausible illicit recall of ~0.94. Investigation revealed **temporal leakage**: the Elliptic dataset has a documented concept-drift event at time-step 43 (Abraxas dark-market shutdown, per Weber et al. 2019 / GuiltyWalker). A random split lets the model memorize pre-shift entity patterns that don't generalize post-shift.

**The fix:** rebuilt the split as time-respecting at the entity level (train 1–42, val 42–45, test 45–49; span-0 enforced programmatically on every run). The honest baseline on this split:

| Metric | Value |
|--------|-------|
| **Illicit recall** | **0.017** (1.7%) |
| **Illicit precision** | **0.500** (50.0%) |
| **Illicit F1** | **0.033** |
| Confusion matrix (test) | TP=2, FP=2, FN=114, TN=2398 (2,509 labeled of 14,084 test txs; 116 illicit) |
| Accuracy (secondary, not meaningful alone) | 95.4% |

**Why this is a strength, not a weakness:** The low recall is *exactly why* the correlation layer exists. A wallet is only **confirmed** when the rule-based signal AND the learned signal independently agree — precisely because either signal on its own is imperfect. The rule engine adds 2 peel-chain catches beyond the ML's 2, giving a union recall of 4/116 = 3.45%. This is the methodology working as intended, not "the ML doesn't work."

**Implication for live tracing:** The Elliptic dataset ends ~2018. Every modern live-traced wallet exists years past the documented regime shift. The learned signal's reliability on any current real-world wallet is fundamentally unverified and likely degraded by the same (or worsened) concept drift. The dashboard explicitly surfaces this limitation (Methodology modal + footer banner: "live-traced wallets operating after the dataset window are outside the model's validated regime").

See [`METHODOLOGY.md`](./METHODOLOGY.md) §1–§2 and [`DATA.md`](./DATA.md) for the full methodology and leakage rationale.

## How to run it

### Prerequisites

- Python 3.11+
- Node.js 18+
- The Elliptic dataset CSVs must be manually placed in `data/raw/` (download from Kaggle: [`ellipticco/elliptic-data-set`](https://www.kaggle.com/datasets/ellipticco/elliptic-data-set)). There is no automatic download or synthetic-fixture fallback in the production pipeline — if the CSVs are missing, `ingest.py` raises FileNotFoundError. Separate, much smaller synthetic fixtures exist only under `backend/tests/fixtures/synthetic/` and are used exclusively by the test suite.

### Backend (Python/FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run API server (port 8000)
uvicorn ledgr.service:app --reload

# Run tests
python3 -m pytest tests/ -q
# 79 passed, 6 warnings (as of 2026-09-06)
```

### Frontend (React/TypeScript)

```bash
npm install
npm run dev    # dev server (port 3000, proxies /api/* to backend)
npm run build  # production build
npm run lint   # tsc --noEmit (0 errors)
```

> Local API wiring: `npm run dev` runs `server.ts` (Express) which embeds Vite in
> middleware mode and serves both the UI and `/api/*` (trace/clusters/brief/mempool)
> on port 3000, aggregating them by proxying to the Python backend
> (`PYTHON_API_URL`, default `http://localhost:8000`). Keep `VITE_API_URL` **empty**
> (`""`) in `.env` so the browser calls same-origin `/api/*` — pointing it at
> `http://localhost:8000` would bypass Express and hit Python's bare `/trace`,
> `/rules`, … routes with the `/api` prefix, which 404.

### Live tracing (demo only)

Set `LEDGR_LIVE_TRACING=1` to enable the live-lookup path (Blockstream primary, BlockCypher fallback). Without it, live endpoints return 503 and traces fall back to the indexed Elliptic graph only.

```bash
LEDGR_LIVE_TRACING=1 uvicorn ledgr.service:app --reload
```

## Test suite

- **Backend:** 79 tests passing (`python3 -m pytest backend/tests/ -q`)
- **Frontend:** TypeScript type-check passes (`npm run lint` → 0 errors)
- **Hardening check:** `python3 backend/scripts/hardening_check.py` — 6/6 checks PASS (known-licit, known-illicit, isolated/low-degree, hub subgraph boundedness, out-of-dataset behavior, R5 correlation invariant)

## Docs index

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — module boundaries, inputs/outputs, core design principle
- [`DATA.md`](./DATA.md) — dataset structure, entity-leakage caveat, supplementary sources
- [`SCOPE.md`](./SCOPE.md) — MVP / stretch / out-of-scope (checkable reference)
- [`ROADMAP.md`](./ROADMAP.md) — phased build plan to submission
- [`METHODOLOGY.md`](./METHODOLOGY.md) — evaluation methodology, entity-based split, metrics, correlation logic
- [`DEMO.md`](./DEMO.md) — curated wallet addresses for live demo walkthrough
- [`STATUS.md`](./STATUS.md) — living audit trail with dated entries per phase