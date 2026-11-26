/** Which dated run, task and shard own a machine reading? */
import { DIGEST_PIPELINE } from './serving-speed';

const LEGACY_DIGEST_TASKS = new Set(['plan', 'work', 'assemble']);

export function shardKey(
	date: string,
	runId: string,
	job: string | null | undefined,
	shard: number | string | null,
	pipelineName?: string | null,
	taskName?: string | null,
	attempt?: number | string | null
): string | null {
	if (shard === null || (typeof shard === 'string' && shard.trim() === '') ||
		!Number.isSafeInteger(Number(shard)) || Number(shard) < 0) return null;
	if (Boolean(pipelineName) !== Boolean(taskName)) return null;
	const name = job || 'work';
	const task = pipelineName && taskName ? [pipelineName, taskName]
		: LEGACY_DIGEST_TASKS.has(name) ? [DIGEST_PIPELINE, name] : [name];
	const tryNumber = attempt == null || attempt === '' ? null : Number(attempt);
	if (tryNumber !== null && (!Number.isSafeInteger(tryNumber) || tryNumber < 1)) return null;
	return JSON.stringify([date, runId, task, Number(shard), tryNumber]);
}
