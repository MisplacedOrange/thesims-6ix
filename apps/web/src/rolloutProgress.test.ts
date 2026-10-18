import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { CouncilFoodTrace, InteractionEvent, RolloutEvent } from './interactables.ts';
import { countdown, rolloutProjects } from './rolloutProgress.ts';

function fixture(): CouncilFoodTrace {
  const trace = JSON.parse(readFileSync(new URL('../public/data/interactables/600-baseline.json', import.meta.url), 'utf8')) as CouncilFoodTrace;
  trace.policy = 'council'; trace.run_id = 'rollout-fixture';
  trace.run_ref = { kind: 'council', run_id: trace.run_id, arm: 'intervention' };
  const site = { ...trace.sites[0]!, id: 'council-site-test', type: 'council' as const,
    name: 'Hypothetical site', active_from: 8000, opens: 8000, closes: 20000 };
  trace.sites = [site];
  const initial = { ...Object.values(trace.initial_sites)[0]!, capacity: 0, served: 0, stock_grams: 0 };
  trace.initial_sites = { [site.id]: initial };
  const base = trace.events[0]!;
  trace.events = [{ ...base, simulation_time: 8000, household_id: null, site_id: site.id,
    site_state: { ...initial, capacity: 12, stock_grams: 20000 } },
  { ...base, simulation_time: 10000, household_id: null, site_id: site.id,
    site_state: { ...initial, capacity: 12, served: 1, stock_grams: 19000 } }] as InteractionEvent[];
  trace.rollout_events = (['readiness', 'funding', 'delivery', 'commissioning', 'opening', 'closure'] as const)
    .map((stage, index) => ({ event_id: `stage-${index}`, stage,
      simulation_time: [500, 1000, 6000, 7000, 8000, 20000][index]!, status: 'completed',
      reason: null, amount_cents: 0, capacity: stage === 'opening' ? 12 : 0, stock_grams: 0 }));
  return trace;
}

test('progress is schedule time and service does not activate before committed opening', () => {
  const trace = fixture();
  const preparing = rolloutProjects(trace, 6500)[0]!;
  assert.equal(preparing.label, 'Commissioning'); assert.equal(preparing.progress, .5);
  assert.equal(preparing.status, 'preparing'); assert.equal(preparing.remaining, 500);
  assert.equal(preparing.capacity, 0); assert.equal(preparing.stock, 0); assert.equal(preparing.served, 0);
  const open = rolloutProjects(trace, 8000)[0]!;
  assert.equal(open.status, 'operating'); assert.equal(open.capacity, 12); assert.equal(open.stock, 20000);
  assert.equal(open.served, 0); assert.equal(open.nextAt, 20000);
  assert.equal(rolloutProjects(trace, 10000)[0]!.served, 1);
});

test('rewinding restores milestones and earlier state without carrying future progress', () => {
  const trace = fixture();
  assert.equal(rolloutProjects(trace, 20000)[0]!.status, 'closed');
  const rewound = rolloutProjects(trace, 250)[0]!;
  assert.equal(rewound.status, 'planned'); assert.equal(rewound.progress, .5);
  assert.equal(rewound.completed.length, 0); assert.equal(rewound.capacity, 0); assert.equal(rewound.served, 0);
  assert.equal(countdown(-10), '0s'); assert.equal(countdown(3660), '1h 1m');
});

test('blocked launch does not reveal a future failure or show an operating site', () => {
  const trace = fixture(); trace.events = [];
  trace.rollout_events = [trace.rollout_events[0]!, { ...trace.rollout_events[1]!, stage: 'no_launch',
    status: 'blocked', reason: 'Funding unavailable' }];
  const before = rolloutProjects(trace, 700)[0]!;
  assert.equal(before.status, 'preparing'); assert.equal(before.reason, null);
  const blocked = rolloutProjects(trace, 1000)[0]!;
  assert.equal(blocked.status, 'blocked'); assert.equal(blocked.reason, 'Funding unavailable');
  assert.equal(blocked.capacity, 0); assert.equal(blocked.nextAt, null);
});

test('capacity-zero changes close the site at their event time', () => {
  const trace = fixture();
  const change: RolloutEvent = { ...trace.rollout_events[4]!, event_id: 'capacity', stage: 'capacity_change', simulation_time: 12000, capacity: 0 };
  trace.rollout_events.splice(5, 0, change);
  trace.events.push({ ...trace.events[0]!, simulation_time: 12000, site_state: { ...trace.initial_sites['council-site-test']!, capacity: 0 } });
  assert.equal(rolloutProjects(trace, 11999)[0]!.status, 'operating');
  assert.equal(rolloutProjects(trace, 12000)[0]!.status, 'closed');
});

test('establishment baseline has no invented project marker', () => {
  const trace = fixture(); trace.run_ref.arm = 'baseline'; trace.sites = [];
  assert.deepEqual(rolloutProjects(trace, 10000), []);
});
