import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { ArrowDownLeft, ArrowRight, BarChart3, Check, ChevronRight, Compass, Expand, Eye, Footprints, Info, Layers3,
  MapPin, Moon, Pause, Play, Plus, Minus, RotateCcw, Settings2, Sun, Sunrise, Trees,
  VolumeX, X } from 'lucide-react';
import { loadDistrict, loadIslands } from './district.ts';
import type { District } from './district.ts';
import type { Layer, Lighting, SceneTick, TorontoScene } from './scene.ts';
import { foodView, loadFoodTrace } from './interactables.ts';
import type { FoodTrace } from './interactables.ts';
import { HouseholdDetails } from './FoodDetails.tsx';
import { isDashboardCommand, LIVE_RUN_CHANNEL, liveRunId } from './liveRun.ts';

const emptyTick: SceneTick = { seconds: 0, walking: 0, resting: 0, selected: null };
function clock(seconds: number): string {
  const time = Math.floor(seconds) + 8 * 3600 + 30 * 60;
  return [Math.floor(time / 3600) % 24, Math.floor(time / 60) % 60, time % 60].map(n => String(n).padStart(2, '0')).join(':');
}
function distance(meters: number): string { return meters >= 1000 ? (meters / 1000).toFixed(1) + ' km' : Math.round(meters) + ' m'; }
function initialPolicy(): 'baseline' | 'emergency' {
  return new URLSearchParams(window.location.search).get('policy') === 'emergency' ? 'emergency' : 'baseline';
}
function initialPopulation(): number {
  const value = Number(new URLSearchParams(window.location.search).get('population'));
  return [200, 600, 1200].includes(value) ? value : 600;
}

export function App() {
  const container = useRef<HTMLDivElement>(null), engine = useRef<TorontoScene | null>(null);
  const liveChannel = useRef<BroadcastChannel | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [district, setDistrict] = useState<District | null>(null);
  const [trace, setTrace] = useState<FoodTrace | null>(null);
  const [policy, setPolicy] = useState<'baseline' | 'emergency'>(initialPolicy);
  const [siteId, setSiteId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false), [runError, setRunError] = useState<string | null>(null);
  const traceRequest = useRef(0);
  const [ready, setReady] = useState(false), [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(emptyTick), [selected, setSelected] = useState<number | null>(null);
  const [paused, setPaused] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches), [speed, setSpeed] = useState(10), [population, setPopulation] = useState(initialPopulation);
  const [lighting, setLighting] = useState<Lighting>('golden');
  const [uiVisible, setUiVisible] = useState(true), [settingsOpen, setSettingsOpen] = useState(false);
  const [layers, setLayers] = useState<Record<Layer, boolean>>({ buildings: true, greenery: true, paths: false, traffic: true });
  useEffect(() => {
    let active = true;
    async function start() {
      try {
        const [map, islands, module, food] = await Promise.all([loadDistrict(), loadIslands(), import('./scene.ts'), loadFoodTrace(population, policy)]);
        if (!active || !container.current) return;
        const view = new module.TorontoScene(container.current, map, islands, setTick,
          id => { setSelected(id); if (id !== null) setSiteId(null); }, food, setSiteId);
        const params = new URLSearchParams(window.location.search);
        const requestedTime = params.has('time') ? Number(params.get('time')) : NaN;
        const startAt = Number.isFinite(requestedTime) ? Math.max(0, Math.min(requestedTime, food.horizon_seconds)) : 0;
        view.seek(startAt);
        const requestedResident = params.has('resident') ? Number(params.get('resident')) : NaN;
        if (Number.isInteger(requestedResident) && requestedResident >= 0 && requestedResident < food.households.length) view.select(requestedResident);
        const requestedSite = params.get('site');
        if (requestedSite) { setSiteId(requestedSite); view.focusSite(requestedSite); }
        engine.current = view; setDistrict(map); setTrace(food); setTick({ ...emptyTick, seconds: startAt }); setReady(true);
      } catch (e) { if (active) setError(e instanceof Error ? e.message : 'The 3D environment could not start.'); }
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
      if (command.type === 'dashboard-seek') engine.current?.seek(command.seconds);
      else void loadRun(command.population, command.policy);
    };
    return () => { channel.close(); liveChannel.current = null; };
  }, []);
  useEffect(() => { engine.current?.setPaused(paused || busy); }, [paused, busy, ready]);
  useEffect(() => { engine.current?.setSpeed(speed); }, [speed, ready]);
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement || dialog.current?.open) return;
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
  function chooseLight(id: Lighting) { setLighting(id); engine.current?.setLighting(id); }
  async function loadRun(count: number, nextPolicy: 'baseline' | 'emergency') {
    const request = ++traceRequest.current;
    setBusy(true); setRunError(null);
    try {
      const next = await loadFoodTrace(count, nextPolicy);
      if (request !== traceRequest.current || !engine.current) return;
      engine.current.setFoodTrace(next); setTick(emptyTick); setTrace(next); setPopulation(count); setPolicy(nextPolicy); setSiteId(null);
    } catch (e) {
      if (request === traceRequest.current) setRunError(e instanceof Error ? e.message : 'The scenario could not load.');
    } finally { if (request === traceRequest.current) setBusy(false); }
  }
  useEffect(() => {
    if (!trace || busy || !liveChannel.current) return;
    const run = {
      type: 'simulation-state' as const,
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
    };
    liveChannel.current.postMessage({ ...run, run_id: liveRunId(run) });
  }, [trace, population, policy, tick.seconds, paused, busy, speed]);
  function toggleLayer(layer: Layer) {
    const visible = !layers[layer]; setLayers(previous => ({ ...previous, [layer]: visible })); engine.current?.setLayer(layer, visible);
  }
  const resident = selected === null ? null : tick.selected;
  const residentStyle: CSSProperties & { '--resident-color': string } = { '--resident-color': resident?.color ?? '#b7c9a2' };
  const mappedHeights = district?.buildings.filter(b => b.basis !== 'estimate').length ?? 0;
  const food = useMemo(() => trace ? foodView(trace, tick.seconds) : null, [trace, tick.seconds]);
  const household = trace?.households.find(h => h.resident_id === selected);
  const selectedSite = trace?.sites.find(site => site.id === siteId);
  return (
    <main className={'environment light-' + lighting + (!uiVisible ? ' cinema' : '')}>
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
              href={'/dashboard?population=' + population + '&policy=' + policy + '&time=' + Math.floor(tick.seconds)
                + (siteId ? '&site=' + encodeURIComponent(siteId) : '')}><BarChart3 size={15} /> Run dashboard <ArrowRight size={14} /></a>
            <button className="icon-button info-button" onClick={() => dialog.current?.showModal()} aria-label="About the environment"><Info size={18} /></button>
            <button className="icon-button mobile-settings" onClick={() => setSettingsOpen(v => !v)} aria-label="Toggle city settings"><Settings2 size={18} /></button>
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
        <button className="meet-button glass" disabled={!ready} onClick={() => engine.current?.meetResident()}>
          <span className="resident-avatars"><i /><i /><i /></span><span>Every dot has somewhere to be.<b>Meet a resident <ArrowRight size={13} /></b></span>
        </button>
        <section className={'settings-panel glass' + (settingsOpen ? ' mobile-open' : '')} aria-label="City settings">
          <div className="settings-title"><span><Layers3 size={15} /> City settings</span></div>
          <label className="section-label">CITY LIFE <span>{population.toLocaleString()}</span></label>
          <div className="segmented population" aria-label="Pedestrian population">
            {[{ n: 200, label: 'Quiet' }, { n: 600, label: 'Everyday' }, { n: 1200, label: 'Lively' }].map(option => <button key={option.n} className={population === option.n ? 'selected' : ''} aria-pressed={population === option.n} disabled={!ready || busy} onClick={() => { void loadRun(option.n, policy); }}>{option.label}</button>)}
          </div>
          <div className="setting-divider" />
          <label className="section-label">FOOD SCENARIO</label>
          <div className="segmented population" aria-label="Food access scenario">
            {[{ id: 'baseline' as const, label: 'Baseline' }, { id: 'emergency' as const, label: 'Emergency site' }].map(option =>
              <button key={option.id} className={policy === option.id ? 'selected' : ''} aria-pressed={policy === option.id}
                disabled={!ready || busy} onClick={() => { void loadRun(population, option.id); }}>{option.label}</button>)}
          </div>
          <div className="setting-divider" />
          <label className="section-label">LIGHT & ATMOSPHERE <Sun size={13} /></label>
          <div className="lighting-controls" aria-label="Lighting">
            {([{ id: 'day', title: 'Daylight', Icon: Sun }, { id: 'golden', title: 'Golden hour', Icon: Sunrise }, { id: 'blue', title: 'Blue hour', Icon: Moon }] satisfies { id: Lighting; title: string; Icon: typeof Sun }[]).map(({ id, title, Icon }) => <button key={id} title={title} aria-label={title} aria-pressed={lighting === id} className={lighting === id ? 'selected' : ''} onClick={() => chooseLight(id)}><Icon size={17} /><span>{title === 'Golden hour' ? 'Golden' : title === 'Blue hour' ? 'Blue hour' : 'Daylight'}</span></button>)}
          </div>
          <div className="setting-divider" />
          <label className="section-label">LAYERS <Eye size={13} /></label>
          {([{ id: 'buildings', label: 'Buildings' }, { id: 'greenery', label: 'Greenery' }, { id: 'paths', label: 'Walking network' }, { id: 'traffic', label: 'Road traffic' }] satisfies { id: Layer; label: string }[]).map(layer => <label className="layer-row" key={layer.id}><span>{layer.label}</span><span className="toggle"><input type="checkbox" checked={layers[layer.id]} onChange={() => toggleLayer(layer.id)} /><i><Check size={10} /></i></span></label>)}
        </section>
        {resident && <section className="resident-card glass" aria-label="Selected resident">
          <div className="resident-heading"><span className="eyebrow">ONE OF THE SIX</span><button className="small-icon" onClick={() => engine.current?.select(null)} aria-label="Close resident details"><X size={15} /></button></div>
          <div className="resident-profile"><div className="resident-portrait" style={residentStyle}><i /><b /></div><div><h2>{resident.name}</h2><span>Synthetic resident · #{String(resident.id + 1).padStart(4, '0')}</span></div></div>
          <p className="resident-purpose">{resident.purpose}</p>
          <div className="resident-destination"><MapPin size={16} /><span>{resident.activity}<b>{resident.destination}</b></span></div>
          <div className="route-progress"><i style={{ width: Math.max(2, resident.progress * 100) + '%' }} /></div>
          <div className="route-meta"><span>{distance(resident.routeLength)} route</span><span>{resident.activity === 'Walking' ? resident.speed.toFixed(1) + ' m/s' : 'Resting'}</span></div>
          <button className="follow-button" onClick={() => engine.current?.followSelected()}><Footprints size={14} /> Follow this journey <ArrowRight size={14} /></button>
          {household && food && <HouseholdDetails household={household} view={food} />}
        </section>}
        <div className="map-controls" aria-label="Camera controls">
          <button onClick={() => engine.current?.resetCamera()} aria-label="Reset camera" title="Return to the city view"><Compass size={21} /><small>N</small></button>
          <div><button aria-label="Zoom in" onClick={() => engine.current?.zoom(1)}><Plus size={19} /></button><button aria-label="Zoom out" onClick={() => engine.current?.zoom(-1)}><Minus size={19} /></button></div>
        </div>
        <section className="playback glass" aria-label="Simulation playback">
          <button className="reset-button" aria-label="Restart pedestrian simulation" title="Restart · R" disabled={!ready} onClick={() => engine.current?.reset()}><RotateCcw size={17} /></button>
          <button className="play-button" aria-label={paused ? 'Resume simulation' : 'Pause simulation'} disabled={!ready} onClick={() => setPaused(v => !v)}>{paused ? <Play size={19} fill="currentColor" /> : <Pause size={19} fill="currentColor" />}</button>
          <div className="time-display"><span>{trace && tick.seconds >= trace.horizon_seconds ? 'DAY COMPLETE' : paused ? 'SIMULATION PAUSED' : 'FOOD ACCESS DAY'}</span><time data-testid="simulation-time">{clock(tick.seconds)}</time></div>
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
