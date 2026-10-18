import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, X } from 'lucide-react';
import { loadCouncilState, loadCouncilTrace, saveOrganization, saveStakeholderInput, submitProposal } from './council.ts';
import type {
  CouncilState, EvidenceState, OrganizationCommand, OrganizationRecord, OrganizationRole,
  StakeholderInputCommand, StakeholderInputRecord,
} from './council.ts';
import type { CouncilFoodTrace } from './interactables.ts';

type LoadStatus = { kind: 'loading' } | { kind: 'ready' } | { kind: 'error'; message: string };
type CouncilPanelProps = {
  id: string;
  open: boolean;
  onClose: () => void;
};
type OrganizationDraft = {
  organization_id: string; name: string; role: OrganizationRole; evidence_state: EvidenceState;
  operating_status: OrganizationRecord['operating_status']; authority_status: OrganizationRecord['authority_status'];
  authority_basis: string; location_id: string; source_label: string; source_url: string;
  budget_cents: string; stock_grams: string; service_capacity: string; operating_hours: string;
  permitted_decisions: string; agreement: string; resource_notes: string; notes: string;
};
type StakeholderDraft = {
  stakeholder_group: StakeholderInputRecord['stakeholder_group']; organization_id: string;
  input_date: string; method: StakeholderInputRecord['method']; evidence_state: EvidenceState;
  source_label: string; source_url: string; geography: string; reach_summary: string;
  consent_limits: string; views_summary: string; groups_not_reached: string; conflicting_views: string;
};
type TraceStatus = 'idle' | 'loading' | 'ready' | 'error';

const organizationRoles: { value: OrganizationRole; label: string }[] = [
  { value: 'city_department', label: 'City department / agency' },
  { value: 'city_funder', label: 'City sponsor / funder' },
  { value: 'property_owner', label: 'Property owner / landlord' },
  { value: 'site_host', label: 'Site host / facility manager' },
  { value: 'site_operator', label: 'Service operator' },
  { value: 'supplier_distributor', label: 'Supplier / distributor' },
  { value: 'delivery_carrier', label: 'Delivery carrier / logistics provider' },
  { value: 'contractor', label: 'Contractor / service provider' },
  { value: 'retailer', label: 'Retailer' },
  { value: 'school', label: 'School / school nutrition provider' },
  { value: 'food_support_provider', label: 'Food-support provider' },
  { value: 'community_organization', label: 'Community organization' },
  { value: 'other', label: 'Other organization' },
];
const evidenceStates: { value: EvidenceState; label: string }[] = [
  { value: 'observed', label: 'Observed' }, { value: 'announced', label: 'Announced' },
  { value: 'estimated', label: 'Estimated' }, { value: 'illustrative_assumption', label: 'Illustrative assumption' },
  { value: 'unknown', label: 'Unknown' },
];
const stakeholderGroups: { value: StakeholderDraft['stakeholder_group']; label: string }[] = [
  { value: 'residents_users', label: 'Residents who use or may use the service' },
  { value: 'nearby_residents', label: 'Residents near the site' },
  { value: 'access_barriers', label: 'People facing access barriers' },
  { value: 'workers_volunteers', label: 'Workers or volunteers' },
  { value: 'nearby_businesses', label: 'Nearby businesses' },
  { value: 'food_support_partners', label: 'Food-support partners' },
  { value: 'community_organization', label: 'Community organization' },
  { value: 'public_authorities', label: 'Public authority' },
  { value: 'other', label: 'Other affected group' },
];
const inputMethods: { value: StakeholderDraft['method']; label: string }[] = [
  { value: 'consultation', label: 'Consultation' }, { value: 'survey', label: 'Survey' },
  { value: 'partner_submission', label: 'Partner submission' }, { value: 'meeting', label: 'Meeting' },
  { value: 'other', label: 'Other' },
];
const operatingStatuses: { value: OrganizationDraft['operating_status']; label: string }[] = [
  { value: 'operating', label: 'Operating' }, { value: 'not_operating', label: 'Not operating' },
  { value: 'seasonal', label: 'Seasonal' }, { value: 'unknown', label: 'Unknown' },
];
const authorityStatuses: { value: OrganizationDraft['authority_status']; label: string }[] = [
  { value: 'documented', label: 'Documented' }, { value: 'assumed', label: 'Assumed' },
  { value: 'unknown', label: 'Unknown' },
];
function emptyOrganizationDraft(): OrganizationDraft {
  return {
    organization_id: '', name: '', role: 'other', evidence_state: 'unknown', operating_status: 'unknown',
    authority_status: 'unknown', authority_basis: '', location_id: '', source_label: '', source_url: '',
    budget_cents: '', stock_grams: '', service_capacity: '', operating_hours: '',
    permitted_decisions: '', agreement: '', resource_notes: '', notes: '',
  };
}
function emptyStakeholderDraft(): StakeholderDraft {
  return {
    stakeholder_group: 'residents_users', organization_id: '', input_date: localISODate(),
    method: 'other', evidence_state: 'unknown', source_label: '', source_url: '', geography: '',
    reach_summary: '', consent_limits: '', views_summary: '', groups_not_reached: '', conflicting_views: '',
  };
}
function localISODate(value = new Date()): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}
function optionalInteger(value: string, label: string): number | null {
  if (!value.trim()) return null;
  if (!/^\d+$/.test(value.trim())) throw new Error(`${label} must be a non-negative whole number.`);
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed > 2_147_483_647) throw new Error(`${label} is outside the supported range.`);
  return parsed;
}
function organizationName(state: CouncilState, recordId: string, fallback: string): string {
  return state.organization_records.find(record => record.id === recordId)?.name ?? fallback;
}
function organizationHistory(state: CouncilState, record: OrganizationRecord): OrganizationRecord[] {
  return state.organization_records
    .filter(item => item.proposal_id === record.proposal_id && item.organization_id === record.organization_id)
    .sort((left, right) => left.organization_revision - right.organization_revision);
}
function revisionLabel(revision: number): string { return `Revision ${revision}`; }
function shortenedHash(value: string): string { return value.slice(0, 12); }
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

export function CouncilPanel({ id, open, onClose }: CouncilPanelProps) {
  const [loadStatus, setLoadStatus] = useState<LoadStatus>({ kind: 'loading' });
  const [state, setState] = useState<CouncilState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [selectedRevisionId, setSelectedRevisionId] = useState('');
  const [organizationDraft, setOrganizationDraft] = useState<OrganizationDraft>(emptyOrganizationDraft);
  const [editingOrganizationId, setEditingOrganizationId] = useState<string | null>(null);
  const [stakeholderDraft, setStakeholderDraft] = useState<StakeholderDraft>(emptyStakeholderDraft);
  const [latestTrace, setLatestTrace] = useState<CouncilFoodTrace | null>(null);
  const [traceStatus, setTraceStatus] = useState<TraceStatus>('idle');
  const [traceError, setTraceError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void loadCouncilState().then(next => {
      if (!active) return;
      setState(next); setLoadStatus({ kind: 'ready' });
      const proposal = next.proposal;
      setDraft(proposal?.markdown ?? '');
      setSelectedRevisionId(proposal?.id ?? '');
    }).catch(error => {
      if (active) setLoadStatus({ kind: 'error', message: error instanceof Error ? error.message : 'The local Council service is unavailable. City playback is still available.' });
    });
    return () => { active = false; };
  }, []);

  const revisions = useMemo(() => {
    if (!state) return [];
    const entries = [...state.proposal_history];
    if (state.proposal && !entries.some(item => item.id === state.proposal?.id)) {
      entries.push({ id: state.proposal.id, revision: state.proposal.revision, sha256: state.proposal.sha256, markdown: state.proposal.markdown });
    }
    return entries.sort((left, right) => left.revision - right.revision);
  }, [state]);
  const selectedRevision = revisions.find(item => item.id === selectedRevisionId) ?? null;
  const proposal = state?.proposal ?? null;
  const latestRunId = state?.runs.filter(run => run.proposal_id === proposal?.id).at(-1)?.id ?? null;

  useEffect(() => {
    if (!latestRunId) {
      setLatestTrace(null); setTraceStatus('idle'); setTraceError(null);
      return;
    }
    let active = true;
    setLatestTrace(null); setTraceStatus('loading'); setTraceError(null);
    void loadCouncilTrace({ kind: 'council', run_id: latestRunId, arm: 'intervention' }).then(trace => {
      if (active) { setLatestTrace(trace); setTraceStatus('ready'); }
    }).catch(error => {
      if (active) {
        setTraceStatus('error');
        setTraceError(error instanceof Error ? error.message : 'The latest intervention trace could not be loaded.');
      }
    });
    return () => { active = false; };
  }, [latestRunId]);

  async function refresh() {
    setBusy('refresh'); setCommandError(null);
    try {
      const next = await loadCouncilState(); setState(next); setLoadStatus({ kind: 'ready' });
      if (!state) {
        setDraft(next.proposal?.markdown ?? '');
        setSelectedRevisionId(next.proposal?.id ?? '');
      }
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
      setOrganizationDraft(emptyOrganizationDraft()); setEditingOrganizationId(null);
      setStakeholderDraft(emptyStakeholderDraft());
    } catch (error) { setCommandError(error instanceof Error ? error.message : 'The proposal was not confirmed as saved.'); }
    finally { setBusy(null); }
  }
  function reviseOrganization(record: OrganizationRecord) {
    setEditingOrganizationId(record.organization_id);
    setOrganizationDraft({
      organization_id: record.organization_id, name: record.name, role: record.role,
      evidence_state: record.evidence_state, operating_status: record.operating_status,
      authority_status: record.authority_status, authority_basis: record.authority_basis,
      location_id: record.location_id ?? '', source_label: record.source_label, source_url: record.source_url,
      budget_cents: record.budget_cents === null ? '' : String(record.budget_cents),
      stock_grams: record.stock_grams === null ? '' : String(record.stock_grams),
      service_capacity: record.service_capacity === null ? '' : String(record.service_capacity),
      operating_hours: record.operating_hours, permitted_decisions: record.permitted_decisions.join(', '),
      agreement: record.agreement, resource_notes: record.resource_notes, notes: record.notes,
    });
  }
  function resetOrganizationForm() {
    setOrganizationDraft(emptyOrganizationDraft()); setEditingOrganizationId(null);
  }
  async function saveOrganizationRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state?.proposal) return;
    setBusy('organization'); setCommandError(null);
    try {
      const command: OrganizationCommand = {
        proposal_id: state.proposal.id, proposal_sha256: state.proposal.sha256,
        organization_id: organizationDraft.organization_id.trim(), name: organizationDraft.name.trim(),
        role: organizationDraft.role, evidence_state: organizationDraft.evidence_state,
        operating_status: organizationDraft.operating_status, authority_status: organizationDraft.authority_status,
        authority_basis: organizationDraft.authority_basis.trim(), location_id: organizationDraft.location_id || null,
        source_label: organizationDraft.source_label.trim(), source_url: organizationDraft.source_url.trim(),
        budget_cents: optionalInteger(organizationDraft.budget_cents, 'Budget'),
        stock_grams: optionalInteger(organizationDraft.stock_grams, 'Stock'),
        service_capacity: optionalInteger(organizationDraft.service_capacity, 'Service capacity'),
        operating_hours: organizationDraft.operating_hours.trim(),
        permitted_decisions: organizationDraft.permitted_decisions.split(/[\n,]/).map(value => value.trim()).filter(Boolean),
        agreement: organizationDraft.agreement.trim(), resource_notes: organizationDraft.resource_notes.trim(),
        notes: organizationDraft.notes.trim(),
      };
      const next = await saveOrganization(command, state.revision);
      setState(next); setLoadStatus({ kind: 'ready' }); resetOrganizationForm();
    } catch (error) {
      setCommandError(error instanceof Error ? error.message : 'The organization record was not confirmed as saved.');
    } finally { setBusy(null); }
  }
  async function saveStakeholderRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state?.proposal) return;
    setBusy('stakeholder'); setCommandError(null);
    try {
      const command: StakeholderInputCommand = {
        proposal_id: state.proposal.id, proposal_sha256: state.proposal.sha256,
        stakeholder_group: stakeholderDraft.stakeholder_group,
        organization_id: stakeholderDraft.organization_id || null,
        input_date: stakeholderDraft.input_date, method: stakeholderDraft.method,
        evidence_state: stakeholderDraft.evidence_state, source_label: stakeholderDraft.source_label.trim(),
        source_url: stakeholderDraft.source_url.trim(), geography: stakeholderDraft.geography.trim(),
        reach_summary: stakeholderDraft.reach_summary.trim(), consent_limits: stakeholderDraft.consent_limits.trim(),
        views_summary: stakeholderDraft.views_summary.trim(), groups_not_reached: stakeholderDraft.groups_not_reached.trim(),
        conflicting_views: stakeholderDraft.conflicting_views.trim(),
      };
      const next = await saveStakeholderInput(command, state.revision);
      setState(next); setLoadStatus({ kind: 'ready' }); setStakeholderDraft(emptyStakeholderDraft());
    } catch (error) {
      setCommandError(error instanceof Error ? error.message : 'The stakeholder input was not confirmed as saved.');
    } finally { setBusy(null); }
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

      <section className="council-section" aria-label="Organization records">
        <div className="council-section-title"><span>02</span><h3>Organizations and resources</h3></div>
        <p className="council-muted">Proposal-linked records describe roles, evidence, authority and resource limits. A map location alone does not establish that an organization is operating. These records provide review context; they do not change organization behavior yet.</p>
        {!proposal ? <p className="council-muted">Save a proposal revision before adding organization records.</p> : <>
          <div className="council-record-list">
            {state.organizations.length === 0 && <p className="council-muted">No organizations are recorded for this proposal revision.</p>}
            {state.organizations.map(record => <article className="council-record-card" key={record.id}>
              <div className="council-record-heading"><strong>{record.name}</strong><span>{organizationRoles.find(item => item.value === record.role)?.label ?? record.role}</span></div>
              <dl>
                <div><dt>Actor ID / revision</dt><dd>{record.organization_id} · rev {record.organization_revision}</dd></div>
                <div><dt>Record ID / hash</dt><dd>{record.id} · {shortenedHash(record.sha256)}</dd></div>
                <div><dt>Evidence / operation</dt><dd>{record.evidence_state.replaceAll('_', ' ')} · {record.operating_status.replaceAll('_', ' ')}</dd></div>
                <div><dt>Authority</dt><dd>{record.authority_status}{record.authority_basis ? ` · ${record.authority_basis}` : ''}</dd></div>
                <div><dt>Source</dt><dd>{record.source_url ? <a href={record.source_url} target="_blank" rel="noreferrer">{record.source_label}</a> : record.source_label}</dd></div>
                <div><dt>Resources</dt><dd>{[
                  record.budget_cents === null ? null : `${record.budget_cents.toLocaleString()}¢`,
                  record.stock_grams === null ? null : `${record.stock_grams.toLocaleString()} g`,
                  record.service_capacity === null ? null : `${record.service_capacity.toLocaleString()} visits`,
                  record.operating_hours || null,
                ].filter(Boolean).join(' · ') || 'Not specified'}</dd></div>
              </dl>
              {record.permitted_decisions.length > 0 && <p className="council-record-note"><strong>Permitted decisions:</strong> {record.permitted_decisions.join(', ')}</p>}
              {record.resource_notes && <p className="council-record-note"><strong>Resource limits:</strong> {record.resource_notes}</p>}
              {record.notes && <p className="council-record-note">{record.notes}</p>}
              {organizationHistory(state, record).length > 1 && <details className="council-entry-form">
                <summary>Previous revisions ({organizationHistory(state, record).length - 1})</summary>
                <ol>{organizationHistory(state, record).filter(item => item.id !== record.id).map(previous => <li key={previous.id}>
                  <strong>Revision {previous.organization_revision}</strong> · {previous.role.replaceAll('_', ' ')} · {previous.evidence_state.replaceAll('_', ' ')} · {shortenedHash(previous.sha256)}
                  <p>{previous.source_url ? <a href={previous.source_url} target="_blank" rel="noreferrer">{previous.source_label}</a> : previous.source_label}</p>
                  {previous.notes && <p>{previous.notes}</p>}
                </li>)}</ol>
              </details>}
              <button type="button" className="council-secondary" onClick={() => reviseOrganization(record)} disabled={busy !== null}>Create revision</button>
            </article>)}
          </div>
          <details className="council-entry-form" open={state.organizations.length === 0 || editingOrganizationId !== null}>
            <summary>{editingOrganizationId ? `Create a new revision for ${editingOrganizationId}` : 'Add an organization record'}</summary>
            <form onSubmit={event => void saveOrganizationRecord(event)}>
              <div className="council-form-grid">
                <label className="council-field"><span>Stable organization ID</span><input required pattern="[a-z0-9][a-z0-9._-]{1,63}" maxLength={64}
                  value={organizationDraft.organization_id} disabled={editingOrganizationId !== null}
                  onChange={event => setOrganizationDraft(current => ({ ...current, organization_id: event.target.value }))} placeholder="site-operator" /></label>
                <label className="council-field"><span>Organization or role name</span><input required maxLength={200} value={organizationDraft.name}
                  onChange={event => setOrganizationDraft(current => ({ ...current, name: event.target.value }))} placeholder="Use a role label if identity is unknown" /></label>
                <label className="council-field"><span>Role</span><select value={organizationDraft.role} onChange={event => setOrganizationDraft(current => ({ ...current, role: event.target.value as OrganizationRole }))}>
                  {organizationRoles.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select></label>
                <label className="council-field"><span>Evidence state</span><select value={organizationDraft.evidence_state} onChange={event => setOrganizationDraft(current => ({ ...current, evidence_state: event.target.value as EvidenceState }))}>
                  {evidenceStates.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select></label>
                <label className="council-field"><span>Operating status</span><select value={organizationDraft.operating_status} onChange={event => setOrganizationDraft(current => ({ ...current, operating_status: event.target.value as OrganizationDraft['operating_status'] }))}>
                  {operatingStatuses.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select></label>
                <label className="council-field"><span>Authority status</span><select value={organizationDraft.authority_status} onChange={event => setOrganizationDraft(current => ({ ...current, authority_status: event.target.value as OrganizationDraft['authority_status'] }))}>
                  {authorityStatuses.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select></label>
                <label className="council-field"><span>Location, if known</span><select value={organizationDraft.location_id} onChange={event => setOrganizationDraft(current => ({ ...current, location_id: event.target.value }))}>
                  <option value="">No mapped location</option>
                  {state.locations.map(location => <option key={location.id} value={location.id}>{location.label}</option>)}
                </select></label>
                <label className="council-field"><span>Evidence source label</span><input required maxLength={300} value={organizationDraft.source_label}
                  onChange={event => setOrganizationDraft(current => ({ ...current, source_label: event.target.value }))} placeholder="Source name or 'scenario assumption'" /></label>
                <label className="council-field"><span>Source link (optional)</span><input type="url" maxLength={1000} value={organizationDraft.source_url}
                  onChange={event => setOrganizationDraft(current => ({ ...current, source_url: event.target.value }))} placeholder="https://…" /></label>
              </div>
              <details className="council-subform">
                <summary>Authority, agreements and resources</summary>
                <div className="council-form-grid">
                  <label className="council-field"><span>Authority basis</span><textarea rows={2} maxLength={2000} value={organizationDraft.authority_basis}
                    onChange={event => setOrganizationDraft(current => ({ ...current, authority_basis: event.target.value }))} placeholder="Mandate, contract, permission, or unknown" /></label>
                  <label className="council-field"><span>Agreement or dependency</span><textarea rows={2} maxLength={2000} value={organizationDraft.agreement}
                    onChange={event => setOrganizationDraft(current => ({ ...current, agreement: event.target.value }))} placeholder="Record a relevant agreement, or leave blank" /></label>
                  <label className="council-field"><span>Budget cap (cents, optional)</span><input type="number" min="0" step="1" value={organizationDraft.budget_cents}
                    onChange={event => setOrganizationDraft(current => ({ ...current, budget_cents: event.target.value }))} /></label>
                  <label className="council-field"><span>Stock cap (grams, optional)</span><input type="number" min="0" step="1" value={organizationDraft.stock_grams}
                    onChange={event => setOrganizationDraft(current => ({ ...current, stock_grams: event.target.value }))} /></label>
                  <label className="council-field"><span>Service capacity (visits, optional)</span><input type="number" min="0" step="1" value={organizationDraft.service_capacity}
                    onChange={event => setOrganizationDraft(current => ({ ...current, service_capacity: event.target.value }))} /></label>
                  <label className="council-field"><span>Operating hours or schedule</span><input maxLength={300} value={organizationDraft.operating_hours}
                    onChange={event => setOrganizationDraft(current => ({ ...current, operating_hours: event.target.value }))} placeholder="Unknown unless sourced" /></label>
                  <label className="council-field"><span>Permitted decisions (comma or line separated)</span><textarea rows={2} maxLength={2000} value={organizationDraft.permitted_decisions}
                    onChange={event => setOrganizationDraft(current => ({ ...current, permitted_decisions: event.target.value }))} placeholder="accept capped orders, set delivery window" /></label>
                  <label className="council-field"><span>Other resource limits</span><textarea rows={2} maxLength={2000} value={organizationDraft.resource_notes}
                    onChange={event => setOrganizationDraft(current => ({ ...current, resource_notes: event.target.value }))} /></label>
                  <label className="council-field"><span>Notes</span><textarea rows={2} maxLength={2000} value={organizationDraft.notes}
                    onChange={event => setOrganizationDraft(current => ({ ...current, notes: event.target.value }))} /></label>
                </div>
              </details>
              <div className="council-form-footer"><small>Saving creates an immutable record revision and requires the impact scope to be reviewed again.</small>
                <div><button type="button" className="council-secondary" onClick={resetOrganizationForm} disabled={busy !== null}>Clear</button>
                  <button className="council-primary" type="submit" disabled={busy !== null || !proposal}>{busy === 'organization' ? 'Saving…' : 'Save organization'} <ArrowRight size={13} /></button></div>
              </div>
            </form>
          </details>
        </>}
        {state.plan && <div className="council-record-card">
          <strong>Organization and input snapshot on current plan</strong>
          <p>{state.plan.organization_refs.length} core organization role(s) linked; {state.plan.stakeholder_input_refs.length} stakeholder record(s) frozen.</p>
          {state.plan.organization_refs.map(reference => <p key={reference.record_id} className="council-record-note">{reference.role.replaceAll('_', ' ')}: {organizationName(state, reference.record_id, reference.organization_id)} · {shortenedHash(reference.sha256)}</p>)}
          {state.plan.organization_record_gaps.length > 0 && <p className="council-record-note">No record: {state.plan.organization_record_gaps.join(', ').replaceAll('_', ' ')}</p>}
          {state.plan.organization_binding_ambiguities.length > 0 && <p className="council-record-note">Choose one record for: {state.plan.organization_binding_ambiguities.join(', ').replaceAll('_', ' ')}</p>}
        </div>}
      </section>

      <section className="council-section" aria-label="Stakeholder input records">
        <div className="council-section-title"><span>03</span><h3>Stakeholder input</h3></div>
        <p className="council-muted">Record consultation, survey, and partner evidence separately from synthetic household behavior. This form logs input you provide; it does not contact participants or verify representativeness. Store group-level summaries only; do not enter names or personal food-assistance details.</p>
        {!proposal ? <p className="council-muted">Save a proposal revision before adding stakeholder input.</p> : <>
          <details className="council-entry-form" open={state.stakeholder_inputs.length === 0}>
            <summary>Add stakeholder input record</summary>
            <form onSubmit={event => void saveStakeholderRecord(event)}>
              <div className="council-form-grid">
                <label className="council-field"><span>Affected group</span><select value={stakeholderDraft.stakeholder_group} onChange={event => setStakeholderDraft(current => ({ ...current, stakeholder_group: event.target.value as StakeholderDraft['stakeholder_group'] }))}>
                  {stakeholderGroups.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select></label>
                <label className="council-field"><span>Input method</span><select value={stakeholderDraft.method} onChange={event => setStakeholderDraft(current => ({ ...current, method: event.target.value as StakeholderDraft['method'] }))}>
                  {inputMethods.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select></label>
                <label className="council-field"><span>Date</span><input type="date" required value={stakeholderDraft.input_date}
                  onChange={event => setStakeholderDraft(current => ({ ...current, input_date: event.target.value }))} /></label>
                <label className="council-field"><span>Evidence state</span><select value={stakeholderDraft.evidence_state} onChange={event => setStakeholderDraft(current => ({ ...current, evidence_state: event.target.value as EvidenceState }))}>
                  {evidenceStates.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select></label>
                <label className="council-field"><span>Submitting organization (optional)</span><select value={stakeholderDraft.organization_id} onChange={event => setStakeholderDraft(current => ({ ...current, organization_id: event.target.value }))}>
                  <option value="">No organization linked</option>
                  {state.organizations.map(item => <option key={item.id} value={item.organization_id}>{item.name} · {item.organization_id}</option>)}
                </select></label>
                <label className="council-field"><span>Evidence source label</span><input required maxLength={300} value={stakeholderDraft.source_label}
                  onChange={event => setStakeholderDraft(current => ({ ...current, source_label: event.target.value }))} placeholder="Survey, meeting, submission, etc." /></label>
                <label className="council-field"><span>Source link (optional)</span><input type="url" maxLength={1000} value={stakeholderDraft.source_url}
                  onChange={event => setStakeholderDraft(current => ({ ...current, source_url: event.target.value }))} placeholder="https://…" /></label>
                <label className="council-field"><span>Geography</span><input required maxLength={300} value={stakeholderDraft.geography}
                  onChange={event => setStakeholderDraft(current => ({ ...current, geography: event.target.value }))} placeholder="Area or catchment covered" /></label>
                <label className="council-field"><span>Who was reached</span><textarea required rows={2} maxLength={2000} value={stakeholderDraft.reach_summary}
                  onChange={event => setStakeholderDraft(current => ({ ...current, reach_summary: event.target.value }))} placeholder="Groups and approximate reach, if known" /></label>
                <label className="council-field"><span>Views or issues raised</span><textarea required rows={3} maxLength={4000} value={stakeholderDraft.views_summary}
                  onChange={event => setStakeholderDraft(current => ({ ...current, views_summary: event.target.value }))} /></label>
                <label className="council-field"><span>Consent or publication limits</span><textarea rows={2} maxLength={2000} value={stakeholderDraft.consent_limits}
                  onChange={event => setStakeholderDraft(current => ({ ...current, consent_limits: event.target.value }))} /></label>
                <label className="council-field"><span>Groups not reached</span><textarea rows={2} maxLength={2000} value={stakeholderDraft.groups_not_reached}
                  onChange={event => setStakeholderDraft(current => ({ ...current, groups_not_reached: event.target.value }))} /></label>
                <label className="council-field"><span>Conflicting views</span><textarea rows={2} maxLength={2000} value={stakeholderDraft.conflicting_views}
                  onChange={event => setStakeholderDraft(current => ({ ...current, conflicting_views: event.target.value }))} /></label>
              </div>
              <div className="council-form-footer"><small>Records are append-only; adding input requires impact scope review.</small>
                <button className="council-primary" type="submit" disabled={busy !== null || !proposal}>{busy === 'stakeholder' ? 'Saving…' : 'Save input record'} <ArrowRight size={13} /></button>
              </div>
            </form>
          </details>
          <div className="council-record-list">
            {state.stakeholder_inputs.length === 0 && <p className="council-muted">No actual stakeholder input is recorded for this proposal revision.</p>}
            {state.stakeholder_inputs.map(record => <article className="council-record-card" key={record.id}>
              <div className="council-record-heading"><strong>{stakeholderGroups.find(item => item.value === record.stakeholder_group)?.label ?? record.stakeholder_group}</strong><span>{record.input_date} · {record.method.replaceAll('_', ' ')}</span></div>
              <dl>
                <div><dt>Record ID / hash</dt><dd>{record.id} · {shortenedHash(record.sha256)}</dd></div>
                <div><dt>Evidence source</dt><dd>{record.source_url ? <a href={record.source_url} target="_blank" rel="noreferrer">{record.source_label}</a> : record.source_label} · {record.evidence_state.replaceAll('_', ' ')}</dd></div>
                <div><dt>Geography</dt><dd>{record.geography}</dd></div>
                <div><dt>Reached</dt><dd>{record.reach_summary}</dd></div>
                {record.organization_id && <div><dt>Submitting organization</dt><dd>{organizationName(state, record.organization_record_id ?? '', record.organization_id)}</dd></div>}
                {record.consent_limits && <div><dt>Consent limits</dt><dd>{record.consent_limits}</dd></div>}
                {record.groups_not_reached && <div><dt>Not reached</dt><dd>{record.groups_not_reached}</dd></div>}
                {record.conflicting_views && <div><dt>Conflicting views</dt><dd>{record.conflicting_views}</dd></div>}
              </dl>
              <p className="council-record-note">{record.views_summary}</p>
            </article>)}
          </div>
        </>}
      </section>

      <section className="council-section" aria-label="Organization links in simulation events">
        <div className="council-section-title"><span>04</span><h3>Organization-linked events</h3></div>
        {!latestRunId && <p className="council-muted">No intervention run exists for the current proposal revision.</p>}
        {traceStatus === 'loading' && <p className="council-muted" role="status">Loading the latest intervention trace…</p>}
        {traceStatus === 'error' && <p className="council-command-error" role="alert">{traceError}</p>}
        {latestTrace && <>
          <p className="council-muted">Run {latestTrace.run_id}. Each rollout event carries the exact organization record IDs and hashes linked to that stage. These links do not mean an organization made a real-world decision; the run still uses the illustrative deterministic schedule.</p>
          {latestTrace.rollout_events.map(event => <article className="council-record-card council-event-card" key={event.event_id}>
            <div className="council-record-heading"><strong>{event.stage.replaceAll('_', ' ')}</strong><span>{event.status}</span></div>
            <p>{(event.organization_refs ?? []).length === 0 ? 'No organization record bound to this event.' : event.organization_refs!.map(reference =>
              `${reference.role.replaceAll('_', ' ')}: ${organizationName(state, reference.record_id, reference.organization_id)} · ${shortenedHash(reference.sha256)}`,
            ).join(' · ')}</p>
            {event.reason && <small>{event.reason}</small>}
          </article>)}
          <p className="council-muted">The paired run froze {latestTrace.council_context?.stakeholder_input_refs.length ?? 0} stakeholder-input record(s) as review context; these records do not generate simulated opinions.</p>
        </>}
      </section>

    </>}
  </section>;
}
