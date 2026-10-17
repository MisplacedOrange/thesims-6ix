import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { ArrowDownLeft, ArrowRight, Check, ChevronRight, Compass, Expand, Eye, Footprints, Info, Layers3,
  MapPin, Moon, MousePointer2, Pause, Play, Plus, Minus, RotateCcw, Settings2, Sun, Sunrise, Trees,
  UsersRound, VolumeX, X } from 'lucide-react';
import { loadDistrict } from './district.ts';
import type { District } from './district.ts';
import type { Layer, Lighting, Preset, SceneTick, TorontoScene } from './scene.ts';

const views: { id: Preset; title: string; subtitle: string; number: string }[] = [
  { id: 'skyline', title: 'The skyline', subtitle: 'See the city come together', number: '01' },
  { id: 'waterfront', title: 'By the water', subtitle: 'A little room to breathe', number: '02' },
  { id: 'oldtown', title: 'Old Toronto', subtitle: 'Follow the historic streets', number: '03' },
  { id: 'street', title: 'At street level', subtitle: 'Get closer to the everyday', number: '04' },
];
const emptyTick: SceneTick = { seconds: 0, walking: 0, resting: 0, selected: null };
function clock(seconds: number): string {
  const time = Math.floor(seconds) + 8 * 3600 + 30 * 60;
  return [Math.floor(time / 3600) % 24, Math.floor(time / 60) % 60, time % 60].map(n => String(n).padStart(2, '0')).join(':');
}
function distance(meters: number): string { return meters >= 1000 ? (meters / 1000).toFixed(1) + ' km' : Math.round(meters) + ' m'; }

export function App() {
  const container = useRef<HTMLDivElement>(null), engine = useRef<TorontoScene | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [district, setDistrict] = useState<District | null>(null);
  const [ready, setReady] = useState(false), [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(emptyTick), [selected, setSelected] = useState<number | null>(null);
  const [paused, setPaused] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches), [speed, setSpeed] = useState(10), [population, setPopulation] = useState(600);
  const [preset, setPreset] = useState<Preset>('skyline'), [lighting, setLighting] = useState<Lighting>('golden');
  const [uiVisible, setUiVisible] = useState(true), [settingsOpen, setSettingsOpen] = useState(false);
  const [layers, setLayers] = useState<Record<Layer, boolean>>({ buildings: true, greenery: true, paths: false, labels: true });
  useEffect(() => {
    let active = true;
    async function start() {
      try {
        const [map, module] = await Promise.all([loadDistrict(), import('./scene.ts')]);
        if (!active || !container.current) return;
        const view = new module.TorontoScene(container.current, map, setTick, setSelected);
        engine.current = view; setDistrict(map); setReady(true);
      } catch (e) { if (active) setError(e instanceof Error ? e.message : 'The 3D environment could not start.'); }
    }
    void start();
    return () => { active = false; engine.current?.dispose(); engine.current = null; };
  }, []);
  useEffect(() => { engine.current?.setPaused(paused); }, [paused, ready]);
  useEffect(() => { engine.current?.setSpeed(speed); }, [speed, ready]);
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement || dialog.current?.open) return;
      if (event.code === 'Space' && !(event.target instanceof HTMLButtonElement)) { event.preventDefault(); setPaused(p => !p); }
      if (event.key.toLowerCase() === 'h') setUiVisible(v => !v);
      if (event.key.toLowerCase() === 'r') engine.current?.reset();
      const view = views[Number(event.key) - 1];
      if (view) { setPreset(view.id); engine.current?.setPreset(view.id); }
      if (event.key === 'Escape') engine.current?.select(null);
    }
    const element = container.current;
    const contextError = (event: Event) => {
      if (event instanceof CustomEvent && typeof event.detail === 'string') setError(event.detail);
    };
    window.addEventListener('keydown', keyboard); element?.addEventListener('scene-error', contextError);
    return () => { window.removeEventListener('keydown', keyboard); element?.removeEventListener('scene-error', contextError); };
  }, []);
  function chooseView(id: Preset) { setPreset(id); engine.current?.setPreset(id); }
  function chooseLight(id: Lighting) { setLighting(id); engine.current?.setLighting(id); }
  function toggleLayer(layer: Layer) {
    const visible = !layers[layer]; setLayers(previous => ({ ...previous, [layer]: visible })); engine.current?.setLayer(layer, visible);
  }
  const resident = selected === null ? null : tick.selected;
  const residentStyle: CSSProperties & { '--resident-color': string } = { '--resident-color': resident?.color ?? '#b7c9a2' };
  const mappedHeights = district?.buildings.filter(b => b.basis !== 'estimate').length ?? 0;
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
            <button className="icon-button info-button" onClick={() => dialog.current?.showModal()} aria-label="About the environment"><Info size={18} /></button>
            <button className="icon-button mobile-settings" onClick={() => setSettingsOpen(v => !v)} aria-label="Toggle city settings"><Settings2 size={18} /></button>
            <button className="quiet-button hide-button" onClick={() => setUiVisible(false)}><Expand size={15} /> Hide interface <kbd>H</kbd></button>
          </nav>
        </header>
        <section className="intro" aria-label="Toronto environment">
          <div className="eyebrow"><span /> THE ENVIRONMENT &nbsp; / &nbsp; 01</div>
          <h1>Toronto,<br /><em>in motion.</em></h1>
          <p>A familiar skyline.<br />Everyday journeys, quietly unfolding.</p>
          <span className="scope-chip"><Footprints size={12} /> A pedestrian world</span>
        </section>
        <section className="explore-panel glass" aria-label="Camera views">
          <div className="panel-heading"><span>FIND YOUR PERSPECTIVE</span><Compass size={14} /></div>
          {views.map(view => <button key={view.id} className={'view-card ' + view.id + (preset === view.id ? ' active' : '')} aria-pressed={preset === view.id} onClick={() => chooseView(view.id)} disabled={!ready}>
            <span className={'view-art art-' + view.id}><i /><i /><i /><i /><i /></span>
            <span className="view-copy"><strong>{view.title}</strong><small>{view.subtitle}</small></span>
            <span className="view-index">{preset === view.id ? <ArrowRight size={14} /> : view.number}</span>
          </button>)}
          <div className="explore-footer"><MousePointer2 size={12} /> Drag to orbit <span>·</span> Scroll to explore</div>
        </section>
        <button className="meet-button glass" disabled={!ready} onClick={() => engine.current?.meetResident()}>
          <span className="resident-avatars"><i /><i /><i /></span><span>Every dot has somewhere to be.<b>Meet a resident <ArrowRight size={13} /></b></span>
        </button>
        <section className={'settings-panel glass' + (settingsOpen ? ' mobile-open' : '')} aria-label="City settings">
          <div className="settings-title"><span><Layers3 size={15} /> Your city view</span><span className="live-indicator"><i /> {paused ? 'PAUSED' : 'LIVE'}</span></div>
          <div className="population-summary"><strong>{population.toLocaleString()}</strong><span>synthetic pedestrians<small>{ready ? 'Moving through mapped streets' : 'Preparing the neighbourhood'}</small></span></div>
          <label className="section-label">CITY LIFE <UsersRound size={13} /></label>
          <div className="segmented population" aria-label="Pedestrian population">
            {[{ n: 200, label: 'Quiet' }, { n: 600, label: 'Everyday' }, { n: 1200, label: 'Lively' }].map(option => <button key={option.n} className={population === option.n ? 'selected' : ''} aria-pressed={population === option.n} disabled={!ready} onClick={() => { setPopulation(option.n); engine.current?.setPopulation(option.n); }}>{option.label}</button>)}
          </div>
          <div className="setting-divider" />
          <label className="section-label">LIGHT & ATMOSPHERE <Sun size={13} /></label>
          <div className="lighting-controls" aria-label="Lighting">
            {([{ id: 'day', title: 'Daylight', Icon: Sun }, { id: 'golden', title: 'Golden hour', Icon: Sunrise }, { id: 'blue', title: 'Blue hour', Icon: Moon }] satisfies { id: Lighting; title: string; Icon: typeof Sun }[]).map(({ id, title, Icon }) => <button key={id} title={title} aria-label={title} aria-pressed={lighting === id} className={lighting === id ? 'selected' : ''} onClick={() => chooseLight(id)}><Icon size={17} /><span>{title === 'Golden hour' ? 'Golden' : title === 'Blue hour' ? 'Blue hour' : 'Daylight'}</span></button>)}
          </div>
          <div className="setting-divider" />
          <label className="section-label">LAYERS <Eye size={13} /></label>
          {([{ id: 'buildings', label: 'Building massing' }, { id: 'greenery', label: 'Trees & green spaces' }, { id: 'paths', label: 'Walking network' }, { id: 'labels', label: 'Place labels' }] satisfies { id: Layer; label: string }[]).map(layer => <label className="layer-row" key={layer.id}><span>{layer.label}</span><span className="toggle"><input type="checkbox" checked={layers[layer.id]} onChange={() => toggleLayer(layer.id)} /><i><Check size={10} /></i></span></label>)}
          <div className="map-status"><span /><span>{(district?.buildings.length ?? 0).toLocaleString()} mapped building forms<small>Real geography. Illustrative city life.</small></span></div>
        </section>
        {resident && <section className="resident-card glass" aria-label="Selected resident">
          <div className="resident-heading"><span className="eyebrow">ONE OF THE SIX</span><button className="small-icon" onClick={() => engine.current?.select(null)} aria-label="Close resident details"><X size={15} /></button></div>
          <div className="resident-profile"><div className="resident-portrait" style={residentStyle}><i /><b /></div><div><h2>{resident.name}</h2><span>Synthetic resident · #{String(resident.id + 1).padStart(4, '0')}</span></div></div>
          <p className="resident-purpose">{resident.purpose}</p>
          <div className="resident-destination"><MapPin size={16} /><span>{resident.activity === 'Walking' ? 'Walking towards' : 'Taking a break near'}<b>{resident.destination}</b></span></div>
          <div className="route-progress"><i style={{ width: Math.max(2, resident.progress * 100) + '%' }} /></div>
          <div className="route-meta"><span>{distance(resident.routeLength)} route</span><span>{resident.activity === 'Walking' ? resident.speed.toFixed(1) + ' m/s' : 'Resting'}</span></div>
          <button className="follow-button" onClick={() => engine.current?.followSelected()}><Footprints size={14} /> Follow this journey <ArrowRight size={14} /></button>
        </section>}
        <div className="map-controls" aria-label="Camera controls">
          <button onClick={() => chooseView('skyline')} aria-label="Reset camera north" title="Return to the skyline"><Compass size={21} /><small>N</small></button>
          <div><button aria-label="Zoom in" onClick={() => engine.current?.zoom(1)}><Plus size={19} /></button><button aria-label="Zoom out" onClick={() => engine.current?.zoom(-1)}><Minus size={19} /></button></div>
        </div>
        <section className="playback glass" aria-label="Simulation playback">
          <button className="reset-button" aria-label="Restart pedestrian simulation" title="Restart · R" disabled={!ready} onClick={() => engine.current?.reset()}><RotateCcw size={17} /></button>
          <button className="play-button" aria-label={paused ? 'Resume simulation' : 'Pause simulation'} disabled={!ready} onClick={() => setPaused(v => !v)}>{paused ? <Play size={19} fill="currentColor" /> : <Pause size={19} fill="currentColor" />}</button>
          <div className="time-display"><span>{paused ? 'A MOMENT IN THE CITY' : 'THE CITY IS MOVING'}</span><time data-testid="simulation-time">{clock(tick.seconds)}</time></div>
          <div className="playback-divider" />
          <div className="speed-controls" aria-label="Simulation speed">{[1, 10, 30].map(value => <button key={value} className={speed === value ? 'selected' : ''} aria-pressed={speed === value} onClick={() => setSpeed(value)}>{value}×</button>)}</div>
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
        <p>This is a visual environment for exploring downtown Toronto and watching synthetic pedestrians move through its streets.</p>
        <div className="source-fact"><MapPin size={19} /><span><strong>The city comes from the map.</strong>Building footprints, streets, parks, railways, and shoreline are a frozen OpenStreetMap snapshot. {(mappedHeights).toLocaleString()} buildings have mapped height or floor-count tags. Other heights are estimates.</span></div>
        <div className="source-fact"><Trees size={19} /><span><strong>The details are stylized.</strong>CN Tower, Rogers Centre, facades, trees, and street details are illustrative interpretations. Derived sidewalk offsets and intersection links form the walking network.</span></div>
        <div className="source-fact"><Footprints size={19} /><span><strong>The residents are synthetic.</strong>Seeded itineraries follow the connected map. Their names, routines, and movement demonstrate city life. They are not observed Toronto travel data or live AI decisions.</span></div>
        <div className="keyboard-guide"><span><kbd>1</kbd>–<kbd>4</kbd> Change view</span><span><kbd>Space</kbd> Pause</span><span><kbd>R</kbd> Restart</span><span><kbd>H</kbd> Hide interface</span></div>
        <p className="source-links">Map data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>, distributed under <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noreferrer">ODbL 1.0</a>. Visual reference: <a href="https://devpost.com/software/shift-t15x3m" target="_blank" rel="noreferrer">God’s Plan, Hack the North 2026</a>. All application and landmark artwork here is newly implemented.</p>
        <button className="primary-button" onClick={() => dialog.current?.close()}>Back to the city <ArrowDownLeft size={16} /></button>
      </dialog>
    </main>
  );
}
