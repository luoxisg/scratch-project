import itertools

import pytest

from policy import decide_web
from web.workflow import evidence_check


@pytest.mark.parametrize(("b", "c"), tuple(itertools.product(("pass", "fail", "unknown"), repeat=2)))
def test_decision_matrix(b, c):
    expected = {
        ("pass", "pass"): "proceed_to_pilot",
        ("pass", "fail"): "compare_alternatives",
        ("fail", "pass"): "redesign_solution",
        ("fail", "fail"): "reject_proposal",
    }
    assert decide_web(b, c)["action"] == expected.get((b, c), "gather_evidence")


def test_unknown_when_citation_is_invented():
    result = evidence_check({"verdict": "pass", "findings": [
        {"criterion_id": "S1", "stance": "supports", "evidence_ids": ["invented"]},
    ]}, {"evidence": [], "success_criteria": ["Measure workload"]})
    assert result["verdict"] == "unknown"
    assert {"code": "invalid_citation", "values": ["invented"]} in result["issues"]


@pytest.mark.parametrize("status", ["claim", "assumption", "inference", "missing", "contradictory", "verified"])
def test_binary_verdict_needs_verified_directional_evidence(status):
    result = evidence_check({"verdict": "fail", "findings": [
        {"criterion_id": "S1", "stance": "challenges", "evidence_ids": ["E1"]},
    ]}, {"evidence": [{"id": "E1", "status": status, "criterion": 1}], "success_criteria": ["Measure workload"]})
    assert result["verdict"] == ("fail" if status == "verified" else "unknown")
