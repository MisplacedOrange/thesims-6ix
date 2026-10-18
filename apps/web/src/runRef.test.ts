import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRunRef, sameRunRef, serializeRunRef } from './runRef.ts';

test('Council RunRef round-trips the run ID and arm exactly', () => {
  const expected = { kind: 'council' as const, run_id: 'council-run:custom-17', arm: 'intervention' as const };
  const serialized = serializeRunRef(expected);
  assert.equal(serialized, 'council:council-run:custom-17:intervention');
  assert.deepEqual(parseRunRef(serialized), expected);
  assert.equal(sameRunRef(parseRunRef(serialized)!, expected), true);
  assert.equal(sameRunRef(expected, { ...expected, arm: 'baseline' }), false);
  assert.equal(sameRunRef(expected, { ...expected, run_id: 'council-run:custom-18' }), false);
});

test('preset RunRef remains distinct from a Council run', () => {
  assert.equal(sameRunRef(
    { kind: 'preset', population: 600, policy: 'baseline' },
    { kind: 'council', run_id: 'run-1', arm: 'baseline' },
  ), false);
  assert.equal(parseRunRef('council:run-1:unknown'), null);
});
