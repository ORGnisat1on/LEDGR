"""Phase R8: end-to-end hardening check against the REAL ingested dataset.

Runs the FastAPI service in-process (real graph index + real trained model)
and exercises the edge cases named in BACKEND_BUILD_PLAN.md Phase R8:
  1. known-licit wallets        -> never 'confirmed' without both signals
  2. known-illicit wallets      -> verdict computed, signals traceable
  3. isolated / low-degree wallets (no illicit signal) -> honest low verdicts
  4. very large subgraph (hub seed, max hop) -> bounded and completing
  5. out-of-dataset address     -> loud 404 / classified:false (never fabricated)
  6. correlation invariant      -> confirmed implies BOTH signals flagged;
                                   no verdict raised when neither signal fired

This is a service-hardening check, NOT a model evaluation: it reports no
accuracy/recall numbers (those come only from the entity-safe-split eval in
artifacts/model_eval.json per METHODOLOGY.md).
Writes artifacts/hardening_report.json and exits non-zero on any failure.
"""

import json
import random
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import ledgr.service as svc  # noqa: E402

ARTIFACTS = ROOT / "artifacts"
CLASSES = ROOT / "data" / "raw" / "elliptic_txs_classes.csv"
RANDOM_SEED = 42  # named constant; sampling only, no metric tuning


def main() -> int:
    with TestClient(svc.app) as client:  # context manager runs startup hooks (loads real artifacts)
        return run_checks(client)


def run_checks(client: TestClient) -> int:
    health = client.get("/health").json()
    if not health.get("graph_loaded") or not health.get("learned_signal_loaded"):
        print("FATAL: real artifacts not loaded — run run_ingest.py / train_model.py first")
        return 2

    G = svc._G
    classes = pd.read_csv(CLASSES)
    illicit_ids = set(classes.loc[classes["class"].astype(str) == "1", "txId"].astype(str))
    licit_ids = set(classes.loc[classes["class"].astype(str) == "2", "txId"].astype(str))
    in_graph = set(G.nodes)
    illicit = sorted(illicit_ids & in_graph)
    licit = sorted(licit_ids & in_graph)
    rng = random.Random(RANDOM_SEED)

    checks = []
    failures = []

    def record(name: str, ok: bool, detail: dict):
        checks.append({"check": name, "ok": ok, "detail": detail})
        if not ok:
            failures.append(name)

    def verdict_of(addr: str) -> dict:
        r = client.post("/verdict", json={"address": addr, "hop_depth": 2})
        return r.json()

    def counts(values) -> dict:
        out: dict = {}
        for v in values:
            out[v] = out.get(v, 0) + 1
        return out

    # --- 1/2: known-licit and known-illicit wallets -------------------------
    licit_verdicts, illicit_verdicts = [], []
    for addr in rng.sample(licit, min(25, len(licit))):
        licit_verdicts.append(verdict_of(addr).get("verdict"))
    for addr in rng.sample(illicit, min(25, len(illicit))):
        illicit_verdicts.append(verdict_of(addr).get("verdict"))
    record(
        "known_licit_never_confirmed",
        all(v != "confirmed" for v in licit_verdicts),
        {"verdicts": counts(licit_verdicts)},
    )
    record(
        "known_illicit_verdicts_computed",
        all(v in {"confirmed", "watch", "none"} for v in illicit_verdicts),
        {"verdicts": counts(illicit_verdicts)},
    )

    # --- 3: isolated / low-degree wallets -----------------------------------
    low_degree = sorted(G.nodes, key=lambda n: G.degree(n))[:25]
    low_verdicts, low_flag_without_signal = [], []
    for addr in low_degree:
        body = verdict_of(addr)
        low_verdicts.append(body.get("verdict"))
        if body.get("verdict") in {"confirmed", "watch"}:
            sig = body.get("contributing_signals", {})
            fired = sig.get("rule_signal", {}).get("flagged", False) or sig.get(
                "learned_signal", {}
            ).get("flagged", False)
            if not fired:
                low_flag_without_signal.append(addr)
    record(
        "isolated_low_degree_wallets_honest",
        not low_flag_without_signal,
        {"verdicts": counts(low_verdicts), "bad": low_flag_without_signal},
    )

    # --- 4: very large subgraph (hub seed, max hop) -------------------------
    hub = max(G.nodes, key=lambda n: G.degree(n))
    t0 = time.time()
    r = client.post("/trace", json={"address": hub, "hop_depth": 10})
    elapsed = time.time() - t0
    body = r.json()
    n_nodes = len(body.get("nodes", [])) if isinstance(body, dict) else 0
    record(
        "hub_subgraph_bounded_and_completes",
        r.status_code == 200 and elapsed < 30 and n_nodes > 0,
        {
            "hub": hub,
            "degree": G.degree(hub),
            "status": r.status_code,
            "subgraph_nodes": n_nodes,
            "seconds": round(elapsed, 2),
        },
    )

    # --- 5: out-of-dataset address -------------------------------------------
    r_trace = client.post("/trace", json={"address": "out-of-dataset-wallet", "hop_depth": 2})
    r_verdict = client.post("/verdict", json={"address": "out-of-dataset-wallet", "hop_depth": 2})
    r_score = client.post("/score", json={"address": "out-of-dataset-wallet"})
    record(
        "out_of_dataset_never_fabricated",
        r_trace.status_code == 404
        and r_verdict.status_code == 404
        and r_score.status_code == 200
        and r_score.json().get("classified") is False,
        {"trace": r_trace.status_code, "verdict": r_verdict.status_code, "score": r_score.json()},
    )

    # --- 6: correlation invariant sweep --------------------------------------
    seeds = rng.sample(sorted(in_graph), min(60, len(in_graph)))
    invariant_bad, verdict_counts = [], {}
    for addr in seeds:
        body = verdict_of(addr)
        v = body.get("verdict")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
        sig = body.get("contributing_signals", {})
        rule_flag = sig.get("rule_signal", {}).get("flagged", False)
        learned_flag = sig.get("learned_signal", {}).get("flagged", False)
        if v == "confirmed" and not (rule_flag and learned_flag):
            invariant_bad.append(f"confirmed_without_both:{addr}")
        if not rule_flag and not learned_flag and v in {"confirmed", "watch"}:
            invariant_bad.append(f"raised_without_any_signal:{addr}")
    record("correlation_invariant", not invariant_bad, {"verdicts": verdict_counts, "bad": invariant_bad})

    report = {
        "kind": "service_hardening_check",
        "note": "Phase R8 hardening check over the real ingested dataset; not a model evaluation (no accuracy/recall reported here — see model_eval.json for the entity-safe-split eval).",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "all_passed": not invariant_bad
        and not [c for c in checks if not c["ok"]],
        "checks": checks,
    }
    out = ARTIFACTS / "hardening_report.json"
    out.write_text(json.dumps(report, indent=2))
    for c in checks:
        print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")
    print(f"Report -> {out}")
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
