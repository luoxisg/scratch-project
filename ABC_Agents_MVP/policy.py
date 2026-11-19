"""Pure, deterministic decision policy for sufficiency/necessity checks."""

from typing import Literal

Verdict = Literal["通过", "不通过", "证据不足"]


def decide(sufficiency: Verdict, necessity: Verdict) -> str:
    """Map two independent assessments to a decision state.

    Do not interpret 'not necessary' as equivalent to 'not worthwhile'.
    An unknown judgement must not be upgraded to a pass.
    """
    allowed = {"通过", "不通过", "证据不足"}
    if sufficiency not in allowed or necessity not in allowed:
        raise ValueError("Verdict must be 通过/不通过/证据不足")

    if "证据不足" in (sufficiency, necessity):
        return "需要补证"
    return {
        ("通过", "通过"): "充分且必要（待实际验证）",
        ("通过", "不通过"): "有效但可替代",
        ("不通过", "通过"): "需求存在但方案不足",
        ("不通过", "不通过"): "暂不支持立项",
    }[(sufficiency, necessity)]


WebVerdict = Literal["pass", "fail", "unknown"]

_WEB_TO_CLI: dict[WebVerdict, Verdict] = {
    "pass": "通过", "fail": "不通过", "unknown": "证据不足",
}

DECISION_MATRIX = (
    ("pass", "pass", "sufficient_necessary", "proceed_to_pilot"),
    ("pass", "fail", "effective_replaceable", "compare_alternatives"),
    ("fail", "pass", "necessary_insufficient", "redesign_solution"),
    ("fail", "fail", "not_supported", "reject_proposal"),
    ("unknown", "any", "evidence_required", "gather_evidence"),
    ("any", "unknown", "evidence_required", "gather_evidence"),
)


def decide_web(sufficiency: WebVerdict, necessity: WebVerdict) -> dict[str, str]:
    """Reuse the CLI rule and expose stable codes for localisation."""
    if sufficiency not in _WEB_TO_CLI or necessity not in _WEB_TO_CLI:
        raise ValueError("Verdict must be pass/fail/unknown")
    legacy = decide(_WEB_TO_CLI[sufficiency], _WEB_TO_CLI[necessity])
    if legacy == "需要补证":
        _, _, state, action = DECISION_MATRIX[-1]
    else:
        state, action = next(
            (state, action) for b, c, state, action in DECISION_MATRIX
            if (b, c) == (sufficiency, necessity)
        )
    return {"state": state, "action": action, "legacy_label": legacy,
            "sufficiency": sufficiency, "necessity": necessity}
