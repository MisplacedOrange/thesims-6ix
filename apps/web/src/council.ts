import type { CouncilFoodTrace, RolloutEvent } from './interactables.ts';
import { isRunRef, sameRunRef } from './runRef.ts';
import type { CouncilRunRef } from './runRef.ts';
import { isPlannerState } from './openaiPlanner.ts';
import type { PlannerState } from './openaiPlanner.ts';

export type Span = { start_line: number; end_line: number; text: string };
export type Citation = { label: string; url: string; status: 'unverified_reference' };
export type SourceContext = {
  snapshot_id: string; sha256: string; retrieved_at: string | null; limits: string[];
};
export type ProposalSections = {
  constraints: Span[]; measures: Span[]; assumptions: Span[]; goals: Span[]; changes: Span[]; unknowns: Span[];
};
export type Proposal = {
  id: string; revision: number; sha256: string; markdown: string; sections: ProposalSections;
  unclassified: Span[]; citations: Citation[]; source_context: SourceContext;
};
export type ProposalRevisionSummary = { id: string; revision: number; sha256: string; markdown: string };
export type ScopeRevision = {
  id: string; proposal_id: string; proposal_sha256: string; sha256: string;
  evaluated_scope: string; excluded_scope: string; reviewer_note: string;
};
export type LocationChoice = {
  id: string; label: string; point: [number, number]; source_record_id: string | null;
  operation_status: 'unknown'; authority: 'unknown';
};
export type SiteParameters = {
  location_id: string; grant_cents: number; stock_grams: number; service_capacity: number;
  operator_assumption: 'hypothetical_municipal_operator';
  readiness_second: number; funding_second: number; delivery_second: number;
  commissioning_second: number; open_second: number; close_second: number;
};
export type CapacityParameters = { base_site: SiteParameters; effective_second: number; target_capacity: number };
export type CandidateAction = 'fund_program' | 'set_municipal_price_policy' | 'arrange_procurement'
  | 'allocate_operating_resources' | 'modify_road_or_transit' | 'develop_housing' | 'modify_utilities';
export type ActionDescriptor = {
  action: Exclude<Plan['action'], 'unsupported'>; version: number; executable: boolean;
  label: string; inputs: string; effects: string; limits: string;
};
const candidateActions: CandidateAction[] = ['fund_program', 'set_municipal_price_policy', 'arrange_procurement',
  'allocate_operating_resources', 'modify_road_or_transit', 'develop_housing', 'modify_utilities'];
export type Advice = {
  role: 'finance' | 'site_readiness' | 'supply' | 'access';
  status: 'ready' | 'caution' | 'blocked'; note: string; authority: 'advisory';
};
export type OrganizationRole =
  | 'city_department' | 'city_funder' | 'property_owner' | 'site_host' | 'site_operator'
  | 'supplier_distributor' | 'delivery_carrier' | 'contractor' | 'retailer' | 'school'
  | 'food_support_provider' | 'community_organization' | 'other';
export type EvidenceState = 'observed' | 'announced' | 'estimated' | 'illustrative_assumption' | 'unknown';
export type OrganizationReference = {
  role: OrganizationRole; organization_id: string; record_id: string; sha256: string;
};
export type StakeholderInputReference = { record_id: string; sha256: string };
export type OrganizationRecord = {
  id: string; sha256: string; proposal_id: string; proposal_sha256: string;
  organization_id: string; organization_revision: number; supersedes_record_id: string | null;
  name: string; role: OrganizationRole; evidence_state: EvidenceState;
  operating_status: 'operating' | 'not_operating' | 'seasonal' | 'unknown';
  authority_status: 'documented' | 'assumed' | 'unknown'; authority_basis: string;
  location_id: string | null; source_label: string; source_url: string;
  budget_cents: number | null; stock_grams: number | null; service_capacity: number | null;
  operating_hours: string; permitted_decisions: string[]; agreement: string;
  resource_notes: string; notes: string;
};
export type StakeholderInputRecord = {
  id: string; sha256: string; proposal_id: string; proposal_sha256: string;
  stakeholder_group: 'residents_users' | 'nearby_residents' | 'access_barriers' | 'workers_volunteers'
    | 'nearby_businesses' | 'food_support_partners' | 'community_organization' | 'public_authorities' | 'other';
  organization_id: string | null; organization_record_id: string | null; organization_record_sha256: string | null;
  input_date: string; method: 'consultation' | 'survey' | 'partner_submission' | 'meeting' | 'other';
  evidence_state: EvidenceState; source_label: string; source_url: string; geography: string;
  reach_summary: string; consent_limits: string; views_summary: string;
  groups_not_reached: string; conflicting_views: string;
};
export type WorldInputs = {
  population: number; seed: number; map_sha256: string; catalog_id: string; catalog_sha256: string;
  source_snapshot_id: string; source_sha256: string; simulator_version: string; sha256: string;
};
type PlanFields = {
  planner_draft_id?: string;
  id: string; proposal_id: string; proposal_sha256: string; sha256: string; scope_id: string; scope_sha256: string;
  execution_blockers: string[]; advice: Advice[]; world: WorldInputs;
  organization_refs: OrganizationReference[]; organization_snapshot_refs: OrganizationReference[];
  stakeholder_input_refs: StakeholderInputReference[]; organization_record_gaps: string[];
  organization_binding_ambiguities: string[];
};
export type Plan = PlanFields & (
  | { action: 'establish_service_site'; parameters: SiteParameters }
  | { action: 'expand_facility' | 'reduce_or_close_service'; parameters: CapacityParameters }
  | { action: 'unsupported' | CandidateAction; parameters: null }
);
export type Decision = {
  id: string; proposal_id: string; proposal_sha256: string; scope_id: string; scope_sha256: string;
  plan_id: string; plan_sha256: string; world_sha256: string;
  choice: 'approve' | 'request_revision' | 'reject'; reason: string; confirmed_no_launch: boolean; current: boolean;
};
export type RunSummary = {
  id: string; proposal_id: string; plan_id: string; decision_id: string; inputs_sha256: string;
  baseline_trace_sha256: string; intervention_trace_sha256: string;
  population: number; seed: number; status: 'complete' | 'blocked'; blockers: string[];
};
export type CouncilState = {
  schema: 1; session_id: string; revision: number; proposal: Proposal | null; scope: ScopeRevision | null;
  scope_history: ScopeRevision[]; proposal_history: ProposalRevisionSummary[]; plan: Plan | null;
  organizations: OrganizationRecord[]; organization_records: OrganizationRecord[];
  stakeholder_inputs: StakeholderInputRecord[];
  decisions: Decision[]; runs: RunSummary[]; locations: LocationChoice[]; service: { available: true };
  action_catalog?: ActionDescriptor[];
  planner?: PlannerState;
};

export type ProposalCommand = { markdown: string };
export type OrganizationCommand = Omit<OrganizationRecord,
  'id' | 'sha256' | 'organization_revision' | 'supersedes_record_id'>;
export type StakeholderInputCommand = Omit<StakeholderInputRecord, 'id' | 'sha256'
  | 'organization_record_id' | 'organization_record_sha256'>;
export type ScopeCommand = {
  proposal_id: string; evaluated_scope: string; excluded_scope: string; reviewer_note: string;
};
export type PlanCommand = {
  planner_draft_id?: string;
  proposal_id: string; scope_id: string; action: Plan['action']; parameters: SiteParameters | CapacityParameters | null;
  population: number; seed: number; organization_bindings?: Partial<Record<OrganizationRole, string>>;
};
export type DecisionCommand = {
  proposal_id: string; proposal_sha256: string; scope_id: string; scope_sha256: string;
  plan_id: string; plan_sha256: string; world_sha256: string; choice: Decision['choice'];
  reason: string; confirmed_no_launch: boolean;
};
export type RunCommand = { decision_id: string };

type CouncilEndpoint = '/api/council/proposals' | '/api/council/organizations' | '/api/council/stakeholder-inputs'
  | '/api/council/scopes' | '/api/council/plans'
  | '/api/council/decisions' | '/api/council/runs' | '/api/council/planner/drafts';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function isString(value: unknown): value is string { return typeof value === 'string'; }
function isNumber(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value); }
function isStringArray(value: unknown): value is string[] { return Array.isArray(value) && value.every(isString); }
function isNullableString(value: unknown): value is string | null { return value === null || isString(value); }
function isNullableInteger(value: unknown): value is number | null { return value === null || Number.isInteger(value); }
function isActorReference(value: unknown): boolean {
  return isRecord(value) && isString(value.role) && isString(value.organization_id)
    && isString(value.record_id) && isString(value.sha256);
}
function isActorReferenceArray(value: unknown): boolean {
  return Array.isArray(value) && value.every(isActorReference);
}
const organizationRoles: OrganizationRole[] = [
  'city_department', 'city_funder', 'property_owner', 'site_host', 'site_operator',
  'supplier_distributor', 'delivery_carrier', 'contractor', 'retailer', 'school',
  'food_support_provider', 'community_organization', 'other',
];
const evidenceStates: EvidenceState[] = ['observed', 'announced', 'estimated', 'illustrative_assumption', 'unknown'];
function isOrganizationReference(value: unknown): value is OrganizationReference {
  return isRecord(value) && organizationRoles.includes(value.role as OrganizationRole)
    && isString(value.organization_id) && isString(value.record_id) && isString(value.sha256);
}
function isOrganizationReferenceArray(value: unknown): value is OrganizationReference[] {
  return Array.isArray(value) && value.every(isOrganizationReference);
}
function isStakeholderInputReference(value: unknown): value is StakeholderInputReference {
  return isRecord(value) && isString(value.record_id) && isString(value.sha256);
}
function isStakeholderInputReferenceArray(value: unknown): value is StakeholderInputReference[] {
  return Array.isArray(value) && value.every(isStakeholderInputReference);
}
function isOrganization(value: unknown): value is OrganizationRecord {
  return isRecord(value) && isString(value.id) && isString(value.sha256)
    && isString(value.proposal_id) && isString(value.proposal_sha256)
    && isString(value.organization_id) && Number.isInteger(value.organization_revision)
    && isNullableString(value.supersedes_record_id) && isString(value.name)
    && organizationRoles.includes(value.role as OrganizationRole)
    && evidenceStates.includes(value.evidence_state as EvidenceState)
    && (value.operating_status === 'operating' || value.operating_status === 'not_operating'
      || value.operating_status === 'seasonal' || value.operating_status === 'unknown')
    && (value.authority_status === 'documented' || value.authority_status === 'assumed' || value.authority_status === 'unknown')
    && isString(value.authority_basis) && isNullableString(value.location_id)
    && isString(value.source_label) && isString(value.source_url)
    && isNullableInteger(value.budget_cents) && isNullableInteger(value.stock_grams)
    && isNullableInteger(value.service_capacity) && isString(value.operating_hours)
    && isStringArray(value.permitted_decisions) && isString(value.agreement)
    && isString(value.resource_notes) && isString(value.notes);
}
function isStakeholderInput(value: unknown): value is StakeholderInputRecord {
  return isRecord(value) && isString(value.id) && isString(value.sha256)
    && isString(value.proposal_id) && isString(value.proposal_sha256)
    && (value.stakeholder_group === 'residents_users' || value.stakeholder_group === 'nearby_residents'
      || value.stakeholder_group === 'access_barriers' || value.stakeholder_group === 'workers_volunteers'
      || value.stakeholder_group === 'nearby_businesses' || value.stakeholder_group === 'food_support_partners'
      || value.stakeholder_group === 'community_organization' || value.stakeholder_group === 'public_authorities'
      || value.stakeholder_group === 'other')
    && isNullableString(value.organization_id) && isNullableString(value.organization_record_id)
    && isNullableString(value.organization_record_sha256) && isString(value.input_date)
    && (value.method === 'consultation' || value.method === 'survey' || value.method === 'partner_submission'
      || value.method === 'meeting' || value.method === 'other')
    && evidenceStates.includes(value.evidence_state as EvidenceState)
    && isString(value.source_label) && isString(value.source_url) && isString(value.geography)
    && isString(value.reach_summary) && isString(value.consent_limits) && isString(value.views_summary)
    && isString(value.groups_not_reached) && isString(value.conflicting_views);
}
function isSpan(value: unknown): value is Span {
  return isRecord(value) && Number.isInteger(value.start_line) && Number.isInteger(value.end_line)
    && isString(value.text);
}
function isSpanArray(value: unknown): value is Span[] { return Array.isArray(value) && value.every(isSpan); }
function isCitation(value: unknown): value is Citation {
  return isRecord(value) && isString(value.label) && isString(value.url) && value.status === 'unverified_reference';
}
function isSourceContext(value: unknown): value is SourceContext {
  return isRecord(value) && isString(value.snapshot_id) && isString(value.sha256)
    && (value.retrieved_at === null || isString(value.retrieved_at)) && isStringArray(value.limits);
}
function isProposalSections(value: unknown): value is ProposalSections {
  return isRecord(value) && isSpanArray(value.constraints) && isSpanArray(value.measures)
    && isSpanArray(value.assumptions) && isSpanArray(value.goals) && isSpanArray(value.changes)
    && isSpanArray(value.unknowns);
}
function isProposal(value: unknown): value is Proposal {
  return isRecord(value) && isString(value.id) && Number.isInteger(value.revision) && isString(value.sha256)
    && isString(value.markdown) && isProposalSections(value.sections) && isSpanArray(value.unclassified)
    && Array.isArray(value.citations) && value.citations.every(isCitation) && isSourceContext(value.source_context);
}
function isProposalRevision(value: unknown): value is ProposalRevisionSummary {
  return isRecord(value) && isString(value.id) && Number.isInteger(value.revision)
    && isString(value.sha256) && isString(value.markdown);
}
function isScope(value: unknown): value is ScopeRevision {
  return isRecord(value) && isString(value.id) && isString(value.proposal_id)
    && isString(value.proposal_sha256) && isString(value.sha256) && isString(value.evaluated_scope)
    && isString(value.excluded_scope) && isString(value.reviewer_note);
}
function isLocation(value: unknown): value is LocationChoice {
  return isRecord(value) && isString(value.id) && isString(value.label)
    && Array.isArray(value.point) && value.point.length === 2 && isNumber(value.point[0]) && isNumber(value.point[1])
    && (value.source_record_id === null || isString(value.source_record_id))
    && value.operation_status === 'unknown' && value.authority === 'unknown';
}
function isSiteParameters(value: unknown): value is SiteParameters {
  if (!isRecord(value)) return false;
  return isString(value.location_id) && Number.isInteger(value.grant_cents) && Number.isInteger(value.stock_grams)
    && Number.isInteger(value.service_capacity) && value.operator_assumption === 'hypothetical_municipal_operator'
    && Number.isInteger(value.readiness_second) && Number.isInteger(value.funding_second)
    && Number.isInteger(value.delivery_second) && Number.isInteger(value.commissioning_second)
    && Number.isInteger(value.open_second) && Number.isInteger(value.close_second);
}
function isAdvice(value: unknown): value is Advice {
  return isRecord(value)
    && (value.role === 'finance' || value.role === 'site_readiness' || value.role === 'supply' || value.role === 'access')
    && (value.status === 'ready' || value.status === 'caution' || value.status === 'blocked')
    && isString(value.note) && value.authority === 'advisory';
}
function isWorld(value: unknown): value is WorldInputs {
  return isRecord(value) && isNumber(value.population) && isNumber(value.seed) && isString(value.map_sha256)
    && isString(value.catalog_id) && isString(value.catalog_sha256) && isString(value.source_snapshot_id)
    && isString(value.source_sha256) && isString(value.simulator_version) && isString(value.sha256);
}
function isPlan(value: unknown): value is Plan {
  if (!isRecord(value)) return false;
  const actionParametersMatch = value.action === 'establish_service_site'
    ? isSiteParameters(value.parameters)
    : value.action === 'expand_facility' || value.action === 'reduce_or_close_service'
      ? isRecord(value.parameters) && isSiteParameters(value.parameters.base_site)
        && Number.isInteger(value.parameters.effective_second) && Number.isInteger(value.parameters.target_capacity)
      : (value.action === 'unsupported' || candidateActions.includes(value.action as CandidateAction)) && value.parameters === null;
  return isString(value.id) && isString(value.proposal_id) && isString(value.proposal_sha256) && isString(value.sha256)
    && isString(value.scope_id) && isString(value.scope_sha256)
    && actionParametersMatch && isStringArray(value.execution_blockers)
    && Array.isArray(value.advice) && value.advice.every(isAdvice) && isWorld(value.world)
    && isOrganizationReferenceArray(value.organization_refs)
    && isOrganizationReferenceArray(value.organization_snapshot_refs)
    && isStakeholderInputReferenceArray(value.stakeholder_input_refs)
    && isStringArray(value.organization_record_gaps) && isStringArray(value.organization_binding_ambiguities);
}
function isDecision(value: unknown): value is Decision {
  return isRecord(value) && isString(value.id) && isString(value.proposal_id) && isString(value.proposal_sha256)
    && isString(value.scope_id) && isString(value.scope_sha256) && isString(value.plan_id) && isString(value.plan_sha256)
    && isString(value.world_sha256)
    && (value.choice === 'approve' || value.choice === 'request_revision' || value.choice === 'reject')
    && isString(value.reason) && typeof value.confirmed_no_launch === 'boolean' && typeof value.current === 'boolean';
}
function isRunSummary(value: unknown): value is RunSummary {
  return isRecord(value) && isString(value.id) && isString(value.proposal_id) && isString(value.plan_id)
    && isString(value.decision_id) && isString(value.inputs_sha256) && isString(value.baseline_trace_sha256)
    && isString(value.intervention_trace_sha256) && Number.isInteger(value.population) && Number.isInteger(value.seed)
    && (value.status === 'complete' || value.status === 'blocked') && isStringArray(value.blockers);
}

export function isCouncilState(value: unknown): value is CouncilState {
  if (!isRecord(value)) return false;
  if ('action_catalog' in value && (!Array.isArray(value.action_catalog) || !value.action_catalog.every(item =>
    isRecord(item) && isString(item.action) && Number.isInteger(item.version) && typeof item.executable === 'boolean'
      && isString(item.label) && isString(item.inputs) && isString(item.effects) && isString(item.limits)))) return false;
  if ('planner' in value && !isPlannerState(value.planner)) return false;
  return value.schema === 1 && isString(value.session_id) && Number.isInteger(value.revision)
    && (value.proposal === null || isProposal(value.proposal))
    && (value.scope === null || isScope(value.scope))
    && Array.isArray(value.scope_history) && value.scope_history.every(isScope)
    && Array.isArray(value.proposal_history) && value.proposal_history.every(isProposalRevision)
    && (value.plan === null || isPlan(value.plan))
    && Array.isArray(value.organizations) && value.organizations.every(isOrganization)
    && Array.isArray(value.organization_records) && value.organization_records.every(isOrganization)
    && Array.isArray(value.stakeholder_inputs) && value.stakeholder_inputs.every(isStakeholderInput)
    && Array.isArray(value.decisions) && value.decisions.every(isDecision)
    && Array.isArray(value.runs) && value.runs.every(isRunSummary)
    && Array.isArray(value.locations) && value.locations.every(isLocation)
    && isRecord(value.service) && value.service.available === true;
}

function errorMessage(value: unknown, status: number): string {
  if (isRecord(value) && isRecord(value.error) && isString(value.error.message)) {
    const revision = Number.isInteger(value.error.current_revision) ? ` Current revision: ${value.error.current_revision}.` : '';
    return value.error.message + revision;
  }
  if (status === 404) return 'The Council API endpoint was not found on this host. The Council service may not be configured.';
  if (status >= 500) return `The Council service is unavailable (HTTP ${status}).`;
  return `Council request failed (HTTP ${status}).`;
}

function isJsonResponse(response: Response): boolean {
  const mediaType = response.headers.get('content-type')?.split(';', 1)[0]?.trim().toLowerCase() ?? '';
  return mediaType === 'application/json' || mediaType.endsWith('+json');
}

async function readJson(response: Response): Promise<unknown> {
  try { return await response.json(); }
  catch { return null; }
}

function councilFormatError(payload: unknown): string {
  if (isRecord(payload)) {
    const required = ['organizations', 'organization_records', 'stakeholder_inputs'];
    const missing = required.filter(field => !(field in payload));
    if (payload.schema === 1 && missing.length > 0) {
      return `The Council backend is an older version: its response is missing ${missing.join(', ')}. Stop all running copies of npm run dev, restart it from apps/web, then refresh this page.`;
    }
  }
  return 'The Council API returned an unexpected data format. Restart the local app and refresh this page. If it persists, the browser and backend need a compatibility fix.';
}

async function fetchCouncilState(): Promise<CouncilState> {
  let response: Response;
  try { response = await fetch('/api/council'); }
  catch { throw new Error('The Council service is unavailable. City playback is still available.'); }
  if (!isJsonResponse(response)) throw new Error('The Council API is unavailable on this host. City playback is still available.');
  const payload = await readJson(response);
  if (!response.ok) throw new Error(errorMessage(payload, response.status));
  if (!isCouncilState(payload)) throw new Error(councilFormatError(payload));
  return payload;
}

export function loadCouncilState(): Promise<CouncilState> { return fetchCouncilState(); }

async function postCouncilCommand(endpoint: CouncilEndpoint, body: object, revision: number): Promise<CouncilState> {
  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Council-Schema': '1',
        'If-Match': String(revision),
        'Idempotency-Key': crypto.randomUUID(),
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error('The Council service is unavailable. This command was not confirmed as saved.');
  }
  if (!isJsonResponse(response)) throw new Error('The Council API did not return a command response. The command outcome is unknown; refresh before retrying.');
  const payload = await readJson(response);
  if (!response.ok) throw new Error(errorMessage(payload, response.status));
  if (!isCouncilState(payload)) throw new Error(councilFormatError(payload) + ' The command result is unknown; refresh before retrying.');
  return payload;
}

export const submitProposal = (command: ProposalCommand, revision: number) =>
  postCouncilCommand('/api/council/proposals', command, revision);
export const saveOrganization = (command: OrganizationCommand, revision: number) =>
  postCouncilCommand('/api/council/organizations', command, revision);
export const saveStakeholderInput = (command: StakeholderInputCommand, revision: number) =>
  postCouncilCommand('/api/council/stakeholder-inputs', command, revision);
export const saveScope = (command: ScopeCommand, revision: number) =>
  postCouncilCommand('/api/council/scopes', command, revision);
export const savePlan = (command: PlanCommand, revision: number) =>
  postCouncilCommand('/api/council/plans', command, revision);
export const saveDecision = (command: DecisionCommand, revision: number) =>
  postCouncilCommand('/api/council/decisions', command, revision);
export const createRun = (command: RunCommand, revision: number) =>
  postCouncilCommand('/api/council/runs', command, revision);

export const generatePlannerDraft = (command: { population: number; seed: number; consent_to_send: boolean }, revision: number) =>
  postCouncilCommand('/api/council/planner/drafts', command, revision);

function isRolloutEvent(value: unknown): value is RolloutEvent {
  return isRecord(value) && isString(value.event_id)
    && (value.stage === 'readiness' || value.stage === 'funding' || value.stage === 'delivery'
      || value.stage === 'commissioning' || value.stage === 'opening' || value.stage === 'closure'
      || value.stage === 'capacity_change' || value.stage === 'blocked' || value.stage === 'no_launch')
    && isNumber(value.simulation_time) && value.simulation_time >= 0
    && (value.status === 'completed' || value.status === 'blocked' || value.status === 'not_started')
    && (value.reason === null || isString(value.reason)) && isNumber(value.amount_cents)
    && isNumber(value.stock_grams) && isNumber(value.capacity)
    && (!('organization_refs' in value) || isActorReferenceArray(value.organization_refs));
}

function isNumberArray(value: unknown): value is number[] { return Array.isArray(value) && value.every(isNumber); }
function isPoint(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length === 2 && isNumber(value[0]) && isNumber(value[1]);
}
function isHouseholdState(value: unknown): boolean {
  return isRecord(value) && isNumber(value.cash_cents) && isNumber(value.pantry_grams)
    && isNumber(value.carrying_grams) && isNumber(value.consumed_grams) && isNumber(value.unmet_grams)
    && isNumber(value.expenditure_cents) && isNumber(value.received_grams) && isNumber(value.purchased_grams);
}
function isSiteState(value: unknown): boolean {
  return isRecord(value) && isNumber(value.stock_grams) && isNumber(value.served) && isNumber(value.visits)
    && isNumber(value.denials) && isNumber(value.sold_grams) && isNumber(value.received_grams)
    && isNumber(value.revenue_cents) && isNumber(value.spending_cents)
    && isNumber(value.price_cents_per_100g) && isNumber(value.capacity);
}
function isHousehold(value: unknown): boolean {
  return isRecord(value) && isString(value.id) && Number.isInteger(value.resident_id)
    && Number.isInteger(value.size) && isString(value.income_band) && isString(value.mobility)
    && Number.isInteger(value.children) && Number.isInteger(value.home_node) && isString(value.area)
    && isNumber(value.opening_cents) && isNumber(value.opening_grams) && isNumber(value.need_grams)
    && isNumber(value.speed) && isNumber(value.time_budget_seconds) && isNumber(value.departure);
}
function isSite(value: unknown): boolean {
  return isRecord(value) && isString(value.id) && isString(value.name)
    && (value.type === 'retailer' || value.type === 'support' || value.type === 'school' || value.type === 'emergency' || value.type === 'council')
    && Number.isInteger(value.node) && isPoint(value.point) && isNumber(value.opens) && isNumber(value.closes)
    && isNumber(value.price_cents_per_100g) && isNumber(value.capacity) && isNumber(value.service_seconds)
    && isNumber(value.active_from) && isString(value.eligible)
    && (!('source_id' in value) || isString(value.source_id))
    && (!('source_record_id' in value) || isString(value.source_record_id))
    && (!('source_site_id' in value) || isString(value.source_site_id))
    && (!('source_url' in value) || isString(value.source_url))
    && (!('source_record_url' in value) || isString(value.source_record_url))
    && (!('source_snapshot_id' in value) || isString(value.source_snapshot_id))
    && (!('source_retrieved_at' in value) || isString(value.source_retrieved_at))
    && (!('source_published_at' in value) || value.source_published_at === null || isString(value.source_published_at))
    && (!('source_updated_at' in value) || value.source_updated_at === null || isString(value.source_updated_at))
    && (!('source_address' in value) || isString(value.source_address))
    && (!('source_quality_flags' in value) || isStringArray(value.source_quality_flags))
    && (!('location_evidence_state' in value) || isString(value.location_evidence_state))
    && (!('operations_evidence_state' in value) || isString(value.operations_evidence_state))
    && (!('listing_current_status' in value) || isString(value.listing_current_status))
    && (!('map_snap_distance_m' in value) || isNumber(value.map_snap_distance_m))
    && (!('network_point' in value) || isPoint(value.network_point))
    && (!('organization_refs' in value) || isActorReferenceArray(value.organization_refs));
}
function isJourney(value: unknown): boolean {
  return isRecord(value) && isString(value.route_id) && isString(value.site_id)
    && isNumberArray(value.nodes) && value.nodes.every(Number.isInteger)
    && isNumberArray(value.times) && isNumber(value.meters) && isNumber(value.depart)
    && isNumber(value.arrival) && isNumber(value.travel_seconds) && isNumber(value.return_start)
    && isNumber(value.home_at) && (!('service_start' in value) || isNumber(value.service_start))
    && isString(value.result);
}
function isInteractionEvent(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const nullableString = (item: unknown) => item === null || isString(item);
  const optionalNumber = (key: string) => !(key in value) || isNumber(value[key]);
  const optionalBoolean = (key: string) => !(key in value) || typeof value[key] === 'boolean';
  const optionsValid = !('options' in value) || (Array.isArray(value.options) && value.options.every(option =>
    isRecord(option) && isString(option.option_id) && (!('quantity_grams' in option) || isNumber(option.quantity_grams))
      && (!('payment_cents' in option) || isNumber(option.payment_cents))
      && (!('total_seconds' in option) || isNumber(option.total_seconds))));
  const excludedValid = !('excluded' in value) || (Array.isArray(value.excluded) && value.excluded.every(item =>
    isRecord(item) && isString(item.site_id) && isString(item.reason)));
  return isString(value.event_id) && isNumber(value.simulation_time)
    && (value.resident_id === null || isNumber(value.resident_id)) && nullableString(value.household_id)
    && nullableString(value.site_id) && isString(value.site_type) && isString(value.action)
    && nullableString(value.decision_id) && nullableString(value.route_id) && isNumber(value.travel_seconds)
    && isNumber(value.queue_seconds) && isNumber(value.service_seconds) && isNumber(value.quantity_grams)
    && isNumber(value.payment_cents) && isString(value.result) && nullableString(value.denial_or_failure_reason)
    && isString(value.evidence_state) && nullableString(value.source_id) && isString(value.scenario_parameter_id)
    && (!('household_state' in value) || isHouseholdState(value.household_state))
    && (!('site_state' in value) || isSiteState(value.site_state)) && isNumber(value.public_spending_cents)
    && (!('organization_refs' in value) || isActorReferenceArray(value.organization_refs))
    && (!('option_id' in value) || isString(value.option_id)) && optionalNumber('shortfall_grams')
    && optionalBoolean('substitution') && optionalBoolean('reduced_basket') && optionalNumber('portions')
    && optionsValid && excludedValid;
}
function isFoodTracePayload(value: Record<string, unknown>): boolean {
  const assumptions = value.assumptions, accounting = value.accounting;
  if (!isRecord(assumptions) || !isString(assumptions.parameter_id) || !isString(assumptions.food_use)
      || !isNumber(assumptions.crossing_delay_seconds) || !isString(assumptions.scope)
      || !isStringArray(assumptions.unknown_inputs)) return false;
  if (!isRecord(accounting) || !isStringArray(accounting.invariant_problems)
      || !isNumber(accounting.total_cash_cents) || !isNumber(accounting.imported_grams)
      || !isNumber(accounting.consumed_grams) || !isNumber(accounting.remaining_grams)
      || accounting.invariant_problems.length > 0 || accounting.total_cash_cents !== 0
      || accounting.imported_grams !== accounting.consumed_grams + accounting.remaining_grams) return false;
  const snapshot = value.data_snapshot;
  const snapshotValid = snapshot === undefined || (isRecord(snapshot) && isRecord(snapshot.content)
    && isString(snapshot.content.snapshot_id) && isString(snapshot.content.source_snapshot_id)
    && isStringArray(snapshot.content.evidence_limits) && isString(snapshot.content_sha256));
  return value.schema === 1 && isString(value.scenario_id) && isNumber(value.seed)
    && isNumber(value.horizon_seconds) && isString(value.start_time) && isString(value.evidence_state)
    && isString(value.geography) && isNumber(value.population)
    && Array.isArray(value.sites) && value.sites.every(isSite)
    && Array.isArray(value.households) && value.households.every(isHousehold)
    && isRecord(value.initial_households) && Object.values(value.initial_households).every(isHouseholdState)
    && isRecord(value.initial_sites) && Object.values(value.initial_sites).every(isSiteState)
    && isRecord(value.journeys) && Object.values(value.journeys).every(isJourney)
    && Array.isArray(value.events) && value.events.every(isInteractionEvent) && snapshotValid;
}

export function isCouncilFoodTrace(value: unknown, expected: CouncilRunRef): value is CouncilFoodTrace {
  if (!isRecord(value) || !isRunRef(value.run_ref)) return false;
  const runRef = value.run_ref;
  const context = value.council_context;
  const contextValid = context === undefined || (isRecord(context)
    && isActorReferenceArray(context.organization_refs)
    && isStakeholderInputReferenceArray(context.stakeholder_input_refs));
  return value.policy === 'council' && isFoodTracePayload(value) && value.run_id === expected.run_id
    && runRef.kind === 'council' && sameRunRef(runRef, expected)
    && Array.isArray(value.rollout_events) && value.rollout_events.every(isRolloutEvent) && contextValid;
}

export async function loadCouncilTrace(runRef: CouncilRunRef): Promise<CouncilFoodTrace> {
  let response: Response;
  try {
    response = await fetch(`/api/council/runs/${encodeURIComponent(runRef.run_id)}/traces/${runRef.arm}`);
  } catch {
    throw new Error('The Council service is unavailable. This Council run could not be loaded.');
  }
  if (!isJsonResponse(response)) throw new Error('The Council API is unavailable on this host. No preset trace was loaded.');
  const payload = await readJson(response);
  if (!response.ok) throw new Error(errorMessage(payload, response.status));
  if (!isCouncilFoodTrace(payload, runRef)) throw new Error('The Council trace does not match the requested run identity or trace contract.');
  return payload;
}
