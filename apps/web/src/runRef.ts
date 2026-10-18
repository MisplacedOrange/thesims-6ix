export type PresetRunRef = { kind: 'preset'; population: number; policy: 'baseline' | 'emergency' };
export type CouncilRunRef = { kind: 'council'; run_id: string; arm: 'baseline' | 'intervention' };
export type RunRef = PresetRunRef | CouncilRunRef;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isRunRef(value: unknown): value is RunRef {
  if (!isRecord(value)) return false;
  if (value.kind === 'preset') {
    return typeof value.population === 'number' && [200, 600, 1200, 2400].includes(value.population)
      && (value.policy === 'baseline' || value.policy === 'emergency');
  }
  return value.kind === 'council' && typeof value.run_id === 'string' && value.run_id.length > 0
    && (value.arm === 'baseline' || value.arm === 'intervention');
}

export function parseRunRef(value: string | null): RunRef | null {
  if (!value?.startsWith('council:')) return null;
  const body = value.slice('council:'.length);
  const separator = body.lastIndexOf(':');
  if (separator <= 0) return null;
  const runId = body.slice(0, separator);
  const arm = body.slice(separator + 1);
  if (!runId || (arm !== 'baseline' && arm !== 'intervention')) return null;
  return { kind: 'council', run_id: runId, arm };
}

export function serializeRunRef(runRef: RunRef): string | null {
  return runRef.kind === 'council' ? `council:${runRef.run_id}:${runRef.arm}` : null;
}

export function sameRunRef(left: RunRef, right: RunRef): boolean {
  switch (left.kind) {
    case 'preset':
      return right.kind === 'preset' && left.population === right.population && left.policy === right.policy;
    case 'council':
      return right.kind === 'council' && left.run_id === right.run_id && left.arm === right.arm;
    default: {
      const exhaustive: never = left;
      return exhaustive;
    }
  }
}
