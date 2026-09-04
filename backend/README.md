# LEDGR Python backend (Phases R1–R4 of BACKEND_BUILD_PLAN.md)

Python pipeline: data ingestion → entity-safe split → graph construction →
**rule-based signal (R3)** → (small) FastAPI inference service. The Node
`server.ts` keeps its API contract and will proxy trace/rules calls here
(wired in Phase R7).

## Setup

```bash
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt   # Windows
```

## Data

Download the **Elliptic** dataset CSVs from Kaggle into `data/raw/`
(any subfolder layout): `elliptic_txs_features.csv`, `elliptic_txs_edgelist.csv`,
`elliptic_txs_classes.csv` (+ optional Elliptic++ address files).

## Mixer list (Phase R3)

Copy `data/mixers.example.txt` → `data/mixers.txt` and fill in a sourced
mixer-address validation set (one address per line). Without it, the
`mixer_adjacent` heuristic stays silent (it never fabricates a fire).

## Run

```bash
backend/.venv/Scripts/python backend/scripts/run_ingest.py      # R1/R2 artifacts
backend/.venv/Scripts/python backend/scripts/validate_rules.py  # R3 validation
backend/.venv/Scripts/uvicorn ledgr.service:app --app-dir backend --port 8000
# POST /trace {"address": "...", "hop_depth": 2}   -> subgraph + stats
# POST /rules {"address": "...", "hop_depth": 2}   -> per-heuristic rule signal
```

Rule validation writes `artifacts/rule_validation.json` (per-heuristic
known-pattern + false-positive cases). No-leakage check writes
`artifacts/split_verification.{json,log}`.

## Tests

```bash
backend/.venv/Scripts/python -m pytest backend/tests -v
```
