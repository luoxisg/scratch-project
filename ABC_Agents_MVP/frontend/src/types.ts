export type Locale = 'en' | 'zh';
export type Verdict = 'pass' | 'fail' | 'unknown';
export type Evidence = {
  id?: string; source: string; date: string | null; claim: string;
  status: string; quality: string; criterion: number | null;
  document_name: string | null; document_text: string | null;
};
export type Assessment = {
  project_name: string; category: string; objective: string; solution: string;
  decision_question: string; success_criteria: string[]; constraints: string[];
  budget: string | null; timeline: string | null; expected_roi: string | null;
  evidence: Evidence[]; cross_examine: boolean; language: Locale;
};
export type Decision = {
  state: string; action: string; legacy_label: string; sufficiency: Verdict; necessity: Verdict;
};
export type Agent = 'A' | 'B' | 'C';
export type Framing = {
  proposition_x: string; objective_y: string; decision_question: string;
  success_measures: string[]; open_questions: string[];
};
export type Finding = {
  criterion_id: string; stance: string; summary: string; evidence_ids: string[];
};
export type Review = {
  verdict: Verdict; rationale: string; findings: Finding[]; counterexamples: string[];
  missing_evidence: string[]; experiments: {title: string; method: string; acceptance_test: string}[];
  challenge: string; objective_necessity?: Verdict; commercial_value?: Verdict;
  willingness_to_pay?: Verdict; counterfactual?: string; alternatives?: string[];
};
export type Synthesis = {
  executive_summary: string; disagreements: string[]; contradictions: string[];
  risks: string[]; open_questions: string[]; next_actions: string[];
};
export type Audit = {
  agent: Agent; step: string; round: number | null; status: string;
  input: unknown; output: Framing | Review | Synthesis | null; model: string;
  usage: Record<string, number | null> | null; duration_ms: number | null;
};
export type Comparison = {
  criterion_id: string; criterion: string; B: Finding[]; C: Finding[];
  possible_disagreement: boolean; contradictory_evidence: string[];
};
export type Qualification = {verdict: Verdict; issues: {code: string; values: string[]}[]};
export type Run = {
  id?: string; status: string; stage?: string; mode?: string; agents: Partial<Record<Agent, string>>;
  error?: string; audit: Audit[]; objective?: Framing; decision?: Decision;
  created_at?: string; initial_comparison?: Comparison[]; comparison?: Comparison[];
  qualifications?: Record<'B' | 'C', Qualification>;
};
export type Detail = {id: string; assessment: Assessment; runs: Run[]};
export type Summary = {
  id: string; project_name: string; category: string; created_at: string;
  status: string; decision?: Decision; mode?: string; agents: Run['agents'];
};
export type Report = {
  run_id: string; mode: string; assessment: Assessment; framing: Framing;
  synthesis: Synthesis; sufficiency: Review; necessity: Review; evidence_matrix: Comparison[];
  qualifications: Record<'B' | 'C', Qualification>; audit: Audit[];
  decision: Decision; decision_matrix: [string, string, string, string][];
};

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch('/api' + path, options);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const detail = typeof error?.detail === 'string' ? error.detail : 'request_failed';
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}
