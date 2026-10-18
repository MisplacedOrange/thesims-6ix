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
  { id: 'overview', label: 'Summary' },
  { id: 'interactions', label: 'Events' },
  { id: 'sites', label: 'Sites' },
  { id: 'households', label: 'Households' },
];
const isDashboardSection = (value: string | null): value is DashboardSection =>
  sections.some(section => section.id === value);
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

function dateTimeAt(seconds: number, startTime: string, timezone = 'America/Toronto') {
  const hasOffset = /(?:Z|[+-]\d{2}:\d{2})$/.test(startTime);
  if (hasOffset) {
    const date = new Date(Date.parse(startTime) + Math.floor(seconds) * 1000);
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone, year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).format(date);
  }
  const start = startTime.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
  if (!start) return at(seconds, startTime, timezone);
  const date = new Date(Date.UTC(Number(start[1]), Number(start[2]) - 1, Number(start[3]),
    Number(start[4]), Number(start[5]), Number(start[6])) + Math.floor(seconds) * 1000);
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'UTC', year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).format(date);
}

function localDateAt(seconds: number, startTime: string, timezone = 'America/Toronto') {
  const hasOffset = /(?:Z|[+-]\d{2}:\d{2})$/.test(startTime);
  let date: Date;
  if (hasOffset) date = new Date(Date.parse(startTime) + Math.floor(seconds) * 1000);
  else {
    const start = startTime.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
    if (!start) return '';
    date = new Date(Date.UTC(Number(start[1]), Number(start[2]) - 1, Number(start[3]),
      Number(start[4]), Number(start[5]), Number(start[6])) + Math.floor(seconds) * 1000);
  }
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: hasOffset ? timezone : 'UTC', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date);
  return `${parts.find(part => part.type === 'year')?.value}-${parts.find(part => part.type === 'month')?.value}-${parts.find(part => part.type === 'day')?.value}`;
}

function timeRangeAt(seconds: number, startTime: string, timezone?: string) {
  if (localDateAt(0, startTime, timezone) !== localDateAt(seconds, startTime, timezone)) {
    return `${dateTimeAt(0, startTime, timezone)} — ${dateTimeAt(seconds, startTime, timezone)}`;
  }
  return `${at(0, startTime, timezone)} — ${at(seconds, startTime, timezone)}`;
}

function siteStatus(site: Site, seconds: number, startTime: string, timezone?: string) {
  if (seconds < site.active_from) return 'Scheduled ' + at(site.active_from, startTime, timezone);
  if (seconds < site.opens || seconds >= site.closes) return 'Closed';
  return 'Open';
}

function EventRow({ trace, event, selected, onSelect }: {
  trace: FoodTrace; event: InteractionEvent; selected: boolean; onSelect: (event: InteractionEvent) => void;
}) {
  const site = trace.sites.find(candidate => candidate.id === event.site_id);
  const subject = event.household_id ? `Household ${event.household_id}`
    : site ? `Site ${site.name}` : event.site_id ? `Site ${event.site_id}` : 'City activity';
  const amount = event.quantity_grams > 0 ? grams(event.quantity_grams)
    : event.portions ? event.portions + ' portions' : 'None';
  const status = event.result.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  return <button type="button" className={'terminal-event-row' + (selected ? ' selected' : '')}
    aria-pressed={selected} onClick={() => onSelect(event)}>
    <time data-label="Time">{at(event.simulation_time, trace.start_time, trace.timezone)}</time>
    <span data-label="Action and subject" className="terminal-event-action"><b>{words(event.action)}</b><small>{subject}{event.household_id && site ? ` · Site ${site.name}` : ''}</small></span>
    <em data-label="Result" className={'terminal-result result-' + status}>{words(event.result)}</em>
    <span data-label="Quantity" className="terminal-event-amount">{amount}</span>
    <span data-label="Payment" className="terminal-event-cash">{event.payment_cents > 0 ? dollars(event.payment_cents) : 'None'}</span>
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
    <text x="8" y="18" className="terminal-axis-unit">{units}</text>
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
    <svg viewBox="0 0 1040 320" role="img" aria-label="Cumulative produce purchased, received, and consumed over simulation time">
      <ChartGrid maximum={maximumGrams / 1000} units="kg" horizon={trace.horizon_seconds} startTime={trace.start_time} timezone={trace.timezone} />
      {series.map(item => <g key={item.key}>
        <path d={chartPath(points, trace.horizon_seconds, maximumGrams, point => point[item.key])} className="terminal-chart-series" style={{ stroke: item.color }} />
        <circle cx={cursorX} cy={chartBox.bottom - current[item.key] / maximumGrams * (chartBox.bottom - chartBox.top)} r="5" className="terminal-chart-point" style={{ fill: item.color }}>
          <title>{item.label}: {(current[item.key] / 1000).toFixed(2)} kg at {at(seconds, trace.start_time, trace.timezone)}</title>
        </circle>
      </g>)}
      <line x1={cursorX} x2={cursorX} y1={chartBox.top} y2={chartBox.bottom} className="terminal-live-cursor" />
    </svg>
    <div className="terminal-chart-legend">{series.map(item => <span key={item.key}><i style={{ backgroundColor: item.color }} />{item.label}</span>)}</div>
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
    <svg viewBox="0 0 1040 320" role="img" aria-label="Cumulative completed services, service denials, and no-purchase decisions over simulation time">
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
  </div>;
}

function SiteStockChart({ trace, points, seconds }: { trace: FoodTrace; points: SiteStockPoint[]; seconds: number }) {
  const maximumGrams = useMemo(() => Math.max(1000,
    ...Object.values(trace.initial_sites).map(state => state.stock_grams),
    ...trace.events.map(event => event.site_state?.stock_grams ?? 0)), [trace]);
  const cursorX = chartBox.left + Math.min(1, seconds / Math.max(1, trace.horizon_seconds)) * (chartBox.right - chartBox.left);
  return <div className="terminal-chart">
    <svg viewBox="0 0 1040 320" role="img" aria-label="Site inventory over simulation time">
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
  </div>;
}

function EventDetails({ trace, event, onSite, onHousehold }: {
  trace: FoodTrace; event: InteractionEvent | null; onSite: (id: string) => void; onHousehold: (id: string) => void;
}) {
  if (!event) return <aside className="terminal-panel terminal-detail-empty"><p>Select an event to view its details.</p></aside>;
  const site = trace.sites.find(candidate => candidate.id === event.site_id);
  return <aside className="terminal-panel terminal-event-detail">
    <div className="terminal-panel-heading"><div><span className="terminal-panel-code">Event details · {at(event.simulation_time, trace.start_time, trace.timezone)}</span>
      <h3>{words(event.action)}</h3></div><em className={'terminal-result result-' + event.result.toLowerCase().replace(/[^a-z0-9]+/g, '-')}>{words(event.result)}</em></div>
    <dl className="terminal-definitions">
      <div><dt>Event ID</dt><dd>{event.event_id}</dd></div>
      {event.household_id && <div><dt>Household</dt><dd>{event.household_id}</dd></div>}
      {event.site_id && <div><dt>Site</dt><dd>{site?.name ?? event.site_id}</dd></div>}
      <div><dt>Quantity</dt><dd>{event.quantity_grams > 0 ? grams(event.quantity_grams) : event.portions ? `${event.portions} portions` : 'None'}</dd></div>
      <div><dt>Payment</dt><dd>{event.payment_cents > 0 ? dollars(event.payment_cents) : 'None'}</dd></div>
      <div><dt>Travel time</dt><dd>{duration(event.travel_seconds)}</dd></div>
      <div><dt>Queue time</dt><dd>{duration(event.queue_seconds)}</dd></div>
      <div><dt>Service time</dt><dd>{duration(event.service_seconds)}</dd></div>
      {event.denial_or_failure_reason && <div><dt>Reason</dt><dd>{words(event.denial_or_failure_reason)}</dd></div>}
      <div><dt>Evidence</dt><dd>{words(event.evidence_state)}</dd></div>
    </dl>
    <div className="terminal-detail-links">
      {event.household_id && <button onClick={() => onHousehold(event.household_id!)}>View household <ArrowRight size={13} /></button>}
      {event.site_id && <button onClick={() => onSite(event.site_id!)}>View site <ArrowRight size={13} /></button>}
    </div>
  </aside>;
}

export function DashboardPage() {
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
  const [activeSection, setActiveSection] = useState<DashboardSection>('overview');
  const [liveState, setLiveState] = useState<LiveRunState | null>(null);
  const [now, setNow] = useState(Date.now());
  const liveChannel = useRef<BroadcastChannel | null>(null);
  const activeRunRef = useRef(runRef);
  const workspaceRef = useRef<HTMLDivElement | null>(null);
  const initialNavigationHandled = useRef(false);
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
    if (loading || !trace || initialNavigationHandled.current) return;
    initialNavigationHandled.current = true;
    const url = new URL(window.location.href);
    const hashSection = isDashboardSection(url.hash.slice(1)) ? url.hash.slice(1) as DashboardSection : null;
    const legacyView = isDashboardSection(url.searchParams.get('view')) ? url.searchParams.get('view') as DashboardSection : null;
    const target = hashSection ?? legacyView ?? (selectedSiteId ? 'sites' : null);
    if (url.searchParams.has('view')) url.searchParams.delete('view');
    if (!target) {
      window.history.replaceState(null, '', url);
      return;
    }
    setActiveSection(target);
    url.hash = target;
    window.history.replaceState(null, '', url);
    requestAnimationFrame(() => document.getElementById(target)?.scrollIntoView({
      block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    }));
  }, [loading, selectedSiteId, trace]);

  useEffect(() => {
    const workspace = workspaceRef.current;
    if (!workspace || loading || !trace) return;
    const observer = new IntersectionObserver(entries => {
      const current = entries.filter(entry => entry.isIntersecting)
        .sort((left, right) => left.boundingClientRect.top - right.boundingClientRect.top)[0];
      if (current && isDashboardSection(current.target.id)) setActiveSection(current.target.id);
    }, { root: workspace, rootMargin: '-120px 0px -60% 0px', threshold: 0 });
    sections.forEach(({ id }) => {
      const target = workspace.querySelector<HTMLElement>(`#${id}`);
      if (target) observer.observe(target);
    });
    return () => observer.disconnect();
  }, [loading, trace]);

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
    if (!liveState?.live_trace_url || trace?.live_day === liveState.live_day
        && trace?.live_trace_url === liveState.live_trace_url) return;
    let active = true;
    void fetch(liveState.live_trace_url).then(async response => {
      if (!response.ok) throw new Error('The current simulation day could not load.');
      return await response.json() as FoodTrace;
    }).then(next => {
      if (!active) return;
      setTrace(next); setSelectedEventId(null); setEventLimit(60);
    }).catch(reason => { if (active) setError(reason instanceof Error ? reason.message : 'Live day unavailable.'); });
    return () => { active = false; };
  }, [liveState?.live_trace_url, liveState?.live_day, trace?.live_trace_url, trace?.live_day]);

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

  function scrollToSection(next: DashboardSection) {
    const target = document.getElementById(next);
    if (!target) return;
    setActiveSection(next);
    target.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    const url = new URL(window.location.href);
    url.searchParams.delete('view');
    url.hash = next;
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
  function selectSite(id: string) { setSelectedSiteId(id); scrollToSection('sites'); }
  function selectHousehold(id: string) { setSelectedHouseholdId(id); scrollToSection('households'); }
  function downloadRun() {
    if (!trace) return;
    const payload = { run: trace, displayed_through_seconds: playhead, filters: { actionFilter, resultFilter, siteFilter } };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url; link.download = 'food-access-' + trace.population + '-' + trace.policy + '-run.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <main className="analytics-shell analytics-single-page">
    <div className="analytics-workspace" ref={workspaceRef}>
      <header className="analytics-topbar">
        <a className="analytics-brand" href="/" aria-label="Back to The Sims 6ix city">
          <span className="analytics-brand-mark">6</span><span>THE SIMS <b>6IX</b><small>TORONTO SIMULATION</small></span>
        </a>
        <div className="analytics-top-actions"><span className="readonly-badge" title={liveConnected ? 'Synchronized with the city simulation' : 'Showing saved run data'}><i />
            {trace && view && view.seconds >= trace.horizon_seconds ? 'Complete' : liveConnected ? liveState?.paused ? 'Paused' : 'Live' : 'Replay'}</span>
          <a target="_blank" rel="noreferrer" href={cityUrl(runRef, view?.seconds ?? 0, selectedSiteId,
            selectedEvent?.resident_id !== null && selectedEvent ? selectedEvent.resident_id : null)} className="city-link">Open city <ArrowDownLeft size={14} /></a>
        </div>
      </header>

      <div className="analytics-content">
        <section className="analytics-heading">
          <div><span className="analytics-kicker">FOOD ACCESS{trace?.live_session_id ? ` · ${trace.local_date} · DAILY TOTALS` : ''}</span><h1>Run dashboard</h1></div>
          <button className="analytics-export" type="button" onClick={downloadRun} disabled={!trace}><Download size={15} /> Export JSON</button>
        </section>

        <section className="analytics-commandbar" aria-label="Run selection">
          <label><span>Scenario</span><select value={policy} onChange={event => {
            if (event.target.value === 'baseline' || event.target.value === 'emergency') chooseRun(population, event.target.value);
          }}>
            <option value="baseline">Baseline (no intervention)</option><option value="emergency">Emergency food site</option>
            <option value="council" disabled={runRef.kind !== 'council'}>Council run</option>
          </select></label>
          <label><span>Household agents</span><select value={population} onChange={event => chooseRun(Number(event.target.value), policy === 'council' ? 'baseline' : policy)}>
            {[200, 600, 1200, 2400].map(count => <option value={count} key={count}>{count.toLocaleString()} household agents</option>)}
          </select></label>
        </section>

        {runRef.kind === 'council' && <section className="council-arm-control" aria-label="Council run comparison">
          <div><span className="analytics-kicker">Council run</span><b>{runRef.run_id}</b>
            <small>Both scenarios use the same run.</small></div>
          <label><span>Scenario arm</span><select value={runRef.arm} onChange={event => {
            if (event.target.value === 'baseline' || event.target.value === 'intervention') chooseCouncilArm(event.target.value);
          }}>
            <option value="baseline">Baseline</option><option value="intervention">Intervention</option>
          </select></label>
        </section>}

        {loading && <div className="analytics-state" role="status"><span className="loading-diamond"><span /></span><b>Loading committed run data</b><small>Rebuilding the event projection for this run.</small></div>}
        {!loading && error && <div className="analytics-state analytics-error" role="alert"><b>Run data unavailable</b><p>{error}</p>
          <button type="button" onClick={() => setRetry(value => value + 1)}>Retry <ArrowRight size={14} /></button></div>}
        {!loading && trace && view && <>
          <section className="analytics-time-control">
            <div><span><Clock3 size={14} /> Simulation time</span><b>{timeRangeAt(view.seconds, trace.start_time, trace.timezone)}</b></div>
            <input aria-label="Simulation time" type="range" min="0" max={trace.horizon_seconds} step="60"
              value={Math.floor(view.seconds)} onChange={event => chooseTime(Number(event.target.value))} />
            <div className="time-control-scale"><span>Start {dateTimeAt(0, trace.start_time, trace.timezone)}</span><span>End {dateTimeAt(trace.horizon_seconds, trace.start_time, trace.timezone)}</span></div>
          </section>

          <nav className="analytics-section-nav" aria-label="Jump to dashboard section">
            <span>Jump to</span>
            {sections.map(item => <a href={'#' + item.id} key={item.id} aria-current={activeSection === item.id ? 'location' : undefined}>
              {item.label}
            </a>)}
          </nav>

          <section id="overview" className="analytics-section" aria-labelledby="overview-heading">
            <div className="analytics-section-title"><h2 id="overview-heading">Summary</h2></div>
            <div className="analytics-live-grid" aria-label="Simulation charts">
              <section className="terminal-panel">
                <div className="terminal-panel-heading"><div><h3>Produce purchased, received, and consumed</h3></div></div>
                <FoodFlowChart trace={trace} points={timeline} seconds={view.seconds} />
              </section>
              <section className="terminal-panel">
                <div className="terminal-panel-heading"><div><h3>Services and purchases</h3></div></div>
                <ServiceActivityChart trace={trace} points={timeline} seconds={view.seconds} />
              </section>
              <section className="terminal-panel site-chart-panel">
                <div className="terminal-panel-heading"><div><h3>Site stock</h3></div></div>
                <SiteStockChart trace={trace} points={stockHistory} seconds={view.seconds} />
              </section>
            </div>

          </section>

          <section id="interactions" className="analytics-section" aria-labelledby="interactions-heading">
            <div className="analytics-section-title"><h2 id="interactions-heading">Events</h2></div>
            <div className="terminal-filterbar">
              <label className="terminal-search"><Search size={15} /><input aria-label="Search events" placeholder="Search events"
                value={query} onChange={event => { setQuery(event.target.value); setEventLimit(60); }} /></label>
              <label><span>Action</span><select value={actionFilter} onChange={event => { setActionFilter(event.target.value); setEventLimit(60); }}>
                <option value="all">All actions</option>{actionOptions.map(action => <option value={action} key={action}>{words(action)}</option>)}</select></label>
              <label><span>Result</span><select value={resultFilter} onChange={event => { setResultFilter(event.target.value); setEventLimit(60); }}>
                <option value="all">All results</option>{resultOptions.map(result => <option value={result} key={result}>{words(result)}</option>)}</select></label>
              <label><span>Site</span><select value={siteFilter} onChange={event => { setSiteFilter(event.target.value); setEventLimit(60); }}>
                <option value="all">All sites</option>{siteIds.map(id => <option value={id} key={id}>{trace.sites.find(site => site.id === id)?.name ?? id}</option>)}</select></label>
            </div>
            <div className="analytics-detail-layout">
              <section className="terminal-panel terminal-table-panel">
                <div className="terminal-event-head"><span>Time</span><span>Action and subject</span><span>Result</span><span>Quantity</span><span>Payment</span></div>
                {filteredEvents.length ? <div className="terminal-event-list">{filteredEvents.slice(0, eventLimit).map(event =>
                  <EventRow key={event.event_id} trace={trace} event={event} selected={event.event_id === selectedEvent?.event_id} onSelect={selectEvent} />)}</div>
                  : <p className="terminal-empty">No events match these filters by {at(view.seconds, trace.start_time, trace.timezone)}.</p>}
                {filteredEvents.length > eventLimit && <button className="terminal-load-more" onClick={() => setEventLimit(limit => limit + 60)}>Load 60 older events</button>}
              </section>
              <EventDetails trace={trace} event={selectedEvent} onSite={selectSite} onHousehold={selectHousehold} />
            </div>
          </section>

          <section id="sites" className="analytics-section" aria-labelledby="sites-heading">
            <div className="analytics-section-title"><h2 id="sites-heading">Sites</h2></div>
            <div className="terminal-filterbar site-filterbar">
              <label><span>Location type</span><select value={siteTypeFilter} onChange={event => setSiteTypeFilter(event.target.value)}>
                <option value="all">All locations</option>{['retailer', 'support', 'school', 'emergency', 'council'].map(type => <option key={type} value={type}>{words(type)}</option>)}</select></label>
            </div>
            <div className="analytics-detail-layout">
              <section className="terminal-panel terminal-table-panel">
                <div className="terminal-site-head"><span>Location</span><span>Status</span><span>Stock</span><span>Visits</span><span>Denials</span><span>Served</span><span>Capacity</span><span>Revenue</span></div>
                <div className="terminal-site-list">{sites.map(site => {
                  const state = view.sites[site.id]!;
                  return <button type="button" className={'terminal-site-row' + (selectedSiteId === site.id ? ' selected' : '')}
                    aria-pressed={selectedSiteId === site.id} key={site.id} onClick={() => setSelectedSiteId(site.id)}>
                    <span data-label="Location"><b>{site.name}</b><small>{words(site.type)} · ID {site.id}</small></span>
                    <span data-label="Status">{siteStatus(site, view.seconds, trace.start_time, trace.timezone)}</span>
                    <span data-label="Stock">{grams(state.stock_grams)}</span><span data-label="Visits">{state.visits}</span>
                    <span data-label="Denials">{state.denials}</span><span data-label="Served">{state.served}</span>
                    <span data-label="Capacity">{state.capacity}</span><span data-label="Revenue">{dollars(state.revenue_cents)}</span>
                  </button>;
                })}</div>
              </section>
              <aside className="terminal-panel terminal-event-detail">
                {selectedSite ? <><div className="terminal-panel-heading"><div><span className="terminal-panel-code">Site details · {words(selectedSite.type)}</span>
                    <h3>{selectedSite.name}</h3></div><span className="site-state-chip">{siteStatus(selectedSite, view.seconds, trace.start_time, trace.timezone)}</span></div>
                  <p className="terminal-site-note">{selectedSite.source_id
                    ? 'Listed by the city. Current operations are unknown. Displayed operating values are modeled.'
                    : 'Synthetic location. All listed operating values are modeled.'}</p>
                  <dl className="terminal-definitions">
                    {selectedSite.source_record_url && <div><dt>Location source</dt><dd><a href={selectedSite.source_record_url} target="_blank" rel="noreferrer">Source ID {selectedSite.source_id} · Record {selectedSite.source_record_id}</a></dd></div>}
                    {selectedSite.source_retrieved_at && <div><dt>Snapshot retrieved</dt><dd>{selectedSite.source_retrieved_at}</dd></div>}
                    <div><dt>Opens</dt><dd>{at(selectedSite.opens, trace.start_time, trace.timezone)}</dd></div>
                    <div><dt>Closes</dt><dd>{at(selectedSite.closes, trace.start_time, trace.timezone)}</dd></div>
                    <div><dt>Eligibility</dt><dd>{selectedSite.eligible}</dd></div>
                    <div><dt>Current stock</dt><dd>{grams(view.sites[selectedSite.id]!.stock_grams)}</dd></div>
                    <div><dt>Price per 100 g</dt><dd>{dollars(view.sites[selectedSite.id]!.price_cents_per_100g)}</dd></div>
                    <div><dt>Served</dt><dd>{view.sites[selectedSite.id]!.served}</dd></div>
                    <div><dt>Capacity</dt><dd>{view.sites[selectedSite.id]!.capacity}</dd></div>
                    <div><dt>Food sold</dt><dd>{grams(view.sites[selectedSite.id]!.sold_grams)}</dd></div>
                    <div><dt>Stock received</dt><dd>{grams(view.sites[selectedSite.id]!.received_grams)}</dd></div>
                    <div><dt>Revenue</dt><dd>{dollars(view.sites[selectedSite.id]!.revenue_cents)}</dd></div>
                    <div><dt>Procurement</dt><dd>{dollars(view.sites[selectedSite.id]!.spending_cents)}</dd></div>
                  </dl>
                  <h4 className="terminal-subheading">Recent events</h4>
                  <div className="terminal-event-list compact">{view.events.filter(event => event.site_id === selectedSite.id).slice(-8).reverse().map(event =>
                    <EventRow key={event.event_id} trace={trace} event={event} selected={event.event_id === selectedEvent?.event_id} onSelect={selected => { selectEvent(selected); scrollToSection('interactions'); }} />)}</div>
                </> : <div className="terminal-detail-empty"><p>Select a site to view its details.</p></div>}
              </aside>
            </div>
          </section>

          <section id="households" className="analytics-section" aria-labelledby="households-heading">
            <div className="analytics-section-title"><h2 id="households-heading">Households</h2></div>
            <section className="terminal-panel cohort-panel">
              <div className="terminal-panel-heading"><div><h3>Average per household</h3></div>
                <label className="terminal-inline-select"><span>Group by</span><select value={groupBy} onChange={event => setGroupBy(event.target.value as GroupDimension)}>
                  <option value="income_band">Income band</option><option value="area">Area</option><option value="mobility">Mobility</option><option value="size">Household size</option>
                </select></label></div>
              <p className="cohort-note">Averages for this synthetic run.</p>
              <div className="terminal-group-head"><span>Group</span><span>Households</span><span>Food obtained per household</span><span>Unmet produce per household</span><span>Spending per household</span></div>
              <div className="terminal-group-list">{groupedHouseholds.map(([label, group]) => <div className="terminal-group-row" key={label}>
                <b data-label="Group">{label}</b><span data-label="Households">{group.count.toLocaleString()}</span>
                <span data-label="Food obtained per household">{grams(Math.round(group.obtained / group.count))}</span>
                <span data-label="Unmet produce per household">{grams(Math.round(group.unmet / group.count))}</span>
                <span data-label="Spending per household">{dollars(Math.round(group.spending / group.count))}</span>
              </div>)}</div>
            </section>
            <div className="analytics-detail-layout household-detail-layout">
              <section className="terminal-panel terminal-table-panel">
                <label className="terminal-search household-search"><Search size={15} /><input aria-label="Search households" placeholder="Search households"
                  value={householdQuery} onChange={event => { setHouseholdQuery(event.target.value); setHouseholdLimit(80); }} /></label>
                <div className="terminal-household-head"><span>Household</span><span>Area, size, income band</span><span>Food obtained</span><span>Unmet produce</span><span>Spending</span></div>
                <div className="terminal-household-list">{filteredHouseholds.slice(0, householdLimit).map(household => {
                  const state = view.households[household.id]!;
                  return <button type="button" key={household.id} aria-pressed={selectedHouseholdId === household.id}
                    className={'terminal-household-row' + (selectedHouseholdId === household.id ? ' selected' : '')}
                    onClick={() => setSelectedHouseholdId(household.id)}>
                    <b data-label="Household">{household.id}</b>
                    <span data-label="Profile">{household.area} · {household.size} people · {household.income_band}</span>
                    <span data-label="Food obtained">{grams(state.purchased_grams + state.received_grams)}</span>
                    <span data-label="Unmet produce">{grams(state.unmet_grams)}</span><span data-label="Spending">{dollars(state.expenditure_cents)}</span>
                  </button>;
                })}</div>
                {filteredHouseholds.length > householdLimit && <button className="terminal-load-more" onClick={() => setHouseholdLimit(limit => limit + 80)}>Load 80 more households</button>}
              </section>
              <aside className="terminal-panel household-inspector">
                {selectedHousehold && view ? <><div className="terminal-panel-heading"><div><span className="terminal-panel-code">Household details</span><h3>{selectedHousehold.id}</h3></div>
                    <span className="household-icon"><Users size={15} /></span></div>
                  <HouseholdDetails household={selectedHousehold} view={view} startTime={trace.start_time} timezone={trace.timezone} /></>
                  : <div className="terminal-detail-empty"><p>Select a household to view its details.</p></div>}
              </aside>
            </div>
          </section>

          <footer className="analytics-footnote">
            <span>All run outcomes are synthetic. They are not observed Toronto service data.</span>
            <details className="terminal-assumptions">
              <summary>Run details</summary>
              <p>Scenario: {trace.scenario_id}. Policy: {words(trace.policy)}. Seed: {trace.seed}. Household agents: {trace.population.toLocaleString()}. Evidence: {words(trace.evidence_state)}.</p>
              {trace.data_snapshot && <p>Input snapshot: {trace.data_snapshot.content.snapshot_id}. Source snapshot: {trace.data_snapshot.content.source_snapshot_id}.</p>}
              <p>Food use: {trace.assumptions.food_use} Crossing delay: {trace.assumptions.crossing_delay_seconds} seconds. Scope: {trace.assumptions.scope}</p>
              <p>Parameter set: {trace.assumptions.parameter_id}. Unknown inputs: {trace.assumptions.unknown_inputs.join(', ') || 'None listed'}.</p>
            </details>
          </footer>
        </>}
      </div>
    </div>
  </main>;
}
