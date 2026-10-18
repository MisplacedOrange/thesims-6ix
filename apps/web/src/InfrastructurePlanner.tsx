import { useState } from 'react';
import { createRun, saveDecision, savePlan, saveScope } from './council.ts';
import type { CouncilState, Plan, SiteParameters } from './council.ts';

const defaults: SiteParameters = {
  location_id: '', operator_assumption: 'hypothetical_municipal_operator',
  grant_cents: 10000, stock_grams: 20000, service_capacity: 12,
  readiness_second: 500, funding_second: 1000, delivery_second: 6000,
  commissioning_second: 7000, open_second: 8000, close_second: 20000,
};
const labels = {
  grant_cents: 'Scenario grant (cents)', stock_grams: 'Stock (grams)', service_capacity: 'Base visit limit',
  readiness_second: 'Readiness (second)', funding_second: 'Funding (second)', delivery_second: 'Delivery (second)',
  commissioning_second: 'Commissioning (second)', open_second: 'Opening (second)', close_second: 'Closure (second)',
} as const;

export function InfrastructurePlanner({ state, onChange, disabled }: {
  state: CouncilState; onChange: (state: CouncilState) => void; disabled: boolean;
}) {
  const [action, setAction] = useState<Plan['action']>('establish_service_site');
  const [site, setSite] = useState(defaults);
  const [effective, setEffective] = useState(12000);
  const [target, setTarget] = useState(24);
  const [scope, setScope] = useState('One hypothetical municipal food service during the six-hour scenario.');
  const [excluded, setExcluded] = useState('Real provider changes, capital construction and multi-day effects.');
  const [reason, setReason] = useState('');
  const [noLaunch, setNoLaunch] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const catalog = state.action_catalog ?? [];
  const descriptor = catalog.find(item => item.action === action);
  const change = action === 'expand_facility' || action === 'reduce_or_close_service';
  const busy = disabled || pending;
  const decision = state.decisions.find(item => item.current);
  async function command(work: () => Promise<CouncilState>) {
    setPending(true); setError(null);
    try { onChange(await work()); } catch (e) { setError(e instanceof Error ? e.message : 'Council command failed.'); }
    finally { setPending(false); }
  }
  return <section className="council-record-section" aria-label="Infrastructure planner">
    <h3>Infrastructure planner</h3>
    <p>Review a scope, save a plan, then record a decision before running. Scenarios are hypothetical and last six hours.</p>
    {error && <p role="alert" className="council-error">{error}</p>}
    <fieldset disabled={busy || !state.proposal} className="council-inline-form">
      <label className="council-label">Evaluated scope<textarea value={scope} onChange={e => setScope(e.target.value)} /></label>
      <label className="council-label">Excluded scope<textarea value={excluded} onChange={e => setExcluded(e.target.value)} /></label>
      <button type="button" disabled={!scope.trim()} onClick={() => void command(() => saveScope({
        proposal_id: state.proposal!.id, evaluated_scope: scope, excluded_scope: excluded, reviewer_note: '',
      }, state.revision))}>Save scope</button>
      <label className="council-label">Action<select value={action} onChange={e => setAction(e.target.value as Plan['action'])}>
        {catalog.map(item => <option key={item.action} value={item.action}>{item.label}{item.executable ? '' : ' (proposal only)'}</option>)}
      </select></label>
      {descriptor && <><p>{descriptor.inputs}</p><p>{descriptor.effects}</p><p>{descriptor.limits}</p></>}
      {descriptor?.executable && <>
        <p>Assumed municipal operation. Capacity means total visits allowed for this operating day; expansion assumes spare capability and adds no stock, equipment or staff.</p>
        <label className="council-label">Base site location<select value={site.location_id || state.locations[0]?.id || ''}
          onChange={e => setSite({ ...site, location_id: e.target.value })}>
          {state.locations.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select></label>
        <div className="council-form-grid">{Object.entries(labels).map(([key, label]) =>
          <label className="council-label" key={key}>{label}<input type="number" min="0" step="1"
            value={site[key as keyof typeof labels]} onChange={e => setSite({ ...site, [key]: e.target.valueAsNumber })} /></label>)}</div>
        {change && <div className="council-form-grid">
          <label className="council-label">Effective second<input type="number" value={effective} onChange={e => setEffective(e.target.valueAsNumber)} /></label>
          <label className="council-label">Absolute target visit limit (zero closes)<input type="number" min="0" value={target} onChange={e => setTarget(e.target.valueAsNumber)} /></label>
        </div>}
      </>}
      <button type="button" disabled={!state.scope || !descriptor} onClick={() => void command(() => {
        const base = { ...site, location_id: site.location_id || state.locations[0]?.id || '' };
        return savePlan({ proposal_id: state.proposal!.id, scope_id: state.scope!.id, action,
          parameters: descriptor?.executable ? (change ? { base_site: base, effective_second: effective, target_capacity: target } : base) : null,
          population: 200, seed: 2026 }, state.revision);
      })}>Save plan for review</button>
    </fieldset>
    {state.plan && <div className="council-record-card">
      <h4>Saved plan: {state.plan.action.replaceAll('_', ' ')}</h4>
      <p>Matched population: {state.plan.world.population}; seed: {state.plan.world.seed}.</p>
      <pre>{JSON.stringify(state.plan.parameters, null, 2)}</pre>
      {state.plan.execution_blockers.map(item => <p key={item}>{item}</p>)}
      {state.plan.advice.map(item => <p key={item.role}>{item.role}: {item.note}</p>)}
      <fieldset disabled={busy}>
        <label className="council-label">Decision reason<textarea value={reason} onChange={e => setReason(e.target.value)} /></label>
        {state.plan.execution_blockers.length > 0 && <label><input type="checkbox" checked={noLaunch} onChange={e => setNoLaunch(e.target.checked)} />Confirm a blocked, no-launch comparison</label>}
        {(['approve', 'request_revision', 'reject'] as const).map(choice => <button type="button" key={choice}
          disabled={!reason.trim() || (choice === 'approve' && (!catalog.find(item => item.action === state.plan!.action)?.executable
            || (state.plan!.execution_blockers.length > 0 && !noLaunch)))}
          onClick={() => void command(() => saveDecision({
            proposal_id: state.proposal!.id, proposal_sha256: state.proposal!.sha256,
            scope_id: state.scope!.id, scope_sha256: state.scope!.sha256,
            plan_id: state.plan!.id, plan_sha256: state.plan!.sha256, world_sha256: state.plan!.world.sha256,
            choice, reason, confirmed_no_launch: state.plan!.execution_blockers.length > 0 && noLaunch,
          }, state.revision))}>{choice.replaceAll('_', ' ')}</button>)}
        <button type="button" disabled={decision?.choice !== 'approve'} onClick={() => void command(() =>
          createRun({ decision_id: decision!.id }, state.revision))}>Run matched comparison</button>
      </fieldset>
    </div>}
  </section>;
}
