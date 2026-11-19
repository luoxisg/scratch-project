import { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity, ArrowRight, CheckCircle2, ClipboardList, Clock3, FlaskConical, FolderOpen,
  GitCompareArrows, History, LayoutDashboard, Play, Plus, Square, Workflow,
} from 'lucide-react';
import { AssessmentForm } from './Form';
import { translator, type Translate } from './locale';
import { Badge, DecisionReport, Workspace } from './Review';
import { request, type Detail, type Locale, type Report, type Run, type Summary } from './types';
import './styles.css';

type Screen = 'dashboard' | 'new' | 'history' | 'live' | 'report';
type Health = { mode: string; model: string };
const active = (status: string) => status === 'queued' || status === 'running';

function App() {
  const [locale, setLocale] = useState<Locale>(() => localStorage.getItem('abc-locale') === 'zh' ? 'zh' : 'en');
  const t = translator(locale);
  const [screen, setScreen] = useState<Screen>('dashboard');
  const [health, setHealth] = useState<Health>();
  const [items, setItems] = useState<Summary[]>([]);
  const [detail, setDetail] = useState<Detail>();
  const [run, setRun] = useState<Run>({ status: 'draft', agents: {}, audit: [] });
  const [report, setReport] = useState<Report>();
  const [selectedRun, setSelectedRun] = useState('');
  const [demoOnOpen, setDemoOnOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const detailId = detail?.id;

  useEffect(() => {
    document.documentElement.lang = locale === 'zh' ? 'zh-CN' : 'en';
    localStorage.setItem('abc-locale', locale);
  }, [locale]);

  const refresh = useCallback(async () => {
    setItems(await request<Summary[]>('/assessments'));
  }, []);
  useEffect(() => {
    void request<Health>('/health').then(setHealth).catch(err => setError(err.message));
  }, []);
  useEffect(() => {
    if (screen !== 'dashboard' && screen !== 'history') return;
    void refresh().catch(err => setError(err.message));
    const timer = window.setInterval(() => { void refresh().catch(err => setError(err.message)); }, 2500);
    return () => clearInterval(timer);
  }, [screen, refresh]);
  useEffect(() => {
    if (!detailId || screen !== 'live') return;
    const controller = new AbortController();
    let timer = 0;
    async function poll() {
      try {
        const status = await request<Run>(`/assessments/${detailId}/status${selectedRun ? '?run_id=' + selectedRun : ''}`,
          { signal: controller.signal });
        if (controller.signal.aborted) return;
        setRun(status);
        if (active(status.status)) timer = window.setTimeout(poll, 600);
        else {
          const updated = await request<Detail>(`/assessments/${detailId}`, { signal: controller.signal });
          if (!controller.signal.aborted) setDetail(updated);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError((err as Error).message);
          timer = window.setTimeout(poll, 2500);
        }
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [detailId, screen, selectedRun, run.id]);

  function navigate(next: Screen) {
    setError('');
    setScreen(next);
    window.scrollTo(0, 0);
  }

  function newAssessment(demo = false) {
    setDemoOnOpen(demo);
    navigate('new');
  }

  async function open(id: string) {
    setError('');
    setBusy(true);
    try {
      const [row, status] = await Promise.all([
        request<Detail>(`/assessments/${id}`), request<Run>(`/assessments/${id}/status`),
      ]);
      setDetail(row); setRun(status); setSelectedRun(''); navigate('live');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function act(action: 'run' | 'cancel' | 'report') {
    setError('');
    setBusy(true);
    try {
      const endpoint = `/assessments/${detailId}/${action}`;
      if (action === 'report') {
        setReport(await request<Report>(endpoint + (run.id ? '?run_id=' + run.id : '')));
        navigate('report');
      } else {
        const result = await request<Run>(endpoint, { method: 'POST' });
        if (action === 'run') {
          setSelectedRun('');
          setRun(result);
        }
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const menu = [
    { id: 'dashboard' as const, icon: LayoutDashboard },
    { id: 'new' as const, icon: Plus },
    { id: 'history' as const, icon: History },
  ];
  const mode = screen === 'live' ? run.mode ?? health?.mode : screen === 'report' ? report?.mode : health?.mode;
  const shown = screen === 'dashboard' ? items.slice(0, 7) : items;
  return <div className="layout">
    <aside className="sidebar no-print">
      <div className="brand"><span className="brand-icon"><Workflow size={21}/></span><div><strong>ABC</strong><span>{t('brand')}</span></div></div>
      <nav aria-label={t('workspace')}>{menu.map(({ id, icon: Icon }) =>
        <button key={id} aria-current={screen === id ? 'page' : undefined} onClick={() => id === 'new' ? newAssessment() : navigate(id)}>
          <Icon size={17}/>{t(id)}
        </button>)}</nav>
      <div className="local"><span className="dot"/>{t('local')}</div>
    </aside>
    <div className="shell">
      <header className="topbar no-print">
        <span>{t('workspace')}</span>
        <div className="actions">
          {mode && <span className={`runtime ${mode}`} title={health?.model}><span className="dot"/>{t(mode)}</span>}
          <div className="languages" aria-label="Language"><button type="button" aria-pressed={locale === 'en'} onClick={() => setLocale('en')}>EN</button>
            <button type="button" aria-pressed={locale === 'zh'} onClick={() => setLocale('zh')}>中文</button></div>
        </div>
      </header>
      <main className="main">
        {error && <p className="alert no-print" role="alert">{t(error)}</p>}
        {mode && screen !== 'report' && <div className="mode-note no-print"><FlaskConical size={16}/>{t(mode === 'mock' ? 'mockNote' : 'liveNote')}</div>}
        {(screen === 'dashboard' || screen === 'history') && <>
          <div className="page-title"><div><h1>{t(screen)}</h1>{screen === 'dashboard' && <p>{t('dashboardIntro')}</p>}</div>
            <div className="actions"><button className="button secondary" onClick={() => newAssessment(true)}><FlaskConical size={16}/>{t('demo')}</button>
              <button className="button primary" onClick={() => newAssessment()}><Plus size={17}/>{t('new')}</button></div>
          </div>
          {screen === 'dashboard' && <div className="metrics">
            {([{ label: 'total', value: items.length, icon: ClipboardList }, { label: 'active', value: items.filter(item => active(item.status)).length, icon: Activity },
              { label: 'complete', value: items.filter(item => item.status === 'complete').length, icon: CheckCircle2 }]).map(({ label, value, icon: Icon }) =>
              <div className="panel metric" key={label}><div><small>{t(label)}</small><strong>{value}</strong></div><span><Icon size={20}/></span></div>)}
          </div>}
          <div className="panel history">
            {screen === 'dashboard' && <h2>{t('recent')}</h2>}
            {shown.length ? <HistoryTable items={shown} t={t} onOpen={open} busy={busy}/> : <div className="empty"><FolderOpen size={28}/><h3>{t('empty')}</h3><p>{t('emptyHelp')}</p></div>}
          </div>
        </>}
        {screen === 'new' && <AssessmentForm t={t} locale={locale} demoOnOpen={demoOnOpen} onSave={saved => {
          setDetail({ ...saved, runs: [] }); setRun({ status: 'draft', agents: {}, audit: [] });
          setSelectedRun(''); navigate('live');
        }}/>}
        {screen === 'live' && detail && <>
          <div className="page-title"><div><div className="eyebrow"><GitCompareArrows size={15}/>{t('live')}</div>
            <h1>{detail.assessment.project_name}</h1><p>{detail.assessment.decision_question}</p></div>
            <div className="actions">
              {active(run.status) ? <button className="button secondary" disabled={busy} onClick={() => act('cancel')}><Square size={15}/>{t('cancel')}</button> :
                <button className="button secondary" disabled={busy} onClick={() => act('run')}><Play size={16}/>{t(run.status === 'draft' ? 'start' : 'rerun')}</button>}
              {run.status === 'complete' && <button className="button primary" disabled={busy} onClick={() => act('report')}>{t('report')}<ArrowRight size={15}/></button>}
            </div>
          </div>
          <div className="run-controls"><Badge value={run.status} t={t}/>
            {run.decision && <strong>{t(run.decision.state)} · {t(run.decision.action)}</strong>}
            {detail.runs.length > 0 && <label className="run-select"><Clock3 size={15}/>{t('selectRun')}<select value={selectedRun} onChange={event => {
              setSelectedRun(event.target.value);
              setRun({ status: 'waiting', agents: {}, audit: [] });
            }}><option value="">{t('recent')}</option>
              {detail.runs.map(item => <option key={item.id} value={item.id}>
                {new Date(item.created_at ?? '').toLocaleString(locale)} · {t(item.status)}</option>)}
            </select></label>}
          </div>
          {run.error && <p className="alert" role="alert">{t(run.error)}</p>}
          <Workspace run={run} evidence={detail.assessment.evidence} cross={detail.assessment.cross_examine} t={t}/>
        </>}
        {screen === 'report' && report && <>
          <button className="button subtle no-print back" onClick={() => navigate('live')}>← {t('live')}</button>
          <DecisionReport report={report} t={t}/>
        </>}
      </main>
    </div>
  </div>;
}

function HistoryTable({ items, t, onOpen, busy }: {
  items: Summary[]; t: Translate; onOpen: (id: string) => void; busy: boolean;
}) {
  return <div className="table-scroll"><table>
    <thead><tr><th>{t('project_name')}</th><th>{t('status')}</th><th>{t('result')}</th><th>{t('agentStatus')}</th></tr></thead>
    <tbody>{items.map(item => <tr key={item.id}>
      <td><button className="row-link" disabled={busy} onClick={() => onOpen(item.id)}>{item.project_name}<ArrowRight size={14}/></button>
        <p className="muted">{t(item.category)} · {new Date(item.created_at).toLocaleDateString(document.documentElement.lang)}</p></td>
      <td><Badge value={item.status} t={t}/></td>
      <td>{item.decision ? <>{t(item.decision.state)}{item.mode === 'mock' && <div className="muted">{t('mock')}</div>}</> : '—'}</td>
      <td><div className="agent-status-list">{(['B', 'A', 'C'] as const).map(agent =>
        <span key={agent} title={t(agent) + ' · ' + t(item.agents[agent] ?? 'waiting')}
          className={`small-agent badge-${item.agents[agent] ?? 'waiting'}`}>{agent}</span>)}</div></td>
    </tr>)}</tbody>
  </table></div>;
}

createRoot(document.getElementById('root')!).render(<App/>);
