"""Central configuration for the LEDGR Python pipeline. All thresholds that are
decisions (hub exclusion, split ratio, seed, rule weights) live here so they are
logged with every run rather than buried in code."""

from __future__ import annotations

import os
from pathlib import Path

# Repo root = backend/.. (this file is backend/ledgr/config.py)
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

# Where the user drops the raw Kaggle CSVs (Elliptic / Elliptic++)
DEFAULT_RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
# Where normalized artifacts, splits, graph index, and verification logs are written
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts"

# --- METHODOLOGY.md §1 binding parameters (logged on every split run) ---
# High-degree hub addresses (major exchange hot wallets) are excluded from the
# component-forming step so one hub cannot merge thousands of unrelated
# entities into a single giant component. Degree above this threshold => hub.
HUB_DEGREE_THRESHOLD = 50
# Entity-level train/val/test split ratio (METHODOLOGY.md §1 step 2: 70/15/15)
TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15
# Fixed seed so the split is reproducible and auditable
SPLIT_SEED = 42

# Label encoding used everywhere downstream
LABEL_ILlicit = 1  # noqa: N816 — kept lowercase-ish for grep-ability
LABEL_LICIT = 0
LABEL_UNKNOWN = -1

RAW_LABEL_MAP = {"1": LABEL_ILlicit, "2": LABEL_LICIT, "unknown": LABEL_UNKNOWN}

# --- Phase R3: rule-based signal parameters (logged with every validation run) ---
# Peel chain: successive nodes each forwarding to exactly one next node
PEEL_CHAIN_MIN_HOPS = 2
PEEL_CHAIN_MAX_TIME_GAP = 1  # consecutive chain edges may span at most N time steps
# Rapid fan-out: few funding inputs, many outputs, tight time window
FANOUT_MIN_OUT = 10
FANOUT_MAX_IN = 1
FANOUT_TIME_WINDOW = 1
# Mixer adjacency: how many hops from a known mixer address still counts as adjacent
MIXER_MAX_HOPS = 2
# Auditable rule weights -> composite rule_score (sum of fired weights, 0..100)
RULE_WEIGHTS = {"peel_chain": 40, "rapid_fan_out": 30, "mixer_adjacent": 30}
# rule_flag tiers from rule_score
RULE_FLAG_THRESHOLDS = {"high": 60, "medium": 30}  # >0 below medium => "low", 0 => "none"

# Mixer-address validation set: one address per line, '#'-comments allowed.
# Not committed with fabricated entries — must be sourced (SCOPE.md / DATA.md).
MIXER_LIST_FILE = REPO_ROOT / "data" / "mixers.txt"

# Optional: per-rule tuning overrides via env (kept explicit, never magic numbers)
def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def data_dir() -> Path:
    return Path(os.environ.get("LEDGR_DATA_DIR", DEFAULT_RAW_DATA_DIR))


def artifacts_dir() -> Path:
    return Path(os.environ.get("LEDGR_ARTIFACTS_DIR", DEFAULT_ARTIFACTS_DIR))


def rule_params() -> dict:
    """Current rule parameters — included in every rule-engine output for auditability."""
    return {
        "peel_chain_min_hops": _env_int("LEDGR_PEEL_MIN_HOPS", PEEL_CHAIN_MIN_HOPS),
        "peel_chain_max_time_gap": PEEL_CHAIN_MAX_TIME_GAP,
        "fanout_min_out": _env_int("LEDGR_FANOUT_MIN_OUT", FANOUT_MIN_OUT),
        "fanout_max_in": FANOUT_MAX_IN,
        "fanout_time_window": FANOUT_TIME_WINDOW,
        "mixer_max_hops": _env_int("LEDGR_MIXER_MAX_HOPS", MIXER_MAX_HOPS),
        "rule_weights": dict(RULE_WEIGHTS),
        "rule_flag_thresholds": dict(RULE_FLAG_THRESHOLDS),
    }


# --- Phase R4: learned signal (random-forest baseline, ARCHITECTURE.md Module 3b) ---
# Fixed seed so the model is reproducible and auditable (logged with every run).
MODEL_SEED = 42
# Random-forest tree count for the committed MVP baseline (ROADMAP.md Phase 4
# decision). Documented, fixed, not tuned to inflate metrics on this dataset.
RF_N_ESTIMATORS = 200
# Learned-signal flag threshold: risk score (P(illicit)) at or above this => the
# learned signal flags the wallet. This is the handoff to the correlation layer
# (Phase R5 confirmed/watch); documented here and in artifacts/model_eval.json,
# never left as an unnamed cutoff (METHODOLOGY.md §4).
LEARNED_FLAG_THRESHOLD = 0.5
# Artifact filenames for the trained model and the feature lookup it needs at
# query time (the pre-indexed graph stores only label + time_step, not features).
LEARNED_MODEL_FILE = "learned_model.joblib"
FEATURE_LOOKUP_FILE = "feature_lookup.pkl"


def model_eval_report(out_dir: Path | None = None) -> Path:
    """Path to the R4 evaluation report (metrics logged per METHODOLOGY.md §2)."""
    base = Path(out_dir) if out_dir else artifacts_dir()
    return base / "model_eval.json"


# --- Phase R6: clustering / attribution (ARCHITECTURE.md Module 5) ---
# Supplementary named-exchange tagging (hot-wallet lists, community tagging).
# Format: data/exchanges.example.txt. Sourced entries only — never fabricated
# (SCOPE.md / DATA.md). Matched attribution is tagged `supplementary-source`
# and kept visibly separate from `elliptic-derived` clustering.
EXCHANGE_LIST_FILE = REPO_ROOT / "data" / "exchanges.txt"
CLUSTER_REPORT_FILE = "clusters.json"
# Max member wallets listed per cluster in the report (full membership is the
# entity_id grouping; the sample keeps the API payload bounded).
CLUSTER_MEMBER_SAMPLE = 10

# --- Phase R9: live address tracing (out-of-dataset wallets) ---
# Live tracing is demo-time only (SCOPE.md): on-demand fetch of a small, bounded
# window around ONE reported address — never continuous ingestion, never bulk.
# Free-tier APIs (Blockstream primary, BlockCypher fallback) — hard caps keep us
# far from rate limits. Disable entirely with LEDGR_LIVE_TRACING=0.
LIVE_MAX_TXS_PER_ADDRESS = 50  # most recent N txs fetched per address (Binance-scale wallets)
LIVE_MAX_COUNTERPARTY_FETCHES = 25  # max extra address fetches beyond the seed (hop_depth > 1)
LIVE_MAX_NODES = 500  # hard cap on the ad-hoc live subgraph size
# Elliptic time steps are ~2 weeks; live block timestamps are mapped to the same
# granularity so the R3 time-window heuristics keep their documented semantics.
LIVE_TIME_STEP_SECONDS = 14 * 24 * 3600


def live_tracing_enabled() -> bool:
    """Live tracing toggle (LEDGR_LIVE_TRACING env, default on)."""
    return os.environ.get("LEDGR_LIVE_TRACING", "1") != "0"
