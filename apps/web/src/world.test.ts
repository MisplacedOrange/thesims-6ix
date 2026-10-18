import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { Building, Point } from './district.ts';
import { buildSurroundings, CAMERA_LIMIT, clampToBox, CORE, inDonValley, insidePolygon, landPolygon, outsideCore,
  resolveBuildingParts, streetGridAngle } from './world.ts';

const square = (x: number, z: number, size: number): Point[] =>
  [[x, z], [x + size, z], [x + size, z + size], [x, z + size], [x, z]];
const building = (id: string, polygon: Point[], height: number): Building =>
  ({ id, name: '', polygon, height, base: 0, basis: 'tag', use: 'yes' });

test('the camera is held inside its box and keeps in-bounds positions', () => {
  assert.deepEqual(clampToBox({ x: 9000, z: -9000 }, CAMERA_LIMIT), { x: CAMERA_LIMIT.maxX, z: CAMERA_LIMIT.minZ });
  assert.deepEqual(clampToBox({ x: 10, z: 20 }, CAMERA_LIMIT), { x: 10, z: 20 });
});

test('an outline covered by its building parts is dropped', () => {
  const outline = building('outline', square(0, 0, 40), 120);
  const parts = [building('podium', [[0, 0], [40, 0], [40, 20], [0, 20], [0, 0]], 20),
    building('tower', [[0, 20], [40, 20], [40, 40], [0, 40], [0, 20]], 120)];

  assert.deepEqual(resolveBuildingParts([outline, ...parts]).map(b => b.id), ['podium', 'tower']);
});

test('raised parts do not replace the outline that holds them up', () => {
  const outline = building('outline', square(0, 0, 40), 120);
  const crown = { ...building('crown', square(0, 0, 40), 120), polygon: [[0, 0], [40, 0], [40, 39], [0, 39], [0, 0]] as Point[], base: 90 };

  assert.deepEqual(resolveBuildingParts([outline, crown]).map(b => b.id), ['outline', 'crown']);
});

test('a part inside a kept outline is inset so no wall or roof coincides', () => {
  const podium = building('podium', square(0, 0, 60), 15);
  const tower = building('tower', square(0, 0, 20), 15);
  const [kept, inset] = resolveBuildingParts([podium, tower]);

  assert.equal(kept!.id, 'podium');
  assert.equal(inset!.id, 'tower');
  assert.ok(inset!.polygon.every(([x, z]) => x > 0 && z > 0 && x < 20 && z < 20));
  assert.ok(inset!.height < podium.height);
});

test('identical footprints keep only the taller building', () => {
  const result = resolveBuildingParts([building('low', square(0, 0, 30), 10), building('high', square(0, 0, 30), 30)]);

  assert.deepEqual(result.map(b => b.id), ['high']);
});

test('the street grid angle is recovered from mapped road directions', () => {
  const angle = -17 * Math.PI / 180, roads = [];
  for (let i = 0; i < 6; i++) {
    roads.push({ kind: 'primary', points: [[0, i * 100], [Math.cos(angle) * 500, i * 100 + Math.sin(angle) * 500]] as Point[] });
    roads.push({ kind: 'residential', points: [[i * 100, 0], [i * 100 - Math.sin(angle) * 300, Math.cos(angle) * 300]] as Point[] });
  }

  assert.ok(Math.abs(streetGridAngle(roads) - angle) < 1 * Math.PI / 180);
});

test('procedural fill stays on land, outside the mapped core and the Don Valley', () => {
  const land = landPolygon([[-6000, 2000], [0, 1500], [6000, 900]], 7000);
  const { buildings, blocks } = buildSurroundings(-0.29, land);

  assert.ok(blocks.length > 500 && buildings.length > 1500);
  for (const b of buildings) {
    assert.ok(outsideCore(b.x, b.z) > 0, 'inside core at ' + b.x + ',' + b.z);
    assert.ok(insidePolygon([b.x, b.z], land), 'in the lake at ' + b.x + ',' + b.z);
    assert.ok(!inDonValley(b.x, b.z), 'in the valley at ' + b.x + ',' + b.z);
  }
  assert.ok(buildings.some(b => b.x > CORE.maxX) && buildings.some(b => b.x < CORE.minX) && buildings.some(b => b.z < CORE.minZ));
});
