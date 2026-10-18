import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, MapPin, X } from 'lucide-react';
import { createRun, loadCouncilState, loadCouncilTrace, saveDecision, savePlan, saveScope, submitProposal } from './council.ts';
import type { CouncilState, Decision, DecisionCommand, LocationChoice, Plan, ScopeRevision, SiteParameters } from './council.ts';
import type { CouncilFoodTrace, FoodTrace } from './interactables.ts';
import { sameRunRef } from './runRef.ts';
import type { CouncilRunRef, RunRef } from './runRef.ts';
import type { Point } from './district.ts';

type LoadStatus = { kind: 'loading' } | { kind: 'ready' } | { kind: 'error'; message: string };
type CouncilPanelProps = {
  id: string;
  open: boolean;
  ready: boolean;
  population: number;
  seed: number;
  currentTrace: FoodTrace | null;
  currentRunRef: RunRef;
  currentSeconds: number;
  onClose: () => void;
  onRunLoaded: (runRef: CouncilRunRef, trace: CouncilFoodTrace) => void;
  onProjectLocation: (point: Point | null) => void;
  onFocusLocation: (point: Point) => void;
  onSeekTo: (seconds: number) => void;
};
type ActionChoice = '' | Plan['action'];
type ParameterDraft = {
  location_id: string; grant_cents: string; stock_grams: string; service_capacity: string;
  readiness_second: string; funding_second: string; delivery_second: string;
  commissioning_second: string; open_second: string; close_second: string;
};

const blankParameters: ParameterDraft = {
  location_id: '', grant_cents: '', stock_grams: '', service_capacity: '', readiness_second: '',
  funding_second: '', delivery_second: '', commissioning_second: '', open_second: '', close_second: '',
};

function revisionLabel(revision: number): string { return `Revision ${revision}`; }
function shortenedHash(value: string): string { return value.slice(0, 12); }
function toInteger(value: string): number { return Number(value); }
function siteParametersProblem(parameters: ParameterDraft, population: number): string | null {
  if (!parameters.location_id) return 'Choose a proposed location.';
  const rawNumbers = [parameters.grant_cents, parameters.stock_grams, parameters.service_capacity,
    parameters.readiness_second, parameters.funding_second, parameters.delivery_second,
    parameters.commissioning_second, parameters.open_second, parameters.close_second];
  if (rawNumbers.some(value => value === '' || !Number.isInteger(Number(value)))) {
    return 'Enter an integer for every plan parameter.';
  }
  const [grant, stock, capacity, readiness, funding, delivery, commissioning, opening, closing] = rawNumbers.map(Number);
  if (grant! < 0 || grant! > 30000) return 'Grant must be between 0 and 30,000 cents.';
  if (stock! < 0 || stock! > 60000) return 'Initial stock must be between 0 and 60,000 grams.';
  if (stock! !== 0 && stock! % 100 !== 0) return 'Initial stock must be 0 or a multiple of 100 grams.';
  if (capacity! < 1 || capacity! > population) return `Service capacity must be between 1 and ${population.toLocaleString()}.`;
  if ([readiness!, funding!, delivery!, commissioning!, opening!, closing!].some(value => value < 0 || value > 21600)) {
    return 'Every schedule value must be between 0 and 21,600 seconds.';
  }
  if (!(readiness! < funding! && funding! < delivery! && delivery! < commissioning!
      && commissioning! < opening! && opening! < closing!)) {
    return 'Use strictly increasing ticks: readiness < funding < delivery < commissioning < open < close.';
  }
  return null;
}
function actionChoice(value: string): ActionChoice {
  if (value === 'establish_service_site' || value === 'unsupported') return value;
  return '';
}

function currentPlanLocation(state: CouncilState): Point | null {
  const { proposal, scope, plan } = state;
  if (!proposal || !scope || !plan || scope.proposal_id !== proposal.id || scope.proposal_sha256 !== proposal.sha256
      || plan.proposal_id !== proposal.id || plan.proposal_sha256 !== proposal.sha256
      || plan.scope_id !== scope.id || plan.scope_sha256 !== scope.sha256 || !plan.parameters) return null;
  return state.locations.find(location => location.id === plan.parameters?.location_id)?.point ?? null;
}

function lineSpans(label: string, spans: { start_line: number; end_line: number; text: string }[]) {
  return <section className="council-span-group" aria-label={label} key={label}>
    <h4>{label} <span>{spans.length}</span></h4>
    {spans.length === 0 ? <p className="council-muted">None classified.</p> : <ul>
      {spans.map((span, index) => <li key={`${span.start_line}-${span.end_line}-${index}`}>
        <small>Lines {span.start_line}{span.end_line !== span.start_line ? `–${span.end_line}` : ''}</small>
        <p>{span.text}</p>
      </li>)}
    </ul>}
  </section>;
}

function simulationTime(second: number): string {
  const total = 8 * 3600 + 30 * 60 + Math.floor(second);
  return [Math.floor(total / 3600) % 24, Math.floor(total / 60) % 60]
    .map(value => String(value).padStart(2, '0')).join(':');
}

function rolloutStageLabel(stage: CouncilFoodTrace['rollout_events'][number]['stage']): string {
  switch (stage) {
    case 'readiness': return 'Readiness';
    case 'funding': return 'Funding';
    case 'delivery': return 'Supplier delivery';
    case 'commissioning': return 'Commissioning';
    case 'opening': return 'Opening';
    case 'closure': return 'Closure';
    case 'blocked': return 'Blocked';
    case 'no_launch': return 'No launch';
  }
}

function RolloutTimeline({ trace, seconds, onSeekTo }: {
  trace: CouncilFoodTrace; seconds: number; onSeekTo: (seconds: number) => void;
}) {
  const reachedCount = trace.rollout_events.filter(event => event.simulation_time <= seconds).length;
  return <section className="council-section council-rollout" aria-label="Committed Council rollout timeline">
    <div className="council-section-title"><span>05</span><h3>Committed rollout trace</h3></div>
    <p className="council-rollout-meta">Run {trace.run_id} · {trace.run_ref.arm} · playhead {simulationTime(seconds)} · {reachedCount} of {trace.rollout_events.length} recorded events reached</p>
    {trace.rollout_events.length === 0 ? <p className="council-muted">This paired baseline contains no intervention rollout events.</p> :
      <ol className="council-rollout-list">{trace.rollout_events.map(event => {
        const reached = event.simulation_time <= seconds;
        const status = reached ? event.status.replace('_', ' ') : 'pending';
        return <li key={event.event_id} className={`rollout-${reached ? event.status : 'pending'}`}>
          <div className="council-rollout-heading"><b>{rolloutStageLabel(event.stage)}</b>
            <span>{simulationTime(event.simulation_time)} · {status}</span></div>
          {reached && event.reason && <p>{event.reason}</p>}
          {reached && seconds > event.simulation_time && <button type="button"
            aria-label={`Rewind to ${rolloutStageLabel(event.stage)} at ${simulationTime(event.simulation_time)}`}
            onClick={() => onSeekTo(event.simulation_time)}>Rewind to {simulationTime(event.simulation_time)}</button>}
        </li>;
      })}</ol>}
  </section>;
}

function SavedScope({ scope }: { scope: ScopeRevision }) {
  return <details className="council-saved-record">
    <summary>Saved scope · {shortenedHash(scope.sha256)}</summary>
    <dl>
      <div><dt>Evaluated</dt><dd>{scope.evaluated_scope}</dd></div>
      <div><dt>Excluded</dt><dd>{scope.excluded_scope}</dd></div>
      <div><dt>Reviewer note</dt><dd>{scope.reviewer_note}</dd></div>
    </dl>
  </details>;
}

function PlanRecord({ plan, locations, onFocus, ready, current }: {
  plan: Plan; locations: LocationChoice[]; onFocus: (point: Point) => void; ready: boolean; current: boolean;
}) {
  const location = plan.parameters ? locations.find(item => item.id === plan.parameters?.location_id) : undefined;
  return <section className="council-record" aria-label="Saved plan draft">
    <div className="council-record-heading"><div><span className="council-overline">SAVED PLAN DRAFT</span><h4>{plan.action === 'unsupported' ? 'Unsupported action' : 'Establish service site'}</h4></div>
      <span className="council-hash">{shortenedHash(plan.sha256)}</span></div>
    {plan.action === 'unsupported' && <p className="council-callout">This action is recorded for review. The current service cannot execute it.</p>}
    {plan.parameters && <>
      <dl className="council-parameters">
        <div><dt>Proposed location</dt><dd>{location?.label ?? plan.parameters.location_id}</dd></div>
        <div><dt>Grant</dt><dd>{plan.parameters.grant_cents.toLocaleString()} cents</dd></div>
        <div><dt>Initial stock</dt><dd>{plan.parameters.stock_grams.toLocaleString()} grams</dd></div>
        <div><dt>Service capacity</dt><dd>{plan.parameters.service_capacity.toLocaleString()}</dd></div>
        <div><dt>Operator assumption</dt><dd>Hypothetical municipal operator</dd></div>
        <div><dt>Readiness</dt><dd>{plan.parameters.readiness_second}s</dd></div>
        <div><dt>Funding</dt><dd>{plan.parameters.funding_second}s</dd></div>
        <div><dt>Delivery</dt><dd>{plan.parameters.delivery_second}s</dd></div>
        <div><dt>Commissioning</dt><dd>{plan.parameters.commissioning_second}s</dd></div>
        <div><dt>Open / close</dt><dd>{plan.parameters.open_second}s / {plan.parameters.close_second}s</dd></div>
        <div><dt>Authority</dt><dd>Unknown</dd></div>
        <div><dt>Operation status</dt><dd>Unknown</dd></div>
      </dl>
      {location && <button className="council-focus-button" type="button" disabled={!ready || !current}
        onClick={() => onFocus(location.point)}><MapPin size={14} /> Focus proposed location</button>}
      <p className="council-projection-note">{current ? 'Map marker is a proposed-site projection.' : 'This plan belongs to an earlier proposal or scope; its projection is cleared.'} It is not evidence of operation or service.</p>
    </>}
    {plan.execution_blockers.length > 0 && <div className="council-callout" role="status">
      <strong>Execution blockers</strong><ul>{plan.execution_blockers.map((blocker, index) => <li key={`${index}-${blocker}`}>{blocker}</li>)}</ul>
    </div>}
    <div className="council-advice-list" aria-label="Deterministic advisory assessments">
      {plan.advice.map((advice, index) => <div className={`council-advice advice-${advice.status}`} key={`${advice.role}-${index}`}>
        <span>{advice.role.replaceAll('_', ' ')} · {advice.status}</span><p>{advice.note}</p><small>Advisory only</small>
      </div>)}
    </div>
    <details className="council-world-inputs"><summary>Frozen world inputs</summary>
      <dl><div><dt>Population</dt><dd>{plan.world.population.toLocaleString()}</dd></div>
        <div><dt>Seed</dt><dd>{plan.world.seed}</dd></div><div><dt>Map SHA-256</dt><dd>{plan.world.map_sha256}</dd></div>
        <div><dt>Catalog</dt><dd>{plan.world.catalog_id} · {plan.world.catalog_sha256}</dd></div>
        <div><dt>Source snapshot</dt><dd>{plan.world.source_snapshot_id} · {plan.world.source_sha256}</dd></div>
        <div><dt>Simulator</dt><dd>{plan.world.simulator_version}</dd></div>
        <div><dt>World SHA-256</dt><dd>{plan.world.sha256}</dd></div></dl>
    </details>
  </section>;
}

function RunRecord({ run, onLoad, busy }: {
  run: CouncilState['runs'][number]; onLoad: (run: CouncilState['runs'][number], arm: CouncilRunRef['arm']) => void; busy: boolean;
}) {
  return <article className="council-run-record">
    <div><span className={`council-run-status status-${run.status}`}>{run.status}</span><b>Run {run.id}</b></div>
    <p>Population {run.population.toLocaleString()} · seed {run.seed} · decision {run.decision_id}</p>
    {run.blockers.length > 0 && <ul>{run.blockers.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>}
    <div className="council-run-actions">
      <button type="button" disabled={busy} onClick={() => onLoad(run, 'baseline')}>Open baseline</button>
      <button type="button" disabled={busy} onClick={() => onLoad(run, 'intervention')}>Open intervention</button>
    </div>
  </article>;
}

export function CouncilPanel({ id, open, ready, population, seed, currentTrace, currentRunRef, currentSeconds,
  onClose, onRunLoaded, onProjectLocation, onFocusLocation, onSeekTo }: CouncilPanelProps) {
  const [loadStatus, setLoadStatus] = useState<LoadStatus>({ kind: 'loading' });
  const [state, setState] = useState<CouncilState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [selectedRevisionId, setSelectedRevisionId] = useState('');
  const [evaluatedScope, setEvaluatedScope] = useState('');
  const [excludedScope, setExcludedScope] = useState('');
  const [reviewerNote, setReviewerNote] = useState('');
  const [action, setAction] = useState<ActionChoice>('');
  const [parameters, setParameters] = useState<ParameterDraft>(blankParameters);
  const [decisionReason, setDecisionReason] = useState('');
  const [confirmedNoLaunch, setConfirmedNoLaunch] = useState(false);

  useEffect(() => {
    let active = true;
    void loadCouncilState().then(next => {
      if (!active) return;
      setState(next); setLoadStatus({ kind: 'ready' });
      const proposal = next.proposal;
      setDraft(proposal?.markdown ?? '');
      setSelectedRevisionId(proposal?.id ?? '');
      if (next.scope && next.scope.proposal_id === proposal?.id) {
        setEvaluatedScope(next.scope.evaluated_scope);
        setExcludedScope(next.scope.excluded_scope);
        setReviewerNote(next.scope.reviewer_note);
      }
      onProjectLocation(currentPlanLocation(next));
    }).catch(error => {
      if (active) setLoadStatus({ kind: 'error', message: error instanceof Error ? error.message : 'The local Council service is unavailable. City playback is still available.' });
    });
    return () => { active = false; };
  }, [onProjectLocation]);

  const revisions = useMemo(() => {
    if (!state) return [];
    const entries = [...state.proposal_history];
    if (state.proposal && !entries.some(item => item.id === state.proposal?.id)) {
      entries.push({ id: state.proposal.id, revision: state.proposal.revision, sha256: state.proposal.sha256, markdown: state.proposal.markdown });
    }
    return entries.sort((left, right) => left.revision - right.revision);
  }, [state]);
  const selectedRevision = revisions.find(item => item.id === selectedRevisionId) ?? null;
  const currentCouncilTrace = currentTrace?.policy === 'council' && currentRunRef.kind === 'council'
    && sameRunRef(currentTrace.run_ref, currentRunRef) ? currentTrace : null;
  const proposal = state?.proposal ?? null;
  const scope = state?.scope ?? null;
  const scopeMatches = !!proposal && !!scope && scope.proposal_id === proposal.id && scope.proposal_sha256 === proposal.sha256;
  const plan = state?.plan ?? null;
  const planMatches = !!plan && !!proposal && !!scopeMatches && plan.proposal_id === proposal.id
    && plan.proposal_sha256 === proposal.sha256 && plan.scope_id === scope?.id && plan.scope_sha256 === scope.sha256;
  const approveDisabled = !planMatches || !plan || plan.action === 'unsupported'
    || (plan.execution_blockers.length > 0 && !confirmedNoLaunch);
  const currentApproval: Decision | null = state?.decisions.find(item => item.current && item.choice === 'approve'
    && item.proposal_id === proposal?.id && item.proposal_sha256 === proposal?.sha256
    && item.scope_id === scope?.id && item.scope_sha256 === scope?.sha256
    && item.plan_id === plan?.id && item.plan_sha256 === plan?.sha256
    && item.world_sha256 === plan?.world.sha256) ?? null;
  const projectedLocation = planMatches && plan?.parameters
    ? state?.locations.find(item => item.id === plan.parameters?.location_id) ?? null : null;
  const parameterProblem = action === 'establish_service_site' ? siteParametersProblem(parameters, population) : null;

  async function refresh() {
    setBusy('refresh'); setCommandError(null);
    try {
      const next = await loadCouncilState(); setState(next); setLoadStatus({ kind: 'ready' });
      if (!state) {
        setDraft(next.proposal?.markdown ?? '');
        setSelectedRevisionId(next.proposal?.id ?? '');
        setEvaluatedScope(next.scope?.evaluated_scope ?? '');
        setExcludedScope(next.scope?.excluded_scope ?? '');
        setReviewerNote(next.scope?.reviewer_note ?? '');
      }
      onProjectLocation(currentPlanLocation(next));
    }
    catch (error) { setLoadStatus({ kind: 'error', message: error instanceof Error ? error.message : 'The local Council service is unavailable. City playback is still available.' }); }
    finally { setBusy(null); }
  }
  async function saveProposal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state || !draft.trim()) return;
    setBusy('proposal'); setCommandError(null);
    try {
      const next = await submitProposal({ markdown: draft }, state.revision);
      setState(next); setLoadStatus({ kind: 'ready' }); setSelectedRevisionId(next.proposal?.id ?? '');
      onProjectLocation(null); setAction(''); setParameters(blankParameters); setConfirmedNoLaunch(false);
    } catch (error) { setCommandError(error instanceof Error ? error.message : 'The proposal was not confirmed as saved.'); }
    finally { setBusy(null); }
  }
  async function saveCurrentScope(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state || !proposal || !evaluatedScope.trim() || !excludedScope.trim() || !reviewerNote.trim()) return;
    setBusy('scope'); setCommandError(null);
    try {
      const next = await saveScope({ proposal_id: proposal.id, evaluated_scope: evaluatedScope,
        excluded_scope: excludedScope, reviewer_note: reviewerNote }, state.revision);
      setState(next); setLoadStatus({ kind: 'ready' }); setAction(''); setParameters(blankParameters); setConfirmedNoLaunch(false);
      onProjectLocation(null);
    } catch (error) { setCommandError(error instanceof Error ? error.message : 'The scope was not confirmed as saved.'); }
    finally { setBusy(null); }
  }
  function updateParameter(field: keyof ParameterDraft, value: string) {
    setParameters(previous => ({ ...previous, [field]: value }));
  }
  function numericParameter(field: Exclude<keyof ParameterDraft, 'location_id'>, label: string, min = 0,
    max: number | null = 21600, step = 1) {
    return <label className="council-field council-number-field" key={field}>
      <span>{label}</span><input type="number" required min={min} {...(max === null ? {} : { max })} step={step} value={parameters[field]}
        onChange={event => updateParameter(field, event.target.value)} />
    </label>;
  }
  function buildSiteParameters(): SiteParameters | null {
    if (siteParametersProblem(parameters, population)) return null;
    const next: SiteParameters = {
      location_id: parameters.location_id, grant_cents: toInteger(parameters.grant_cents),
      stock_grams: toInteger(parameters.stock_grams), service_capacity: toInteger(parameters.service_capacity),
      operator_assumption: 'hypothetical_municipal_operator',
      readiness_second: toInteger(parameters.readiness_second), funding_second: toInteger(parameters.funding_second),
      delivery_second: toInteger(parameters.delivery_second), commissioning_second: toInteger(parameters.commissioning_second),
      open_second: toInteger(parameters.open_second), close_second: toInteger(parameters.close_second),
    };
    return next;
  }
  async function saveCurrentPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state || !proposal || !scopeMatches || !scope || !action) return;
    const planParameters = action === 'unsupported' ? null : buildSiteParameters();
    if (action === 'establish_service_site' && !planParameters) return;
    setBusy('plan'); setCommandError(null);
    try {
      const next = await savePlan({ proposal_id: proposal.id, scope_id: scope.id, action,
        parameters: planParameters, population, seed }, state.revision);
      setState(next); setLoadStatus({ kind: 'ready' }); setConfirmedNoLaunch(false);
      if (planParameters) {
        const location = next.locations.find(item => item.id === planParameters.location_id);
        onProjectLocation(location?.point ?? null);
      } else onProjectLocation(null);
    } catch (error) { setCommandError(error instanceof Error ? error.message : 'The plan was not confirmed as saved.'); }
    finally { setBusy(null); }
  }
  async function recordDecision(choice: DecisionCommand['choice']) {
    if (!state || !proposal || !scopeMatches || !scope || !planMatches || !plan || !decisionReason.trim()) return;
    if (choice === 'approve' && approveDisabled) return;
    setBusy('decision'); setCommandError(null);
    try {
      const next = await saveDecision({ proposal_id: proposal.id, proposal_sha256: proposal.sha256,
        scope_id: scope.id, scope_sha256: scope.sha256, plan_id: plan.id, plan_sha256: plan.sha256,
        world_sha256: plan.world.sha256, choice, reason: decisionReason,
        confirmed_no_launch: choice === 'approve' && plan.execution_blockers.length > 0 && confirmedNoLaunch }, state.revision);
      setState(next); setLoadStatus({ kind: 'ready' });
    } catch (error) { setCommandError(error instanceof Error ? error.message : 'The decision was not confirmed as saved.'); }
    finally { setBusy(null); }
  }
  async function runApprovedPlan() {
    if (!state || !currentApproval || !plan) return;
    setBusy('run'); setCommandError(null);
    try {
      const next = await createRun({ decision_id: currentApproval.id }, state.revision);
      setState(next); setLoadStatus({ kind: 'ready' });
      const run = next.runs.find(item => item.decision_id === currentApproval.id);
      if (!run) throw new Error('The service returned no run receipt for the approved decision.');
      const runRef: CouncilRunRef = { kind: 'council', run_id: run.id, arm: 'intervention' };
      const trace = await loadCouncilTrace(runRef);
      onRunLoaded(runRef, trace);
    } catch (error) { setCommandError(error instanceof Error ? error.message : 'The run result could not be loaded.'); }
    finally { setBusy(null); }
  }
  async function loadRecordedRun(run: CouncilState['runs'][number], arm: CouncilRunRef['arm']) {
    const runRef: CouncilRunRef = { kind: 'council', run_id: run.id, arm };
    setBusy(`trace:${run.id}:${arm}`); setCommandError(null);
    try { const trace = await loadCouncilTrace(runRef); onRunLoaded(runRef, trace); }
    catch (error) { setCommandError(error instanceof Error ? error.message : `Run ${run.id} ${arm} trace is unavailable.`); }
    finally { setBusy(null); }
  }

  return <section id={id} className="council-panel glass" aria-label="Council proposal and simulation review" hidden={!open}>
    <header className="council-panel-header">
      <div><span className="council-overline">SIMULATION REVIEW</span><h2>City Council</h2></div>
      <div className="council-panel-actions">
        {loadStatus.kind === 'ready' && <button type="button" onClick={() => void refresh()} disabled={busy !== null} aria-label="Refresh Council state">Refresh</button>}
        <button type="button" className="small-icon" onClick={onClose} aria-label="Close Council panel"><X size={16} /></button>
      </div>
    </header>
    {loadStatus.kind === 'loading' && <p className="council-state-message" role="status">Connecting to the local Council service…</p>}
    {loadStatus.kind === 'error' && <div className="council-unavailable" role="alert">
      <strong>Local Council service unavailable</strong><p>{loadStatus.message}</p>
      <p>City playback remains usable. No Council command has been saved.</p>
      <button type="button" onClick={() => void refresh()} disabled={busy !== null}>Try again</button>
    </div>}
    {loadStatus.kind === 'ready' && state && <>
      <div className="council-session-meta"><span>Session revision {state.revision}</span><span>{state.session_id}</span></div>
      {commandError && <p className="council-command-error" role="alert">{commandError}</p>}

      <section className="council-section">
        <div className="council-section-title"><span>01</span><h3>Proposal intake</h3></div>
        <form onSubmit={event => void saveProposal(event)}>
          <label className="council-field"><span>Markdown proposal</span><textarea rows={5} value={draft} onChange={event => setDraft(event.target.value)}
            placeholder={'## Goals\nDescribe the proposed change.\n\n## Unknowns\nList what still needs review.'} />
          </label>
          <div className="council-form-footer"><small>Submitting creates a new immutable revision.</small>
            <button className="council-primary" type="submit" disabled={busy !== null || !draft.trim()}>
              {busy === 'proposal' ? 'Saving…' : 'Save next revision'} <ArrowRight size={13} />
            </button></div>
        </form>
        {revisions.length > 0 && <div className="council-revision-browser">
          <label className="council-field"><span>Inspect exact saved revision</span>
            <select value={selectedRevisionId} onChange={event => setSelectedRevisionId(event.target.value)}>
              {revisions.map(item => <option key={item.id} value={item.id}>{revisionLabel(item.revision)} · {shortenedHash(item.sha256)}</option>)}
            </select>
          </label>
          {selectedRevision && <>
            <pre className="council-markdown-preview">{selectedRevision.markdown}</pre>
            <button type="button" className="council-secondary" onClick={() => setDraft(selectedRevision.markdown)}>Load this revision into editor</button>
          </>}
        </div>}
        {proposal && <details className="council-analysis" open>
          <summary>Current revision {proposal.revision} · {shortenedHash(proposal.sha256)}</summary>
          <div className="council-span-grid">
            {lineSpans('Constraints', proposal.sections.constraints)}{lineSpans('Measures', proposal.sections.measures)}
            {lineSpans('Assumptions', proposal.sections.assumptions)}{lineSpans('Goals', proposal.sections.goals)}
            {lineSpans('Changes', proposal.sections.changes)}{lineSpans('Unknowns', proposal.sections.unknowns)}
            {lineSpans('Unclassified text', proposal.unclassified)}
          </div>
          <div className="council-source-context"><h4>Source context</h4>
            <p>Snapshot {proposal.source_context.snapshot_id} · SHA-256 {shortenedHash(proposal.source_context.sha256)}</p>
            <p>Retrieved {proposal.source_context.retrieved_at ?? 'time not recorded'}</p>
            {proposal.source_context.limits.length > 0 && <ul>{proposal.source_context.limits.map((limit, index) => <li key={`${index}-${limit}`}>{limit}</li>)}</ul>}
            {proposal.citations.length > 0 && <div className="council-citations"><h4>References</h4><ul>{proposal.citations.map((citation, index) => <li key={`${index}-${citation.url}`}>
              <a href={citation.url} target="_blank" rel="noreferrer">{citation.label || citation.url}</a><span>Unverified reference</span>
            </li>)}</ul></div>}
          </div>
        </details>}
      </section>

      <section className="council-section">
        <div className="council-section-title"><span>02</span><h3>Reviewed scope</h3></div>
        {!proposal && <p className="council-muted">Save a proposal revision before defining scope.</p>}
        {proposal && <>
          {scope && <SavedScope scope={scope} />}
          <form onSubmit={event => void saveCurrentScope(event)}>
            <label className="council-field"><span>Included in evaluation</span><textarea rows={2} required value={evaluatedScope}
              onChange={event => setEvaluatedScope(event.target.value)} /></label>
            <label className="council-field"><span>Excluded from evaluation</span><textarea rows={2} required value={excludedScope}
              onChange={event => setExcludedScope(event.target.value)} /></label>
            <label className="council-field"><span>Reviewer note</span><textarea rows={2} required value={reviewerNote}
              onChange={event => setReviewerNote(event.target.value)} /></label>
            <button className="council-secondary" type="submit" disabled={busy !== null || !evaluatedScope.trim() || !excludedScope.trim() || !reviewerNote.trim()}>
              {busy === 'scope' ? 'Saving…' : scopeMatches ? 'Save new scope revision' : 'Save explicit scope'}
            </button>
          </form>
          {!scopeMatches && scope && <p className="council-muted">The saved scope belongs to an earlier proposal revision. Save a new scope before planning.</p>}
        </>}
      </section>

      <section className="council-section">
        <div className="council-section-title"><span>03</span><h3>Selected action and plan</h3></div>
        {!scopeMatches && <p className="council-muted">Save an explicit scope for the current proposal before creating a plan.</p>}
        {scopeMatches && <form onSubmit={event => void saveCurrentPlan(event)}>
          <label className="council-field"><span>Action</span>
            <select value={action} onChange={event => setAction(actionChoice(event.target.value))} required>
              <option value="" disabled>Choose an action</option>
              <option value="establish_service_site">Establish a service site</option>
              <option value="unsupported">Record an unsupported action</option>
            </select>
          </label>
          {action === 'establish_service_site' && <>
            <label className="council-field"><span>Proposed location</span>
              <select required value={parameters.location_id} onChange={event => updateParameter('location_id', event.target.value)}>
                <option value="" disabled>Choose a location</option>
                {state.locations.map(location => <option key={location.id} value={location.id}>{location.label} · authority unknown · operation status unknown</option>)}
              </select>
            </label>
            {parameters.location_id && state.locations.find(item => item.id === parameters.location_id) && <p className="council-location-note">
              Authority: unknown. Operation status: unknown. Selecting this point projects a proposed site onto the city map.
            </p>}
            <div className="council-parameter-grid">
              {numericParameter('grant_cents', 'Grant (cents)', 0, 30000)}
              {numericParameter('stock_grams', 'Initial stock (grams; 100 g increments)', 0, 60000, 100)}
              {numericParameter('service_capacity', `Service capacity (1–${population.toLocaleString()})`, 1, population)}
              {numericParameter('readiness_second', 'Readiness (seconds)')}
              {numericParameter('funding_second', 'Funding (seconds)')}
              {numericParameter('delivery_second', 'Delivery (seconds)')}
              {numericParameter('commissioning_second', 'Commissioning (seconds)')}
              {numericParameter('open_second', 'Open (seconds)')}
              {numericParameter('close_second', 'Close (seconds)')}
            </div>
            {parameterProblem && <p className="council-validation" role="status" aria-live="polite">{parameterProblem}</p>}
            <button type="button" className="council-secondary" disabled={state.locations.length === 0}
              onClick={() => {
                const location = state.locations[0];
                if (!location) return;
                setParameters({ location_id: location.id, grant_cents: '5000', stock_grams: '10000',
                  service_capacity: String(Math.min(24, population)), readiness_second: '3600', funding_second: '7200',
                  delivery_second: '9000', commissioning_second: '10800', open_second: '12600', close_second: '18000' });
              }}>Use illustrative assumptions</button>
            <p className="council-location-note">Ticks must be strictly increasing from 0–21,600 seconds. Grant max 30,000 cents; stock is 0 or 100 g increments, max 60,000 grams. These values are a scenario draft, not operating evidence.</p>
            <p className="council-assumption"><strong>Scenario assumption</strong> Operator: hypothetical municipal operator.</p>
          </>}
          {action === 'unsupported' && <p className="council-callout">This plan will be retained as a readable draft. It cannot be approved for execution or run.</p>}
          <div className="council-form-footer"><small>Population {population.toLocaleString()} · seed {seed}</small>
            <button className="council-secondary" type="submit" disabled={busy !== null || !action
              || (action === 'establish_service_site' && !buildSiteParameters())}>
              {busy === 'plan' ? 'Saving…' : 'Save plan draft'}
            </button></div>
        </form>}
        {plan && <PlanRecord plan={plan} locations={state.locations} onFocus={onFocusLocation} ready={ready} current={planMatches} />}
      </section>

      <section className="council-section">
        <div className="council-section-title"><span>04</span><h3>Decision and run</h3></div>
        {!planMatches && <p className="council-muted">The current plan must match the saved proposal and scope before recording a decision.</p>}
        {planMatches && plan && <>
          {plan.action === 'unsupported' && <p className="council-callout">This unsupported plan cannot be approved or executed. You may request revision or reject it.</p>}
          {plan.execution_blockers.length > 0 && plan.action !== 'unsupported' && <label className="council-confirmation">
            <input type="checkbox" checked={confirmedNoLaunch} onChange={event => setConfirmedNoLaunch(event.target.checked)} />
            <span>If approved, this run will record no launch because the plan has execution blockers.</span>
          </label>}
          <label className="council-field"><span>Decision reason</span><textarea rows={2} value={decisionReason}
            onChange={event => setDecisionReason(event.target.value)} placeholder="Record why this decision was made." /></label>
          <div className="council-decision-actions">
            <button type="button" className="council-approve" disabled={busy !== null || approveDisabled || !decisionReason.trim()}
              onClick={() => void recordDecision('approve')}>Approve plan</button>
            <button type="button" className="council-secondary" disabled={busy !== null || !decisionReason.trim()}
              onClick={() => void recordDecision('request_revision')}>Request revision</button>
            <button type="button" className="council-danger" disabled={busy !== null || !decisionReason.trim()}
              onClick={() => void recordDecision('reject')}>Reject</button>
          </div>
          {currentApproval && <div className="council-run-action"><p>Current approval is bound to this plan and frozen world.</p>
            <button type="button" className="council-primary" disabled={busy !== null}
              onClick={() => void runApprovedPlan()}>{busy === 'run' ? 'Running paired scenario…' : 'Run approved plan'} <ArrowRight size={13} /></button>
          </div>}
        </>}
        {state.decisions.length > 0 && <details className="council-history"><summary>Decision history · {state.decisions.length}</summary>
          <ol>{state.decisions.map(decision => <li key={decision.id}>
            <strong>{decision.choice.replace('_', ' ')}</strong>{decision.current ? ' · current' : ''}<p>{decision.reason}</p>
            <small>Proposal {shortenedHash(decision.proposal_sha256)} · scope {shortenedHash(decision.scope_sha256)} · plan {shortenedHash(decision.plan_sha256)} · world {shortenedHash(decision.world_sha256)}</small>
            {decision.confirmed_no_launch && <small>Confirmed no launch</small>}
          </li>)}</ol>
        </details>}
        {state.runs.length > 0 && <div className="council-run-history"><h4>Recorded runs</h4>
          {state.runs.map(run => <RunRecord key={run.id} run={run} onLoad={(item, arm) => void loadRecordedRun(item, arm)} busy={busy !== null} />)}
        </div>}
      </section>
      {projectedLocation && plan?.parameters && <p className="council-marker-status" role="status">
        Proposed site shown on map: {projectedLocation.label}. Projection only.
      </p>}
    </>}
    {currentCouncilTrace && <RolloutTimeline trace={currentCouncilTrace} seconds={currentSeconds} onSeekTo={onSeekTo} />}
  </section>;
}
