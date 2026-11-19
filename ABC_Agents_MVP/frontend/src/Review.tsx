import type { ReactNode } from 'react';
import { ArrowRight, Check, ClipboardList, Download, FileText, Printer } from 'lucide-react';
import type { Translate } from './locale';
import type { Audit, Comparison, Evidence, Report, Review, Run, Synthesis } from './types';

export function Badge({ value, t }: { value: string; t: Translate }) {
  return <span className={`badge badge-${value}`}><span className="dot"/>{t(value)}</span>;
}

function TextList({ values, t }: { values: string[]; t: Translate }) {
  return values.length ? <ul className="text-list">{values.map((value, index) => <li key={index}>{value}</li>)}</ul>
    : <p className="muted">{t('emptyList')}</p>;
}
function Cites({ ids, evidence }: { ids: string[]; evidence: Evidence[] }) {
  return <>{ids.filter(id => evidence.some(item => item.id === id)).map((id, index) => {
    const item = evidence.find(e => e.id === id);
    return <span key={index} className="cite" title={item?.source}>{id}</span>;
  })}</>;
}

function ReviewBody({ review, evidence, t }: { review: Review; evidence: Evidence[]; t: Translate }) {
  return <div className="review-body">
    <Badge value={review.verdict} t={t}/><p>{review.rationale}</p>
    {review.objective_necessity && <dl className="dimensions">
      {(['objective_necessity', 'specific', 'commercial_value', 'willingness_to_pay'] as const).map(key =>
        <div key={key}><dt>{t(key)}</dt><dd><Badge value={key === 'specific' ? review.verdict : review[key] ?? 'unknown'} t={t}/></dd></div>)}
    </dl>}
    {review.findings.map((finding, i) => <div className="finding" key={i}>
      <strong>{finding.criterion_id}</strong> <small>{t(finding.stance)}</small>
      <p>{finding.summary}</p><Cites ids={finding.evidence_ids} evidence={evidence}/>
    </div>)}
    {review.challenge && <div className="callout"><strong>{t('cross_examine')}</strong><p>{review.challenge}</p></div>}
    {review.counterexamples.length > 0 && <><strong>{t('counterexamples')}</strong><TextList values={review.counterexamples} t={t}/></>}
    {review.missing_evidence.length > 0 && <><strong>{t('missingEvidence')}</strong><TextList values={review.missing_evidence} t={t}/></>}
  </div>;
}

function SynthesisBody({ summary, t }: { summary: Synthesis; t: Translate }) {
  return <div className="review-body"><p>{summary.executive_summary}</p>
    {(['disagreements', 'contradictions', 'open_questions'] as const).map((key, index) =>
      <div key={key}><strong>{t(['disagreements', 'contradictions', 'questions'][index])}</strong>
        <TextList values={summary[key]} t={t}/></div>)}</div>;
}

export function AuditTrail({ audit, t }: { audit: Audit[]; t: Translate }) {
  if (!audit.length) return null;
  return <section className="panel audit"><h2>{t('audit')}</h2>
    {audit.map((entry, index) => <details key={index}>
      <summary><strong>{entry.agent} · {entry.round ? `${t('round')} ${entry.round}` : t(entry.step)}</strong>
        <Badge value={entry.status} t={t}/><span className="muted">{entry.model}{entry.duration_ms === null ? '' : ` · ${entry.duration_ms} ms`}</span></summary>
      <div className="audit-content"><p>{t('auditDetail')}</p><pre>{JSON.stringify({ input: entry.input, output: entry.output, usage: entry.usage }, null, 2)}</pre></div>
    </details>)}
  </section>;
}

function ComparisonTable({ rows, evidence, t }: { rows: Comparison[]; evidence: Evidence[]; t: Translate }) {
  return <div className="table-scroll"><table>
    <thead><tr><th>{t('criterion')}</th><th>B · {t('B')}</th><th>C · {t('C')}</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.criterion_id}>
      <td><strong>{row.criterion_id}</strong><p>{row.criterion}</p>
        {(row.possible_disagreement || row.contradictory_evidence.length > 0) &&
        <p className="muted">{t('conflict')} <Cites ids={row.contradictory_evidence} evidence={evidence}/></p>}</td>
      {(['B', 'C'] as const).map(agent => <td key={agent}>{row[agent].map((item, index) =>
        <p key={index}>{item.summary} <Cites ids={item.evidence_ids} evidence={evidence}/></p>)}</td>)}
    </tr>)}</tbody>
  </table></div>;
}

export function Workspace({ run, evidence, cross, t }: {
  run: Run; evidence: Evidence[]; cross: boolean; t: Translate;
}) {
  const stages = ['define', 'independent', 'compare', ...(cross ? ['cross_examine'] : []), 'policy', 'synthesize', 'report'];
  const current = stages.indexOf(run.stage ?? '');
  const summary = run.audit.findLast(entry => entry.step === 'synthesize')?.output as Synthesis | undefined;
  return <>
    <div className="panel stage-bar" aria-label={t('status')}>{stages.map((stage, index) =>
      <span key={stage} className={index === current ? 'stage-current' : index < current ? 'stage-done' : ''}>
        {index < current ? <Check size={14}/> : <span className="stage-dot"/>}{t(stage)}
      </span>)}</div>
    <div className="agent-grid">{(['B', 'A', 'C'] as const).map(agent => {
      const records = run.audit.filter(entry => entry.agent === agent && entry.output);
      return <article key={agent} className={`panel agent agent-${agent}`}>
        <header><span className="agent-id">{agent}</span><div><h2>{t(agent)}</h2><p>{t(agent + 'Prompt')}</p></div></header>
        <div className="agent-content">
          <Badge value={run.agents[agent] ?? 'waiting'} t={t}/>
          {agent === 'A' && run.objective && <div className="review-body">
            <strong>{t('solution')}</strong><p>{run.objective.proposition_x}</p>
            <strong>{t('objective')}</strong><p>{run.objective.objective_y}</p>
            <strong>{t('decision_question')}</strong><p>{run.objective.decision_question}</p>
            <strong>{t('success_criteria')}</strong><TextList values={run.objective.success_measures} t={t}/>
            <strong>{t('questions')}</strong><TextList values={run.objective.open_questions} t={t}/>
          </div>}
          {agent === 'A' && summary && <SynthesisBody summary={summary} t={t}/>}
          {agent !== 'A' && records.map(entry => <details className="round" key={entry.round} open={entry === records.at(-1)}>
            <summary>{t('round')} {entry.round}</summary>
            <ReviewBody review={entry.output as Review} evidence={evidence} t={t}/>
          </details>)}
          {agent !== 'A' && run.qualifications?.[agent] && <div className="callout">
            <strong>{t('policyValue')}</strong> <Badge value={run.qualifications[agent].verdict} t={t}/>
            {run.qualifications[agent].issues.map(issue => <p key={issue.code}>{t(issue.code)} {issue.values.join(', ')}</p>)}
          </div>}
          {!records.length && <p className="muted">{t('pending')}</p>}
        </div>
      </article>;
    })}</div>
    {(run.comparison || run.initial_comparison) && <section className="panel audit">
      <h2>{t('compare')}</h2><ComparisonTable rows={run.comparison ?? run.initial_comparison ?? []} evidence={evidence} t={t}/>
    </section>}
    <AuditTrail audit={run.audit} t={t}/>
  </>;
}

export function DecisionReport({ report, t }: { report: Report; t: Translate }) {
  const { assessment, synthesis, decision, sufficiency, necessity, evidence_matrix } = report;
  const section = (id: number, content: ReactNode) => <section className="panel report-section">
    <h2><span>{String(id).padStart(2, '0')}</span>{t('sections' + id)}</h2>{content}
  </section>;

  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `abc-review-${report.run_id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <div className="report">
    <div className="page-title"><div><h1>{t('report')}</h1><p>{assessment.project_name}</p></div><div className="actions no-print">
      <button className="button secondary" onClick={download}><Download size={16}/>{t('json')}</button>
      <button className="button primary" onClick={() => window.print()}><Printer size={16}/>{t('print')}</button>
    </div></div>
    <div className="decision-banner"><ClipboardList size={24}/><div><strong>{t(decision.state)}</strong>
      <span>{t(decision.action)}</span></div>{report.mode === 'mock' && <strong className="mode-tag">{t('mock')}</strong>}</div>
    {section(1, <><p>{synthesis.executive_summary}</p><p>{report.framing.decision_question}</p><p className="muted">{t('caveat')}</p></>)}
    {section(2, <ReviewBody review={sufficiency} evidence={assessment.evidence} t={t}/>)}
    {section(3, <><ReviewBody review={necessity} evidence={assessment.evidence} t={t}/><p className="muted">{t('commercialNote')}</p></>)}
    {section(4, <>
      <ComparisonTable rows={evidence_matrix} evidence={assessment.evidence} t={t}/>
      <h3>{t('evidence')}</h3>
      {assessment.evidence.map(item => <details key={item.id}>
        <summary><span className="cite">{item.id}</span> {item.source} · {t(item.status)}</summary>
        <p>{item.claim}</p><small className="muted">{[item.date, t(item.quality), item.criterion ? `S${item.criterion}` : t('general'), item.document_name].filter(Boolean).join(' · ')}</small>
        {item.document_text && <pre>{item.document_text}</pre>}
      </details>)}
      {!assessment.evidence.length && <p className="muted">{t('emptyList')}</p>}
    </>)}
    {section(5, <p>{necessity.counterfactual}</p>)}
    {section(6, <TextList values={necessity.alternatives ?? []} t={t}/>)}
    {section(7, <TextList values={[...synthesis.risks, ...synthesis.open_questions, ...synthesis.disagreements, ...synthesis.contradictions]} t={t}/>)}
    {section(8, <>
      <div className="table-scroll"><table><thead><tr><th>B</th><th>C</th><th>{t('result')}</th><th>{t('sections10')}</th></tr></thead>
        <tbody>{report.decision_matrix.map(([b, c, state, action]) => <tr key={b + c} className={(b === 'any' || b === decision.sufficiency) && (c === 'any' || c === decision.necessity) ? 'current-row' : ''}>
          <td>{t(b)}</td><td>{t(c)}</td><td>{t(state)}</td><td>{t(action)}</td>
        </tr>)}</tbody></table></div>
      {(['B', 'C'] as const).flatMap(agent => report.qualifications[agent].issues.map(issue =>
        <p className="muted" key={agent + issue.code}>{agent} · {t(issue.code)} {issue.values.join(', ')}</p>))}
    </>)}
    {section(9, <div className="experiments">{[...sufficiency.experiments, ...necessity.experiments].map((experiment, index) =>
      <article key={index}><h3>{experiment.title}</h3><p>{experiment.method}</p><div className="callout"><strong>{t('acceptance')}</strong><p>{experiment.acceptance_test}</p></div></article>)}</div>)}
    {section(10, <><h3 className="recommendation">{t(decision.action)} <ArrowRight size={17}/></h3>
      {decision.state === 'necessary_insufficient' && <p>{t('redesign')}</p>}
      <TextList values={synthesis.next_actions} t={t}/></>)}
    <div className="no-print"><AuditTrail audit={report.audit} t={t}/></div>
    <div className="report-end"><FileText size={14}/> ABC Decision Review</div>
  </div>;
}
