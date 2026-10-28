"""A-B-C 多 Agent 决策审查 MVP：A 总调度，B 充分性，C 必要性。

Requires:
  pip install -r requirements.txt
  export OPENAI_API_KEY=...
  python abc_agents.py --input example_input.json --output review.json

This program is an evidence-assisted review, not a mathematical proof engine.
"""

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from agents import Agent, Runner
from pydantic import BaseModel, Field

from policy import decide


class ReviewInput(BaseModel):
    goal: str = Field(description="Desired outcome Y")
    solution: str = Field(description="Proposed option X")
    decision_question: str = Field(description="Precisely scoped decision question")
    success_criteria: list[str] = Field(description="Observable acceptance criteria")
    evidence: list[str] = Field(default_factory=list, description="Verified evidence, each with source/date")
    constraints: list[str] = Field(default_factory=list)


class IndependentReview(BaseModel):
    verdict: Literal["通过", "不通过", "证据不足"]
    rationale: str = Field(description="Reasoning summary with explicit uncertainties")
    supporting_evidence: list[str] = Field(description="Only evidence provided in the input; quote/cite the source ID")
    counterexamples: list[str] = Field(description="Potential falsifiers, not invented facts")
    missing_evidence: list[str] = Field(description="What needs testing or independent validation")
    next_experiment: str = Field(description="Cheapest concrete verification experiment")


class AConclusion(BaseModel):
    executive_summary: str
    disagreements: list[str]
    risk_controls: list[str]
    prioritized_actions: list[str]
    evidence_limitations: str


COMMON_RULES = """
你是独立审查员，必须围绕同一个清晰的X(待审方案)与Y(目标)判断。
只可使用输入中的证据；不联网，不猜测市场价格、技术指标、法律要求或客户意愿。
没有可靠证据应填“证据不足”，不能用自信表达代替实证。
区分事实、假设、推论，支持证据须引用输入证据项的原始编号。
严格执行指定的逻辑检查，不输出最终投资/采购建议。
"""

B = Agent(
    name="Agent B - Sufficiency",
    model=os.getenv("ABC_AGENTS_MODEL", "gpt-4.1-mini"),
    instructions=COMMON_RULES + """
你的唯一职责是【充分性】审查：方案X连同明确列出的前提是否足以实现目标Y？
查找实现链条、边界条件、集成/运营/成本与可测量成功标准，尝试构造反例。
不能把必要性/客户不可替代性当作充分性。
如果存在未验证的决定性条件，verdict=证据不足；已有可信反例则可判不通过。
""",
    output_type=IndependentReview,
)

C = Agent(
    name="Agent C - Necessity",
    model=os.getenv("ABC_AGENTS_MODEL", "gpt-4.1-mini"),
    instructions=COMMON_RULES + """
你的唯一职责是【必要性】审查：为了实现目标Y，是否一定需要X？
使用反事实删除测试：移除X，使用人工、已有功能、第三方替代或改变流程，能否达到同等Y？
明确目标Y本身的必要前提，与“特定厂商/特定技术X是否必要”是两个不同命题。
只有输入中有可信的等效替代证据，才能判X“不通过”(非必要)。
只有输入中有强证据排除了主要可行替代路径，才判X“通过”(必要)。
仅能想象替代方案而无实证，应列为假设并判“证据不足”。
必要性不等于商业价值：非必要方案仍可通过性价比创造价值。
""",
    output_type=IndependentReview,
)

A = Agent(
    name="Agent A - Orchestrator",
    model=os.getenv("ABC_AGENTS_MODEL", "gpt-4.1-mini"),
    instructions="""
你是三Agent系统的最终综合调度角色。B与C已经被程序强制独立完成审查。
只基于输入中的任务、B审查、C审查与程序化决策标签总结；不得改写B或C的原始结论。
绝不把AI审查输出称为逻辑证明、法律意见或实际付费承诺。
输出可验证的下一步实验、风险控制和双方分歧。
不得虚构证据或宣传此项目已获客户认可。
""",
    output_type=AConclusion,
)


def payload_data(task: ReviewInput) -> str:
    numbered = [f"E{i+1}: {e}" for i, e in enumerate(task.evidence)]
    return json.dumps(
        {**task.model_dump(exclude={"evidence"}), "evidence": numbered},
        ensure_ascii=False, indent=2,
    )


async def perform_review(task: ReviewInput, cross_examine: bool = False) -> dict:
    """Code-owned orchestration guarantees both specialists are called."""
    shared = payload_data(task)
    b_run, c_run = await asyncio.gather(
        Runner.run(B, "对下列任务独立进行充分性审查：\n" + shared),
        Runner.run(C, "对下列任务独立进行必要性审查：\n" + shared),
    )
    b_initial: IndependentReview = b_run.final_output
    c_initial: IndependentReview = c_run.final_output
    b, c = b_initial, c_initial

    # Optional bounded second round. First-round reports stay visible for audit.
    if cross_examine:
        b_second_prompt = (
            "请重新独立审核充分性。你可以反驳对方的必要性意见，"
            "但不得把必要性判断代替充分性，亦不得采信对方没有证据的断言。\n"
            + shared + "\n你第一轮的意见：\n" + b_initial.model_dump_json()
            + "\nC 的独立意见：\n" + c_initial.model_dump_json()
        )
        c_second_prompt = (
            "请重新独立审核必要性。你可以反驳对方的充分性意见，"
            "但不得把充分性判断代替必要性，亦不得采信对方没有证据的断言。\n"
            + shared + "\n你第一轮的意见：\n" + c_initial.model_dump_json()
            + "\nB 的独立意见：\n" + b_initial.model_dump_json()
        )
        b_again, c_again = await asyncio.gather(
            Runner.run(B, b_second_prompt), Runner.run(C, c_second_prompt)
        )
        b, c = b_again.final_output, c_again.final_output

    label = decide(b.verdict, c.verdict)   # Deterministic gate; A cannot override it

    a_input = json.dumps({
        "task": task.model_dump(),
        "b_sufficiency": b.model_dump(),
        "c_necessity": c.model_dump(),
        "rule_based_decision": label,
    }, ensure_ascii=False, indent=2)
    a_run = await Runner.run(A, "请综合两项独立报告并提出验证行动：\n" + a_input)
    a: AConclusion = a_run.final_output

    return {
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": os.getenv("ABC_AGENTS_MODEL", "gpt-4.1-mini"),
        "task": task.model_dump(),
        "B_sufficiency": b.model_dump(),
        "C_necessity": c.model_dump(),
        "cross_examine": cross_examine,
        "initial_independent_reviews": (
            {"B": b_initial.model_dump(), "C": c_initial.model_dump()}
            if cross_examine else None
        ),
        "deterministic_decision": label,
        "A_orchestrator": a.model_dump(),
        "disclaimer": "该结论仅是基于提供证据的初步审查，不能替代实测、法律意见或客户采购决定。",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A-B-C multi-agent logic review")
    parser.add_argument("--input", type=Path, default=Path("example_input.json"))
    parser.add_argument("--output", type=Path, default=Path("review.json"))
    parser.add_argument("--cross-examine", action="store_true", help="增加第二轮互相质询审查")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        parser.error("请先配置环境变量 OPENAI_API_KEY")
    task = ReviewInput.model_validate_json(args.input.read_text(encoding="utf-8"))
    report = asyncio.run(perform_review(task, cross_examine=args.cross_examine))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"审查结束：{report['deterministic_decision']}，结果写入 {args.output}")


if __name__ == "__main__":
    main()
