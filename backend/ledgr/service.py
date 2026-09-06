"""Phase R2 (rebuilt as R3 prerequisite) — FastAPI inference service.

Endpoints:
  GET  /health   -> service + artifact status
  POST /trace    -> {address (tx id or wallet), hop_depth} -> real local subgraph + stats
  POST /rules    -> {address, hop_depth} -> per-heuristic rule-based signal (Phase R3)
  POST /score    -> {address} -> learned-signal risk score (Phase R4, Module 3b)
  POST /verdict  -> {address, hop_depth} -> confirmed/watch/none correlation (Phase R5)
  GET  /clusters -> Phase R6 cluster report (confidence tiers + attribution)

The Node backend (server.ts) will call these endpoints (Phase R7 wiring).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .cluster import load_cluster_report
from .config import live_tracing_enabled
from .correlate import VERDICT_WATCH, correlate
from .graph import load_graph_index, local_subgraph
from .learn import load_feature_lookup, load_learned_model, predict_wallet
from .live_graph import (
    SOURCE_LIVE,
    SOURCE_NOT_FOUND_ON_CHAIN,
    LiveSourceError,
    live_subgraph_payload,
    trace_live,
)
from .rules import run_rules

logger = logging.getLogger(__name__)

app = FastAPI(title="LEDGR Inference Service", version="0.1.0")
_G = None
_MODEL = None
_FEATURES = None


class TraceRequest(BaseModel):
    address: str = Field(..., min_length=1, description="Wallet address or Elliptic tx id")
    hop_depth: int = Field(2, ge=1, le=10, description="Bounded hop depth for subgraph extraction")


class ScoreRequest(BaseModel):
    address: str = Field(..., min_length=1, description="Wallet address or Elliptic tx id")


@app.on_event("startup")
def _load_index() -> None:
    global _G
    try:
        _G = load_graph_index()
    except FileNotFoundError as e:
        logger.error("%s", e)
        _G = None


@app.on_event("startup")
def _load_learned_signal() -> None:
    """Load the R4 trained model + feature lookup so /score can serve real risks."""
    global _MODEL, _FEATURES
    try:
        _MODEL = load_learned_model()
        _FEATURES = load_feature_lookup()
    except FileNotFoundError as e:
        logger.warning("Learned signal unavailable (R4): %s", e)
        _MODEL = None
        _FEATURES = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if _G is not None else "degraded",
        "graph_loaded": _G is not None,
        "learned_signal_loaded": _MODEL is not None and _FEATURES is not None,
        "service": "ledgr-inference",
    }


@app.post("/trace")
def trace(req: TraceRequest) -> dict:
    """Indexed lookup first (fast path); on miss, a bounded live lookup (Phase R9).

    Failure modes stay distinct: `elliptic-indexed` (fast path), `live-lookup`
    (bounded real-chain fetch + rules), `not-found-on-chain` (address genuinely
    has no history — honest result, not an error), and 503 (live API itself
    failed) — never collapsed into one "unavailable" message.
    """
    if _G is not None:
        try:
            result = local_subgraph(_G, req.address, req.hop_depth)
            result["source"] = "elliptic-indexed"
            return result
        except KeyError:
            pass  # not in the indexed graph — fall through to live lookup
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
    return _trace_live_response(req.address, req.hop_depth)


def _trace_live_response(address: str, hop_depth: int) -> dict:
    """Live-lookup path shared by /trace, /rules and /verdict (Phase R9)."""
    if not live_tracing_enabled():
        raise HTTPException(
            status_code=404,
            detail="Address not in the indexed Elliptic graph and live tracing is disabled.",
        )
    try:
        outcome = trace_live(address, hop_depth)
    except LiveSourceError as e:
        if e.kind == "bad-address":
            # The explorers rejected the address itself: honest 'bad address'
            # result — NOT a service failure (never collapsed into one message).
            return {
                "source": SOURCE_NOT_FOUND_ON_CHAIN,
                "note": "Address is not valid / not recognized by the Bitcoin chain explorers — nothing to trace and no signal to compute.",
                "address": address,
            }
        raise HTTPException(
            status_code=503,
            detail=f"Live block-explorer API failed (address is not in the indexed dataset): {e}",
        ) from e
    if outcome["source"] == SOURCE_NOT_FOUND_ON_CHAIN:
        return {"source": SOURCE_NOT_FOUND_ON_CHAIN, "note": outcome["note"], "address": address}
    G = outcome["graph"]
    return live_subgraph_payload(G, address, outcome["meta"])


def _live_rules(address: str, hop_depth: int) -> dict:
    """Run the R3 rule engine on the live-fetched subgraph (rules need no training data)."""
    if not live_tracing_enabled():
        raise HTTPException(
            status_code=404,
            detail="Address not in the indexed Elliptic graph and live tracing is disabled.",
        )
    try:
        outcome = trace_live(address, hop_depth)
    except LiveSourceError as e:
        if e.kind == "bad-address":
            return {
                "source": SOURCE_NOT_FOUND_ON_CHAIN,
                "note": "Address is not valid / not recognized by the Bitcoin chain explorers — nothing to trace and no signal to compute.",
                "address": address,
            }
        raise HTTPException(
            status_code=503,
            detail=f"Live block-explorer API failed (address is not in the indexed dataset): {e}",
        ) from e
    if outcome["source"] == SOURCE_NOT_FOUND_ON_CHAIN:
        return {"source": SOURCE_NOT_FOUND_ON_CHAIN, "note": outcome["note"], "address": address}
    rules_out = run_rules(outcome["graph"], address, hop_depth=hop_depth)
    rules_out["source"] = SOURCE_LIVE
    rules_out["live_meta"] = outcome["meta"]
    rules_out["ml_signal"] = "unavailable — address not in training dataset"
    return rules_out


def _live_verdict(address: str, hop_depth: int) -> dict:
    """Verdict for a live-looked-up address, CAPPED AT `watch` in code.

    Only the rule signal can run on a live-fetched wallet; the learned signal
    has no feature vector for it (honestly classified:false). `confirmed`
    requires two agreeing signals, so a live verdict can never be confirmed —
    enforced here explicitly, not assumed.
    """
    rules_out = _live_rules(address, hop_depth)
    if rules_out.get("source") == SOURCE_NOT_FOUND_ON_CHAIN:
        return rules_out
    learned_unavailable = {
        "wallet": address,
        "classified": False,
        "risk_score": None,
        "prediction": None,
        "learned_flag": False,
        "note": "unavailable — address not in training dataset",
    }
    verdict = correlate(rules_out, learned_unavailable)
    if verdict["verdict"] == "confirmed":  # correlation cap (defensive; unreachable)
        verdict["verdict"] = VERDICT_WATCH
        verdict["correlation_cap"] = "live-lookup verdicts are capped at watch: only one independent signal exists"
    verdict["correlation_cap"] = (
        "live-lookup verdicts are capped at watch: only the rule signal can run on a "
        "live-fetched wallet, and confirmed requires two independent signals agreeing"
    )
    verdict["source"] = SOURCE_LIVE
    verdict["live_meta"] = rules_out.get("live_meta")
    return verdict


@app.post("/rules")
def rules(req: TraceRequest) -> dict:
    """Rule-based signal (Module 3a): indexed fast path, bounded live lookup on miss (R9)."""
    if _G is not None:
        try:
            return run_rules(_G, req.address, hop_depth=req.hop_depth)
        except KeyError:
            pass  # not in the indexed graph — fall through to live lookup
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
    return _live_rules(req.address, req.hop_depth)


@app.post("/score")
def score(req: ScoreRequest) -> dict:
    """Learned-signal risk score (Phase R4, Module 3b) for one wallet.

    Replaces the hardcoded mlScore/mlPrediction. Returns a real P(illicit) for
    wallets present in the Elliptic feature set; honestly reports `classified:
    False` (no fabricated risk) for out-of-dataset addresses.
    """
    if _MODEL is None or _FEATURES is None:
        raise HTTPException(
            status_code=503,
            detail="Learned signal unavailable. Run scripts/train_model.py first.",
        )
    return predict_wallet(_MODEL, _FEATURES, req.address)


@app.post("/verdict")
def verdict(req: TraceRequest) -> dict:
    """Phase R5 correlation: confirmed/watch/none with contributing-signal traceability.

    Indexed fast path: rule signal + learned signal -> correlate. If the wallet
    is not in the indexed graph, Phase R9's live path applies: rule signal only
    (rules need no training data), learned signal honestly unavailable, and the
    verdict is CAPPED AT `watch` in code — confirmed requires two independent
    signals and only one can exist for a live-fetched wallet.
    """
    if _G is not None:
        try:
            rules_out = run_rules(_G, req.address, hop_depth=req.hop_depth)
        except KeyError:
            return _live_verdict(req.address, req.hop_depth)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        if _MODEL is not None and _FEATURES is not None:
            learned_out = predict_wallet(_MODEL, _FEATURES, req.address)
        else:
            learned_out = {
                "wallet": req.address, "classified": False, "risk_score": None,
                "prediction": None, "learned_flag": False,
                "note": "learned signal unavailable — model artifacts not loaded",
            }
        return correlate(rules_out, learned_out)
    return _live_verdict(req.address, req.hop_depth)


@app.get("/clusters")
def clusters() -> dict:
    """Phase R6: Elliptic-derived entity clusters with confidence tiers and
    supplementary-source attribution (kept separate per the R6 requirement)."""
    try:
        return load_cluster_report()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail="Cluster report unavailable. Run scripts/build_clusters.py first.",
        ) from e
