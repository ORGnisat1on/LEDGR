import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from ledgr.correlate import (  # noqa: E402
    VERDICT_CONFIRMED,
    VERDICT_NONE,
    VERDICT_WATCH,
    correlate,
)

# Minimal but shape-accurate rule / learned results (matching run_rules and
# predict_wallet output schemas).


def _rules_fired(fired, score=40, flag="medium", wallet="w"):
    return {
        "wallet": wallet,
        "rule_score": score,
        "rule_flag": flag,
        "rules_fired": fired,
        "contributing_signals": {},
    }


def _learned(flagged, risk=0.9, classified=True, wallet="w"):
    return {
        "wallet": wallet,
        "classified": classified,
        "risk_score": risk if classified else None,
        "prediction": ("illicit" if flagged and classified else "licit"),
        "learned_flag": flagged,
        "flag_threshold": 0.5,
    }


def test_both_fire_is_confirmed():
    out = correlate(_rules_fired(["peel_chain"]), _learned(True))
    assert out["verdict"] == VERDICT_CONFIRMED
    assert out["contributing_signals"]["rule_signal"]["flagged"] is True
    assert out["contributing_signals"]["learned_signal"]["flagged"] is True


def test_only_rule_is_watch():
    out = correlate(_rules_fired(["peel_chain"]), _learned(False))
    assert out["verdict"] == VERDICT_WATCH


def test_only_learned_is_watch():
    out = correlate(_rules_fired([]), _learned(True))
    assert out["verdict"] == VERDICT_WATCH


def test_neither_is_none():
    out = correlate(_rules_fired([]), _learned(False))
    assert out["verdict"] == VERDICT_NONE


def test_confirmed_is_strict_subset_of_each_flagged_set():
    """A wallet is 'confirmed' only if BOTH signals flag it — the confirmed set
    is a strict subset of each individual flagged set (R5 spec)."""
    # Rule-flagged set includes both fire / rule-only / ... ; learned only where
    # learned flagged. Confirmed requires rule_flagged AND learned_flagged.
    both = correlate(_rules_fired(["peel_chain"]), _learned(True)).get("verdict") == VERDICT_CONFIRMED
    assert both
    # If either individual signal does NOT flag, it cannot be confirmed.
    for rule_ok, learned_ok in [(True, False), (False, True), (False, False)]:
        v = correlate(_rules_fired(["peel_chain"] if rule_ok else []), _learned(learned_ok))
        assert v["verdict"] != VERDICT_CONFIRMED


def test_neither_fire_never_upgraded():
    """'neither fires' -> 'none', never upgraded to a flag (R5 spec)."""
    assert correlate(_rules_fired([]), _learned(False))["verdict"] == VERDICT_NONE


def test_unclassified_learned_not_a_flag():
    """An out-of-dataset wallet has a 'classified: False' learned result; the
    learned signal must NOT count as flagged, so it cannot become confirmed."""
    out = correlate(_rules_fired(["peel_chain"]), {
        "wallet": "w", "classified": False, "risk_score": None,
        "prediction": None, "learned_flag": False,
    })
    assert out["verdict"] == VERDICT_WATCH  # only the rule fired


def test_unclassified_learned_and_no_rule_is_none():
    out = correlate(_rules_fired([]), {
        "wallet": "w", "classified": False, "risk_score": None,
        "prediction": None, "learned_flag": False,
    })
    assert out["verdict"] == VERDICT_NONE


def test_contributing_signal_traceability():
    """contributing_signals must expose which signal(s) fired and their evidence."""
    out = correlate(_rules_fired(["rapid_fan_out"], score=30, flag="medium"),
                    _learned(False, risk=0.2))
    cs = out["contributing_signals"]
    assert cs["rule_signal"]["flagged"] is True
    assert cs["rule_signal"]["rules_fired"] == ["rapid_fan_out"]
    assert cs["rule_signal"]["rule_score"] == 30
    assert cs["learned_signal"]["risk_score"] == 0.2
    assert cs["learned_signal"]["flag_threshold"] == 0.5
    assert out["wallet"] == "w"


def test_verdicts_are_valid_enumeration():
    for rf, lf in ((True, True), (True, False), (False, True), (False, False)):
        v = correlate(_rules_fired(["peel_chain"] if rf else []), _learned(lf))["verdict"]
        assert v in (VERDICT_CONFIRMED, VERDICT_WATCH, VERDICT_NONE)