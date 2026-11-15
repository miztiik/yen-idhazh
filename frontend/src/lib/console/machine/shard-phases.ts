/** How much prefill and decode time did each recorded shard spend? */
import type { Row } from '../../data/ledger';
import { isDay } from '../../data/slice-shapes';
import { finiteCell, qualifyingWork } from '../rates';
import { shardKey } from './shard-key';

/** Ledger durations are milliseconds; chart durations are seconds. */
const MS_PER_SECOND = 1000;

function identity(row: Row, item: boolean): string | null {
	if (typeof row.date !== 'string' || !isDay(row.date) ||
		typeof row.run_id !== 'string' || !row.run_id.trim()) return null;
	const job = item ? row.machine_job : row.job;
	const pipeline = item ? row.machine_pipeline_name : row.pipeline_name;
	const task = item ? row.machine_task_name : row.task_name;
	return shardKey(row.date, row.run_id, typeof job === 'string' ? job : null,
		finiteCell(item ? row.machine_shard : row.shard),
		typeof pipeline === 'string' ? pipeline : null, typeof task === 'string' ? task : null);
}

export function shardPhases(rows: readonly Row[], hosts: readonly Row[]) {
	const metadata = new Map<string, { cpus: Set<string>; caches: Set<number> }>();
	for (const host of hosts) {
		const key = identity(host, false);
		if (key === null) continue;
		const held = metadata.get(key) ?? { cpus: new Set<string>(), caches: new Set<number>() };
		if (typeof host.cpu_model === 'string' && host.cpu_model.trim()) held.cpus.add(host.cpu_model);
		const cache = finiteCell(host.l3_cache_bytes);
		if (cache !== null && Number.isSafeInteger(cache) && cache >= 0) held.caches.add(cache);
		metadata.set(key, held);
	}
	const shards = new Map<string, {
		key: string; label: string; cpus: Set<string>;
		articles: number; prefill: number; decode: number; input: number; output: number
	}>();
	let excluded = 0;
	for (const row of rows) {
		const work = qualifyingWork(row);
		const key = identity(row, true);
		const prefill = finiteCell(row.prefill_ms), decode = finiteCell(row.decode_ms);
		if (key === null || work === null || prefill === null || decode === null || prefill <= 0 || decode <= 0) {
			excluded++;
			continue;
		}
		const task = row.machine_pipeline_name && row.machine_task_name
			? `${row.machine_pipeline_name}/${row.machine_task_name}` : row.machine_job || 'work';
		const held = shards.get(key) ?? {
			key, label: `${row.date} UTC; run ${row.run_id}; ${task}; shard ${row.machine_shard}`,
			cpus: new Set<string>(), articles: 0, prefill: 0, decode: 0, input: 0, output: 0
		};
		if (typeof row.cpu_model === 'string' && row.cpu_model.trim()) held.cpus.add(row.cpu_model);
		held.articles++;
		held.prefill += prefill / MS_PER_SECOND;
		held.decode += decode / MS_PER_SECOND;
		held.input += work.freshInput;
		held.output += work.output;
		shards.set(key, held);
	}
	return {
		excluded,
		shards: [...shards.values()].map(({ cpus, ...shard }) => {
			const host = metadata.get(shard.key);
			const prefillTps = shard.input / shard.prefill;
			const decodeTps = shard.output / shard.decode;
			return {
				...shard, prefillTps, decodeTps, total: shard.prefill + shard.decode,
				prefillShare: 100 * shard.prefill / (shard.prefill + shard.decode),
				cpuModels: [...(host?.cpus.size ? host.cpus : cpus)].sort(),
				l3CacheBytes: [...(host?.caches ?? [])].sort((a, b) => a - b)
			};
		}).sort((a, b) => b.total - a.total || a.label.localeCompare(b.label))
	};
}
