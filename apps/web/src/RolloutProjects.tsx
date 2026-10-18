import { useEffect, useMemo, useRef } from 'react';
import type { RefObject } from 'react';
import { ArrowUpRight, Check, ClipboardCheck, Coins, Hammer, MapPin, PackageCheck, Play, Store, Truck, TriangleAlert } from 'lucide-react';
import type { FoodTrace, RolloutEvent } from './interactables.ts';
import type { TorontoScene } from './scene.ts';
import { at } from './FoodDetails.tsx';
import { countdown, rolloutProjects, stageLabels } from './rolloutProgress.ts';
import type { RolloutProject } from './rolloutProgress.ts';
import './rollout-projects.css';

const icons = { readiness: Hammer, funding: Coins, delivery: Truck, commissioning: ClipboardCheck,
  opening: Store, closure: Store, capacity_change: ArrowUpRight, blocked: TriangleAlert,
  no_launch: TriangleAlert, waiting: PackageCheck };

function Progress({ project }: { project: RolloutProject }) {
  return <div className="rollout-progress" role="progressbar" aria-label={`${project.label} schedule progress`}
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(project.progress * 100)}>
    <span style={{ width: `${project.progress * 100}%` }} />
  </div>;
}

export function RolloutProjects({ trace, seconds, engine, onSeek, onReplay, onSwitchArm }: {
  trace: FoodTrace; seconds: number; engine: RefObject<TorontoScene | null>;
  onSeek: (seconds: number) => void; onReplay: () => void; onSwitchArm: (arm: 'baseline' | 'intervention') => void;
}) {
  const projects = useMemo(() => rolloutProjects(trace, seconds), [trace, seconds]);
  const markers = useRef(new Map<string, HTMLButtonElement>());
  useEffect(() => {
    if (!projects.length) return;
    let frame = 0;
    const update = () => {
      for (const project of projects) {
        const marker = markers.current.get(project.site.id);
        const position = engine.current?.projectSite(project.site.point);
        if (marker && position) {
          marker.style.visibility = position.visible ? 'visible' : 'hidden';
          marker.style.left = `${position.x}px`; marker.style.top = `${position.y}px`;
        }
      }
      frame = requestAnimationFrame(update);
    };
    frame = requestAnimationFrame(update);
    return () => cancelAnimationFrame(frame);
  }, [projects, engine]);
  if (trace.policy !== 'council') return null;
  const focus = (project: RolloutProject) => engine.current?.focusProposedSite(project.site.point);
  const clock = (time: number) => at(time, trace.start_time, trace.timezone);
  return <>
    <div className="rollout-markers" aria-label="Project markers">
      {projects.map(project => {
        const Icon = project.status === 'blocked' ? TriangleAlert : icons[project.stage];
        return <button key={project.site.id} type="button" className={`rollout-pin ${project.status}`}
          ref={element => { if (element) markers.current.set(project.site.id, element); else markers.current.delete(project.site.id); }}
          aria-label={`Focus ${project.site.name}: ${project.label}`} onClick={() => focus(project)}>
          <span className="rollout-pin-icon"><Icon size={22} /></span>
          <span className="rollout-pin-info"><strong>{project.label}</strong>
            <span>{project.nextAt === null ? project.status : `${countdown(project.remaining)} simulated`}</span>
            <Progress project={project} />
          </span>
        </button>;
      })}
    </div>
    <section className="rollout-tracker" aria-label="Council project tracker">
      <div className="rollout-tracker-heading"><span><Hammer size={17} /> COUNCIL PROJECTS</span>
        <b>{projects.length} {projects.length === 1 ? 'site' : 'sites'}</b></div>
      <div className="rollout-arm-switch" aria-label="Comparison view">
        {(['baseline', 'intervention'] as const).map(arm => <button type="button" key={arm}
          aria-pressed={trace.run_ref.arm === arm} onClick={() => onSwitchArm(arm)}>
          {arm === 'baseline' ? 'Baseline' : 'Approved changes'}
        </button>)}
      </div>
      {projects.length === 0 && <p className="rollout-note">This baseline has no municipal site rollout. Choose Approved changes to watch the proposal.</p>}
      {projects.map(project => {
        const Icon = project.status === 'blocked' ? TriangleAlert : icons[project.stage];
        const done = new Set(project.completed.map(event => event.event_id));
        return <article key={project.site.id} className={`rollout-project ${project.status}`}>
          <div className="rollout-project-title"><span className="rollout-project-icon"><Icon size={23} /></span>
            <div><span className="rollout-status">{project.status}</span><h2>{project.site.name}</h2></div></div>
          <div className="rollout-stage"><strong>{project.label}</strong><span>{project.nextAt === null ? 'Recorded outcome' : countdown(project.remaining)}</span></div>
          <Progress project={project} />
          <p className="rollout-schedule-note">{project.nextAt === null ? 'Simulation replay' : `Next milestone ${clock(project.nextAt)} · simulated time`}</p>
          {project.reason && <p className="rollout-blocked-reason">{project.reason}</p>}
          <div className="rollout-project-metrics">
            <span><b>{project.served}</b>served</span><span><b>{project.capacity}</b>visit limit</span><span><b>{(project.stock / 1000).toFixed(1)} kg</b>stock</span>
          </div>
          <div className="rollout-project-actions">
            <button type="button" onClick={() => focus(project)}><MapPin size={14} /> Locate site</button>
            <button type="button" onClick={onReplay}><Play size={14} /> Replay rollout</button>
          </div>
          <details className="rollout-milestones"><summary>Track milestones · {project.completed.length} completed</summary>
            <ol>{project.milestones.map(event => {
              const reached = event.simulation_time <= seconds;
              const complete = done.has(event.event_id);
              const EventIcon = reached && event.status === 'blocked' ? TriangleAlert : complete ? Check : icons[event.stage];
              return <li key={event.event_id} className={complete ? 'done' : reached ? 'failed' : 'pending'}>
                <EventIcon size={14} /><span>{stageLabels[event.stage as RolloutEvent['stage']]}<small>{clock(event.simulation_time)} · {reached ? event.status : 'upcoming'}</small></span>
                <button type="button" aria-label={`View ${event.stage} milestone`} onClick={() => onSeek(event.simulation_time)}><ArrowUpRight size={14} /></button>
              </li>;
            })}</ol>
          </details>
        </article>;
      })}
      <label className="rollout-timeline">Replay position <b>{clock(seconds)}</b>
        <input aria-label="Rollout replay time" type="range" min={0} max={trace.horizon_seconds} step={1}
          value={Math.floor(seconds)} onChange={event => onSeek(Number(event.target.value))} />
      </label>
      <p className="rollout-note">Bars show schedule time, not measured construction work. Site visuals are illustrative; recorded events control service.</p>
    </section>
  </>;
}
