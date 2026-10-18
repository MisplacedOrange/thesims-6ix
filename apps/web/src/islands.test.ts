import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseIslands } from './district.ts';

const shipped: unknown = JSON.parse(readFileSync(new URL('../public/data/islands.json', import.meta.url), 'utf8'));

test('the shipped islands snapshot parses with Centre Island and both runways', () => {
  const { islands, runways } = parseIslands(shipped);
  const centre = islands.find(i => i.name === 'Centre Island');
  assert.ok(centre && centre.polygon.length > 100);
  assert.equal(runways.length, 2);
  for (const island of islands) for (const [, z] of island.polygon) assert.ok(z > 1500);
});
test('parseIslands rejects unsupported schemas and broken geometry', () => {
  assert.throws(() => parseIslands({ schema: 2, islands: [], runways: [] }), /Unsupported islands map version/);
  assert.throws(() => parseIslands({ schema: 1, islands: [{ id: 'a', name: 'a', polygon: [[0, 0], [1, 0], [0, 0]] }], runways: [] }), /Incomplete island outline/);
  assert.throws(() => parseIslands({ schema: 1, islands: [], runways: [{ id: 'r', width: 0, points: [[0, 0], [1, 1]] }] }), /Invalid runway/);
});
