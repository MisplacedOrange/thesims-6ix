import { loadCouncilTrace } from './council.ts';
import { loadFoodTrace } from './interactables.ts';
import type { FoodTrace } from './interactables.ts';
import type { RunRef } from './runRef.ts';

export function runRefForTrace(trace: FoodTrace): RunRef {
  if (trace.policy === 'council') return trace.run_ref;
  return { kind: 'preset', population: trace.population, policy: trace.policy };
}

export async function loadRunTrace(runRef: RunRef): Promise<FoodTrace> {
  switch (runRef.kind) {
    case 'preset': return loadFoodTrace(runRef.population, runRef.policy);
    case 'council': return loadCouncilTrace(runRef);
    default: {
      const exhaustive: never = runRef;
      return exhaustive;
    }
  }
}
