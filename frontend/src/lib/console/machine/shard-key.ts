/** Which dated run, task and shard own a machine reading? */
export function shardKey(
	date: string,
	runId: string,
	job: string | null | undefined,
	shard: number | string | null,
	pipelineName?: string | null,
	taskName?: string | null
): string | null {
	if (shard === null || (typeof shard === 'string' && shard.trim() === '') ||
		!Number.isSafeInteger(Number(shard)) || Number(shard) < 0) return null;
	const task = pipelineName && taskName ? [pipelineName, taskName] : [job || 'work'];
	return JSON.stringify([date, runId, task, Number(shard)]);
}
