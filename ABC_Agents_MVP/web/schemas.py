from datetime import date as CalendarDate
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from policy import WebVerdict

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12_000)]
EvidenceKind = Literal["verified", "claim", "assumption", "inference", "missing", "contradictory"]


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Short
    date: CalendarDate | None = None
    claim: Long
    document_name: Short | None = None
    document_text: Annotated[str, StringConstraints(max_length=20_000)] | None = None
    status: EvidenceKind = "claim"
    quality: Literal["unrated", "low", "medium", "high"] = "unrated"
    criterion: int | None = Field(None, ge=1, le=12)


class AssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_name: Annotated[Short, StringConstraints(max_length=150)]
    category: Literal["feasibility", "investment", "purchase", "competition", "procurement", "delivery"]
    objective: Long
    solution: Long
    decision_question: Long
    success_criteria: list[Short] = Field(min_length=1, max_length=12)
    constraints: list[Short] = Field(default_factory=list, max_length=20)
    evidence: list[EvidenceInput] = Field(default_factory=list, max_length=20)
    budget: Short | None = None
    timeline: Short | None = None
    expected_roi: Short | None = None
    cross_examine: bool = True
    language: Literal["en", "zh"] = "en"

    @model_validator(mode="after")
    def validate_registry(self):
        if any(item.criterion and item.criterion > len(self.success_criteria) for item in self.evidence):
            raise ValueError("Evidence criterion must refer to an existing success criterion")
        if sum(len(e.document_text or "") + len(e.claim) for e in self.evidence) > 90_000:
            raise ValueError("Combined evidence text exceeds 90,000 characters")
        return self


class Objective(BaseModel):
    proposition_x: str
    objective_y: str
    decision_question: str
    success_measures: list[str]
    open_questions: list[str]


class Finding(BaseModel):
    criterion_id: str
    stance: Literal["supports", "challenges", "unknown"]
    summary: str
    evidence_ids: list[str]


class Experiment(BaseModel):
    title: str
    method: str
    acceptance_test: str


class BReview(BaseModel):
    verdict: WebVerdict
    rationale: str
    findings: list[Finding]
    counterexamples: list[str]
    missing_evidence: list[str]
    experiments: list[Experiment]
    challenge: str


class CReview(BReview):
    objective_necessity: WebVerdict
    commercial_value: WebVerdict
    willingness_to_pay: WebVerdict
    counterfactual: str
    alternatives: list[str]


class Synthesis(BaseModel):
    executive_summary: str
    disagreements: list[str]
    contradictions: list[str]
    risks: list[str]
    open_questions: list[str]
    next_actions: list[str]


class RegisteredEvidence(EvidenceInput):
    id: str


class RegisteredAssessment(AssessmentInput):
    evidence: list[RegisteredEvidence]


class Decision(BaseModel):
    state: str
    action: str
    legacy_label: str
    sufficiency: WebVerdict
    necessity: WebVerdict


class EvidenceIssue(BaseModel):
    code: str
    values: list[str]


class Qualification(BaseModel):
    verdict: WebVerdict
    issues: list[EvidenceIssue]


class EvidenceComparison(BaseModel):
    criterion_id: str
    criterion: str
    B: list[Finding]
    C: list[Finding]
    possible_disagreement: bool
    contradictory_evidence: list[str]


class AuditEntry(BaseModel):
    agent: Literal["A", "B", "C"]
    step: str
    round: Literal[1, 2] | None
    status: str
    input: dict
    output: dict | None
    model: str
    usage: dict[str, int | None] | None
    duration_ms: int | None
    started_at: str


class RunSummary(BaseModel):
    id: str | None = None
    assessment_id: str | None = None
    status: str
    stage: str | None = None
    mode: Literal["mock", "openai"] | None = None
    agents: dict[str, str]
    error: str | None = None
    created_at: str | None = None
    finished_at: str | None = None
    decision: Decision | None = None


class RunStatus(RunSummary):
    audit: list[AuditEntry]
    objective: Objective | None = None
    initial_comparison: list[EvidenceComparison] | None = None
    comparison: list[EvidenceComparison] | None = None
    qualifications: dict[str, Qualification] | None = None


class SavedAssessment(BaseModel):
    id: str
    created_at: str
    assessment: RegisteredAssessment


class AssessmentDetail(SavedAssessment):
    runs: list[RunSummary]


class AssessmentSummary(BaseModel):
    id: str
    created_at: str
    project_name: str
    category: str
    status: str
    decision: Decision | None
    mode: Literal["mock", "openai"] | None
    agents: dict[str, str]


class DecisionReport(BaseModel):
    version: Literal[1]
    run_id: str
    mode: Literal["mock", "openai"]
    assessment: RegisteredAssessment
    framing: Objective
    synthesis: Synthesis
    sufficiency: BReview
    necessity: CReview
    evidence_matrix: list[EvidenceComparison]
    initial_comparison: list[EvidenceComparison]
    decision: Decision
    decision_matrix: list[tuple[str, str, str, str]]
    qualifications: dict[str, Qualification]
    audit: list[AuditEntry]


class Health(BaseModel):
    status: Literal["ok"]
    mode: Literal["mock", "openai"]
    model: str


class ParsedDocument(BaseModel):
    document_name: str
    document_text: str
    truncated: bool
