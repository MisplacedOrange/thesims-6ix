import type { PlanCommand } from './council.ts';

export type PlannerDraft = {
  id: string; sha256: string; call_id: string; input_sha256: string; source_revision: number;
  command: PlanCommand;
  context: { proposal: { id: string; sha256: string }; scope: { id: string; sha256: string } };
  output: { rationale: string; assumptions: string; exclusions: string; uncertainties: string };
};
export type PlannerCall = {
  id: string; status: 'running' | 'completed' | 'failed'; model: string; started_at: string;
  response_id?: string; resolved_model?: string; request_id?: string; usage?: unknown;
  error?: { code: string; message: string };
};
export type PlannerState = {
  ready: boolean; reason: string | null; model: string; timeout_seconds: number;
  max_output_tokens: number; drafts: PlannerDraft[]; calls: PlannerCall[];
};

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function reference(value: unknown): boolean {
  return record(value) && typeof value.id === 'string' && typeof value.sha256 === 'string';
}
export function isPlannerState(value: unknown): value is PlannerState {
  if (!record(value)) return false;
  return typeof value.ready === 'boolean' && (value.reason === null || typeof value.reason === 'string')
    && typeof value.model === 'string' && Number.isInteger(value.timeout_seconds) && Number.isInteger(value.max_output_tokens)
    && Array.isArray(value.drafts) && value.drafts.every(draft => record(draft) && reference(draft)
      && typeof draft.call_id === 'string' && typeof draft.input_sha256 === 'string' && Number.isInteger(draft.source_revision)
      && record(draft.context) && reference(draft.context.proposal) && reference(draft.context.scope)
      && record(draft.command) && typeof draft.command.action === 'string'
      && typeof draft.command.proposal_id === 'string' && typeof draft.command.scope_id === 'string'
      && Number.isInteger(draft.command.population) && Number.isInteger(draft.command.seed)
      && record(draft.output) && ['rationale', 'assumptions', 'exclusions', 'uncertainties'].every(key => typeof (draft.output as Record<string, unknown>)[key] === 'string'))
    && Array.isArray(value.calls) && value.calls.every(call => record(call) && typeof call.id === 'string'
      && ['running', 'completed', 'failed'].includes(String(call.status)) && typeof call.model === 'string'
      && typeof call.started_at === 'string' && (call.error === undefined || (record(call.error)
        && typeof call.error.code === 'string' && typeof call.error.message === 'string')));
}
