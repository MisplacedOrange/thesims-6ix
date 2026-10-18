import { isRunRef } from './runRef.ts';
import type { CouncilRunRef, PresetRunRef, RunRef } from './runRef.ts';

export const LIVE_RUN_CHANNEL = 'the-sims-6ix:live-run:v1';

type LiveRunFields = {
  type: 'simulation-state';
  scenario_id: string;
  seed: number;
  input_snapshot_id: string | null;
  source_snapshot_id: string | null;
  seconds: number;
  horizon_seconds: number;
  paused: boolean;
  speed: number;
  published_at: number;
  live_trace_url?: string;
  live_day?: number;
};

export type LiveRunState = LiveRunFields & (
  | { run_ref: PresetRunRef; population: number; policy: 'baseline' | 'emergency' }
  | { run_ref: CouncilRunRef; population: number; policy: 'council' }
);

export type DashboardCommand =
  | { type: 'dashboard-seek'; run_ref: RunRef; seconds: number }
  | { type: 'dashboard-select-run'; run_ref: RunRef };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function isLiveRunState(value: unknown): value is LiveRunState {
  if (!isRecord(value) || value.type !== 'simulation-state' || !isRunRef(value.run_ref)) return false;
  const runRef = value.run_ref;
  const identityMatches = runRef.kind === 'preset'
    ? value.population === runRef.population && value.policy === runRef.policy
    : Number.isInteger(value.population) && isFiniteNumber(value.population) && value.population > 0 && value.policy === 'council';
  return identityMatches
    && typeof value.scenario_id === 'string'
    && isFiniteNumber(value.seed)
    && (value.input_snapshot_id === null || typeof value.input_snapshot_id === 'string')
    && (value.source_snapshot_id === null || typeof value.source_snapshot_id === 'string')
    && isFiniteNumber(value.seconds) && value.seconds >= 0
    && isFiniteNumber(value.horizon_seconds) && value.horizon_seconds >= 0
    && (value.live_trace_url === undefined || (typeof value.live_trace_url === 'string'
      && /^\/api\/council\/live\/[a-zA-Z0-9-]+$/.test(value.live_trace_url)))
    && (value.live_day === undefined || (isFiniteNumber(value.live_day) && Number.isInteger(value.live_day) && value.live_day >= 0))
    && typeof value.paused === 'boolean'
    && isFiniteNumber(value.speed)
    && isFiniteNumber(value.published_at);
}

export function isDashboardCommand(value: unknown): value is DashboardCommand {
  if (!isRecord(value) || !isRunRef(value.run_ref)) return false;
  if (value.type === 'dashboard-seek') return isFiniteNumber(value.seconds) && value.seconds >= 0;
  return value.type === 'dashboard-select-run';
}
