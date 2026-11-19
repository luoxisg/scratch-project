import { useEffect, useState, type FormEvent } from 'react';
import { ArrowRight, FlaskConical, Plus, Upload, X } from 'lucide-react';
import { categories, evidenceKinds, type Translate } from './locale';
import { request, type Assessment, type Detail, type Evidence, type Locale } from './types';

const empty: Assessment = {
  project_name: '', category: 'feasibility', objective: '', solution: '', decision_question: '',
  success_criteria: [], constraints: [], budget: null, timeline: null, expected_roi: null,
  evidence: [], cross_examine: true, language: 'en',
};
type DraftEvidence = Evidence & { key: number; uploading?: boolean; error?: string; truncated?: boolean };

export function AssessmentForm({ t, locale, onSave, demoOnOpen }: {
  t: Translate; locale: Locale; demoOnOpen: boolean; onSave: (detail: Detail) => void;
}) {
  const [form, setForm] = useState(empty);
  const [criteria, setCriteria] = useState('');
  const [constraints, setConstraints] = useState('');
  const [evidence, setEvidence] = useState<DraftEvidence[]>([]);
  const [sequence, setSequence] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lines = (value: string) => value.split('\n').map(line => line.trim()).filter(Boolean);
  const criteriaLines = lines(criteria);
  const patch = (key: number, update: Partial<DraftEvidence>) =>
    setEvidence(items => items.map(item => item.key === key ? { ...item, ...update } : item));

  async function loadDemo() {
    setError('');
    try {
      const data = await request<Assessment>('/demo');
      setForm(data);
      setCriteria(data.success_criteria.join('\n'));
      setConstraints(data.constraints.join('\n'));
      setEvidence(data.evidence.map((item, index) => ({ ...item, key: sequence + index })));
      setSequence(sequence + data.evidence.length);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => { if (demoOnOpen) void loadDemo(); }, [demoOnOpen]);

  async function attach(key: number, file?: File) {
    if (!file) return;
    patch(key, { uploading: true, error: '', truncated: false });
    try {
      if (file.size > 4 * 1024 * 1024) throw new Error('request_too_large');
      const body = new FormData();
      body.append('file', file);
      const result = await request<{ document_name: string; document_text: string; truncated: boolean }>(
        '/evidence/parse', { method: 'POST', body },
      );
      patch(key, result);
    } catch (err) {
      patch(key, { error: (err as Error).message });
    } finally {
      patch(key, { uploading: false });
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const payload = {
        ...form, language: locale, success_criteria: criteriaLines, constraints: lines(constraints),
        evidence: evidence.map(draft => ({
          source: draft.source, claim: draft.claim, date: draft.date, status: draft.status,
          quality: draft.quality, criterion: draft.criterion,
          document_name: draft.document_name, document_text: draft.document_text,
        })),
      };
      const saved = await request<Detail>('/assessments', {
        method: 'POST', body: JSON.stringify(payload), headers: { 'Content-Type': 'application/json' },
      });
      onSave(saved);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <form onSubmit={submit} className="form-stack">
    <div className="page-title">
      <div><h1>{t('new')}</h1><p>{t('assessIntro')}</p></div>
      <button className="button secondary" type="button" onClick={loadDemo}><FlaskConical size={16}/>{t('demo')}</button>
    </div>
    <div className="panel form-panel">
      <div className="fields two">
        <label>{t('project_name')}<input required maxLength={150} value={form.project_name} onChange={event => setForm({ ...form, project_name: event.target.value })}/></label>
        <label>{t('category')}<select value={form.category} onChange={event => setForm({ ...form, category: event.target.value })}>
          {categories.map(item => <option key={item} value={item}>{t(item)}</option>)}
        </select></label>
      </div>
      <div className="fields two">{(['objective', 'solution'] as const).map(key =>
        <label key={key}>{t(key)}<textarea required maxLength={12000} rows={4} value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })}/></label>)}</div>
      <label>{t('decision_question')}<textarea required maxLength={12000} rows={2} value={form.decision_question} onChange={event => setForm({ ...form, decision_question: event.target.value })}/></label>
      <div className="fields two">
        <label>{t('success_criteria')}<textarea required rows={5} placeholder={t('lines')} value={criteria} onChange={event => setCriteria(event.target.value)}/></label>
        <label>{t('constraints')}<textarea rows={5} placeholder={t('lines')} value={constraints} onChange={event => setConstraints(event.target.value)}/></label>
      </div>
      <div className="fields three">{(['budget', 'timeline', 'expected_roi'] as const).map(key =>
        <label key={key}>{t(key)}<input maxLength={500} placeholder={t('optional')} value={form[key] ?? ''} onChange={event => setForm({ ...form, [key]: event.target.value || null })}/></label>)}</div>
    </div>
    <div className="panel form-panel">
      <div className="panel-heading"><div><h2>{t('evidence')}</h2><p>{t('evidenceHelp')}</p></div>
        <button type="button" className="button secondary" disabled={evidence.length >= 20} onClick={() => {
          setEvidence([...evidence, { key: sequence, source: '', claim: '', date: null, status: 'claim', quality: 'unrated', criterion: null, document_name: null, document_text: null }]);
          setSequence(sequence + 1);
        }}><Plus size={16}/>{t('addEvidence')}</button>
      </div>
      {evidence.map((item, index) => <div className="evidence-form" key={item.key}>
        <div className="panel-heading"><strong className="mono">E{index + 1}</strong>
          <button type="button" className="button subtle" onClick={() => setEvidence(list => list.filter(row => row.key !== item.key))}><X size={14}/>{t('remove')}</button></div>
        <div className="fields two">
          <label>{t('source')}<input required maxLength={500} value={item.source} onChange={event => patch(item.key, { source: event.target.value })}/></label>
          <label>{t('date')}<input type="date" value={item.date ?? ''} onChange={event => patch(item.key, { date: event.target.value || null })}/></label>
        </div>
        <label>{t('claimText')}<textarea required maxLength={12000} rows={2} value={item.claim} onChange={event => patch(item.key, { claim: event.target.value })}/></label>
        <div className="fields three">
          <label>{t('verification')}<select value={item.status} onChange={event => patch(item.key, { status: event.target.value })}>{evidenceKinds.map(kind => <option key={kind} value={kind}>{t(kind)}</option>)}</select></label>
          <label>{t('quality')}<select value={item.quality} onChange={event => patch(item.key, { quality: event.target.value })}>{['unrated', 'low', 'medium', 'high'].map(kind => <option key={kind} value={kind}>{t(kind)}</option>)}</select></label>
          <label>{t('criterion')}<select value={item.criterion ?? ''} onChange={event => patch(item.key, { criterion: Number(event.target.value) || null })}>
            <option value="">{t('general')}</option>
            {criteriaLines.map((value, idx) => <option key={idx} value={idx + 1}>S{idx + 1} · {value.slice(0, 65)}</option>)}
          </select></label>
        </div>
        <label className="upload"><span><Upload size={16}/>{t('upload')}</span><small>{t('limits')}</small>
          <input type="file" accept=".pdf,.docx,.txt,.md,.markdown" disabled={item.uploading} onChange={event => { void attach(item.key, event.target.files?.[0]); event.target.value = ''; }}/>
        </label>
        {item.uploading && <p>{t('loading')}</p>}
        {item.error && <p className="alert" role="alert">{t(item.error)}</p>}
        {item.document_name && <details><summary>{item.document_name}</summary>{item.truncated && <p>{t('truncated')}</p>}<pre>{item.document_text}</pre></details>}
      </div>)}
    </div>
    <div className="panel form-panel"><label className="checkbox">
      <input type="checkbox" checked={form.cross_examine} onChange={event => setForm({ ...form, cross_examine: event.target.checked })}/>
      <span>{t('cross')}<small>{t('crossHelp')}</small></span>
    </label></div>
    {error && <p className="alert" role="alert">{t(error)}</p>}
    <div className="form-actions"><button className="button primary" disabled={busy || evidence.some(item => item.uploading)}>
      {t(busy ? 'saving' : 'save')}<ArrowRight size={17}/>
    </button></div>
  </form>;
}
