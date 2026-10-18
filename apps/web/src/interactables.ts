import type { District, Point } from './district.ts';
import type { Crowd, Inspection, Pose, Resident } from './pedestrians.ts';
import type { CouncilRunRef } from './runRef.ts';

export type Household = {
  id: string; resident_id: number; size: number; income_band: string; mobility: string; children: number;
  home_node: number; area: string; opening_cents: number; opening_grams: number; need_grams: number;
  speed: number; time_budget_seconds: number; departure: number;
};
export type HouseholdState = {
  cash_cents: number; pantry_grams: number; carrying_grams: number; consumed_grams: number;
  unmet_grams: number; expenditure_cents: number; received_grams: number; purchased_grams: number;
};
export type OrganizationActorReference = {
  role: string; organization_id: string; record_id: string; sha256: string;
};
export type Site = {
  id: string; name: string; type: 'retailer' | 'support' | 'school' | 'emergency' | 'council'; node: number; point: Point;
  opens: number; closes: number; price_cents_per_100g: number; capacity: number; service_seconds: number;
  active_from: number; eligible: string;
  source_id?: string; source_record_id?: string; source_site_id?: string; source_url?: string; source_record_url?: string;
  source_snapshot_id?: string; source_retrieved_at?: string; source_published_at?: string | null;
  source_updated_at?: string | null; source_address?: string; source_quality_flags?: string[];
  location_evidence_state?: string; operations_evidence_state?: string; listing_current_status?: string;
  map_snap_distance_m?: number; network_point?: Point; organization_refs?: OrganizationActorReference[];
};
export type SiteState = {
  stock_grams: number; served: number; visits: number; denials: number; sold_grams: number;
  received_grams: number; revenue_cents: number; spending_cents: number;
  price_cents_per_100g: number; capacity: number;
};
export type InteractionEvent = {
  event_id: string; simulation_time: number; resident_id: number | null; household_id: string | null;
  site_id: string | null; site_type: string; action: string; decision_id: string | null; route_id: string | null;
  travel_seconds: number; queue_seconds: number; service_seconds: number; quantity_grams: number; payment_cents: number;
  result: string; denial_or_failure_reason: string | null; evidence_state: string; source_id: string | null;
  scenario_parameter_id: string; household_state?: HouseholdState; site_state?: SiteState;
  organization_refs?: OrganizationActorReference[];
  public_spending_cents: number; option_id?: string; shortfall_grams?: number; substitution?: boolean;
  reduced_basket?: boolean; portions?: number;
  options?: { option_id: string; quantity_grams?: number; payment_cents?: number; total_seconds?: number }[];
  excluded?: { site_id: string; reason: string }[];
};
export type Journey = {
  route_id: string; site_id: string; nodes: number[]; times: number[]; meters: number;
  depart: number; arrival: number; travel_seconds: number; return_start: number; home_at: number;
  service_start?: number; result: string;
};
export type FoodTraceFields = {
  schema: number; scenario_id: string; seed: number; horizon_seconds: number;
  start_time: string; timezone?: string; local_date?: string | null; end_time_exclusive?: string | null;
  scenario_manifest_id?: string; scenario_manifest_sha256?: string;
  evidence_state: string; geography: string; population: number;
  sites: Site[]; households: Household[]; initial_households: Record<string, HouseholdState>;
  initial_sites: Record<string, SiteState>; journeys: Record<string, Journey>; events: InteractionEvent[];
  assumptions: { parameter_id: string; food_use: string; crossing_delay_seconds: number; scope: string; unknown_inputs: string[] };
  accounting: { invariant_problems: string[]; total_cash_cents: number; imported_grams: number; consumed_grams: number; remaining_grams: number };
  data_snapshot?: { content: { snapshot_id: string; source_snapshot_id: string; evidence_limits: string[] }; content_sha256: string };
};
export type PresetFoodTrace = FoodTraceFields & { policy: 'baseline' | 'emergency' };
export type CouncilFoodTrace = FoodTraceFields & {
  policy: 'council'; run_id: string; run_ref: CouncilRunRef; rollout_events: RolloutEvent[];
  council_context?: { organization_refs: OrganizationActorReference[]; stakeholder_input_refs: { record_id: string; sha256: string }[] };
};
export type FoodTrace = PresetFoodTrace | CouncilFoodTrace;
export type RolloutEvent = {
  event_id: string; stage: 'readiness' | 'funding' | 'delivery' | 'commissioning' | 'opening' | 'closure' | 'blocked' | 'no_launch';
  simulation_time: number; status: 'completed' | 'blocked' | 'not_started'; reason: string | null;
  amount_cents: number; stock_grams: number; capacity: number; organization_refs?: OrganizationActorReference[];
};
export type FoodView = {
  households: Record<string, HouseholdState>; sites: Record<string, SiteState>; events: InteractionEvent[];
  publicSpending: number; seconds: number;
};
export type FoodTimelinePoint = {
  seconds: number;
  purchased_grams: number;
  received_grams: number;
  consumed_grams: number;
  unmet_grams: number;
  completed_services: number;
  denied_services: number;
  no_purchase: number;
};
export type SiteStockPoint = { seconds: number; stock_grams: Record<string, number> };

export async function loadFoodTrace(population: number, policy: 'baseline' | 'emergency'): Promise<FoodTrace> {
  const response = await fetch(`/data/interactables/${population}-${policy}.json`);
  if (!response.ok) throw new Error('Food simulation data could not load. Run npm run data:interactables and reload.');
  const trace = await response.json() as FoodTrace;
  if (trace.schema !== 1 || trace.population !== population || trace.policy !== policy || !Array.isArray(trace.events)
      || trace.accounting.invariant_problems.length || trace.accounting.total_cash_cents !== 0
      || trace.accounting.imported_grams !== trace.accounting.consumed_grams + trace.accounting.remaining_grams) {
    throw new Error('The food simulation trace has an invalid contract or accounting balance.');
  }
  return trace;
}

/** Read committed projections up to the playhead; never settle or infer a transaction. */
export function foodView(trace: FoodTrace, seconds: number): FoodView {
  const households = { ...trace.initial_households }, sites = { ...trace.initial_sites };
  const events: InteractionEvent[] = [];
  let publicSpending = 0;
  for (const event of trace.events) {
    if (event.simulation_time > seconds) break;
    events.push(event);
    if (event.household_id && event.household_state) households[event.household_id] = event.household_state;
    if (event.site_id && event.site_state) sites[event.site_id] = event.site_state;
    publicSpending = event.public_spending_cents;
  }
  return { households, sites, events, publicSpending, seconds };
}

const colors = ['#daf3a6', '#f4c680', '#78c8be', '#e89d85', '#90b9d4', '#c3acd9'];
const names = ['Alex', 'Sam', 'Jordan', 'Taylor', 'Morgan', 'Avery', 'Robin', 'Jamie', 'Casey', 'Riley', 'Cameron', 'Devon'];
export function foodCrowd(trace: FoodTrace, district: District): Crowd {
  return { usableNodes: [], residents: trace.households.map(h => {
    const journey = trace.journeys[h.id];
    const route = (journey?.nodes ?? [h.home_node, h.home_node]).map(n => district.walkNodes[n]!);
    if (route.some(p => !p)) throw new Error('Food journey references a missing map node.');
    const cumulative = [0];
    for (let i = 1; i < route.length; i++) cumulative.push(cumulative[i - 1]! + Math.hypot(route[i]![0] - route[i - 1]![0], route[i]![1] - route[i - 1]![1]));
    return { id: h.resident_id, name: `${names[h.resident_id % names.length]} ${String(h.resident_id + 1).padStart(3, '0')}`,
      purpose: 'Household food trip', color: colors[h.resident_id % colors.length]!,
      destination: trace.sites.find(s => s.id === journey?.site_id)?.name ?? 'Home and pantry',
      route, cumulative, length: cumulative[cumulative.length - 1]!, speed: h.speed, pause: 0, offset: 0 };
  }) };
}

export function foodPose(trace: FoodTrace, resident: Resident, seconds: number): Pose {
  const trip = trace.journeys[`hh-${resident.id}`];
  const returning = !!trip && seconds >= trip.return_start;
  let elapsed = 0;
  if (trip && seconds >= trip.depart) {
    elapsed = seconds < trip.arrival ? seconds - trip.depart : seconds < trip.return_start ? trip.travel_seconds
      : Math.max(0, trip.travel_seconds - (seconds - trip.return_start));
  }
  const times = trip?.times ?? [0, 1];
  let i = 0, high = times.length - 1;
  while (i < high - 1) { const mid = (i + high) >> 1; if (times[mid]! <= elapsed) i = mid; else high = mid; }
  const a = resident.route[i]!, b = resident.route[Math.min(i + 1, resident.route.length - 1)]!;
  const fraction = Math.max(0, Math.min(1, (elapsed - times[i]!) / Math.max(1, times[i + 1]! - times[i]!)));
  const moving = !!trip && ((seconds >= trip.depart && seconds < trip.arrival) || (seconds >= trip.return_start && seconds < trip.home_at));
  return { x: a[0] + (b[0] - a[0]) * fraction, z: a[1] + (b[1] - a[1]) * fraction,
    heading: Math.atan2(b[0] - a[0], b[1] - a[1]) + (returning ? Math.PI : 0),
    walking: moving && (a[0] !== b[0] || a[1] !== b[1]), returning,
    progress: trip ? elapsed / trip.travel_seconds : 0, distance: resident.length * (trip ? elapsed / trip.travel_seconds : 0) };
}

export function foodInspection(trace: FoodTrace, resident: Resident, seconds: number): Inspection {
  const p = foodPose(trace, resident, seconds), trip = trace.journeys[`hh-${resident.id}`];
  const activity = !trip || seconds < trip.depart || seconds >= trip.home_at ? 'At home'
    : seconds < trip.arrival ? p.walking ? 'Walking' : 'Waiting at crossing'
      : seconds < (trip.service_start ?? trip.return_start) ? 'Queuing'
        : seconds < trip.return_start ? 'Receiving service' : p.walking ? 'Walking home' : 'Waiting at crossing';
  return { id: resident.id, name: resident.name, purpose: resident.purpose, color: resident.color,
    destination: p.returning || activity === 'At home' ? 'Home and pantry' : resident.destination,
    activity, speed: resident.speed, progress: p.returning ? 1 - p.progress : p.progress,
    routeLength: resident.length, x: p.x, z: p.z };
}

export function foodMetrics(trace: FoodTrace, view: FoodView) {
  const states = Object.values(view.households);
  const sum = (key: keyof HouseholdState) => states.reduce((n, h) => n + h[key], 0);
  const attempts = view.events.filter(e => ['purchase', 'receive_service', 'service', 'no_purchase'].includes(e.action));
  const successful = attempts.filter(e => e.result === 'completed');
  const failures = attempts.filter(e => e.result === 'denied');
  const failureReasons: Record<string, number> = {};
  for (const e of failures) { const reason = e.denial_or_failure_reason ?? 'unknown'; failureReasons[reason] = (failureReasons[reason] ?? 0) + 1; }
  const strata = (field: 'income_band' | 'area' | 'mobility' | 'size') => {
    const groups: Record<string, { count: number; unmet: number; obtained: number; spending: number }> = {};
    for (const h of trace.households) {
      const group = groups[String(h[field])] ??= { count: 0, unmet: 0, obtained: 0, spending: 0 };
      const state = view.households[h.id]!;
      group.count++; group.unmet += state.unmet_grams;
      group.obtained += state.purchased_grams + state.received_grams; group.spending += state.expenditure_cents;
    }
    return groups;
  };
  return { purchased: sum('purchased_grams'), received: sum('received_grams'), spending: sum('expenditure_cents'),
    pantry: sum('pantry_grams'), consumed: sum('consumed_grams'), unmet: sum('unmet_grams'),
    portions: states.reduce((n, h) => n + Math.floor(h.consumed_grams / 300), 0), completed: view.events.filter(e => e.action === 'return_home').length,
    attempts: attempts.length, successful: successful.length, failures: failures.length, failureReasons,
    travel: view.events.filter(e => e.action === 'return_home').reduce((n, e) => n + e.travel_seconds, 0),
    queue: attempts.reduce((n, e) => n + e.queue_seconds, 0),
    service: attempts.reduce((n, e) => n + e.service_seconds, 0),
    shortfall: view.events.reduce((n, e) => n + (e.shortfall_grams ?? 0), 0),
    legalSites: view.events.filter(e => e.action === 'offered').at(-1)?.options?.filter(o => o.quantity_grams).length ?? 0,
    strata };
}

/** Summarize the committed trace at 30-minute boundaries up to the live playhead. */
export function foodTimeline(trace: FoodTrace, seconds: number, interval = 1800): FoodTimelinePoint[] {
  const through = Math.max(0, Math.min(seconds, trace.horizon_seconds));
  const households = { ...trace.initial_households };
  const totals = { purchased_grams: 0, received_grams: 0, consumed_grams: 0, unmet_grams: 0 };
  for (const state of Object.values(households)) {
    totals.purchased_grams += state.purchased_grams;
    totals.received_grams += state.received_grams;
    totals.consumed_grams += state.consumed_grams;
    totals.unmet_grams += state.unmet_grams;
  }

  const points: FoodTimelinePoint[] = [];
  let eventIndex = 0, completedServices = 0, deniedServices = 0, noPurchase = 0;
  const applyThrough = (cutoff: number) => {
    while (eventIndex < trace.events.length && trace.events[eventIndex]!.simulation_time <= cutoff) {
      const event = trace.events[eventIndex]!;
      if (event.household_id && event.household_state) {
        const previous = households[event.household_id];
        if (previous) {
          totals.purchased_grams += event.household_state.purchased_grams - previous.purchased_grams;
          totals.received_grams += event.household_state.received_grams - previous.received_grams;
          totals.consumed_grams += event.household_state.consumed_grams - previous.consumed_grams;
          totals.unmet_grams += event.household_state.unmet_grams - previous.unmet_grams;
        }
        households[event.household_id] = event.household_state;
      }
      if (event.result === 'completed' && ['purchase', 'receive_service', 'school_meal', 'delivery'].includes(event.action)) completedServices++;
      if (event.action === 'service' && event.result === 'denied') deniedServices++;
      if (event.action === 'no_purchase') noPurchase++;
      eventIndex++;
    }
  };
  const snapshot = (atSeconds: number): FoodTimelinePoint => ({
    seconds: atSeconds,
    ...totals,
    completed_services: completedServices,
    denied_services: deniedServices,
    no_purchase: noPurchase,
  });

  applyThrough(0);
  points.push(snapshot(0));
  for (let boundary = interval; boundary < through; boundary += interval) {
    applyThrough(boundary);
    points.push(snapshot(boundary));
  }
  applyThrough(through);
  if (points.at(-1)!.seconds < through) points.push(snapshot(through));
  else points[points.length - 1] = snapshot(through);
  return points;
}

/** Preserve discrete site stock changes from committed event projections. */
export function siteStockHistory(trace: FoodTrace, seconds: number): SiteStockPoint[] {
  const through = Math.max(0, Math.min(seconds, trace.horizon_seconds));
  const stock = Object.fromEntries(trace.sites.map(site => [site.id, trace.initial_sites[site.id]!.stock_grams]));
  const points: SiteStockPoint[] = [{ seconds: 0, stock_grams: { ...stock } }];
  for (const event of trace.events) {
    if (event.simulation_time > through) break;
    if (!event.site_id || !event.site_state || stock[event.site_id] === event.site_state.stock_grams) continue;
    stock[event.site_id] = event.site_state.stock_grams;
    points.push({ seconds: event.simulation_time, stock_grams: { ...stock } });
  }
  if (points[points.length - 1]!.seconds < through) points.push({ seconds: through, stock_grams: { ...stock } });
  return points;
}
