import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDownLeft, ArrowRight, Clock3, Download, Search, Users } from 'lucide-react';
import { foodTimeline, foodView, siteStockHistory } from './interactables.ts';
import type { FoodTimelinePoint, FoodTrace, InteractionEvent, Site, SiteStockPoint } from './interactables.ts';
import { at, dollars, duration, grams, HouseholdDetails, words } from './FoodDetails.tsx';
import { isLiveRunState, LIVE_RUN_CHANNEL } from './liveRun.ts';
import type { DashboardCommand, LiveRunState } from './liveRun.ts';
import { parseRunRef, sameRunRef, serializeRunRef } from './runRef.ts';
import type { RunRef } from './runRef.ts';
import { loadRunTrace } from './runTrace.ts';

type DashboardSection = 'overview' | 'interactions' | 'sites' | 'households';
type GroupDimension = 'income_band' | 'area' | 'mobility' | 'size';
const sections: { id: DashboardSection; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'interactions', label: 'Interaction log' },
  { id: 'sites', label: 'Sites & services' },
  { id: 'households', label: 'Households' },
];
const sectionFromQuery = (): DashboardSection => {
  const value = new URLSearchParams(window.location.search).get('view');
  return sections.some(section => section.id === value) ? value as DashboardSection : 'overview';
};
const populationFromQuery = () => {
  const value = Number(new URLSearchParams(window.location.search).get('population'));
  return [200, 600, 1200, 2400].includes(value) ? value : 2400;
};
const policyFromQuery = (): 'baseline' | 'emergency' =>
  new URLSearchParams(window.location.search).get('policy') === 'emergency' ? 'emergency' : 'baseline';
const runRefFromQuery = (): RunRef => parseRunRef(new URLSearchParams(window.location.search).get('run'))
  ?? { kind: 'preset', population: populationFromQuery(), policy: policyFromQuery() };
function cityUrl(runRef: RunRef, seconds: number, siteId: string | null, residentId: number | null): string {
  const params = new URLSearchParams();
  const serialized = serializeRunRef(runRef);
  if (runRef.kind === 'council') params.set('run', serialized ?? '');
  else { params.set('population', String(runRef.population)); params.set('policy', runRef.policy); }
  params.set('time', String(Math.floor(seconds)));
  if (siteId) params.set('site', siteId);
  if (residentId !== null) params.set('resident', String(residentId));
  return '/?' + params.toString();
}
const timeFromQuery = (horizon: number) => {
  const raw = new URLSearchParams(window.location.search).get('time');
  const value = raw === null ? NaN : Number(raw);
  return Number.isFinite(value) && value >= 0 ? Math.min(value, horizon) : horizon;
};

function siteStatus(site: Site, seconds: number, startTime: string, timezone?: string) {
  if (seconds < site.active_from) return 'Scheduled ' + at(site.active_from, startTime, timezone);
  if (seconds < site.opens || seconds >= site.closes) return 'Closed';
  return 'Open';
}

function EventRow({ trace, event, selected, onSelect }: {
  trace: FoodTrace; event: InteractionEvent; selected: boolean; onSelect: (event: InteractionEvent) => void;
}) {
  const site = trace.sites.find(candidate => candidate.id === event.site_id);
  const subject = event.household_id ?? event.site_id ?? 'City activity';
  const amount = event.quantity_grams > 0 ? grams(event.quantity_grams)
    : event.portions ? event.portions + ' portions' : '—';
  const status = event.result.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  return <button type="button" className={'terminal-event-row' + (selected ? ' selected' : '')}
    aria-pressed={selected} onClick={() => onSelect(event)}>
    <time>{at(event.simulation_time, trace.start_time, trace.timezone)}</time>
    <span className="terminal-event-action"><b>{words(event.action)}</b><small>{subject}{site ? ' / ' + site.name : ''}</small></span>
    <em className={'terminal-result result-' + status}>{words(event.result)}</em>
    <span className="terminal-event-amount">{amount}</span>
    <span className="terminal-event-cash">{event.payment_cents > 0 ? dollars(event.payment_cents) : '—'}</span>
  </button>;
}

const chartBox = { left: 62, right: 1000, top: 32, bottom: 252 };
const seriesColors = ['#538a6d', '#c58b61', '#82966d', '#6488a0', '#8978a4'];

function chartPath<T extends { seconds: number }>(points: T[], horizon: number, maximum: number,
  value: (point: T) => number, stepped = false): string {
  if (!points.length) return '';
  const x = (seconds: number) => chartBox.left + Math.max(0, Math.min(1, seconds / Math.max(1, horizon))) * (chartBox.right - chartBox.left);
  const y = (amount: number) => chartBox.bottom - Math.max(0, Math.min(1, amount / Math.max(1, maximum))) * (chartBox.bottom - chartBox.top);
  let path = `M ${x(points[0]!.seconds)} ${y(value(points[0]!))}`;
  for (let index = 1; index < points.length; index++) {
    const point = points[index]!;
    path += stepped
      ? ` H ${x(point.seconds)} V ${y(value(point))}`
      : ` L ${x(point.seconds)} ${y(value(point))}`;
  }
  return path;
}

function ChartGrid({ maximum, units, horizon, startTime, timezone }: {
  maximum: number; units: string; horizon: number; startTime: string; timezone?: string;
}) {
  const y = (fraction: number) => chartBox.bottom - fraction * (chartBox.bottom - chartBox.top);
  return <>
    {[0, 1 / 3, 2 / 3, 1].map(fraction => <g key={fraction}>
      <line x1={chartBox.left} x2={chartBox.right} y1={y(fraction)} y2={y(fraction)} className="terminal-gridline" />
      <text x="52" y={y(fraction) + 4} textAnchor="end">{(maximum * fraction).toFixed(units === 'kg' ? 1 : 0)}</text>
    </g>)}
    {[0, 0.5, 1].map(fraction => <text key={fraction} x={chartBox.left + fraction * (chartBox.right - chartBox.left)} y="288" textAnchor={fraction === 0 ? 'start' : fraction === 1 ? 'end' : 'middle'}>
      {at(horizon * fraction, startTime, timezone)}
    </text>)}
    <text x="8" y="18" className="terminal-axis-unit">{units.toUpperCase()}</text>
  </>;
}

function FoodFlowChart({ trace, points, seconds }: { trace: FoodTrace; points: FoodTimelinePoint[]; seconds: number }) {
  const series = [
    { key: 'purchased_grams' as const, label: 'Purchased', color: seriesColors[0]! },
    { key: 'received_grams' as const, label: 'Program food received', color: seriesColors[1]! },
    { key: 'consumed_grams' as const, label: 'Consumed', color: seriesColors[2]! },
  ];
  const maximumGrams = Math.max(1000, Math.ceil(trace.accounting.imported_grams / 1000) * 1000);
  const current = points.at(-1)!;
  const cursorX = chartBox.left + Math.min(1, seconds / Math.max(1, trace.horizon_seconds)) * (chartBox.right - chartBox.left);
  return <div className="terminal-chart">
    <svg viewBox="0 0 1040 320" role="img" aria-label="Cumulative purchased, received, and consumed produce in kilograms through the live simulation playhead">
      <ChartGrid maximum={maximumGrams / 1000} units="kg" horizon={trace.horizon_seconds} startTime={trace.start_time} timezone={trace.timezone} />
      {series.map(item => <g key={item.key}>
        <path d={chartPath(points, trace.horizon_seconds, maximumGrams, point => point[item.key])} className="terminal-chart-series" style={{ stroke: item.color }} />
        <circle cx={cursorX} cy={chartBox.bottom - current[item.key] / maximumGrams * (chartBox.bottom - chartBox.top)} r="5" className="terminal-chart-point" style={{ fill: item.color }}>
          <title>{item.label}: {(current[item.key] / 1000).toFixed(2)} kg at {at(seconds, trace.start_time, trace.timezone)}</title>
        </circle>
      </g>)}
      <line x1={cursorX} x2={cursorX} y1={chartBox.top} y2={chartBox.bottom} className="terminal-live-cursor" />
      <text x="1028" y="18" textAnchor="end" className="terminal-axis-unit">PRODUCE COMPONENT</text>
    </svg>
    <div className="terminal-chart-legend">{series.map(item => <span key={item.key}><i style={{ backgroundColor: item.color }} />{item.label}</span>)}</div>
    <div className="terminal-chart-footer"><span>COMMITTED HOUSEHOLD FOOD FLOW</span><span>PLAYHEAD {at(seconds, trace.start_time, trace.timezone)}</span></div>
  </div>;
}

function ServiceActivityChart({ trace, points, seconds }: { trace: FoodTrace; points: FoodTimelinePoint[]; seconds: number }) {
  const series = [
    { key: 'completed_services' as const, label: 'Completed food transactions', color: seriesColors[0]! },
    { key: 'denied_services' as const, label: 'Denied service', color: seriesColors[1]! },
    { key: 'no_purchase' as const, label: 'No purchase chosen', color: '#899487' },
  ];
  const fullCounts = trace.events.reduce((counts, event) => {
    if (event.result === 'completed' && ['purchase', 'receive_service', 'school_meal', 'delivery'].includes(event.action)) counts.completed++;
    if (event.action === 'service' && event.result === 'denied') counts.denied++;
    if (event.action === 'no_purchase') counts.noPurchase++;
    return counts;
  }, { completed: 0, denied: 0, noPurchase: 0 });
  const maximum = Math.max(1, fullCounts.completed, fullCounts.denied, fullCounts.noPurchase);
  const cursorX = chartBox.left + Math.min(1, seconds / Math.max(1, trace.horizon_seconds)) * (chartBox.right - chartBox.left);
  return <div className="terminal-chart">
    <svg viewBox="0 0 1040 320" role="img" aria-label="Cumulative completed services, service denials, and no-purchase decisions through the live simulation playhead">
      <ChartGrid maximum={maximum} units="events" horizon={trace.horizon_seconds} startTime={trace.start_time} timezone={trace.timezone} />
      {series.map(item => <g key={item.key}>
        <path d={chartPath(points, trace.horizon_seconds, maximum, point => point[item.key])} className="terminal-chart-series" style={{ stroke: item.color }} />
        <circle cx={cursorX} cy={chartBox.bottom - points.at(-1)![item.key] / maximum * (chartBox.bottom - chartBox.top)} r="5" className="terminal-chart-point" style={{ fill: item.color }}>
          <title>{item.label}: {points.at(-1)![item.key]} at {at(seconds, trace.start_time, trace.timezone)}</title>
        </circle>
      </g>)}
      <line x1={cursorX} x2={cursorX} y1={chartBox.top} y2={chartBox.bottom} className="terminal-live-cursor" />
    </svg>
    <div className="terminal-chart-legend">{series.map(item => <span key={item.key}><i style={{ backgroundColor: item.color }} />{item.label}</span>)}</div>
    <div className="terminal-chart-footer"><span>EVENT COUNTS / CUMULATIVE</span><span>PLAYHEAD {at(seconds, trace.start_time, trace.timezone)}</span></div>
  </div>;
}

function SiteStockChart({ trace, points, seconds }: { trace: FoodTrace; points: SiteStockPoint[]; seconds: number }) {
  const maximumGrams = useMemo(() => Math.max(1000,
    ...Object.values(trace.initial_sites).map(state => state.stock_grams),
    ...trace.events.map(event => event.site_state?.stock_grams ?? 0)), [trace]);
  const cursorX = chartBox.left + Math.min(1, seconds / Math.max(1, trace.horizon_seconds)) * (chartBox.right - chartBox.left);
  return <div className="terminal-chart">
    <svg viewBox="0 0 1040 320" role="img" aria-label="Site inventory in kilograms, updated from committed site stock changes">
      <ChartGrid maximum={maximumGrams / 1000} units="kg" horizon={trace.horizon_seconds} startTime={trace.start_time} timezone={trace.timezone} />
      {trace.sites.map((site, index) => {
        const color = seriesColors[index % seriesColors.length]!;
        const value = (point: SiteStockPoint) => point.stock_grams[site.id] ?? 0;
        return <g key={site.id}>
          <path d={chartPath(points, trace.horizon_seconds, maximumGrams, value, true)} className="terminal-chart-series" style={{ stroke: color }} />
          <circle cx={cursorX} cy={chartBox.bottom - value(points.at(-1)!) / maximumGrams * (chartBox.bottom - chartBox.top)} r="5" className="terminal-chart-point" style={{ fill: color }}>
            <title>{site.name}: {(value(points.at(-1)!) / 1000).toFixed(2)} kg at {at(seconds, trace.start_time, trace.timezone)}</title>
          </circle>
        </g>;
      })}
      <line x1={cursorX} x2={cursorX} y1={chartBox.top} y2={chartBox.bottom} className="terminal-live-cursor" />
    </svg>
    <div className="terminal-chart-legend">{trace.sites.map((site, index) => <span key={site.id}><i style={{ backgroundColor: seriesColors[index % seriesColors.length] }} />{site.name}</span>)}</div>
    <div className="terminal-chart-footer"><span>MODELED SITE INVENTORY</span><span>PLAYHEAD {at(seconds, trace.start_time, trace.timezone)}</span></div>
  </div>;
}

function EventDetails({ trace, event, onSite, onHousehold }: {
  trace: FoodTrace; event: InteractionEvent | null; onSite: (id: string) => void; onHousehold: (id: string) => void;
}) {
  if (!event) return <aside className="terminal-panel terminal-detail-empty"><span className="terminal-panel-code">EVENT INSPECTOR</span>
    <p>Select a record to inspect its result, service timing, and related household or site.</p></aside>;
  const site = trace.sites.find(candidate => candidate.id === event.site_id);
  return <aside className="terminal-panel terminal-event-detail">
    <div className="terminal-panel-heading"><div><span className="terminal-panel-code">EVENT INSPECTOR / {at(event.simulation_time, trace.start_time, trace.timezone)}</span>
      <h3>{words(event.action)}</h3></div><em className={'terminal-result result-' + event.result.toLowerCase().replace(/[^a-z0-9]+/g, '-')}>{words(event.result)}</em></div>
    <dl className="terminal-definitions">
      <div><dt>Event ID</dt><dd>{event.event_id}</dd></div>
      {event.household_id && <div><dt>Household</dt><dd>{event.household_id}</dd></div>}
      {event.site_id && <div><dt>Site</dt><dd>{site?.name ?? event.site_id}</dd></div>}
      {event.quantity_grams > 0 && <div><dt>Quantity</dt><dd>{grams(event.quantity_grams)}</dd></div>}
      {event.payment_cents > 0 && <div><dt>Payment</dt><dd>{dollars(event.payment_cents)}</dd></div>}
      <div><dt>Travel / queue / service</dt><dd>{duration(event.travel_seconds)} / {duration(event.queue_seconds)} / {duration(event.service_seconds)}</dd></div>
      {event.denial_or_failure_reason && <div><dt>Reason</dt><dd>{words(event.denial_or_failure_reason)}</dd></div>}
      <div><dt>Evidence state</dt><dd>{words(event.evidence_state)}</dd></div>
    </dl>
    <div className="terminal-detail-links">
      {event.household_id && <button onClick={() => onHousehold(event.household_id!)}>Open household <ArrowRight size={13} /></button>}
      {event.site_id && <button onClick={() => onSite(event.site_id!)}>Open site <ArrowRight size={13} /></button>}
    </div>
  </aside>;
}

export function DashboardPage() {
  const [section, setSection] = useState<DashboardSection>(sectionFromQuery);
  const [trace, setTrace] = useState<FoodTrace | null>(null);
  const [runRef, setRunRef] = useState<RunRef>(runRefFromQuery);
  const [policy, setPolicy] = useState<'baseline' | 'emergency' | 'council'>(() => {
    const initial = runRefFromQuery(); return initial.kind === 'council' ? 'council' : initial.policy;
  });
  const [population, setPopulation] = useState(() => {
    const initial = runRefFromQuery();
    return initial.kind === 'preset' ? initial.population : populationFromQuery();
  });
  const [playhead, setPlayhead] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [query, setQuery] = useState('');
  const [actionFilter, setActionFilter] = useState('all');
  const [resultFilter, setResultFilter] = useState('all');
  const [siteFilter, setSiteFilter] = useState('all');
  const [siteTypeFilter, setSiteTypeFilter] = useState('all');
  const [eventLimit, setEventLimit] = useState(60);
  const [householdQuery, setHouseholdQuery] = useState('');
  const [householdLimit, setHouseholdLimit] = useState(80);
  const [groupBy, setGroupBy] = useState<GroupDimension>('income_band');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(() => new URLSearchParams(window.location.search).get('site'));
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<string | null>(null);
  const [liveState, setLiveState] = useState<LiveRunState | null>(null);
  const [now, setNow] = useState(Date.now());
  const liveChannel = useRef<BroadcastChannel | null>(null);
  const activeRunRef = useRef(runRef);
  useEffect(() => { activeRunRef.current = runRef; }, [runRef]);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(null); setTrace(null); setPlayhead(0);
    setSelectedEventId(null); setSelectedHouseholdId(null); setEventLimit(60); setHouseholdLimit(80);
    void loadRunTrace(runRef).then(next => {
      if (active) {
        setTrace(next); setPlayhead(timeFromQuery(next.horizon_seconds));
        setPopulation(next.population); setPolicy(next.policy);
      }
    }).catch(reason => {
      if (active) setError(reason instanceof Error ? reason.message : 'The run could not be loaded.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [runRef, retry]);

  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return;
    const channel = new BroadcastChannel(LIVE_RUN_CHANNEL);
    liveChannel.current = channel;
    channel.onmessage = event => {
      if (!isLiveRunState(event.data)) return;
      if (!sameRunRef(event.data.run_ref, activeRunRef.current)) return;
      setLiveState(event.data);
      setNow(Date.now());
      setPopulation(event.data.population);
      setPolicy(event.data.policy);
      setPlayhead(Math.max(0, Math.min(event.data.seconds, event.data.horizon_seconds)));
    };
    return () => { channel.close(); liveChannel.current = null; };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (trace && selectedSiteId && !trace.sites.some(site => site.id === selectedSiteId)) setSelectedSiteId(null);
  }, [selectedSiteId, trace]);

  const view = useMemo(() => trace ? foodView(trace, playhead) : null, [trace, playhead]);
  const timeline = useMemo(() => trace ? foodTimeline(trace, view?.seconds ?? playhead) : [], [trace, view?.seconds, playhead]);
  const stockHistory = useMemo(() => trace ? siteStockHistory(trace, view?.seconds ?? playhead) : [], [trace, view?.seconds, playhead]);
  const liveConnected = !!liveState && now - liveState.published_at < 5000
    && sameRunRef(liveState.run_ref, runRef)
    && (!trace || (liveState.scenario_id === trace.scenario_id && liveState.seed === trace.seed
      && liveState.input_snapshot_id === (trace.data_snapshot?.content.snapshot_id ?? null)
      && liveState.source_snapshot_id === (trace.data_snapshot?.content.source_snapshot_id ?? null)));
  const actionOptions = useMemo(() => [...new Set(view?.events.map(event => event.action) ?? [])].sort(), [view]);
  const resultOptions = useMemo(() => [...new Set(view?.events.map(event => event.result) ?? [])].sort(), [view]);
  const filteredEvents = useMemo(() => {
    if (!trace || !view) return [];
    const needle = query.trim().toLowerCase();
    return view.events.filter(event => {
      const site = trace.sites.find(candidate => candidate.id === event.site_id);
      const matchesText = !needle || [event.action, event.result, event.household_id ?? '', event.site_id ?? '',
        site?.name ?? '', event.denial_or_failure_reason ?? ''].some(value => value.toLowerCase().includes(needle));
      return matchesText && (actionFilter === 'all' || event.action === actionFilter)
        && (resultFilter === 'all' || event.result === resultFilter)
        && (siteFilter === 'all' || event.site_id === siteFilter);
    }).slice().reverse();
  }, [actionFilter, query, resultFilter, siteFilter, trace, view]);
  const filteredHouseholds = useMemo(() => {
    if (!trace) return [];
    const needle = householdQuery.trim().toLowerCase();
    return trace.households.filter(household => [household.id, household.area, household.income_band, household.mobility, String(household.size)]
      .some(value => value.toLowerCase().includes(needle)));
  }, [householdQuery, trace]);
  const groupedHouseholds = useMemo(() => {
    if (!trace || !view) return [];
    const groups = new Map<string, { count: number; obtained: number; unmet: number; spending: number }>();
    for (const household of trace.households) {
      const label = String(household[groupBy]);
      const group = groups.get(label) ?? { count: 0, obtained: 0, unmet: 0, spending: 0 };
      const state = view.households[household.id]!;
      group.count++;
      group.obtained += state.purchased_grams + state.received_grams;
      group.unmet += state.unmet_grams;
      group.spending += state.expenditure_cents;
      groups.set(label, group);
    }
    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right));
  }, [groupBy, trace, view]);

  const selectedEvent = view?.events.find(event => event.event_id === selectedEventId) ?? null;
  const selectedSite = trace?.sites.find(site => site.id === selectedSiteId) ?? null;
  const selectedHousehold = trace?.households.find(household => household.id === selectedHouseholdId) ?? null;
  const siteIds = trace ? [...new Set([...trace.sites.map(site => site.id), ...(view?.events.map(event => event.site_id).filter((id): id is string => id !== null) ?? [])])] : [];
  const sites = trace ? trace.sites.filter(site => siteTypeFilter === 'all' || site.type === siteTypeFilter) : [];

  function chooseSection(next: DashboardSection) {
    setSection(next);
    const url = new URL(window.location.href);
    url.searchParams.set('view', next);
    window.history.replaceState(null, '', url);
  }
  function chooseRun(nextPopulation: number, nextPolicy: 'baseline' | 'emergency') {
    const nextRunRef: RunRef = { kind: 'preset', population: nextPopulation, policy: nextPolicy };
    if (liveConnected) {
      const command: DashboardCommand = { type: 'dashboard-select-run', run_ref: nextRunRef };
      liveChannel.current?.postMessage(command);
    }
    const url = new URL(window.location.href);
    url.searchParams.set('population', String(nextPopulation));
    url.searchParams.set('policy', nextPolicy);
    url.searchParams.delete('run');
    url.searchParams.delete('time');
    window.history.replaceState(null, '', url);
    setPopulation(nextPopulation); setPolicy(nextPolicy); setRunRef(nextRunRef);
  }
  function chooseCouncilArm(arm: 'baseline' | 'intervention') {
    if (runRef.kind !== 'council' || runRef.arm === arm) return;
    const nextRunRef: RunRef = { kind: 'council', run_id: runRef.run_id, arm };
    if (liveConnected) {
      const command: DashboardCommand = { type: 'dashboard-select-run', run_ref: nextRunRef };
      liveChannel.current?.postMessage(command);
    }
    const url = new URL(window.location.href);
    url.searchParams.set('run', serializeRunRef(nextRunRef) ?? '');
    url.searchParams.delete('population'); url.searchParams.delete('policy');
    window.history.replaceState(null, '', url);
    setRunRef(nextRunRef); setPolicy('council');
  }
  function chooseTime(seconds: number) {
    if (liveConnected) {
      const command: DashboardCommand = { type: 'dashboard-seek', run_ref: runRef, seconds };
      liveChannel.current?.postMessage(command);
    }
    setPlayhead(seconds);
    const url = new URL(window.location.href);
    url.searchParams.set('time', String(Math.floor(seconds)));
    window.history.replaceState(null, '', url);
  }
  function selectEvent(event: InteractionEvent) {
    setSelectedEventId(event.event_id);
    setSelectedSiteId(event.site_id);
    chooseTime(event.simulation_time);
    const url = new URL(window.location.href);
    url.searchParams.set('time', String(Math.floor(event.simulation_time)));
    if (event.site_id) url.searchParams.set('site', event.site_id);
    else url.searchParams.delete('site');
    window.history.replaceState(null, '', url);
  }
  function selectSite(id: string) { setSelectedSiteId(id); chooseSection('sites'); }
  function selectHousehold(id: string) { setSelectedHouseholdId(id); chooseSection('households'); }
  function downloadRun() {
    if (!trace) return;
    const payload = { run: trace, displayed_through_seconds: playhead, section, filters: { actionFilter, resultFilter, siteFilter } };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url; link.download = 'food-access-' + trace.population + '-' + trace.policy + '-run.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <main className="analytics-shell">
    <aside className="analytics-rail">
      <a className="analytics-brand" href="/" aria-label="Back to The Sims 6ix simulation">
        <span className="analytics-brand-mark">6</span><span>THE SIMS <b>6IX</b><small>TORONTO SIMULATION</small></span>
      </a>
      <nav className="analytics-nav" aria-label="Analytics sections">
        {sections.map(item => <button type="button" key={item.id} aria-current={section === item.id ? 'page' : undefined}
          className={section === item.id ? 'active' : ''} onClick={() => chooseSection(item.id)}>
          <span>{item.label}</span><i />
        </button>)}
      </nav>
    </aside>

    <div className="analytics-workspace">
      <header className="analytics-topbar">
        <div className="analytics-top-actions"><span className="readonly-badge" title={liveConnected ? 'Synchronized to the simulation tab' : 'Showing the selected committed trace'}><i />
            {trace && view && view.seconds >= trace.horizon_seconds ? 'COMPLETE' : liveConnected ? liveState?.paused ? 'PAUSED' : 'SYNCED' : 'LOCAL REPLAY'}</span>
          <a target="_blank" rel="noreferrer" href={cityUrl(runRef, view?.seconds ?? 0, selectedSiteId,
            selectedEvent?.resident_id !== null && selectedEvent ? selectedEvent.resident_id : null)} className="city-link">Open city <ArrowDownLeft size={14} /></a>
        </div>
      </header>

      <div className="analytics-content">
        <section className="analytics-heading">
          <div><span className="analytics-kicker">FOOD ACCESS</span><h1>Run dashboard</h1>
            <p>Simulation outcomes and service activity.</p></div>
          <button className="analytics-export" type="button" onClick={downloadRun} disabled={!trace}><Download size={15} /> Export run data</button>
        </section>

        <section className="analytics-commandbar" aria-label="Run selection">
          <label><span>SCENARIO</span><select value={policy} onChange={event => {
            if (event.target.value === 'baseline' || event.target.value === 'emergency') chooseRun(population, event.target.value);
          }}>
            <option value="baseline">Baseline / no intervention</option><option value="emergency">Emergency food site</option>
            <option value="council" disabled={runRef.kind !== 'council'}>Council run</option>
          </select></label>
          <label><span>POPULATION</span><select value={population} onChange={event => chooseRun(Number(event.target.value), policy === 'council' ? 'baseline' : policy)}>
            {[200, 600, 1200, 2400].map(count => <option value={count} key={count}>{count.toLocaleString()} household agents</option>)}
          </select></label>
        </section>

        {runRef.kind === 'council' && <section className="council-arm-control" aria-label="Council run comparison">
          <div><span className="analytics-kicker">EXACT COUNCIL RUN</span><b>{runRef.run_id}</b>
            <small>Baseline and intervention are stored arms of this same run.</small></div>
          <label><span>COMPARISON ARM</span><select value={runRef.arm} onChange={event => {
            if (event.target.value === 'baseline' || event.target.value === 'intervention') chooseCouncilArm(event.target.value);
          }}>
            <option value="baseline">Paired baseline</option><option value="intervention">Intervention</option>
          </select></label>
        </section>}

        {loading && <div className="analytics-state" role="status"><span className="loading-diamond"><span /></span><b>Loading committed run data</b><small>Rebuilding the event projection for this run.</small></div>}
        {!loading && error && <div className="analytics-state analytics-error" role="alert"><b>Run data unavailable</b><p>{error}</p>
          <button type="button" onClick={() => setRetry(value => value + 1)}>Retry load <ArrowRight size={14} /></button></div>}
        {!loading && trace && view && <>
          <section className="analytics-time-control">
            <div><span><Clock3 size={14} /> SIMULATION TIME</span><b>{at(0, trace.start_time, trace.timezone)} — {at(view.seconds, trace.start_time, trace.timezone)}</b></div>
            <input aria-label="Run time playhead" type="range" min="0" max={trace.horizon_seconds} step="60"
              value={Math.floor(view.seconds)} onChange={event => chooseTime(Number(event.target.value))} />
            <div className="time-control-scale"><span>{at(0, trace.start_time, trace.timezone)} START</span><span>{at(trace.horizon_seconds, trace.start_time, trace.timezone)} END</span></div>
          </section>

          {section === 'overview' && <section className="analytics-section">
            <div className="analytics-section-title"><h2>Overview</h2></div>
            <div className="analytics-live-grid" aria-label="Live simulation charts">
              <section className="terminal-panel">
                <div className="terminal-panel-heading"><div><span className="terminal-panel-code">HOUSEHOLD FOOD / CUMULATIVE</span><h3>Produce flow through the run</h3></div>
                  <span className="panel-unit">KG</span></div>
                <FoodFlowChart trace={trace} points={timeline} seconds={view.seconds} />
              </section>
              <section className="terminal-panel">
                <div className="terminal-panel-heading"><div><span className="terminal-panel-code">COMMITTED EVENTS / CUMULATIVE</span><h3>Service and purchase activity</h3></div>
                  <span className="panel-unit">EVENTS</span></div>
                <ServiceActivityChart trace={trace} points={timeline} seconds={view.seconds} />
              </section>
              <section className="terminal-panel site-chart-panel">
                <div className="terminal-panel-heading"><div><span className="terminal-panel-code">SCENARIO PROJECTION / INVENTORY</span><h3>Modeled site stock</h3></div>
                  <span className="panel-unit">KG</span></div>
                <SiteStockChart trace={trace} points={stockHistory} seconds={view.seconds} />
              </section>
            </div>

          </section>}

          {section === 'interactions' && <section className="analytics-section">
            <div className="analytics-section-title"><h2>Interaction log</h2></div>
            <div className="terminal-filterbar">
              <label className="terminal-search"><Search size={15} /><input aria-label="Search interactions" placeholder="Search household, site, or reason"
                value={query} onChange={event => { setQuery(event.target.value); setEventLimit(60); }} /></label>
              <label><span>ACTION</span><select value={actionFilter} onChange={event => { setActionFilter(event.target.value); setEventLimit(60); }}>
                <option value="all">All actions</option>{actionOptions.map(action => <option value={action} key={action}>{words(action)}</option>)}</select></label>
              <label><span>RESULT</span><select value={resultFilter} onChange={event => { setResultFilter(event.target.value); setEventLimit(60); }}>
                <option value="all">All results</option>{resultOptions.map(result => <option value={result} key={result}>{words(result)}</option>)}</select></label>
              <label><span>SITE</span><select value={siteFilter} onChange={event => { setSiteFilter(event.target.value); setEventLimit(60); }}>
                <option value="all">All sites</option>{siteIds.map(id => <option value={id} key={id}>{trace.sites.find(site => site.id === id)?.name ?? id}</option>)}</select></label>
            </div>
            <div className="analytics-detail-layout">
              <section className="terminal-panel terminal-table-panel">
                <div className="terminal-event-head"><span>TIME</span><span>ACTION / SUBJECT</span><span>RESULT</span><span>QUANTITY</span><span>PAYMENT</span></div>
                {filteredEvents.length ? <div className="terminal-event-list">{filteredEvents.slice(0, eventLimit).map(event =>
                  <EventRow key={event.event_id} trace={trace} event={event} selected={event.event_id === selectedEvent?.event_id} onSelect={selectEvent} />)}</div>
                  : <p className="terminal-empty">No events match the selected filters through {at(view.seconds, trace.start_time, trace.timezone)}.</p>}
                {filteredEvents.length > eventLimit && <button className="terminal-load-more" onClick={() => setEventLimit(limit => limit + 60)}>Load 60 earlier events</button>}
              </section>
              <EventDetails trace={trace} event={selectedEvent} onSite={selectSite} onHousehold={selectHousehold} />
            </div>
          </section>}

          {section === 'sites' && <section className="analytics-section">
            <div className="analytics-section-title"><h2>Sites & services</h2></div>
            <div className="terminal-filterbar site-filterbar">
              <label><span>LOCATION TYPE</span><select value={siteTypeFilter} onChange={event => setSiteTypeFilter(event.target.value)}>
                <option value="all">All locations</option>{['retailer', 'support', 'school', 'emergency', 'council'].map(type => <option key={type} value={type}>{words(type)}</option>)}</select></label>
            </div>
            <div className="analytics-detail-layout">
              <section className="terminal-panel terminal-table-panel">
                <div className="terminal-site-head"><span>LOCATION</span><span>STATUS</span><span>STOCK</span><span>VISITS / DENIALS</span><span>SERVED</span><span>REVENUE</span></div>
                <div className="terminal-site-list">{sites.map(site => {
                  const state = view.sites[site.id]!;
                  return <button type="button" className={'terminal-site-row' + (selectedSiteId === site.id ? ' selected' : '')}
                    aria-pressed={selectedSiteId === site.id} key={site.id} onClick={() => setSelectedSiteId(site.id)}>
                    <span><b>{site.name}</b><small>{words(site.type)} / {site.id}</small></span><span>{siteStatus(site, view.seconds, trace.start_time, trace.timezone)}</span>
                    <span>{grams(state.stock_grams)}</span><span>{state.visits} / {state.denials}</span>
                    <span>{state.served} / {state.capacity}</span><span>{dollars(state.revenue_cents)}</span>
                  </button>;
                })}</div>
              </section>
              <aside className="terminal-panel terminal-event-detail">
                {selectedSite ? <><div className="terminal-panel-heading"><div><span className="terminal-panel-code">SITE RECORD / {words(selectedSite.type)}</span>
                    <h3>{selectedSite.name}</h3></div><span className="site-state-chip">{siteStatus(selectedSite, view.seconds, trace.start_time, trace.timezone)}</span></div>
                  <p className="terminal-site-note">{selectedSite.source_id
                    ? `City-listed location from ${selectedSite.source_snapshot_id}. Current operating status is unknown; price, stock, hours, capacity, eligibility, and modeled activity remain illustrative.`
                    : `Synthetic intervention location and operating values under ${trace.scenario_id}.`}</p>
                  <dl className="terminal-definitions">
                    {selectedSite.source_record_url && <div><dt>Location source</dt><dd><a href={selectedSite.source_record_url} target="_blank" rel="noreferrer">{selectedSite.source_id} / {selectedSite.source_record_id}</a></dd></div>}
                    {selectedSite.source_retrieved_at && <div><dt>Snapshot retrieved</dt><dd>{selectedSite.source_retrieved_at}</dd></div>}
                    <div><dt>Service window</dt><dd>{at(selectedSite.opens, trace.start_time, trace.timezone)} — {at(selectedSite.closes, trace.start_time, trace.timezone)}</dd></div>
                    <div><dt>Eligibility</dt><dd>{selectedSite.eligible}</dd></div>
                    <div><dt>Current stock</dt><dd>{grams(view.sites[selectedSite.id]!.stock_grams)}</dd></div>
                    <div><dt>Price / 100 g</dt><dd>{dollars(view.sites[selectedSite.id]!.price_cents_per_100g)}</dd></div>
                    <div><dt>Served / capacity</dt><dd>{view.sites[selectedSite.id]!.served} / {view.sites[selectedSite.id]!.capacity}</dd></div>
                    <div><dt>Distributed / sold</dt><dd>{grams(view.sites[selectedSite.id]!.sold_grams)}</dd></div>
                    <div><dt>Replenishment</dt><dd>{grams(view.sites[selectedSite.id]!.received_grams)}</dd></div>
                    <div><dt>Revenue / procurement</dt><dd>{dollars(view.sites[selectedSite.id]!.revenue_cents)} / {dollars(view.sites[selectedSite.id]!.spending_cents)}</dd></div>
                  </dl>
                  <h4 className="terminal-subheading">Recent site activity</h4>
                  <div className="terminal-event-list compact">{view.events.filter(event => event.site_id === selectedSite.id).slice(-8).reverse().map(event =>
                    <EventRow key={event.event_id} trace={trace} event={event} selected={event.event_id === selectedEvent?.event_id} onSelect={selected => { selectEvent(selected); chooseSection('interactions'); }} />)}</div>
                </> : <div className="terminal-detail-empty"><span className="terminal-panel-code">SITE INSPECTOR</span><p>Select a location to inspect availability, inventory, throughput, and activity.</p></div>}
              </aside>
            </div>
          </section>}

          {section === 'households' && <section className="analytics-section">
            <div className="analytics-section-title"><h2>Households</h2></div>
            <section className="terminal-panel cohort-panel">
              <div className="terminal-panel-heading"><div><span className="terminal-panel-code">GROUPED OUTCOMES</span><h3>Average per household</h3></div>
                <label className="terminal-inline-select"><span>GROUP BY</span><select value={groupBy} onChange={event => setGroupBy(event.target.value as GroupDimension)}>
                  <option value="income_band">Income band</option><option value="area">Area</option><option value="mobility">Mobility</option><option value="size">Household size</option>
                </select></label></div>
              <p className="cohort-note">Per-household averages for this synthetic run. Group counts are shown; treat these values as descriptive.</p>
              <div className="terminal-group-head"><span>GROUP</span><span>HOUSEHOLDS</span><span>FOOD OBTAINED / HH</span><span>UNMET PRODUCE / HH</span><span>SPENDING / HH</span></div>
              <div className="terminal-group-list">{groupedHouseholds.map(([label, group]) => <div className="terminal-group-row" key={label}>
                <b>{label}</b><span>{group.count.toLocaleString()}</span><span>{grams(Math.round(group.obtained / group.count))}</span>
                <span>{grams(Math.round(group.unmet / group.count))}</span><span>{dollars(Math.round(group.spending / group.count))}</span>
              </div>)}</div>
            </section>
            <div className="analytics-detail-layout household-detail-layout">
              <section className="terminal-panel terminal-table-panel">
                <label className="terminal-search household-search"><Search size={15} /><input aria-label="Search households" placeholder="Search ID, area, income, or mobility"
                  value={householdQuery} onChange={event => { setHouseholdQuery(event.target.value); setHouseholdLimit(80); }} /></label>
                <div className="terminal-household-head"><span>HOUSEHOLD</span><span>AREA / PROFILE</span><span>FOOD OBTAINED</span><span>UNMET PRODUCE</span><span>SPENDING</span></div>
                <div className="terminal-household-list">{filteredHouseholds.slice(0, householdLimit).map(household => {
                  const state = view.households[household.id]!;
                  return <button type="button" key={household.id} aria-pressed={selectedHouseholdId === household.id}
                    className={'terminal-household-row' + (selectedHouseholdId === household.id ? ' selected' : '')}
                    onClick={() => setSelectedHouseholdId(household.id)}>
                    <b>{household.id}</b><span>{household.area} / {household.size} people / {household.income_band}</span>
                    <span>{grams(state.purchased_grams + state.received_grams)}</span><span>{grams(state.unmet_grams)}</span><span>{dollars(state.expenditure_cents)}</span>
                  </button>;
                })}</div>
                {filteredHouseholds.length > householdLimit && <button className="terminal-load-more" onClick={() => setHouseholdLimit(limit => limit + 80)}>Load 80 more households</button>}
              </section>
              <aside className="terminal-panel household-inspector">
                {selectedHousehold && view ? <><div className="terminal-panel-heading"><div><span className="terminal-panel-code">HOUSEHOLD RECORD</span><h3>{selectedHousehold.id}</h3></div>
                    <span className="household-icon"><Users size={15} /></span></div>
                  <HouseholdDetails household={selectedHousehold} view={view} startTime={trace.start_time} timezone={trace.timezone} /></>
                  : <div className="terminal-detail-empty"><span className="terminal-panel-code">HOUSEHOLD INSPECTOR</span><p>Select a household to inspect its modeled resources, food use, and event history.</p></div>}
              </aside>
            </div>
          </section>}

          <footer className="analytics-footnote">
            <span>Synthetic scenario output; not observed Toronto service data.</span>
            <details className="terminal-assumptions">
              <summary>Run notes and provenance</summary>
              <p>{trace.scenario_id} / {trace.policy} / seed {trace.seed} / {trace.population.toLocaleString()} synthetic household agents. Evidence: {words(trace.evidence_state)}.</p>
              {trace.data_snapshot && <p>Ingested input: {trace.data_snapshot.content.snapshot_id}. Retrieved source: {trace.data_snapshot.content.source_snapshot_id}.</p>}
              <p>{trace.assumptions.food_use} Crossing wait: {trace.assumptions.crossing_delay_seconds} seconds. {trace.assumptions.scope}</p>
              <p>Parameter set: {trace.assumptions.parameter_id}. Unknown inputs: {trace.assumptions.unknown_inputs.join(', ') || 'None listed'}.</p>
              <p>Prices, stock, hours, capacity, eligibility, and service activity are illustrative where the trace does not provide observed values.</p>
            </details>
          </footer>
        </>}
      </div>
    </div>
  </main>;
}
