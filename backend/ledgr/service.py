"""Phase R2 (rebuilt as R3 prerequisite) — FastAPI inference service.

Endpoints:
  GET  /health   -> service + artifact status
  POST /trace    -> {address (tx id or wallet), hop_depth} -> real local subgraph + stats
  POST /rules    -> {address, hop_depth} -> per-heuristic rule-based signal (Phase R3)

The Node backend (server.ts) will call these endpoints (Phase R7 wiring).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .graph import load_graph_index, local_subgraph
from .rules import run_rules

logger = logging.getLogger(__name__)

app = FastAPI(title="LEDGR Inference Service", version="0.1.0")
_G = None


class TraceRequest(BaseModel):
    address: str = Field(..., min_length=1, description="Wallet address or Elliptic tx id")
    hop_depth: int = Field(2, ge=1, le=10, description="Bounded hop depth for subgraph extraction")


@app.on_event("startup")
def _load_index() -> None:
    global _G
    try:
        _G = load_graph_index()
    except FileNotFoundError as e:
        logger.error("%s", e)
        _G = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if _G is not None else "degraded",
        "graph_loaded": _G is not None,
        "service": "ledgr-inference",
    }


@app.post("/trace")
def trace(req: TraceRequest) -> dict:
    if _G is None:
        raise HTTPException(status_code=503, detail="Graph index unavailable. Run scripts/run_ingest.py.")
    try:
        return local_subgraph(_G, req.address, req.hop_depth)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/rules")
def rules(req: TraceRequest) -> dict:
    """Rule-based signal (Module 3a) for one wallet: per-heuristic, auditable output."""
    if _G is None:
        raise HTTPException(status_code=503, detail="Graph index unavailable. Run scripts/run_ingest.py.")
    try:
        return run_rules(_G, req.address, hop_depth=req.hop_depth)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
