# LEDGR Python backend (Phases R1–R4 of BACKEND_BUILD_PLAN.md)

Python pipeline: data ingestion → entity-safe split → graph construction →
**rule-based signal (R3)** → **learned signal (R4)** → (small) FastAPI inference
service. The Node `server.ts` keeps its API contract and will proxy trace/rules/
score calls here (wired in Phase R7).

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
backend/.venv/Scripts/python backend/scripts/train_model.py     # R4 trained signal
backend/.venv/Scripts/uvicorn ledgr.service:app --app-dir backend --port 8000
# POST /trace  {"address": "...", "hop_depth": 2}  -> subgraph + stats
# POST /rules  {"address": "...", "hop_depth": 2}  -> per-heuristic rule signal
# POST /score  {"address": "..."}                 -> learned-signal risk score
```

Rule validation writes `artifacts/rule_validation.json` (per-heuristic
known-pattern + false-positive cases). No-leakage check writes
`artifacts/split_verification.{json,log}`.

## Learned signal (Phase R4)

`scripts/train_model.py` trains the **random-forest baseline** (ROADMAP.md Phase 4
decision; the committed MVP learned signal, not the GNN) on Elliptic's 166
features using the **entity-safe train/test split**. It evaluates honestly on the
held-out test entities — **illicit recall / precision / F1** per `METHODOLOGY.md`
§2, with accuracy reported as a secondary-only number — and writes:

- `artifacts/learned_model.joblib` — trained random forest
- `artifacts/feature_lookup.pkl` — tx_id → 166-feature row for query-time scoring
- `artifacts/model_eval.json` — logged evaluation report + used parameters

The `POST /score` endpoint serves a real `P(illicit)` risk score per wallet
(replacing the old hardcoded `mlScore`). Wallets not present in the Elliptic
feature set are honestly reported as `classified: false` (no risk is fabricated).
The learned flag threshold (`LEARNED_FLAG_THRESHOLD = 0.5`) is documented in
`ledgr/config.py` and passed to Phase R5's confirmed/watch correlation.

## Tests

```bash
backend/.venv/Scripts/python -m pytest backend/tests -v
```
