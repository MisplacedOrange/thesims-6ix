export const LIVE_RUN_CHANNEL = 'the-sims-6ix:live-run:v1';

export type LiveRunState = {
  type: 'simulation-state';
  run_id: string;
  population: number;
  policy: 'baseline' | 'emergency';
  scenario_id: string;
  seed: number;
  input_snapshot_id: string | null;
  source_snapshot_id: string | null;
  seconds: number;
  horizon_seconds: number;
  paused: boolean;
  speed: number;
  published_at: number;
};

export type DashboardCommand =
  | { type: 'dashboard-seek'; seconds: number }
  | { type: 'dashboard-select-run'; population: number; policy: 'baseline' | 'emergency' };

export function liveRunId(state: Pick<LiveRunState, 'scenario_id' | 'population' | 'policy' | 'seed' | 'input_snapshot_id' | 'source_snapshot_id'>): string {
  return [state.scenario_id, state.population, state.policy, state.seed,
    state.input_snapshot_id ?? 'no-input-snapshot', state.source_snapshot_id ?? 'no-source-snapshot'].join(':');
}

export function isLiveRunState(value: unknown): value is LiveRunState {
  if (!value || typeof value !== 'object') return false;
  const state = value as Partial<LiveRunState>;
  return state.type === 'simulation-state'
    && typeof state.run_id === 'string'
    && typeof state.population === 'number' && [200, 600, 1200].includes(state.population)
    && (state.policy === 'baseline' || state.policy === 'emergency')
    && typeof state.scenario_id === 'string'
    && typeof state.seed === 'number' && Number.isFinite(state.seed)
    && (state.input_snapshot_id === null || typeof state.input_snapshot_id === 'string')
    && (state.source_snapshot_id === null || typeof state.source_snapshot_id === 'string')
    && typeof state.seconds === 'number' && Number.isFinite(state.seconds)
    && typeof state.horizon_seconds === 'number' && Number.isFinite(state.horizon_seconds)
    && typeof state.paused === 'boolean'
    && typeof state.speed === 'number' && Number.isFinite(state.speed)
    && typeof state.published_at === 'number' && Number.isFinite(state.published_at);
}

export function isDashboardCommand(value: unknown): value is DashboardCommand {
  if (!value || typeof value !== 'object') return false;
  const command = value as Record<string, unknown>;
  if (command.type === 'dashboard-seek') return typeof command.seconds === 'number' && Number.isFinite(command.seconds) && command.seconds >= 0;
  return command.type === 'dashboard-select-run'
    && typeof command.population === 'number' && [200, 600, 1200].includes(command.population)
    && (command.policy === 'baseline' || command.policy === 'emergency');
}
