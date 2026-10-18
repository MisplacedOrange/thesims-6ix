import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { isCouncilFoodTrace, isCouncilState, loadCouncilState } from './council.ts';
import type { CouncilRunRef } from './runRef.ts';

const expectedRun: CouncilRunRef = { kind: 'council', run_id: 'custom-run-17', arm: 'intervention' };

test('a stale Council backend gives restart instructions and names missing fields', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ schema: 1, organizations: [] }), {
    headers: { 'Content-Type': 'application/json' },
  });
  try {
    await assert.rejects(loadCouncilState(), error => error instanceof Error
      && error.message.includes('older version') && error.message.includes('organization_records')
      && error.message.includes('stakeholder_inputs') && error.message.includes('restart'));
  } finally { globalThis.fetch = originalFetch; }
});

function validTrace(): Record<string, unknown> {
  const trace = JSON.parse(readFileSync(new URL('../public/data/interactables/600-baseline.json', import.meta.url), 'utf8')) as Record<string, unknown>;
  trace.policy = 'council';
  trace.run_id = expectedRun.run_id;
  trace.run_ref = expectedRun;
  trace.rollout_events = [{ event_id: 'rollout-0', stage: 'readiness', simulation_time: 3600,
    status: 'completed', reason: 'Scenario readiness assumption.', amount_cents: 0, stock_grams: 0, capacity: 0 }];
  return trace;
}

test('Council trace decoder accepts a valid trace only for its exact run and arm', () => {
  assert.equal(isCouncilFoodTrace(validTrace(), expectedRun), true);
  assert.equal(isCouncilFoodTrace(validTrace(), { ...expectedRun, arm: 'baseline' }), false);
  assert.equal(isCouncilFoodTrace(validTrace(), { ...expectedRun, run_id: 'custom-run-18' }), false);
});

test('Council trace decoder accepts the Council service-site type', () => {
  const trace = validTrace();
  const sites = trace.sites as Array<Record<string, unknown>>;
  sites[0]!.type = 'council';
  assert.equal(isCouncilFoodTrace(trace, expectedRun), true);
});

test('Council trace decoder rejects wrong schema and broken accounting', () => {
  const wrongSchema = validTrace();
  wrongSchema.schema = 2;
  assert.equal(isCouncilFoodTrace(wrongSchema, expectedRun), false);

  const brokenBalance = validTrace();
  (brokenBalance.accounting as Record<string, unknown>).consumed_grams = -1;
  assert.equal(isCouncilFoodTrace(brokenBalance, expectedRun), false);

  const reportedInvariant = validTrace();
  (reportedInvariant.accounting as Record<string, unknown>).invariant_problems = ['broken conservation'];
  assert.equal(isCouncilFoodTrace(reportedInvariant, expectedRun), false);
});

test('Council trace decoder rejects malformed records before scene and dashboard use them', () => {
  for (const field of ['sites', 'households', 'events'] as const) {
    const trace = validTrace();
    trace[field] = [null];
    assert.equal(isCouncilFoodTrace(trace, expectedRun), false, `${field} entries must be decoded`);
  }

  const invalidJourney = validTrace();
  invalidJourney.journeys = { route: null };
  assert.equal(isCouncilFoodTrace(invalidJourney, expectedRun), false);

  const invalidInitialState = validTrace();
  invalidInitialState.initial_sites = { site: null };
  assert.equal(isCouncilFoodTrace(invalidInitialState, expectedRun), false);
});

test('Council state decoder rejects unsupported schema versions', () => {
  const state = { schema: 1, session_id: 'session', revision: 0, proposal: null, scope: null,
    scope_history: [], proposal_history: [], plan: null, organizations: [], organization_records: [],
    stakeholder_inputs: [], decisions: [], runs: [], locations: [], service: { available: true } };
  assert.equal(isCouncilState(state), true);
  assert.equal(isCouncilState({ ...state, schema: 2 }), false);
  assert.equal(isCouncilState({ ...state, action_catalog: [null] }), false);
  assert.equal(isCouncilState({ ...state, action_catalog: [{ action: 'expand_facility', version: 1,
    executable: true, label: 'Expand', inputs: 'Base site and target', effects: 'Visit limit', limits: 'Six hours' }] }), true);
});

test('Council trace decoder accepts capacity changes and rejects unknown stages', () => {
  const trace = validTrace();
  (trace.rollout_events as Array<Record<string, unknown>>)[0]!.stage = 'capacity_change';
  assert.equal(isCouncilFoodTrace(trace, expectedRun), true);
  (trace.rollout_events as Array<Record<string, unknown>>)[0]!.stage = 'unvalidated_world_edit';
  assert.equal(isCouncilFoodTrace(trace, expectedRun), false);
});
