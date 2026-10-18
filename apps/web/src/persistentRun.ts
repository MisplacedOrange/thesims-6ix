import type { FoodTrace } from './interactables.ts';
import type { RunRef } from './runRef.ts';
import { loadRunTrace } from './runTrace.ts';

async function command(path: string, body: object): Promise<FoodTrace> {
  const response = await fetch(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Council-Schema': '1' },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message ?? 'The next simulation day could not load.');
  return result as FoodTrace;
}

export function startPersistentRun(run: RunRef): Promise<FoodTrace> {
  return run.kind === 'preset'
    ? command('/api/council/live', { population: run.population, policy: run.policy })
    : loadRunTrace(run);
}

export function nextPersistentDay(trace: FoodTrace): Promise<FoodTrace> {
  if (!trace.live_session_id || trace.live_day === undefined) throw new Error('This run has no live session.');
  return command(`/api/council/live/${trace.live_session_id}/next`, { day: trace.live_day });
}

export function closePersistentRun(trace: FoodTrace | null): void {
  if (!trace?.live_session_id) return;
  void fetch(`/api/council/live/${trace.live_session_id}/close`, {
    method: 'POST', keepalive: true,
    headers: { 'Content-Type': 'application/json', 'X-Council-Schema': '1' }, body: '{}',
  }).catch(() => { /* Abandoned sessions also expire on the server. */ });
}
