/** Hardware answers over only its declared query cells. No disk or manifest reads. */
import type { Row } from '../../data/ledger';
import { normalizeHostRow } from '../../data/host-fingerprint';
import type { MachineProcessors } from './article-cost';
import { machineCounters, type MachineLimits } from './counters';
import { finiteCell, nearestRank, qualifyingWork, referenceWork, typicalSeconds } from '../rates';
import type { RankedInput } from '../../charts/d3/rankedList';
import type { SeriesInput } from '../../charts/d3/dateSeries';
import * as queries from '../queries/machine';
import type { PanelQuery } from '../queries/window';

export const PANEL_QUERIES: Readonly<Record<string, readonly PanelQuery[]>> = {
	'two-clocks': [queries.twoClocksQuery, queries.twoClocksHostsQuery, queries.platformMixQuery, queries.runShardsQuery],
	'slower-machines': [queries.slowerMachinesQuery],
	'platform-mix': [queries.platformMixQuery],
	'slower-on-same-work': [queries.slowerOnSameWorkQuery],
	'closest-to-memory': [queries.closestToMemoryQuery],
	'memory-held': [queries.memoryHeldQuery],
	'context-headroom': [queries.contextHeadroomQuery],
	'article-cost': [queries.articleCostQuery, queries.articleCostHostsQuery],
	'prompt-reuse': [queries.promptReuseQuery],
	'read-against-written': [queries.readAgainstWrittenQuery]
};

export function textRows(rows: readonly Row[]): Record<string, string>[] {
	return rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) =>
		[key, value === null ? '' : typeof value === 'boolean' ? (value ? 'True' : 'False') : String(value)])));
}

export function shardCounts(rows: readonly Row[]): Map<string, number> {
	const result = new Map<string, number>();
	for (const row of rows) {
		const count = row.shards;
		if (typeof row.run_id !== 'string' || !row.run_id) throw new Error('The count record has no run identity.');
		if (row.shards === null) continue;
		if (typeof count !== 'number' || !Number.isSafeInteger(count) || count < 1) throw new Error('Invalid recorded shard count.');
		const old = result.get(row.run_id);
		if (old !== undefined && old !== count) throw new Error('The count record contains unsettled corrections.');
		result.set(row.run_id, count);
	}
	return result;
}

export function countersFrom(hosts: readonly Row[], items: readonly Row[], counts: readonly Row[], limits: MachineLimits) {
	return machineCounters(textRows(hosts), textRows(items), shardCounts(counts), limits);
}

/** The cost join needs measured logical counts, not a fingerprint or private metadata. */
export function processors(rows: readonly Row[]): MachineProcessors[] {
	return rows.flatMap((row) => {
		const shard = finiteCell(row.shard);
		const genericTask = typeof row.pipeline_name === 'string' && typeof row.task_name === 'string';
		if (typeof row.date !== 'string' || typeof row.run_id !== 'string' ||
			(typeof row.job !== 'string' && !genericTask) ||
			shard === null || !Number.isSafeInteger(shard) || shard < 0) return [];
		const normalized = normalizeHostRow(row);
		if (normalized === null) return [];
		return [{ date: row.date, run_id: row.run_id, job: typeof row.job === 'string' ? row.job : undefined,
			pipeline_name: typeof row.pipeline_name === 'string' ? row.pipeline_name : undefined,
			task_name: typeof row.task_name === 'string' ? row.task_name : undefined, shard,
			cpu_logical_processors: finiteCell(normalized.cpu_logical_processors) }];
	});
}

export function slowerMachines(rows: readonly Row[]) {
	const reference = referenceWork(rows);
	const typical = typicalSeconds(rows, reference);
	const byRun = new Map<string, Row[]>();
	for (const row of rows) {
		const run = String(row.run_id ?? '');
		const bucket = byRun.get(run) ?? [];
		bucket.push(row);
		byRun.set(run, bucket);
	}
	const readings = new Map<string, { read: number[]; write: number[] }>();
	let withoutReference = 0;
	for (const run of byRun.values()) {
		const base = run.flatMap((row) => row.cpu_model === reference.cpuModel && qualifyingWork(row) !== null
			? [qualifyingWork(row)!] : []);
		const read = nearestRank(base.map((one) => one.readMsPerToken), 0.5);
		const write = nearestRank(base.map((one) => one.writeMsPerToken), 0.5);
		if (read === null || write === null || read <= 0 || write <= 0) { withoutReference++; continue; }
		for (const row of run) {
			const work = qualifyingWork(row);
			if (work === null || typeof row.cpu_model !== 'string' || !row.cpu_model) continue;
			const held = readings.get(row.cpu_model) ?? { read: [], write: [] };
			if (typical.read !== null) held.read.push(work.readMsPerToken / read * typical.read);
			if (typical.write !== null) held.write.push(work.writeMsPerToken / write * typical.write);
			readings.set(row.cpu_model, held);
		}
	}
	const list = (kind: 'read' | 'write'): RankedInput[] => [...readings].filter(([, values]) => values[kind].length > 0).map(([label, values]) => ({
		label, value: nearestRank(values[kind], 0.5)!,
		range: { high: [...values[kind]].sort((a, b) => a - b)[Math.ceil(0.9 * values[kind].length) - 1], count: values[kind].length },
		context: `${values[kind].length} articles; notch: slowest tenth`
	}));
	return { reference, typical, reading: list('read'), writing: list('write'), withoutReference };
}

export function closestToMemory(rows: readonly Row[]): RankedInput[] {
	const articles = new Map<string, RankedInput>();
	for (const row of rows) {
		const total = finiteCell(row.os_mem_total_bytes), available = finiteCell(row.os_mem_available_min_bytes);
		if (total === null || available === null || total <= 0 || available < 0 || available > total) continue;
		const label = `${row.item_id ?? 'unnamed article'} · ${row.source_id ?? 'source not recorded'} · ${row.date ?? 'date not recorded'}`;
		const measured: RankedInput = {
			label,
			value: (total - available) / 2 ** 30, ends: { end: total / 2 ** 30 },
			context: `${row.source_words ?? 'unrecorded'} words; ${row.date ?? ''}`
		};
		const old = articles.get(label);
		// Multiple attempts of one dated article contribute its tightest reading,
		// not extra ranked rows. The endpoint breaks equal-held ties deterministically.
		if (!old || measured.value > old.value || (measured.value === old.value && total / 2 ** 30 > (old.ends?.end ?? 0))) articles.set(label, measured);
	}
	return [...articles.values()];
}

export function contextReadings(rows: readonly Row[]) {
	const values = (key: string) => rows.flatMap((row) => {
		const value = finiteCell(row[key]);
		return value === null || value <= 0 ? [] : [value];
	});
	const slots = rows.flatMap((row) => {
		const context = finiteCell(row.n_ctx_configured), parallel = finiteCell(row.n_parallel);
		return context === null || parallel === null || context <= 0 || parallel <= 0 ? [] : [context / parallel];
	}).sort((a, b) => a - b);
	const cut = rows.filter((row) => finiteCell(row.truncation_cap_tokens) !== null);
	const cap = nearestRank(cut.flatMap((row) => {
		const tokens = finiteCell(row.label_input_tokens);
		return tokens === null ? [] : [tokens];
	}), 0.5);
	const rules = [
		...(slots.length ? [{ at: slots[0], label: `Reading limit: ${slots[0]} tokens per slot` }] : []),
		...(cap !== null && cap > 0 ? [{ at: cap, label: `Cut articles' middle label request: ${cap} tokens` }] : [])
	];
	return { label: values('label_input_tokens'), summary: values('summary_input_tokens'), rules,
		limits: [...new Set(slots)], cut: cut.length };
}

export function labelHeldMedian(rows: readonly Row[]): number | null {
	return nearestRank(rows.flatMap((row) => {
		const held = finiteCell(row.label_cached_tokens);
		return held === null || held < 0 ? [] : [held];
	}), 0.5);
}

export function reuseSeries(rows: readonly Row[]): SeriesInput[] {
	const days = [...new Set(rows.map((row) => String(row.date)))].sort();
	const median = (date: string, value: (row: Row) => number | null) =>
		nearestRank(rows.filter((row) => row.date === date).flatMap((row) => {
			const measured = value(row);
			return measured === null ? [] : [measured];
		}), 0.5);
	return [
		{ label: 'Label text held', token: '--chart-4', points: days.map((date) =>
			({ date, value: median(date, (row) => finiteCell(row.label_cached_tokens)) })) },
		{ label: 'Summary text read fresh', token: '--chart-5', points: days.map((date) =>
			({ date, value: median(date, (row) => {
				const input = finiteCell(row.summary_input_tokens), cached = finiteCell(row.summary_cached_tokens);
				return input === null || cached === null || cached < 0 || input < cached ? null : input - cached;
			}) })) }
	];
}

export function reuseChecks(rows: readonly Row[]) {
	return ['label', 'summary'].map((call) => {
		const pairs = rows.flatMap((row) => {
			const input = finiteCell(row[`${call}_input_tokens`]), cached = finiteCell(row[`${call}_cached_tokens`]);
			return input === null || cached === null || input <= 0 || cached < 0 || cached > input ? [] : [{ input, cached }];
		});
		const input = pairs.reduce((n, pair) => n + pair.input, 0);
		const server = nearestRank(rows.flatMap((row) => {
			const value = finiteCell(row[`${call}_cache_pct`]);
			return value === null || value < 0 || value > 100 ? [] : [value];
		}), 0.5);
		return { call, ours: input > 0 ? 100 * pairs.reduce((n, pair) => n + pair.cached, 0) / input : null, server, count: pairs.length };
	});
}
