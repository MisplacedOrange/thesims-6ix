import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { ArrowRight, Compass, Expand, Eye, Footprints, MapPin, Pause, Play,
  Plus, Minus, RotateCcw, VolumeX, X } from 'lucide-react';
import { loadDistrict, loadIslands } from './district.ts';
import type { SceneTick, TorontoScene } from './scene.ts';
import { foodView, loadFoodTrace } from './interactables.ts';
import type { FoodTrace } from './interactables.ts';
import { FoodPanel, HouseholdDetails } from './FoodPanel.tsx';

const emptyTick: SceneTick = { seconds: 0, walking: 0, resting: 0, selected: null };
const DEFAULT_POPULATION = 1200;
function clock(seconds: number): string {
  const time = Math.floor(seconds) + 8 * 3600 + 30 * 60;
  return [Math.floor(time / 3600) % 24, Math.floor(time / 60) % 60, time % 60].map(n => String(n).padStart(2, '0')).join(':');
}
function distance(meters: number): string { return meters >= 1000 ? (meters / 1000).toFixed(1) + ' km' : Math.round(meters) + ' m'; }

export function App() {
  const container = useRef<HTMLDivElement>(null), engine = useRef<TorontoScene | null>(null);
  const [trace, setTrace] = useState<FoodTrace | null>(null);
  const [policy, setPolicy] = useState<'baseline' | 'emergency'>('baseline');
  const [siteId, setSiteId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false), [runError, setRunError] = useState<string | null>(null);
  const traceRequest = useRef(0);
  const [ready, setReady] = useState(false), [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(emptyTick), [selected, setSelected] = useState<number | null>(null);
  const [paused, setPaused] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches), [speed, setSpeed] = useState(10);
  const [uiVisible, setUiVisible] = useState(true);
  useEffect(() => {
    let active = true;
    async function start() {
      try {
        const [map, islands, module, food] = await Promise.all([loadDistrict(), loadIslands(), import('./scene.ts'), loadFoodTrace(DEFAULT_POPULATION, 'baseline')]);
        if (!active || !container.current) return;
        const view = new module.TorontoScene(container.current, map, islands, setTick,
          id => { setSelected(id); if (id !== null) setSiteId(null); }, food, setSiteId);
        engine.current = view; setTrace(food); setReady(true);
      } catch (e) { if (active) setError(e instanceof Error ? e.message : 'The 3D environment could not start.'); }
    }
    void start();
    return () => { active = false; traceRequest.current++; engine.current?.dispose(); engine.current = null; };
  }, []);
  useEffect(() => { engine.current?.setPaused(paused || busy); }, [paused, busy, ready]);
  useEffect(() => { engine.current?.setSpeed(speed); }, [speed, ready]);
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return;
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
  async function loadRun(nextPolicy: 'baseline' | 'emergency') {
    const request = ++traceRequest.current;
    setBusy(true); setRunError(null);
    try {
      const next = await loadFoodTrace(DEFAULT_POPULATION, nextPolicy);
      if (request !== traceRequest.current || !engine.current) return;
      engine.current.setFoodTrace(next); setTick(emptyTick); setTrace(next); setPolicy(nextPolicy);
    } catch (e) {
      if (request === traceRequest.current) setRunError(e instanceof Error ? e.message : 'The scenario could not load.');
    } finally { if (request === traceRequest.current) setBusy(false); }
  }
  const resident = selected === null ? null : tick.selected;
  const residentStyle: CSSProperties & { '--resident-color': string } = { '--resident-color': resident?.color ?? '#b7c9a2' };
  const food = useMemo(() => trace ? foodView(trace, tick.seconds) : null, [trace, tick.seconds]);
  const household = trace?.households.find(h => h.resident_id === selected);
  return (
    <main className={'environment' + (!uiVisible ? ' cinema' : '')}>
      <div className="world" ref={container} />
      <div className="vignette" />
      {!ready && !error && <div className="loading-screen" role="status">
        <div className="loading-diamond"><span /></div><p>Finding our place in the city.</p>
        <span>Building Toronto, one street at a time</span><div className="loading-line" />
      </div>}
      {error && <div className="error-screen" role="alert"><MapPin size={28} /><h1>Let’s get the city back.</h1><p>{error}</p><button className="primary-button" onClick={() => window.location.reload()}>Reload environment <RotateCcw size={15} /></button></div>}
      <div className="interface" inert={!uiVisible}>
        <header className="topbar">
          <nav className="header-actions" aria-label="Environment tools">
            <button className="icon-button hide-button" aria-label="Hide interface" title="Hide interface (H)" onClick={() => setUiVisible(false)}><Expand size={15} /></button>
          </nav>
        </header>
        <section className="intro food-intro" aria-label="Toronto environment">
          <div className="eyebrow"><span /> THE ENVIRONMENT &nbsp; / &nbsp; 01</div>
          <h1>Toronto,<br /><em>in motion.</em></h1>
          <p>A familiar skyline.<br />Everyday journeys, quietly unfolding.</p>
          <span className="scope-chip"><Footprints size={12} /> A pedestrian world</span>
        </section>
        {trace && food && <FoodPanel trace={trace} view={food} siteId={siteId} policy={policy} busy={busy} residentId={selected}
          onPolicy={p => { void loadRun(p); }} onSite={id => { setSiteId(id); engine.current?.focusSite(id); }}
          onCloseSite={() => setSiteId(null)} onSeek={seconds => engine.current?.seek(seconds)} />}
        {busy && <div className="food-loading" role="status">Loading food scenario…</div>}
        {runError && <div className="food-run-error" role="alert">{runError}</div>}
        <button className="meet-button glass" disabled={!ready} onClick={() => engine.current?.meetResident()}>
          <span className="resident-avatars"><i /><i /><i /></span><span>Every dot has somewhere to be.<b>Meet a resident <ArrowRight size={13} /></b></span>
        </button>
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
          <div><span className="map-scale">TORONTO CORE</span><span className="source-credit">© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a> · <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noreferrer">ODbL</a></span></div>
          <span className="footer-note"><VolumeX size={12} /> Take a moment. Watch the city.</span>
        </footer>
      </div>
      {!uiVisible && <button className="show-interface glass" onClick={() => setUiVisible(true)}><Eye size={16} /> Show interface <kbd>H</kbd></button>}
      {!uiVisible && <a className="cinema-credit" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors · ODbL</a>}
    </main>
  );
}
