/** What elapsed windows and item costs did the newest recorded run actually measure? */
import type { Row } from '../../data/ledger';
import { newestRunRows } from '../queries/shared';
import { finiteCell } from '../rates';
import { DURATION_STAGES, DURATION_DETAILS, durationCohort } from '../duration-cohort';

export interface TimelineReading {
	cell: string;
	label: string;
	ms: number | null;
	token?: string;
}

export interface TimelineItem {
	itemId: string;
	sourceId: string | null;
	shard: number | null;
	index: number | null;
	startMs: number | null;
	endMs: number | null;
	elapsedMs: number | null;
	workMs: number | null;
	queueMs: number | null;
	robotsMs: number | null;
	gapMs: number | null;
	outcome: string | null;
	stage: string | null;
	code: string | null;
	planEstimated: boolean | null;
	stages: TimelineReading[];
	calls: TimelineReading[];
}

export interface TimelineShard {
	shard: number;
	items: TimelineItem[];
	startMs: number | null;
	endMs: number | null;
	elapsedMs: number | null;
	workMs: number | null;
	timedCount: number;
	workCount: number;
	breakdown: ReturnType<typeof durationCohort>['days'][number];
}

export interface RunTimelineView {
	empty: boolean;
	runId: string;
	date: string;
	items: TimelineItem[];
	shards: TimelineShard[];
	itemCount: number;
	timedCount: number;
	workCount: number;
	unassigned: number;
	startMs: number | null;
	endMs: number | null;
	spanMs: number | null;
	workMs: number | null;
	itemsPerMinute: number | null;
	detailLimit: number;
}

function instant(value: Row[string] | undefined): number | null {
	if (typeof value !== 'string' || !value.endsWith('Z')) return null;
	const ms = Date.parse(value);
	return Number.isFinite(ms) ? ms : null;
}

function duration(value: Row[string] | undefined): number | null {
	const ms = finiteCell(value);
	return ms !== null && ms >= 0 ? ms : null;
}

function whole(value: Row[string] | undefined): number | null {
	const number = finiteCell(value);
	return number !== null && Number.isSafeInteger(number) && number >= 0 ? number : null;
}

function text(value: Row[string] | undefined): string | null {
	return typeof value === 'string' && value !== '' ? value : null;
}

function itemOf(row: Row): TimelineItem {
	const itemId = text(row.item_id);
	if (itemId === null) throw new Error('A run timeline item needs its recorded item id.');
	const startMs = instant(row.item_started_at);
	const endMs = instant(row.item_ended_at);
	return {
		itemId, sourceId: text(row.source_id), shard: whole(row.machine_shard),
		index: whole(row.item_index), startMs, endMs,
		elapsedMs: startMs !== null && endMs !== null && endMs >= startMs ? endMs - startMs : null,
		workMs: duration(row.item_total_ms), queueMs: duration(row.queue_wait_ms),
		robotsMs: duration(row.robots_ms), gapMs: finiteCell(row.stage_gap_ms),
		outcome: text(row.outcome), stage: text(row.stage), code: text(row.code),
		planEstimated: typeof row.visual_plan_ms_is_estimate === 'boolean' ? row.visual_plan_ms_is_estimate : null,
		stages: DURATION_STAGES.map(([cell, label, token]) => ({ cell, label, token, ms: duration(row[cell]) })),
		calls: DURATION_DETAILS.map(([cell, label]) => ({ cell, label, ms: duration(row[cell]) }))
	};
}

function measuredCosts(items: readonly TimelineItem[]) {
	const costs = items.flatMap((item) => item.workMs === null ? [] : [item.workMs]);
	return { workMs: costs.length === 0 ? null : costs.reduce((sum, ms) => sum + ms, 0), workCount: costs.length };
}

function measuredWindow(items: readonly TimelineItem[]) {
	const timed = items.filter((item): item is TimelineItem & { startMs: number; endMs: number } =>
		item.elapsedMs !== null && item.startMs !== null && item.endMs !== null);
	const startMs = timed.length === 0 ? null : Math.min(...timed.map((item) => item.startMs));
	const endMs = timed.length === 0 ? null : Math.max(...timed.map((item) => item.endMs));
	return { startMs, endMs, timedCount: timed.length,
		elapsedMs: startMs === null || endMs === null ? null : endMs - startMs };
}

/** Missing endpoints never erase measured costs, and missing costs never erase endpoints. */
export function runTimeline(rows: readonly Row[], detailLimit: number): RunTimelineView {
	if (!Number.isSafeInteger(detailLimit) || detailLimit <= 0) {
		throw new Error('timeline_bars must be a positive whole count');
	}
	const newest = newestRunRows(rows);
	const runId = newest.length === 0 ? '' : String(newest[0].run_id);
	const date = runId.slice(0, 10);
	const items = newest.map(itemOf);
	const window = measuredWindow(items);
	const costs = measuredCosts(items);
	const grouped = new Map<number, { item: TimelineItem; row: Row }[]>();
	items.forEach((item, index) => {
		if (item.shard === null) return;
		const own = grouped.get(item.shard) ?? [];
		own.push({ item, row: newest[index] });
		grouped.set(item.shard, own);
	});
	const shards = [...grouped].sort(([a], [b]) => a - b).map(([shard, own]): TimelineShard => {
		const items = own.map(({ item }) => item);
		return {
			shard, items, ...measuredWindow(items), ...measuredCosts(items),
			breakdown: durationCohort(own.map(({ row }) => ({ ...row, date })), [date]).days[0]
		};
	});
	return {
		empty: newest.length === 0, runId, date, items, shards, itemCount: items.length,
		timedCount: window.timedCount, ...costs, startMs: window.startMs, endMs: window.endMs,
		spanMs: window.elapsedMs, unassigned: items.filter((item) => item.shard === null).length,
		itemsPerMinute: window.timedCount === items.length && window.elapsedMs !== null && window.elapsedMs > 0
			? items.length * 60_000 / window.elapsedMs : null,
		detailLimit
	};
}
