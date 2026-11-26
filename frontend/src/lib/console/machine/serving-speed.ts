/** How a recorded host gets an independent prompt speed without guessing its server. */
import { promptRate } from '../../charts/machine-colour';
import type { Row } from '../../data/ledger';
import { finiteCell } from '../rates';

// Writer identities, not tunables. Other serving scopes measure different work.
export const DIGEST_PIPELINE = 'digest';
export const SERVE_SUMMARIZER = 'serve-summarizer';
export const MODEL_SERVING = 'model-serving';
const FIRST_HOST_WITH_PROMPT_TOTALS = '2026-09-19';

function hostKey(unit: Row[string], run: Row[string], attempt: Row[string]): string | null {
	return typeof unit === 'string' && unit !== '' && typeof run === 'string' && run !== '' &&
		typeof attempt === 'number' && Number.isSafeInteger(attempt) && attempt > 0
		? JSON.stringify([unit, run, attempt])
		: null;
}

function pairedSpeed(row: Row): number | null {
	const tokens = finiteCell(row.server_prompt_tokens);
	const seconds = finiteCell(row.server_prompt_seconds);
	if (tokens === null || !Number.isSafeInteger(tokens) || tokens < 0) return null;
	const rate = promptRate(tokens, seconds);
	return rate !== null && Number.isFinite(rate) ? rate : null;
}

export function servingSpeeds(rows: readonly Row[]): ReadonlyMap<string, number | null> {
	const byHost = new Map<string, number | null>();
	for (const row of rows) {
		if (row.pipeline_name !== DIGEST_PIPELINE || row.task_name !== SERVE_SUMMARIZER ||
			row.task_kind !== MODEL_SERVING) continue;
		const key = hostKey(row.host_unit_id, row.run_id, row.attempt);
		if (key === null) continue;
		if (byHost.has(key)) {
			console.warn('[machine] Multiple serving rows name the same host and attempt.');
			byHost.set(key, null);
		} else {
			byHost.set(key, pairedSpeed(row));
		}
	}
	return byHost;
}

/** Call only for a host whose schema stamp the host reader already accepted. */
export function speedForHost(host: Row, version: string, serving: ReadonlyMap<string, number | null>): number | null {
	const key = hostKey(host.unit_id, host.run_id, host.attempt);
	if (key !== null) {
		const speed = serving.get(key);
		// Null is an observed but unusable pair, not permission to fall back.
		if (speed !== undefined) return speed;
	}
	return version >= FIRST_HOST_WITH_PROMPT_TOTALS ? pairedSpeed(host) : null;
}
