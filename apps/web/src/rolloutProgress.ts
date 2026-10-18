import { foodView } from './interactables.ts';
import type { FoodTrace, FoodView, RolloutEvent, Site } from './interactables.ts';

export type RolloutProject = {
  site: Site; status: 'planned' | 'preparing' | 'operating' | 'closed' | 'blocked';
  stage: RolloutEvent['stage'] | 'waiting'; label: string; progress: number;
  nextAt: number | null; remaining: number; reason: string | null;
  completed: RolloutEvent[]; milestones: RolloutEvent[];
  capacity: number; served: number; stock: number;
};
export const stageLabels: Record<RolloutEvent['stage'], string> = {
  readiness: 'Site preparation', funding: 'Funding', delivery: 'Supplier delivery',
  commissioning: 'Commissioning', opening: 'Opening', closure: 'Closure',
  capacity_change: 'Capacity change', blocked: 'Review', no_launch: 'Review',
};

/** Schedule interpolation is presentation only. Effects come from events at/before the playhead. */
export function rolloutProjects(trace: FoodTrace, seconds: number, view?: FoodView): RolloutProject[] {
  if (trace.policy !== 'council' || !trace.rollout_events.length) return [];
  const time = Math.max(0, Math.min(trace.horizon_seconds, seconds));
  const state = view ?? foodView(trace, time);
  const milestones = [...trace.rollout_events].sort((a, b) => a.simulation_time - b.simulation_time);
  const reached = milestones.filter(event => event.simulation_time <= time);
  const completed = reached.filter(event => event.status === 'completed');
  const failure = reached.find(event => event.status === 'blocked');
  const lastCapacity = completed.filter(event => event.stage === 'opening' || event.stage === 'capacity_change').at(-1);
  const closed = completed.some(event => event.stage === 'closure')
    || (lastCapacity?.stage === 'capacity_change' && lastCapacity.capacity === 0);
  const opened = completed.some(event => event.stage === 'opening');
  const next = milestones.find(event => event.simulation_time > time);
  const previousAt = reached.at(-1)?.simulation_time ?? 0;
  const terminal = Boolean(failure) || closed;
  const stage = !terminal && next ? next.stage : reached.at(-1)?.stage ?? 'waiting';
  const progress = terminal || !next ? 1 : Math.max(0, Math.min(1,
    (time - previousAt) / Math.max(1, next.simulation_time - previousAt)));
  // The current Council format owns one site per trace; rollout events describe that site.
  return trace.sites.filter(site => site.type === 'council').map(site => ({
    site, status: failure ? 'blocked' : closed ? 'closed' : opened ? 'operating' : completed.length ? 'preparing' : 'planned',
    stage, label: failure ? 'Launch blocked' : closed ? 'Service closed' : opened && stage === 'closure' ? 'Open for service'
      : stage === 'waiting' ? 'Awaiting schedule' : stageLabels[stage],
    progress, nextAt: terminal ? null : next?.simulation_time ?? null,
    remaining: terminal || !next ? 0 : Math.max(0, next.simulation_time - time),
    reason: failure?.reason ?? null, completed, milestones,
    capacity: state.sites[site.id]?.capacity ?? 0,
    served: state.sites[site.id]?.served ?? 0, stock: state.sites[site.id]?.stock_grams ?? 0,
  }));
}

export function countdown(seconds: number): string {
  const value = Math.max(0, Math.ceil(seconds));
  const hours = Math.floor(value / 3600), minutes = Math.floor(value % 3600 / 60), rest = value % 60;
  return hours ? `${hours}h ${minutes}m` : minutes ? `${minutes}m ${rest}s` : `${rest}s`;
}
