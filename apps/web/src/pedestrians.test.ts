import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createCrowd, sampleResident } from './pedestrians.ts';
import { parseDistrict } from './district.ts';
import type { Point, WalkEdge } from './district.ts';

const fixture = {
  walkNodes: [[0, 0], [100, 0], [100, 100], [0, 100], [200, 100], [200, 0], [9000, 9000], [9010, 9000]] satisfies Point[],
  walkEdges: [[0, 1, 'sidewalk'], [1, 2, 'crossing'], [2, 3, 'sidewalk'], [3, 0, 'sidewalk'], [2, 4, 'sidewalk'], [4, 5, 'sidewalk'], [5, 1, 'sidewalk'], [6, 7, 'footpath']] satisfies WalkEdge[],
};
test('every itinerary uses real edges of the largest connected walking network', () => {
  const crowd = createCrowd(fixture, 80, 17);
  assert.equal(crowd.usableNodes.length, 6);
  const edges = new Set(fixture.walkEdges.flatMap(([a, b]) => [
    JSON.stringify([fixture.walkNodes[a], fixture.walkNodes[b]]),
    JSON.stringify([fixture.walkNodes[b], fixture.walkNodes[a]]),
  ]));
  for (const resident of crowd.residents) {
    assert.ok(resident.length > 0);
    for (let i = 1; i < resident.route.length; i++) {
      assert.ok(edges.has(JSON.stringify([resident.route[i - 1], resident.route[i]])));
    }
  }
});
test('seeded routes and arbitrary-time replay are independent of sampling order', () => {
  const a = createCrowd(fixture, 20, 2026), b = createCrowd(fixture, 20, 2026);
  assert.deepEqual(a, b);
  const resident = a.residents[0]!;
  const atStart = sampleResident(resident, 0), atLater = sampleResident(resident, 20);
  sampleResident(resident, 400); sampleResident(resident, 3);
  assert.deepEqual(sampleResident(resident, 0), atStart);
  assert.deepEqual(sampleResident(resident, 20), atLater);
  assert.notDeepEqual(createCrowd(fixture, 20, 99).residents, a.residents);
});
test('walking speed and a full loop preserve continuous positions', () => {
  const resident = createCrowd(fixture, 1, 23).residents[0]!;
  const walking = { ...resident, offset: 0 };
  assert.deepEqual([sampleResident(walking, 0).x, sampleResident(walking, 0).z], walking.route[0]);
  const a = sampleResident(walking, 1), b = sampleResident(walking, 2);
  assert.ok(Math.abs(Math.hypot(b.x - a.x, b.z - a.z) - resident.speed) < 0.000001);
  const cycle = resident.length / resident.speed * 2 + resident.pause * 2;
  assert.deepEqual(sampleResident(walking, cycle), sampleResident(walking, 0));
  assert.equal(sampleResident(walking, resident.length / resident.speed + 1).walking, false);
});
test('the shipped Toronto snapshot parses and yields finite routes on real data', () => {
  const value: unknown = JSON.parse(readFileSync(new URL('../public/data/toronto.json', import.meta.url), 'utf8'));
  const district = parseDistrict(value);
  assert.ok(district.buildings.length > 1000);
  assert.ok(district.shores.length > 0);
  const crowd = createCrowd(district, 30);
  assert.ok(crowd.usableNodes.length > 1000);
  for (const resident of crowd.residents) for (const seconds of [0, 10, 600, 3600]) {
    const pose = sampleResident(resident, seconds);
    assert.ok(Number.isFinite(pose.x) && Number.isFinite(pose.z));
    assert.ok(pose.progress >= 0 && pose.progress <= 1);
  }
});
