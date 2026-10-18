import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { parseDistrict } from './district.ts';
import { foodCrowd, foodInspection, foodMetrics, foodPose, foodView } from './interactables.ts';
import type { FoodTrace } from './interactables.ts';

const trace = JSON.parse(readFileSync(new URL('../public/data/interactables/200-baseline.json', import.meta.url), 'utf8')) as FoodTrace;
const district = parseDistrict(JSON.parse(readFileSync(new URL('../public/data/toronto.json', import.meta.url), 'utf8')));
const crowd = foodCrowd(trace, district);

test('seeking backward restores opening balances and never applies future events', () => {
  const end = foodView(trace, trace.horizon_seconds);
  const start = foodView(trace, 0);
  assert.deepEqual(start.households, trace.initial_households);
  assert.equal(start.events.length, 0);
  assert.deepEqual(foodView(trace, trace.horizon_seconds), end);
  const event = trace.events.find(e => e.action === 'purchase')!;
  const before = foodView(trace, event.simulation_time - 1);
  assert.ok(before.events.every(e => e.simulation_time < event.simulation_time));
  assert.ok(!before.events.some(e => e.event_id === event.event_id));
  assert.deepEqual(trace.initial_households, start.households);
});

test('food stays carried until the committed return-home event', () => {
  const event = trace.events.find(e => e.action === 'purchase')!;
  const trip = trace.journeys[event.household_id!]!;
  const collected = foodView(trace, event.simulation_time).households[event.household_id!]!;
  assert.ok(collected.carrying_grams > 0);
  const home = foodView(trace, trip.home_at).households[event.household_id!]!;
  assert.equal(home.carrying_grams, 0);
  assert.ok(home.pantry_grams > collected.pantry_grams);
});

test('resident playback follows trip timing, returns home, and stops at the day boundary', () => {
  const h = trace.households.find(h => trace.journeys[h.id])!;
  const resident = crowd.residents[h.resident_id]!, trip = trace.journeys[h.id]!;
  assert.equal(foodInspection(trace, resident, 0).activity, 'At home');
  const start = foodPose(trace, resident, 0), end = foodPose(trace, resident, trace.horizon_seconds);
  assert.equal(end.walking, false);
  assert.equal(end.x, start.x); assert.equal(end.z, start.z);
  const arrival = foodPose(trace, resident, trip.arrival);
  const destination = resident.route.at(-1)!;
  assert.equal(arrival.x, destination[0]); assert.equal(arrival.z, destination[1]);
  assert.equal(arrival.walking, false);
  assert.deepEqual(foodPose(trace, resident, trip.arrival), arrival);
});

test('dashboard totals and strata agree with committed household projections', () => {
  const view = foodView(trace, trace.horizon_seconds), metrics = foodMetrics(trace, view);
  assert.equal(metrics.unmet, Object.values(view.households).reduce((n, h) => n + h.unmet_grams, 0));
  for (const dimension of ['area', 'income_band', 'size', 'mobility'] as const) {
    const groups = Object.values(metrics.strata(dimension));
    assert.equal(groups.reduce((n, g) => n + g.count, 0), trace.population);
    assert.equal(groups.reduce((n, g) => n + g.unmet, 0), metrics.unmet);
    assert.equal(groups.reduce((n, g) => n + g.obtained, 0), metrics.purchased + metrics.received);
  }
});
