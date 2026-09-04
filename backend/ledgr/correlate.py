"""Phase R5 — Correlation Layer (ARCHITECTURE.md Module 4, METHODOLOGY.md §4).

Combines the two independently-validated signals into a single per-wallet
verdict, exactly as METHODOLOGY.md §4 defines:

  Confirmed  = rule-based signal flags the wallet AND learned-signal
               confidence exceeds its flag threshold (learned_flag = True).
  Watch      = exactly one of the two signals flags the wallet.
  None       = neither signal flags the wallet.

The confirmed set is therefore always a strict subset of each individual
flagged set (it requires *both*), and a wallet neither signal flags can never
be upgraded to a flag — both invariants verified by test_correlate.py.

This **replaces** the mock analyzer's always-`confirmed` verdict.
"""

from __future__ import annotations

import logging

from .config import LEARNED_FLAG_THRESHOLD

logger = logging.getLogger(__name__)

VERDICT_CONFIRMED = "confirmed"
VERDICT_WATCH = "watch"
VERDICT_NONE = "none"

# All valid verdicts (for validation / auditing).
VERDICTS = (VERDICT_CONFIRMED, VERDICT_WATCH, VERDICT_NONE)


def correlate(rules_result: dict, learned_result: dict) -> dict:
    """Combine the R3 rule signal and R4 learned signal into a verdict.

    Args:
        rules_result: output of ledgr.rules.run_rules (keys: wallet, rule_score,
            rule_flag, rules_fired, contributing_signals, ...).
        learned_result: output of ledgr.learn.predict_wallet (keys: wallet,
            classified, risk_score, prediction, learned_flag, flag_threshold).

    Returns:
        A dict with `wallet`, `verdict`, and auditable `contributing_signals`.

    An unclassified learned result (`classified: False`) means the learned
    signal is NOT flagged, so a wallet with only an unclassified learned result
    and no rule fire is "none" (never upgraded).
    """
    wallet = rules_result.get("wallet") or learned_result.get("wallet")

    rule_flagged = bool(rules_result.get("rules_fired"))
    learned_flagged = bool(learned_result.get("learned_flag"))

    if rule_flagged and learned_flagged:
        verdict = VERDICT_CONFIRMED
    elif rule_flagged or learned_flagged:
        verdict = VERDICT_WATCH
    else:
        verdict = VERDICT_NONE

    learned_threshold = learned_result.get("flag_threshold") or LEARNED_FLAG_THRESHOLD

    contributing = {
        "rule_signal": {
            "flagged": rule_flagged,
            "rule_score": rules_result.get("rule_score"),
            "rule_flag": rules_result.get("rule_flag"),
            "rules_fired": list(rules_result.get("rules_fired") or []),
        },
        "learned_signal": {
            "flagged": learned_flagged,
            "classified": learned_result.get("classified"),
            "risk_score": learned_result.get("risk_score"),
            "prediction": learned_result.get("prediction"),
            "flag_threshold": learned_threshold,
        },
    }

    result = {
        "wallet": wallet,
        "verdict": verdict,
        "contributing_signals": contributing,
    }
    logger.info("Correlation %s: verdict=%s (rule_flagged=%s learned_flagged=%s)",
                wallet, verdict, rule_flagged, learned_flagged)
    return result