import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, Building2, FileText, Landmark, RotateCcw, Users, X } from 'lucide-react';
import { loadCouncilState, loadCouncilTrace, saveOrganization, saveStakeholderInput, submitProposal } from './council.ts';
import type {
  CouncilState, EvidenceState, OrganizationCommand, OrganizationRecord, OrganizationRole,
  ProposalRevisionSummary, StakeholderInputCommand, StakeholderInputRecord,
} from './council.ts';
import type { CouncilFoodTrace } from './interactables.ts';

type LoadStatus = { kind: 'loading' } | { kind: 'ready' } | { kind: 'error'; message: string };
type PanelTab = 'proposal' | 'evidence' | 'simulation';
type BusyAction = 'refresh' | 'proposal' | 'organization' | 'stakeholder' | null;
type CouncilPanelProps = { id: string; open: boolean; onClose: () => void };
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

const panelTabs = [
  { id: 'proposal', label: 'Proposal', icon: FileText },
  { id: 'evidence', label: 'Evidence', icon: Users },
  { id: 'simulation', label: 'Simulation', icon: Building2 },
] satisfies { id: PanelTab; label: string; icon: typeof FileText }[];

const organizationRoles: { value: OrganizationRole; label: string }[] = [
  { value: 'city_department', label: 'City department / agency' },
  { value: 'city_funder', label: 'City sponsor / funder' },
  { value: 'property_owner', label: 'Property owner / landlord' },
  { value: 'site_host', label: 'Site host / facility manager' },
  { value: 'site_operator', label: 'Service operator' },
  { value: 'supplier_distributor', label: 'Supplier / distributor' },
  { value: 'delivery_carrier', label: 'Delivery carrier / logistics provider' },
  { value: 'contractor', label: 'Contractor / service provider' },
  { value: 'retailer', label: 'Retailer' }, { value: 'school', label: 'School / school nutrition provider' },
  { value: 'food_support_provider', label: 'Food-support provider' },
  { value: 'community_organization', label: 'Community organization' },
  { value: 'other', label: 'Other organization' },
];
const evidenceStates: { value: EvidenceState; label: string }[] = [
  { value: 'observed', label: 'Observed' }, { value: 'announced', label: 'Announced' },
  { value: 'estimated', label: 'Estimated' }, { value: 'illustrative_assumption', label: 'Illustrative assumption' },
  { value: 'unknown', label: 'Unknown' },
];
const stakeholderGroups: { value: StakeholderInputRecord['stakeholder_group']; label: string }[] = [
  { value: 'residents_users', label: 'Residents who use or may use the service' },
  { value: 'nearby_residents', label: 'Residents near the site' }, { value: 'access_barriers', label: 'People facing access barriers' },
  { value: 'workers_volunteers', label: 'Workers or volunteers' }, { value: 'nearby_businesses', label: 'Nearby businesses' },
  { value: 'food_support_partners', label: 'Food-support partners' }, { value: 'community_organization', label: 'Community organization' },
  { value: 'public_authorities', label: 'Public authority' }, { value: 'other', label: 'Other affected group' },
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
  { value: 'documented', label: 'Documented' }, { value: 'assumed', label: 'Assumed' }, { value: 'unknown', label: 'Unknown' },
];

function localISODate(value = new Date()): string {
  return [value.getFullYear(), String(value.getMonth() + 1).padStart(2, '0'), String(value.getDate()).padStart(2, '0')].join('-');
}
function emptyOrganizationDraft(): OrganizationDraft {
  return {
    organization_id: '', name: '', role: 'site_operator', evidence_state: 'illustrative_assumption',
    operating_status: 'unknown', authority_status: 'unknown', authority_basis: '', location_id: '',
    source_label: 'User-entered assumption', source_url: '', budget_cents: '', stock_grams: '',
    service_capacity: '', operating_hours: '', permitted_decisions: '', agreement: '', resource_notes: '', notes: '',
  };
}
function emptyStakeholderDraft(): StakeholderDraft {
  return {
    stakeholder_group: 'residents_users', organization_id: '', input_date: localISODate(), method: 'other',
    evidence_state: 'observed', source_label: 'User-provided note', source_url: '',
    geography: 'Not recorded', reach_summary: 'Not recorded', consent_limits: '',
    views_summary: '', groups_not_reached: '', conflicting_views: '',
  };
}
function optionalInteger(value: string, label: string): number | null {
  if (!value.trim()) return null;
  if (!/^\d+$/.test(value.trim())) throw new Error(label + ' must be a non-negative whole number.');
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed > 2_147_483_647) throw new Error(label + ' is outside the supported range.');
  return parsed;
}
function optionValue<T extends string>(options: readonly { value: T; label: string }[], value: string): T | null {
  return options.find(option => option.value === value)?.value ?? null;
}
function proposalChanges(markdown: string): string {
  const lines = markdown.split(/\r?\n/);
  const start = lines.findIndex(line => /^##\s+Changes\s*$/i.test(line));
  if (start >= 0) {
    const end = lines.findIndex((line, index) => index > start && /^##\s+/.test(line));
    return lines.slice(start + 1, end < 0 ? lines.length : end).join('\n').trim();
  }
  return lines.filter((line, index) => index > 0 || !/^#\s+/.test(line)).join('\n').trim();
}
function proposalMarkdown(previous: string | null, change: string): string {
  const content = change.trim();
  if (!previous) {
    const title = content.split(/[\n.!?]+/)[0]?.trim().slice(0, 72) || 'New proposal';
    return '# ' + title + '\n\n## Changes\n' + content + '\n';
  }
  const lines = previous.split(/\r?\n/);
  const start = lines.findIndex(line => /^##\s+Changes\s*$/i.test(line));
  if (start < 0) return previous.trimEnd() + '\n\n## Changes\n' + content + '\n';
  const end = lines.findIndex((line, index) => index > start && /^##\s+/.test(line));
  return [...lines.slice(0, start + 1), content, ...lines.slice(end < 0 ? lines.length : end)].join('\n').trimEnd() + '\n';
}
function organizationId(name: string, records: OrganizationRecord[], editingId: string | null): string {
  if (editingId) return editingId;
  const plain = name.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
  const base = plain.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 54) || 'organization';
  const safeBase = base.length >= 2 ? base : base + '-org';
  const used = new Set(records.map(record => record.organization_id));
  let candidate = safeBase;
  let suffix = 2;
  while (used.has(candidate)) candidate = safeBase.slice(0, 58) + '-' + suffix++;
  return candidate;
}
function organizationHistory(state: CouncilState, record: OrganizationRecord): OrganizationRecord[] {
  return state.organization_records
    .filter(item => item.proposal_id === record.proposal_id && item.organization_id === record.organization_id)
    .sort((left, right) => left.organization_revision - right.organization_revision);
}
function organizationName(state: CouncilState, recordId: string, fallback: string): string {
  return state.organization_records.find(record => record.id === recordId)?.name ?? fallback;
}
function roleLabel(role: string): string {
  return organizationRoles.find(item => item.value === role)?.label ?? role.replaceAll('_', ' ');
}
function groupLabel(group: StakeholderInputRecord['stakeholder_group']): string {
  return stakeholderGroups.find(item => item.value === group)?.label ?? group.replaceAll('_', ' ');
}
function shortHash(value: string): string { return value.slice(0, 12); }

export function CouncilPanel({ id, open, onClose }: CouncilPanelProps) {
  const [loadStatus, setLoadStatus] = useState<LoadStatus>({ kind: 'loading' });
  const [state, setState] = useState<CouncilState | null>(null);
  const [busy, setBusy] = useState<BusyAction>(null);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [activeTab, setActiveTab] = useState<PanelTab>('proposal');
  const [organizationDraft, setOrganizationDraft] = useState<OrganizationDraft>(emptyOrganizationDraft);
  const [editingOrganizationId, setEditingOrganizationId] = useState<string | null>(null);
  const [organizationFormOpen, setOrganizationFormOpen] = useState(false);
  const [stakeholderDraft, setStakeholderDraft] = useState<StakeholderDraft>(emptyStakeholderDraft);
  const [stakeholderFormOpen, setStakeholderFormOpen] = useState(false);
  const [latestTrace, setLatestTrace] = useState<CouncilFoodTrace | null>(null);
  const [traceStatus, setTraceStatus] = useState<TraceStatus>('idle');
  const [traceError, setTraceError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void loadCouncilState().then(next => {
      if (!active) return;
      setState(next);
      setDraft(next.proposal ? proposalChanges(next.proposal.markdown) : '');
      setLoadStatus({ kind: 'ready' });
    }).catch(error => {
      if (active) setLoadStatus({
        kind: 'error',
        message: error instanceof Error ? error.message : 'The local Council service is unavailable.',
      });
    });
    return () => { active = false; };
  }, []);

  const revisions = useMemo<ProposalRevisionSummary[]>(() => {
    if (!state) return [];
    const entries = [...state.proposal_history];
    if (state.proposal && !entries.some(item => item.id === state.proposal?.id)) {
      entries.push({ id: state.proposal.id, revision: state.proposal.revision, sha256: state.proposal.sha256, markdown: state.proposal.markdown });
    }
    return entries.sort((left, right) => right.revision - left.revision);
  }, [state]);
  const proposal = state?.proposal ?? null;
  const proposalHasChanges = proposal
    ? draft.trim() !== proposalChanges(proposal.markdown)
    : Boolean(draft.trim());
  const latestRunId = state?.runs.filter(run => run.proposal_id === proposal?.id).at(-1)?.id ?? null;
  const latestRun = state?.runs.find(run => run.id === latestRunId) ?? null;

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
        setTraceError(error instanceof Error ? error.message : 'The latest simulation could not be loaded.');
      }
    });
    return () => { active = false; };
  }, [latestRunId]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  async function refresh() {
    setBusy('refresh'); setCommandError(null);
    try {
      const next = await loadCouncilState();
      setState(next); setLoadStatus({ kind: 'ready' });
    } catch (error) {
      setLoadStatus({ kind: 'error', message: error instanceof Error ? error.message : 'The local Council service is unavailable.' });
    } finally { setBusy(null); }
  }
  async function saveProposal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state || !draft.trim()) return;
    setBusy('proposal'); setCommandError(null);
    try {
      const next = await submitProposal({ markdown: proposalMarkdown(state.proposal?.markdown ?? null, draft) }, state.revision);
      setState(next); setDraft(next.proposal ? proposalChanges(next.proposal.markdown) : draft.trim());
      setLoadStatus({ kind: 'ready' });
    } catch (error) {
      setCommandError(error instanceof Error ? error.message : 'The proposal could not be saved.');
    } finally { setBusy(null); }
  }
  function reviseOrganization(record: OrganizationRecord) {
    setEditingOrganizationId(record.organization_id); setOrganizationFormOpen(true);
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
    setOrganizationDraft(emptyOrganizationDraft()); setEditingOrganizationId(null); setOrganizationFormOpen(false);
  }
  async function saveOrganizationRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state?.proposal) return;
    setBusy('organization'); setCommandError(null);
    try {
      const command: OrganizationCommand = {
        proposal_id: state.proposal.id, proposal_sha256: state.proposal.sha256,
        organization_id: organizationId(organizationDraft.name.trim(), state.organization_records, editingOrganizationId),
        name: organizationDraft.name.trim(), role: organizationDraft.role,
        evidence_state: organizationDraft.evidence_state, operating_status: organizationDraft.operating_status,
        authority_status: organizationDraft.authority_status, authority_basis: organizationDraft.authority_basis.trim(),
        location_id: organizationDraft.location_id || null,
        source_label: organizationDraft.source_label.trim() || 'Not provided', source_url: organizationDraft.source_url.trim(),
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
      setCommandError(error instanceof Error ? error.message : 'The organization could not be saved.');
    } finally { setBusy(null); }
  }
  async function saveStakeholderRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state?.proposal) return;
    setBusy('stakeholder'); setCommandError(null);
    try {
      const command: StakeholderInputCommand = {
        proposal_id: state.proposal.id, proposal_sha256: state.proposal.sha256,
        stakeholder_group: stakeholderDraft.stakeholder_group, organization_id: stakeholderDraft.organization_id || null,
        input_date: stakeholderDraft.input_date, method: stakeholderDraft.method, evidence_state: stakeholderDraft.evidence_state,
        source_label: stakeholderDraft.source_label.trim() || 'User-provided note', source_url: stakeholderDraft.source_url.trim(),
        geography: stakeholderDraft.geography.trim() || 'Not recorded', reach_summary: stakeholderDraft.reach_summary.trim() || 'Not recorded',
        consent_limits: stakeholderDraft.consent_limits.trim(), views_summary: stakeholderDraft.views_summary.trim(),
        groups_not_reached: stakeholderDraft.groups_not_reached.trim(), conflicting_views: stakeholderDraft.conflicting_views.trim(),
      };
      const next = await saveStakeholderInput(command, state.revision);
      setState(next); setLoadStatus({ kind: 'ready' }); setStakeholderDraft(emptyStakeholderDraft()); setStakeholderFormOpen(false);
    } catch (error) {
      setCommandError(error instanceof Error ? error.message : 'The input note could not be saved.');
    } finally { setBusy(null); }
  }

  return <div className="council-overlay" hidden={!open} onMouseDown={event => {
    if (event.target === event.currentTarget) onClose();
  }}>
    <section id={id} className="council-workspace" role="dialog" aria-modal="true" aria-labelledby="council-title">
      <aside className="council-sidebar">
        <div className="council-brand">
          <span className="council-brand-mark"><Landmark size={16} /></span>
          <h2 id="council-title">City Council</h2>
        </div>
        <nav className="council-tabs" aria-label="Council sections">
          {panelTabs.map(tab => {
            const Icon = tab.icon;
            return <button key={tab.id} type="button" className={activeTab === tab.id ? 'active' : ''}
              aria-pressed={activeTab === tab.id} onClick={() => setActiveTab(tab.id)}>
              <Icon size={17} /><span>{tab.label}</span>
              {tab.id === 'evidence' && <small>{(state?.organizations.length ?? 0) + (state?.stakeholder_inputs.length ?? 0)}</small>}
            </button>;
          })}
        </nav>
      </aside>
      <main className="council-main">
        <header className="council-main-header">
          <div>
            <h3>{activeTab === 'proposal' ? 'Proposal' : activeTab === 'evidence' ? 'Evidence' : 'Simulation'}</h3>
          </div>
          <div className="council-header-actions">
            {loadStatus.kind === 'ready' && <button type="button" className="council-icon-button" onClick={() => void refresh()}
              disabled={busy !== null} aria-label="Refresh Council data" title="Refresh"><RotateCcw size={17} /></button>}
            <button type="button" className="council-icon-button" onClick={onClose} aria-label="Close Council" title="Close"><X size={18} /></button>
          </div>
        </header>
        <div className="council-content">
          {loadStatus.kind === 'loading' && <div className="council-empty" role="status">Connecting to Council…</div>}
          {loadStatus.kind === 'error' && <div className="council-error" role="alert">
            <strong>Council is unavailable</strong><p>{loadStatus.message}</p>
            <button type="button" onClick={() => void refresh()} disabled={busy !== null}>Try again</button>
          </div>}
          {loadStatus.kind === 'ready' && state && <>
            {commandError && <p className="council-error council-command-error" role="alert">{commandError}</p>}
            {activeTab === 'proposal' && <section className="council-page">
              {!proposal && <button type="button" className="council-example" onClick={() => setDraft('Open a municipal food site to test local produce access.')}>
                <span>Start with an example</span><ArrowRight size={15} />
              </button>}
              <form className="council-proposal-form" onSubmit={event => void saveProposal(event)}>
                <label className="council-label" htmlFor="council-change">What would you like to change?</label>
                <textarea id="council-change" rows={5} maxLength={8000} value={draft} onChange={event => setDraft(event.currentTarget.value)}
                  placeholder="For example, open a produce pickup site near the waterfront." />
                <div className="council-form-actions">
                  <button type="submit" className="council-primary" disabled={busy !== null || !draft.trim() || !proposalHasChanges}>
                    {busy === 'proposal' ? 'Saving…' : proposal ? proposalHasChanges ? 'Save changes' : 'Saved' : 'Create proposal'}
                    {proposalHasChanges && <ArrowRight size={16} />}
                  </button>
                </div>
              </form>
              {proposal && <details className="council-details">
                <summary>Sources and saved versions</summary>
                <div className="council-source-summary">
                  <strong>Evidence snapshot</strong><span>{proposal.source_context.snapshot_id}</span>
                  <span>Retrieved {proposal.source_context.retrieved_at ?? 'date not recorded'}</span>
                  {proposal.source_context.limits.length > 0 && <ul>{proposal.source_context.limits.map((limit, index) => <li key={index + '-' + limit}>{limit}</li>)}</ul>}
                  {proposal.citations.length > 0 && <div className="council-citations">
                    {proposal.citations.map((citation, index) => <a key={index + '-' + citation.url} href={citation.url}
                      target="_blank" rel="noreferrer">{citation.label || citation.url}</a>)}
                  </div>}
                </div>
                <div className="council-revisions">
                  {revisions.map(item => <details key={item.id} className="council-revision">
                    <summary>{item.id === proposal.id ? 'Current version' : 'Saved version'}</summary>
                    <div className="council-revision-meta">SHA-256 {shortHash(item.sha256)}</div>
                    <pre>{item.markdown}</pre>
                    {item.id !== proposal.id && <button type="button" className="council-secondary"
                      onClick={() => setDraft(proposalChanges(item.markdown))}>Restore this version</button>}
                  </details>)}
                </div>
              </details>}
            </section>}

            {activeTab === 'evidence' && <section className="council-page">
              {!proposal && <div className="council-empty">Create a proposal before adding evidence.</div>}
              {proposal && <>
                <section className="council-record-section" aria-labelledby="organizations-heading">
                  <header className="council-record-section-header">
                    <div><Building2 size={18} /><h5 id="organizations-heading">Organizations</h5><span>{state.organizations.length}</span></div>
                    <button type="button" className="council-secondary" onClick={() => {
                      const next = !organizationFormOpen;
                      if (!next) resetOrganizationForm();
                      else setOrganizationFormOpen(true);
                    }}>{organizationFormOpen ? 'Cancel' : 'Add organization'}</button>
                  </header>
                  {organizationFormOpen && <form className="council-inline-form" onSubmit={event => void saveOrganizationRecord(event)}>
                    <label className="council-label" htmlFor="organization-name">Organization name</label>
                    <input id="organization-name" required maxLength={200} value={organizationDraft.name} placeholder="Use a role name if its identity is unknown"
                      onChange={event => {
                        const name = event.currentTarget.value;
                        setOrganizationDraft(current => ({ ...current, name }));
                      }} />
                    <div className="council-form-grid">
                      <label className="council-label">Role
                        <select value={organizationDraft.role} onChange={event => {
                          const value = optionValue(organizationRoles, event.currentTarget.value);
                          if (value) setOrganizationDraft(current => ({ ...current, role: value }));
                        }}>{organizationRoles.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                      </label>
                      <label className="council-label">Location, if known
                        <select value={organizationDraft.location_id} onChange={event => {
                          const locationId = event.currentTarget.value;
                          setOrganizationDraft(current => ({ ...current, location_id: locationId }));
                        }}>
                          <option value="">No location selected</option>
                          {state.locations.map(location => <option key={location.id} value={location.id}>{location.label}</option>)}
                        </select>
                      </label>
                    </div>
                    <details className="council-details council-optional-details">
                      <summary>Add source or operating details</summary>
                      <div className="council-form-grid">
                        <label className="council-label">Evidence
                          <select value={organizationDraft.evidence_state} onChange={event => {
                            const value = optionValue(evidenceStates, event.currentTarget.value);
                            if (value) setOrganizationDraft(current => ({ ...current, evidence_state: value }));
                          }}>{evidenceStates.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                        </label>
                        <label className="council-label">Operating status
                          <select value={organizationDraft.operating_status} onChange={event => {
                            const value = optionValue(operatingStatuses, event.currentTarget.value);
                            if (value) setOrganizationDraft(current => ({ ...current, operating_status: value }));
                          }}>{operatingStatuses.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                        </label>
                        <label className="council-label">Authority
                          <select value={organizationDraft.authority_status} onChange={event => {
                            const value = optionValue(authorityStatuses, event.currentTarget.value);
                            if (value) setOrganizationDraft(current => ({ ...current, authority_status: value }));
                          }}>{authorityStatuses.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                        </label>
                        <label className="council-label">Evidence source
                          <input maxLength={300} value={organizationDraft.source_label} onChange={event => {
                            const sourceLabel = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, source_label: sourceLabel }));
                          }} />
                        </label>
                        <label className="council-label">Source link
                          <input type="url" maxLength={1000} value={organizationDraft.source_url} placeholder="https://" onChange={event => {
                            const sourceUrl = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, source_url: sourceUrl }));
                          }} />
                        </label>
                        <label className="council-label">Operating hours
                          <input maxLength={300} value={organizationDraft.operating_hours} onChange={event => {
                            const operatingHours = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, operating_hours: operatingHours }));
                          }} />
                        </label>
                        <label className="council-label">Authority basis
                          <textarea rows={2} maxLength={2000} value={organizationDraft.authority_basis} onChange={event => {
                            const authorityBasis = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, authority_basis: authorityBasis }));
                          }} />
                        </label>
                        <label className="council-label">Agreement or dependency
                          <textarea rows={2} maxLength={2000} value={organizationDraft.agreement} onChange={event => {
                            const agreement = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, agreement }));
                          }} />
                        </label>
                        <label className="council-label">Budget cap, cents
                          <input type="number" min="0" step="1" value={organizationDraft.budget_cents} onChange={event => {
                            const budgetCents = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, budget_cents: budgetCents }));
                          }} />
                        </label>
                        <label className="council-label">Stock cap, grams
                          <input type="number" min="0" step="1" value={organizationDraft.stock_grams} onChange={event => {
                            const stockGrams = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, stock_grams: stockGrams }));
                          }} />
                        </label>
                        <label className="council-label">Service capacity
                          <input type="number" min="0" step="1" value={organizationDraft.service_capacity} onChange={event => {
                            const serviceCapacity = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, service_capacity: serviceCapacity }));
                          }} />
                        </label>
                        <label className="council-label">Permitted decisions
                          <textarea rows={2} maxLength={2000} value={organizationDraft.permitted_decisions} onChange={event => {
                            const permittedDecisions = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, permitted_decisions: permittedDecisions }));
                          }} />
                        </label>
                        <label className="council-label">Resource limits
                          <textarea rows={2} maxLength={2000} value={organizationDraft.resource_notes} onChange={event => {
                            const resourceNotes = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, resource_notes: resourceNotes }));
                          }} />
                        </label>
                        <label className="council-label">Notes
                          <textarea rows={2} maxLength={2000} value={organizationDraft.notes} onChange={event => {
                            const notes = event.currentTarget.value;
                            setOrganizationDraft(current => ({ ...current, notes }));
                          }} />
                        </label>
                      </div>
                    </details>
                    <div className="council-form-actions">
                      <span>Missing details are saved as unknown.</span>
                      <button type="submit" className="council-primary" disabled={busy !== null || !organizationDraft.name.trim()}>
                        {busy === 'organization' ? 'Saving…' : editingOrganizationId ? 'Save changes' : 'Save organization'}
                      </button>
                    </div>
                  </form>}
                  <div className="council-record-list">
                    {state.organizations.length === 0 && !organizationFormOpen && <p className="council-empty-inline">No organizations added.</p>}
                    {state.organizations.map(record => <article className="council-record-card" key={record.id}>
                      <div className="council-record-card-heading">
                        <div><strong>{record.name}</strong><span>{roleLabel(record.role)}</span></div>
                        <button type="button" className="council-text-button" onClick={() => reviseOrganization(record)}>Edit</button>
                      </div>
                      <details className="council-record-details">
                        <summary>Record details</summary>
                        <dl>
                          <div><dt>Organization ID</dt><dd>{record.organization_id}</dd></div>
                          <div><dt>Evidence</dt><dd>{record.evidence_state.replaceAll('_', ' ')}</dd></div>
                          <div><dt>Operating status</dt><dd>{record.operating_status.replaceAll('_', ' ')}</dd></div>
                          <div><dt>Authority</dt><dd>{record.authority_status}{record.authority_basis ? ' · ' + record.authority_basis : ''}</dd></div>
                          <div><dt>Source</dt><dd>{record.source_url ? <a href={record.source_url} target="_blank" rel="noreferrer">{record.source_label}</a> : record.source_label}</dd></div>
                          <div><dt>Resources</dt><dd>{[
                            record.budget_cents === null ? null : record.budget_cents.toLocaleString() + ' cents',
                            record.stock_grams === null ? null : record.stock_grams.toLocaleString() + ' g',
                            record.service_capacity === null ? null : record.service_capacity.toLocaleString() + ' visits',
                            record.operating_hours || null,
                          ].filter(Boolean).join(' · ') || 'Not recorded'}</dd></div>
                          <div><dt>Record hash</dt><dd>{shortHash(record.sha256)}</dd></div>
                        </dl>
                        {record.agreement && <p>{record.agreement}</p>}
                        {record.resource_notes && <p>{record.resource_notes}</p>}
                        {record.permitted_decisions.length > 0 && <p>Permitted decisions: {record.permitted_decisions.join(', ')}</p>}
                        {record.notes && <p>{record.notes}</p>}
                        {organizationHistory(state, record).length > 1 && <details className="council-record-details">
                          <summary>Earlier versions</summary>
                          <ol>{organizationHistory(state, record).filter(item => item.id !== record.id).map(previous => <li key={previous.id}>
                            Saved version · {shortHash(previous.sha256)}
                          </li>)}</ol>
                        </details>}
                      </details>
                    </article>)}
                  </div>
                </section>

                <section className="council-record-section" aria-labelledby="stakeholders-heading">
                  <header className="council-record-section-header">
                    <div><Users size={18} /><h5 id="stakeholders-heading">Community input</h5><span>{state.stakeholder_inputs.length}</span></div>
                    <button type="button" className="council-secondary" onClick={() => setStakeholderFormOpen(value => !value)}>
                      {stakeholderFormOpen ? 'Cancel' : 'Add input'}
                    </button>
                  </header>
                  {stakeholderFormOpen && <form className="council-inline-form" onSubmit={event => void saveStakeholderRecord(event)}>
                    <label className="council-label">Who gave the input?
                      <select value={stakeholderDraft.stakeholder_group} onChange={event => {
                        const value = optionValue(stakeholderGroups, event.currentTarget.value);
                        if (value) setStakeholderDraft(current => ({ ...current, stakeholder_group: value }));
                      }}>{stakeholderGroups.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                    </label>
                    <label className="council-label" htmlFor="stakeholder-summary">What did they say?</label>
                    <textarea id="stakeholder-summary" required rows={4} maxLength={4000} value={stakeholderDraft.views_summary}
                      onChange={event => {
                        const viewsSummary = event.currentTarget.value;
                        setStakeholderDraft(current => ({ ...current, views_summary: viewsSummary }));
                      }} placeholder="Summarize the feedback." />
                    <details className="council-details council-optional-details">
                      <summary>Add source and reach details</summary>
                      <div className="council-form-grid">
                        <label className="council-label">Date
                          <input type="date" required value={stakeholderDraft.input_date} onChange={event => {
                            const inputDate = event.currentTarget.value;
                            setStakeholderDraft(current => ({ ...current, input_date: inputDate }));
                          }} />
                        </label>
                        <label className="council-label">How was input collected?
                          <select value={stakeholderDraft.method} onChange={event => {
                            const value = optionValue(inputMethods, event.currentTarget.value);
                            if (value) setStakeholderDraft(current => ({ ...current, method: value }));
                          }}>{inputMethods.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                        </label>
                        <label className="council-label">Evidence state
                          <select value={stakeholderDraft.evidence_state} onChange={event => {
                            const value = optionValue(evidenceStates, event.currentTarget.value);
                            if (value) setStakeholderDraft(current => ({ ...current, evidence_state: value }));
                          }}>{evidenceStates.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                        </label>
                        <label className="council-label">Submitting organization
                          <select value={stakeholderDraft.organization_id} onChange={event => {
                            const organizationId = event.currentTarget.value;
                            setStakeholderDraft(current => ({ ...current, organization_id: organizationId }));
                          }}>
                            <option value="">No organization linked</option>
                            {state.organizations.map(item => <option key={item.id} value={item.organization_id}>{item.name}</option>)}
                          </select>
                        </label>
                        <label className="council-label">Evidence source
                          <input maxLength={300} value={stakeholderDraft.source_label} onChange={event => {
                            const sourceLabel = event.currentTarget.value;
                            setStakeholderDraft(current => ({ ...current, source_label: sourceLabel }));
                          }} />
                        </label>
                        <label className="council-label">Source link
                          <input type="url" maxLength={1000} value={stakeholderDraft.source_url} placeholder="https://" onChange={event => {
                            const sourceUrl = event.currentTarget.value;
                            setStakeholderDraft(current => ({ ...current, source_url: sourceUrl }));
                          }} />
                        </label>
                        <label className="council-label">Area covered
                          <input maxLength={300} value={stakeholderDraft.geography} onChange={event => {
                            const geography = event.currentTarget.value;
                            setStakeholderDraft(current => ({ ...current, geography }));
                          }} />
                        </label>
                        <label className="council-label">Who was reached?
                          <input maxLength={2000} value={stakeholderDraft.reach_summary} onChange={event => {
                            const reachSummary = event.currentTarget.value;
                            setStakeholderDraft(current => ({ ...current, reach_summary: reachSummary }));
                          }} />
                        </label>
                        <label className="council-label">Consent or sharing limits
                          <input maxLength={2000} value={stakeholderDraft.consent_limits} onChange={event => {
                            const consentLimits = event.currentTarget.value;
                            setStakeholderDraft(current => ({ ...current, consent_limits: consentLimits }));
                          }} />
                        </label>
                        <label className="council-label">Groups not reached
                          <input maxLength={2000} value={stakeholderDraft.groups_not_reached} onChange={event => {
                            const groupsNotReached = event.currentTarget.value;
                            setStakeholderDraft(current => ({ ...current, groups_not_reached: groupsNotReached }));
                          }} />
                        </label>
                        <label className="council-label">Different views
                          <input maxLength={2000} value={stakeholderDraft.conflicting_views} onChange={event => {
                            const conflictingViews = event.currentTarget.value;
                            setStakeholderDraft(current => ({ ...current, conflicting_views: conflictingViews }));
                          }} />
                        </label>
                      </div>
                    </details>
                    <div className="council-form-actions">
                      <span>Names and personal details are not needed.</span>
                      <button type="submit" className="council-primary" disabled={busy !== null || !stakeholderDraft.views_summary.trim()}>
                        {busy === 'stakeholder' ? 'Saving…' : 'Save input'}
                      </button>
                    </div>
                  </form>}
                  <div className="council-record-list">
                    {state.stakeholder_inputs.length === 0 && !stakeholderFormOpen && <p className="council-empty-inline">No community input recorded.</p>}
                    {state.stakeholder_inputs.map(record => <article className="council-record-card" key={record.id}>
                      <div className="council-record-card-heading">
                        <div><strong>{groupLabel(record.stakeholder_group)}</strong><span>{record.input_date}</span></div>
                        <span className="council-record-tag">{record.method.replaceAll('_', ' ')}</span>
                      </div>
                      <p>{record.views_summary}</p>
                      <details className="council-record-details">
                        <summary>Record details</summary>
                        <dl>
                          <div><dt>Evidence</dt><dd>{record.evidence_state.replaceAll('_', ' ')}</dd></div>
                          <div><dt>Source</dt><dd>{record.source_url ? <a href={record.source_url} target="_blank" rel="noreferrer">{record.source_label}</a> : record.source_label}</dd></div>
                          <div><dt>Area</dt><dd>{record.geography}</dd></div>
                          <div><dt>Who was reached</dt><dd>{record.reach_summary}</dd></div>
                          {record.consent_limits && <div><dt>Sharing limits</dt><dd>{record.consent_limits}</dd></div>}
                          {record.groups_not_reached && <div><dt>Not reached</dt><dd>{record.groups_not_reached}</dd></div>}
                          {record.conflicting_views && <div><dt>Different views</dt><dd>{record.conflicting_views}</dd></div>}
                          <div><dt>Record hash</dt><dd>{shortHash(record.sha256)}</dd></div>
                        </dl>
                      </details>
                    </article>)}
                  </div>
                </section>
              </>}
            </section>}

            {activeTab === 'simulation' && <section className="council-page">
              {!latestRunId && <div className="council-empty">No simulation is saved for this proposal yet.</div>}
              {latestRunId && <>
                {traceStatus === 'loading' && <div className="council-empty" role="status">Loading the latest run…</div>}
                {traceStatus === 'error' && <div className="council-error" role="alert">{traceError}</div>}
                {latestRun && <div className="council-run-summary">
                  <span className={latestRun.status === 'complete' ? 'council-status complete' : 'council-status blocked'}>
                    {latestRun.status === 'complete' ? 'Complete' : 'Blocked'}
                  </span>
                  <span>{latestRun.population.toLocaleString()} residents</span><span>Seed {latestRun.seed}</span>
                  <details className="council-record-details">
                    <summary>Run ID and inputs</summary>
                    <p>{latestRun.id}</p><p>Input hash {shortHash(latestRun.inputs_sha256)}</p>
                    <p>Baseline hash {shortHash(latestRun.baseline_trace_sha256)}</p>
                    <p>Proposal hash {shortHash(latestRun.intervention_trace_sha256)}</p>
                  </details>
                </div>}
                {latestRun?.status === 'blocked' && latestRun.blockers.length > 0 && <div className="council-blockers">
                  <strong>Why it stopped</strong><ul>{latestRun.blockers.map(blocker => <li key={blocker}>{blocker}</li>)}</ul>
                </div>}
                {latestTrace && <ol className="council-timeline">
                  {latestTrace.rollout_events.map(event => {
                    const linkedRecords = event.organization_refs ?? [];
                    return <li key={event.event_id} className={event.status === 'blocked' ? 'blocked' : ''}>
                      <div className="council-timeline-heading"><strong>{event.stage.replaceAll('_', ' ')}</strong><span>{event.status}</span></div>
                      {event.reason && <p>{event.reason}</p>}
                      {linkedRecords.length > 0 && <details className="council-record-details">
                        <summary>Linked records ({linkedRecords.length})</summary>
                        <ul>{linkedRecords.map(reference => <li key={reference.record_id}>
                          {roleLabel(reference.role)}: {organizationName(state, reference.record_id, reference.organization_id)} · {shortHash(reference.sha256)}
                        </li>)}</ul>
                      </details>}
                    </li>;
                  })}
                </ol>}
                {latestTrace && <details className="council-details">
                  <summary>Simulation notes</summary>
                  <p>{latestTrace.council_context?.stakeholder_input_refs.length ?? 0} community input record(s) were included as review context. They do not generate simulated opinions.</p>
                </details>}
                {state.plan && <details className="council-details">
                  <summary>Inputs frozen into the plan</summary>
                  <p>{state.plan.world.population.toLocaleString()} residents · seed {state.plan.world.seed}</p>
                  <p>{state.plan.organization_refs.length} organizations and {state.plan.stakeholder_input_refs.length} input records linked.</p>
                  {state.plan.organization_record_gaps.length > 0 && <p>Missing organization records: {state.plan.organization_record_gaps.map(role => role.replaceAll('_', ' ')).join(', ')}.</p>}
                </details>}
              </>}
            </section>}
          </>}
        </div>
      </main>
    </section>
  </div>;
}

