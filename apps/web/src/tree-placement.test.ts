import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildRoadClearanceIndex, isCircleClearOfRoads } from './treePlacement.ts';

test('tree canopies are rejected when they overlap a mapped road ribbon', () => {
  const roads = buildRoadClearanceIndex([{ width: 10, points: [[0, 0], [100, 0]] }]);

  assert.equal(isCircleClearOfRoads([50, 7], 2, roads), false);
  assert.equal(isCircleClearOfRoads([50, 8], 2, roads), true);
});

test('the street-tree crown fits outside its source road at the curb setback', () => {
  const roads = buildRoadClearanceIndex([{ width: 10, points: [[0, 0], [100, 0]] }]);

  assert.equal(isCircleClearOfRoads([50, 9.4], 3.3, roads), true);
  assert.equal(isCircleClearOfRoads([50, 9.4], 6.6, roads), false);
});

test('road clearance finds segments across spatial-index cell boundaries', () => {
  const roads = buildRoadClearanceIndex([{ width: 4, points: [[63, -20], [63, 20]] }]);

  assert.equal(isCircleClearOfRoads([66, 0], 2, roads), false);
  assert.equal(isCircleClearOfRoads([70, 0], 2, roads), true);
});
