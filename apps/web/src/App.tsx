import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { ArrowDownLeft, ArrowRight, BarChart3, ChevronRight, Compass, Expand, Eye, Footprints, Info, Landmark,
  MapPin, Pause, Play, Plus, Minus, RotateCcw, Trees, VolumeX, X } from 'lucide-react';
import { loadDistrict, loadIslands } from './district.ts';
import type { District } from './district.ts';
import type { SceneTick, TorontoScene } from './scene.ts';
import { foodView } from './interactables.ts';
import type { FoodTrace } from './interactables.ts';
import { at, HouseholdDetails } from './FoodDetails.tsx';
import { isDashboardCommand, LIVE_RUN_CHANNEL } from './liveRun.ts';
import { parseRunRef, sameRunRef, serializeRunRef } from './runRef.ts';
import type { RunRef } from './runRef.ts';
import { loadRunTrace } from './runTrace.ts';
import { CouncilPanel } from './CouncilPanel.tsx';

const emptyTick: SceneTick = { seconds: 0, walking: 0, resting: 0, selected: null };
function distance(meters: number): string { return meters >= 1000 ? (meters / 1000).toFixed(1) + ' km' : Math.round(meters) + ' m'; }
function initialPolicy(): 'baseline' | 'emergency' {
  return new URLSearchParams(window.location.search).get('policy') === 'emergency' ? 'emergency' : 'baseline';
}
function initialPopulation(): number {
  const value = Number(new URLSearchParams(window.location.search).get('population'));
  return [200, 600, 1200, 2400].includes(value) ? value : 2400;
}
function initialRunRef(): RunRef {
  const fromUrl = new URLSearchParams(window.location.search).get('run');
  const parsed = parseRunRef(fromUrl);
  if (parsed) return parsed;
  return { kind: 'preset', population: initialPopulation(), policy: initialPolicy() };
}
function updateRunUrl(runRef: RunRef, seconds: number): void {
  const url = new URL(window.location.href);
  const serialized = serializeRunRef(runRef);
  if (runRef.kind === 'council') {
    url.searchParams.set('run', serialized ?? '');
    url.searchParams.delete('population'); url.searchParams.delete('policy');
  } else {
    url.searchParams.delete('run');
    url.searchParams.set('population', String(runRef.population));
    url.searchParams.set('policy', runRef.policy);
  }
  url.searchParams.set('time', String(Math.floor(seconds)));
  window.history.replaceState(null, '', url);
}

export function App() {
  const container = useRef<HTMLDivElement>(null), engine = useRef<TorontoScene | null>(null);
  const liveChannel = useRef<BroadcastChannel | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [district, setDistrict] = useState<District | null>(null);
  const [trace, setTrace] = useState<FoodTrace | null>(null);
  const [runRef, setRunRef] = useState<RunRef>(initialRunRef);
  const activeRunRef = useRef(runRef);
  const [policy, setPolicy] = useState<'baseline' | 'emergency' | 'council'>(() => {
    const initial = initialRunRef(); return initial.kind === 'council' ? 'council' : initial.policy;
  });
  const [siteId, setSiteId] = useState<string | null>(null);
  const [councilOpen, setCouncilOpen] = useState(false);
  const [busy, setBusy] = useState(false), [runError, setRunError] = useState<string | null>(null);
  const traceRequest = useRef(0);
  const [ready, setReady] = useState(false), [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(emptyTick), [selected, setSelected] = useState<number | null>(null);
  const [paused, setPaused] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches), [speed, setSpeed] = useState(10), [population, setPopulation] = useState(initialPopulation);
  const [uiVisible, setUiVisible] = useState(true);
  useEffect(() => { activeRunRef.current = runRef; }, [runRef]);
  useEffect(() => {
    let active = true;
    async function start() {
      const requestedRun = initialRunRef();
      try {
        const [map, islands, module] = await Promise.all([loadDistrict(), loadIslands(), import('./scene.ts')]);
        const food = await loadRunTrace(requestedRun);
        if (!active || !container.current) return;
        const view = new module.TorontoScene(container.current, map, islands, setTick,
          id => { setSelected(id); if (id !== null) setSiteId(null); }, food, setSiteId, requestedRun);
        const params = new URLSearchParams(window.location.search);
        const requestedTime = params.has('time') ? Number(params.get('time')) : NaN;
        const startAt = Number.isFinite(requestedTime) ? Math.max(0, Math.min(requestedTime, food.horizon_seconds)) : 0;
        view.seek(startAt);
        const requestedResident = params.has('resident') ? Number(params.get('resident')) : NaN;
        if (Number.isInteger(requestedResident) && requestedResident >= 0 && requestedResident < food.households.length) view.select(requestedResident);
        const requestedSite = params.get('site');
        if (requestedSite) { setSiteId(requestedSite); view.focusSite(requestedSite); }
        engine.current = view; setDistrict(map); setTrace(food); setRunRef(requestedRun);
        setPopulation(food.population); setPolicy(food.policy); setTick({ ...emptyTick, seconds: startAt }); setReady(true);
      } catch (e) {
        if (!active) return;
        const message = e instanceof Error ? e.message : 'The requested run could not load.';
        setError(requestedRun.kind === 'council'
          ? `Council run ${requestedRun.run_id} (${requestedRun.arm}) is unavailable. ${message}`
          : message);
      }
    }
    void start();
    return () => { active = false; traceRequest.current++; engine.current?.dispose(); engine.current = null; };
  }, []);
  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return;
    const channel = new BroadcastChannel(LIVE_RUN_CHANNEL);
    liveChannel.current = channel;
    channel.onmessage = event => {
      const command = event.data;
      if (!isDashboardCommand(command)) return;
      if (command.type === 'dashboard-seek') {
        if (sameRunRef(command.run_ref, activeRunRef.current)) engine.current?.seek(command.seconds);
      } else void loadRunRef(command.run_ref);
    };
    return () => { channel.close(); liveChannel.current = null; };
  }, []);
  useEffect(() => { engine.current?.setPaused(paused || busy); }, [paused, busy, ready]);
  useEffect(() => { engine.current?.setSpeed(speed); }, [speed, ready]);
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement
          || event.target instanceof HTMLSelectElement || (event.target instanceof HTMLElement && event.target.isContentEditable)
          || dialog.current?.open) return;
      if (event.code === 'Space' && !(event.target instanceof HTMLButtonElement)) { event.preventDefault(); setPaused(p => !p); }
      if (event.key.toLowerCase() === 'h') setUiVisible(v => !v);
      if (event.key.toLowerCase() === 'r') engine.current?.reset();
      if (event.key === 'Escape') engine.current?.select(null);
    }
    const element = container.current;
    const contextError = (event: Event) => {
      if (event instanceof CustomEvent && typeof event.detail === 'string') setError(event.detail);
    };
    window.addEventListener('keydown', keyboard); element?.addEventListener('scene-error', contextError);
    return () => { window.removeEventListener('keydown', keyboard); element?.removeEventListener('scene-error', contextError); };
  }, []);
  async function loadRunRef(nextRunRef: RunRef) {
    const request = ++traceRequest.current;
    activeRunRef.current = nextRunRef;
    setBusy(true); setRunError(null);
    try {
      const next = await loadRunTrace(nextRunRef);
      if (request !== traceRequest.current || !engine.current) return;
      engine.current.setFoodTrace(next, nextRunRef); setTick(emptyTick); setTrace(next); setRunRef(nextRunRef);
      setPopulation(next.population); setPolicy(next.policy); setSiteId(null);
      updateRunUrl(nextRunRef, 0);
    } catch (e) {
      if (request === traceRequest.current) setRunError(e instanceof Error ? e.message : 'The scenario could not load.');
    } finally { if (request === traceRequest.current) setBusy(false); }
  }
  useEffect(() => {
    if (!trace || busy || !liveChannel.current) return;
    const publish = () => {
      liveChannel.current?.postMessage({
        type: 'simulation-state' as const,
        run_ref: runRef,
        population,
        policy,
        scenario_id: trace.scenario_id,
        seed: trace.seed,
        input_snapshot_id: trace.data_snapshot?.content.snapshot_id ?? null,
        source_snapshot_id: trace.data_snapshot?.content.source_snapshot_id ?? null,
        seconds: Math.max(0, Math.min(tick.seconds, trace.horizon_seconds)),
        horizon_seconds: trace.horizon_seconds,
        paused: paused || busy || tick.seconds >= trace.horizon_seconds,
        speed,
        published_at: Date.now(),
      });
    };
    publish();
    const timer = window.setInterval(publish, 1000);
    return () => window.clearInterval(timer);
  }, [trace, runRef, population, policy, tick.seconds, paused, busy, speed]);
  const resident = selected === null ? null : tick.selected;
  const residentStyle: CSSProperties & { '--resident-color': string } = { '--resident-color': resident?.color ?? '#b7c9a2' };
  const mappedHeights = district?.buildings.filter(b => b.basis !== 'estimate').length ?? 0;
  const food = useMemo(() => trace ? foodView(trace, tick.seconds) : null, [trace, tick.seconds]);
  const household = trace?.households.find(h => h.resident_id === selected);
  const selectedSite = trace?.sites.find(site => site.id === siteId);
  return (
    <main className={'environment light-golden' + (!uiVisible ? ' cinema' : '')}>
      <div className="world" ref={container} />
      <div className="vignette" />
      {!ready && !error && <div className="loading-screen" role="status">
        <div className="loading-diamond"><span /></div><p>Finding our place in the city.</p>
        <span>Building Toronto, one street at a time</span><div className="loading-line" />
      </div>}
      {error && <div className="error-screen" role="alert"><MapPin size={28} /><h1>Let’s get the city back.</h1><p>{error}</p><button className="primary-button" onClick={() => window.location.reload()}>Reload environment <RotateCcw size={15} /></button></div>}
      <div className="interface" inert={!uiVisible}>
        <header className="topbar">
          <a className="brand" href="/" aria-label="The Sims 6ix home"><span className="brand-mark"><i /></span><span>the sims <b>6ix</b><small>A LIVING TORONTO</small></span></a>
          <div className="location"><span className="location-dot" /><span>DOWNTOWN TORONTO<small>43.6500° N &nbsp; 79.3850° W</small></span></div>
          <nav className="header-actions" aria-label="Environment tools">
            <a className="quiet-button analytics-link" aria-label="Open run dashboard" target="_blank" rel="noreferrer"
              href={'/dashboard?' + (runRef.kind === 'council'
                ? `run=${encodeURIComponent(serializeRunRef(runRef) ?? '')}`
                : `population=${runRef.population}&policy=${runRef.policy}`)
                + '&time=' + Math.floor(tick.seconds) + (siteId ? '&site=' + encodeURIComponent(siteId) : '')}>
              <BarChart3 size={15} /> Run dashboard <ArrowRight size={14} /></a>
            <button className="quiet-button council-toggle" aria-expanded={councilOpen} aria-controls="council-panel"
              onClick={() => setCouncilOpen(open => !open)}><Landmark size={15} /> Council</button>
            <button className="icon-button info-button" onClick={() => dialog.current?.showModal()} aria-label="About the environment"><Info size={18} /></button>
            <button className="quiet-button hide-button" onClick={() => setUiVisible(false)}><Expand size={15} /> Hide interface <kbd>H</kbd></button>
          </nav>
        </header>
        <section className="intro food-intro" aria-label="Toronto environment">
          <div className="eyebrow"><span /> THE ENVIRONMENT &nbsp; / &nbsp; 01</div>
          <h1>Toronto,<br /><em>in motion.</em></h1>
          <p>A familiar skyline.<br />Everyday journeys, quietly unfolding.</p>
          <span className="scope-chip"><Footprints size={12} /> A pedestrian world</span>
        </section>
        {selectedSite && <section className="site-dashboard-link glass" aria-label="Selected food site">
          <div><span className="eyebrow">FOOD SITE SELECTED</span><b>{selectedSite.name}</b></div>
          <a target="_blank" rel="noreferrer" href={'/dashboard?view=sites&site=' + encodeURIComponent(selectedSite.id) + '&population=' + population + '&policy=' + policy + '&time=' + Math.floor(tick.seconds)}>Open site record <ArrowRight size={14} /></a>
          <button className="small-icon" aria-label="Clear selected site" onClick={() => setSiteId(null)}><X size={14} /></button>
        </section>}
        {busy && <div className="food-loading" role="status">Loading food scenario…</div>}
        {runError && <div className="food-run-error" role="alert">{runError}</div>}
        <CouncilPanel id="council-panel" open={councilOpen} onClose={() => setCouncilOpen(false)} />
        {resident && <section className="resident-card glass" aria-label="Selected resident">
          <div className="resident-heading"><span className="eyebrow">ONE OF THE SIX</span><button className="small-icon" onClick={() => engine.current?.select(null)} aria-label="Close resident details"><X size={15} /></button></div>
          <div className="resident-profile"><div className="resident-portrait" style={residentStyle}><i /><b /></div><div><h2>{resident.name}</h2><span>Synthetic resident · #{String(resident.id + 1).padStart(4, '0')}</span></div></div>
          <p className="resident-purpose">{resident.purpose}</p>
          <div className="resident-destination"><MapPin size={16} /><span>{resident.activity}<b>{resident.destination}</b></span></div>
          <div className="route-progress"><i style={{ width: Math.max(2, resident.progress * 100) + '%' }} /></div>
          <div className="route-meta"><span>{distance(resident.routeLength)} route</span><span>{resident.activity === 'Walking' ? resident.speed.toFixed(1) + ' m/s' : 'Resting'}</span></div>
          <button className="follow-button" onClick={() => engine.current?.followSelected()}><Footprints size={14} /> Follow this journey <ArrowRight size={14} /></button>
          {household && food && <HouseholdDetails household={household} view={food} startTime={trace?.start_time} timezone={trace?.timezone} />}
        </section>}
        <div className="map-controls" aria-label="Camera controls">
          <button onClick={() => engine.current?.resetCamera()} aria-label="Reset camera" title="Return to the city view"><Compass size={21} /><small>N</small></button>
          <div><button aria-label="Zoom in" onClick={() => engine.current?.zoom(1)}><Plus size={19} /></button><button aria-label="Zoom out" onClick={() => engine.current?.zoom(-1)}><Minus size={19} /></button></div>
        </div>
        <section className="playback glass" aria-label="Simulation playback">
          <button className="reset-button" aria-label="Restart pedestrian simulation" title="Restart · R" disabled={!ready} onClick={() => engine.current?.reset()}><RotateCcw size={17} /></button>
          <button className="play-button" aria-label={paused ? 'Resume simulation' : 'Pause simulation'} disabled={!ready} onClick={() => setPaused(v => !v)}>{paused ? <Play size={19} fill="currentColor" /> : <Pause size={19} fill="currentColor" />}</button>
          <div className="time-display"><span>{trace && tick.seconds >= trace.horizon_seconds ? 'DAY COMPLETE' : paused ? 'SIMULATION PAUSED' : 'FOOD ACCESS DAY'}</span><time data-testid="simulation-time">{at(tick.seconds, trace?.start_time, trace?.timezone)}</time></div>
          <div className="playback-divider" />
          <div className="speed-controls" aria-label="Simulation speed">{[1, 10, 30, 120].map(value => <button key={value} className={speed === value ? 'selected' : ''} aria-pressed={speed === value} onClick={() => setSpeed(value)}>{value}×</button>)}</div>
          <div className="activity-pill"><span /><b data-testid="walking-count">{tick.walking.toLocaleString()}</b> walking</div>
        </section>
        <footer className="map-footer">
          <div><span className="map-scale">TORONTO CORE</span><span className="source-credit">© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a> · <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noreferrer">ODbL</a><button onClick={() => dialog.current?.showModal()}>About this world <ChevronRight size={11} /></button></span></div>
          <span className="footer-note"><VolumeX size={12} /> Take a moment. Watch the city.</span>
        </footer>
      </div>
      {!uiVisible && <button className="show-interface glass" onClick={() => setUiVisible(true)}><Eye size={16} /> Show interface <kbd>H</kbd></button>}
      {!uiVisible && <a className="cinema-credit" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors · ODbL</a>}
      <dialog ref={dialog} className="about-dialog" onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }}>
        <button className="dialog-close icon-button" aria-label="Close about environment" onClick={() => dialog.current?.close()}><X size={19} /></button>
        <span className="eyebrow">THE SIMS 6IX / FIELD NOTES</span><h2>A real place.<br /><em>A little imagination.</em></h2>
        <p>This environment replays a six-hour food-access day settled in Python. Select a pedestrian to inspect household food and cash, or open the run dashboard to inspect site stock and service.</p>
        <div className="source-fact"><MapPin size={19} /><span><strong>The city comes from the map.</strong>Building footprints, streets, parks, railways, and shoreline are a frozen OpenStreetMap snapshot. {(mappedHeights).toLocaleString()} buildings have mapped height or floor-count tags. Other heights are estimates.</span></div>
        <div className="source-fact"><Trees size={19} /><span><strong>The details are stylized.</strong>CN Tower, Rogers Centre, facades, trees, and street details are illustrative interpretations. Road traffic is decorative and does not show measured vehicle counts or congestion. Derived sidewalk offsets and intersection links form the walking network.</span></div>
        <div className="source-fact"><Footprints size={19} /><span><strong>The residents are synthetic.</strong>Seeded itineraries follow the connected map. Their names, routines, and movement demonstrate city life. They are not observed Toronto travel data or live AI decisions.</span></div>
        <div className="keyboard-guide"><span><kbd>Space</kbd> Pause</span><span><kbd>R</kbd> Restart</span><span><kbd>H</kbd> Hide interface</span></div>
        <p className="source-links">Map data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>, distributed under <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noreferrer">ODbL 1.0</a>. Visual reference: <a href="https://devpost.com/software/shift-t15x3m" target="_blank" rel="noreferrer">God’s Plan, Hack the North 2026</a>. All application and landmark artwork here is newly implemented.</p>
        <button className="primary-button" onClick={() => dialog.current?.close()}>Back to the city <ArrowDownLeft size={16} /></button>
      </dialog>
    </main>
  );
}
