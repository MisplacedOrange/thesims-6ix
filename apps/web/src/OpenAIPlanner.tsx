import { useState } from 'react';
import { generatePlannerDraft, loadCouncilState, savePlan } from './council.ts';
import type { CouncilState } from './council.ts';
import type { PlannerDraft } from './openaiPlanner.ts';
import './openai-planner.css';

export function OpenAIPlanner({ state, onChange, disabled }: {
  state: CouncilState; onChange: (state: CouncilState) => void; disabled: boolean;
}) {
  const [population, setPopulation] = useState(200);
  const [seed, setSeed] = useState(2026);
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const planner = state.planner;
  const drafts = (planner?.drafts ?? []).filter(draft => draft.context.proposal.id === state.proposal?.id);
  const draft = drafts.find(item => item.id === selected) ?? drafts.at(-1);
  const busy = disabled || pending;
  const current = (item: PlannerDraft) => item.context.proposal.sha256 === state.proposal?.sha256
    && item.context.scope.sha256 === state.scope?.sha256;

  async function command(work: () => Promise<CouncilState>) {
    if (busy) return;
    setPending(true); setError(null);
    try { onChange(await work()); }
    catch (e) {
      setError(e instanceof Error ? e.message : 'Planner command failed.');
      // Errors can still have audit records, or an unknown network outcome.
      try { onChange(await loadCouncilState()); } catch { /* Keep the original error visible. */ }
    } finally { setPending(false); }
  }
  return <section className="council-record-section openai-planner" aria-label="OpenAI plan drafts" aria-busy={pending}>
    <h3>OpenAI plan drafts</h3>
    <p>Generate a proposal from the saved scope and evidence, review its assumptions, then adopt it as a plan for a separate approval decision.</p>
    <p role="status">{planner?.ready ? `Ready · ${planner.model}` : planner?.reason ?? 'This server does not expose model planning.'}</p>
    {!state.scope && <p>Save a proposal and evaluated scope in the infrastructure planner below first.</p>}
    {error && <p role="alert" className="council-error">{error}</p>}
    <fieldset disabled={busy}>
      <div className="council-form-grid">
        <label className="council-label">Population<select value={population} onChange={e => setPopulation(Number(e.target.value))}>
          {[200, 600, 1200, 2400].map(value => <option key={value} value={value}>{value}</option>)}
        </select></label>
        <label className="council-label">Seed<input type="number" min="0" max="2147483647" step="1" value={seed}
          onChange={e => setSeed(e.target.valueAsNumber)} /></label>
      </div>
      <label className="openai-consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
        Send the saved proposal, scope, organization records, stakeholder inputs and pinned location context to OpenAI. I have reviewed their sharing and consent limits. API usage is billed to the configured account.
      </label>
      <button type="button" disabled={!planner?.ready || !state.scope || !state.proposal || !consent
        || !Number.isInteger(seed) || seed < 0 || seed > 2147483647}
        onClick={() => void command(async () => {
          await generatePlannerDraft({ population, seed, consent_to_send: consent }, state.revision);
          return loadCouncilState();
        })}>{pending ? 'Working…' : 'Generate draft with OpenAI'}</button>
    </fieldset>
    {drafts.length > 0 && <label className="council-label">Saved drafts<select value={draft?.id ?? ''} disabled={busy}
      onChange={e => setSelected(e.target.value)}>{drafts.map(item => <option key={item.id} value={item.id}>
        {item.command.action.replaceAll('_', ' ')} · {item.id.slice(-8)}
      </option>)}</select></label>}
    {draft && <article className="council-record-card">
      <h4>Draft: {draft.command.action.replaceAll('_', ' ')}</h4>
      <p>{draft.output.rationale}</p>
      <dl>{(['assumptions', 'exclusions', 'uncertainties'] as const).map(key => <div key={key}>
        <dt>{key}</dt><dd>{draft.output[key] || 'None recorded'}</dd>
      </div>)}</dl>
      <details><summary>Exact proposed plan and provenance</summary>
        <pre>{JSON.stringify(draft.command, null, 2)}</pre>
        <p>Draft hash: {draft.sha256}</p><p>Input hash: {draft.input_sha256}</p><p>Call: {draft.call_id}</p>
      </details>
      {!current(draft) && <p>The proposal or scope changed. Generate a new draft.</p>}
      <button type="button" disabled={busy || !current(draft)} onClick={() => void command(() =>
        savePlan({ ...draft.command, planner_draft_id: draft.id }, state.revision))}>Adopt draft for review</button>
      <p>Adoption validates and saves the plan. Review its blockers below, record an approval decision, then run the matched comparison.</p>
    </article>}
    {state.plan?.planner_draft_id && <p>Current plan adopted from {state.plan.planner_draft_id}.</p>}
    {(planner?.calls.length ?? 0) > 0 && <details><summary>Recent model calls</summary>
      {planner!.calls.map(call => <article key={call.id} className="council-record-card">
        <p>{call.started_at} · {call.status} · {call.resolved_model ?? call.model}</p>
        {call.error && <p>{call.error.code}: {call.error.message}</p>}
        {call.status === 'running' && <p>If the server stopped during this call, its outcome may be unknown. Calls are never automatically retried.</p>}
        <p>{call.id}</p>{call.response_id && <p>Response: {call.response_id}</p>}
        {call.usage !== undefined && <pre>{JSON.stringify(call.usage, null, 2)}</pre>}
      </article>)}
    </details>}
  </section>;
}
