/** Where did the newest run's native items sit on their own clock? */
import type { Row } from '../../data/ledger';
import { newestRunRows } from '../queries/shared';
import { finiteCell } from '../rates';
import { SERIES_TOKENS } from '../series-tokens';
export type TimelineStep = 'plan_ms' | 'fetch_ms' | 'extract_ms' | 'label_ms' |
	'summary_ms' | 'visual_plan_ms' | 'score_ms' | 'publish_ms';

export interface TimelineRow {
	date: string; runId: string; shard: number; itemId: string;
	startOffsetMs: number; totalMs: number; residualMs: number;
	steps: { name: TimelineStep; ms: number }[];
}

export interface TimelineRun {
	runId: string; date: string; rows: TimelineRow[];
}

export interface TimelineBar {
	id: string; label: string; shard: number; startOffsetMs: number; totalMs: number;
	workMs: number; itemCount: number; residualMs: number; offset: string;
	residualWidth: string; overrunOffset: string; overrunWidth: string;
	segments: { name: TimelineStep; label: string; stop: number; ms: number; width: string }[];
}

export interface RunTimelineView {
	empty: boolean; runId: string; date: string; bars: TimelineBar[];
	shardOrder: number[]; shardBars: TimelineBar[]; itemCount: number; shards: number[];
	spanMs: number; scaleMs: number; ticks: { at: string; ms: number }[]; workMs: number;
	drawn: TimelineStep[]; legend: { name: TimelineStep; label: string; stop: number }[];
	unproduced: TimelineStep[]; unrecorded: TimelineStep[]; overrunCount: number;
	residualMs: number; shardResidualMs: number;
}

const STEPS: readonly { name: TimelineStep; cell: string; label: string; token: string }[] = [
	{ name: 'fetch_ms', cell: 'fetch_ms', label: 'reading the page', token: SERIES_TOKENS.fetch },
	{ name: 'extract_ms', cell: 'extract_ms', label: 'taking the article out', token: SERIES_TOKENS.extract },
	{ name: 'label_ms', cell: 'label_ms', label: 'the label call', token: SERIES_TOKENS['label-call'] },
	{ name: 'summary_ms', cell: 'summary_ms', label: 'the summary call', token: SERIES_TOKENS['summary-call'] },
	{ name: 'visual_plan_ms', cell: 'visual_plan_ms', label: 'the visual plan', token: SERIES_TOKENS['visual-plan'] },
	{ name: 'score_ms', cell: 'faithfulness_ms', label: 'scoring it', token: SERIES_TOKENS.checking }
];
const UNPRODUCED: TimelineStep[] = ['plan_ms', 'publish_ms'];

function instant(cell: Row[string] | undefined): number | null {
	if (typeof cell !== 'string' || !cell.endsWith('Z')) return null;
	const value = Date.parse(cell);
	return Number.isFinite(value) ? value : null;
}

export interface NativeTimeline {
	readonly run: TimelineRun | null;
	readonly unplaced: number;
	readonly queue: readonly { itemId: string; milliseconds: number | null }[];
	readonly robots: readonly { itemId: string; milliseconds: number | null }[];
}

/** Only eligible native starts determine zero; clocks are not inferred. */
export function timelineRun(rows: readonly Row[]): NativeTimeline {
	const newest = newestRunRows(rows);
	const timed = newest.flatMap((row) => {
		const start = instant(row.item_started_at);
		const total = finiteCell(row.item_total_ms);
		const shard = finiteCell(row.machine_shard);
		if (start === null || total === null || shard === null || total < 0 ||
			!Number.isSafeInteger(shard) || shard < 0 || typeof row.item_id !== 'string' || row.item_id === '') return [];
		return [{ row, start, total, shard }];
	});
	if (timed.length === 0) return { run: null, unplaced: newest.length, queue: [], robots: [] };
	const zero = Math.min(...timed.map((one) => one.start));
	const runId = String(timed[0].row.run_id);
	const made: TimelineRow[] = timed.map(({ row, start, total, shard }) => {
		const steps = STEPS.flatMap(({ name, cell }) => {
			const ms = finiteCell(row[cell]);
			return ms === null ? [] : [{ name, ms }];
		});
		return {
			date: runId.slice(0, 10), runId, itemId: String(row.item_id), shard,
			startOffsetMs: start - zero, totalMs: total,
			residualMs: total - steps.reduce((sum, step) => sum + step.ms, 0), steps
		};
	}).sort((a, b) => a.startOffsetMs - b.startOffsetMs || a.itemId.localeCompare(b.itemId));
	return {
		run: { runId, date: runId.slice(0, 10), rows: made }, unplaced: newest.length - timed.length,
		queue: timed.map(({ row }) => ({ itemId: String(row.item_id), milliseconds: finiteCell(row.queue_wait_ms) })),
		robots: timed.map(({ row }) => ({ itemId: String(row.item_id), milliseconds: finiteCell(row.robots_ms) }))
	};
}

/** Both grains share uncapped totals and one scale, just as the retained drawing did. */
export function timelineView(run: TimelineRun | null, limit: number): RunTimelineView {
	if (!Number.isSafeInteger(limit) || limit <= 0) throw new Error('timeline_bars must be a positive whole count');
	if (run === null || run.rows.length === 0) return {
		empty: true, runId: '', date: '', bars: [], shardOrder: [], shardBars: [], itemCount: 0,
		shards: [], spanMs: 0, scaleMs: 0, ticks: [], workMs: 0, drawn: [], legend: [],
		unproduced: UNPRODUCED, unrecorded: STEPS.map((step) => step.name),
		overrunCount: 0, residualMs: 0, shardResidualMs: 0
	};
	const grouped = new Map<number, TimelineRow[]>();
	for (const row of run.rows) grouped.set(row.shard, [...(grouped.get(row.shard) ?? []), row]);
	const shards = [...grouped].sort(([a], [b]) => a - b).map(([shard, own]) => {
		const startOffsetMs = Math.min(...own.map((row) => row.startOffsetMs));
		const totalMs = Math.max(...own.map((row) => row.startOffsetMs + row.totalMs)) - startOffsetMs;
		const steps = STEPS.flatMap(({ name }) => {
			const readings = own.flatMap((row) => row.steps.filter((step) => step.name === name));
			return readings.length === 0 ? [] : [{ name, ms: readings.reduce((sum, step) => sum + step.ms, 0) }];
		});
		return {
			itemId: `shard-${shard}`, shard, startOffsetMs, totalMs, steps, items: own.length,
			workMs: own.reduce((sum, row) => sum + row.totalMs, 0),
			residualMs: totalMs - steps.reduce((sum, step) => sum + step.ms, 0)
		};
	});
	const spanMs = Math.max(...run.rows.map((row) => row.startOffsetMs + row.totalMs));
	const scaleMs = Math.max(spanMs, ...[...run.rows, ...shards].map((row) =>
		row.startOffsetMs + Math.max(row.totalMs, row.steps.reduce((sum, step) => sum + step.ms, 0))));
	const width = (ms: number) => `${scaleMs > 0 ? (ms / scaleMs * 100).toFixed(4) : 0}%`;
	const bar = (row: TimelineRow | typeof shards[number]): TimelineBar => {
		const named = row.steps.reduce((sum, step) => sum + step.ms, 0);
		return {
			id: row.itemId, label: 'items' in row ? `Shard ${row.shard}` : row.itemId,
			shard: row.shard, startOffsetMs: row.startOffsetMs, totalMs: row.totalMs,
			workMs: 'workMs' in row ? row.workMs : row.totalMs, itemCount: 'items' in row ? row.items : 1,
			residualMs: row.residualMs, offset: width(row.startOffsetMs),
			residualWidth: row.residualMs > 0 ? width(row.residualMs) : '',
			overrunOffset: row.residualMs < 0 ? width(row.startOffsetMs + named + row.residualMs) : '',
			overrunWidth: row.residualMs < 0 ? width(-row.residualMs) : '',
			segments: row.steps.map((one) => {
				const step = STEPS.find((step) => step.name === one.name);
				if (step === undefined) throw new Error(`No native timeline step ${one.name}`);
				return { ...one, label: step.label, stop: Number(step.token.slice('--chart-'.length)), width: width(one.ms) };
			})
		};
	};
	const bars = run.rows.slice(0, limit).map(bar);
	const drawn = STEPS.filter((step) => run.rows.some((row) => row.steps.some((one) => one.name === step.name)));
	return {
		empty: false, runId: run.runId, date: run.date, bars,
		shardOrder: bars.map((one, at) => ({ at, shard: one.shard, start: one.startOffsetMs }))
			.sort((a, b) => a.shard - b.shard || a.start - b.start || a.at - b.at).map((one) => one.at),
		shardBars: shards.map(bar), itemCount: run.rows.length, shards: shards.map((one) => one.shard),
		spanMs, scaleMs, ticks: [0, 1, 2, 3, 4].map((step) => ({ at: `${step * 25}%`, ms: scaleMs * step / 4 })),
		workMs: run.rows.reduce((sum, row) => sum + row.totalMs, 0),
		drawn: drawn.map((step) => step.name),
		legend: drawn.map((step) => ({ name: step.name, label: step.label, stop: Number(step.token.slice('--chart-'.length)) })),
		unproduced: UNPRODUCED,
		unrecorded: STEPS.filter((step) => !drawn.includes(step)).map((step) => step.name),
		overrunCount: run.rows.filter((row) => row.residualMs < 0).length,
		residualMs: run.rows.reduce((sum, row) => sum + row.residualMs, 0),
		shardResidualMs: shards.reduce((sum, row) => sum + row.residualMs, 0)
	};
}

export function runTimeline(rows: readonly Row[], limit: number) {
	const native = timelineRun(rows);
	const view = timelineView(native.run, limit);
	return { ...native, view, itemsPerMinute: view.spanMs > 0 ? view.itemCount * 60_000 / view.spanMs : null };
}
