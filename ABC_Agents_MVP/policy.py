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
