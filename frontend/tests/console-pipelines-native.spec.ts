/** Native query answers, not a telemetry fetch or an engine double, drive the route. */
import { expect, test } from './support/door-page';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as queries from '../src/lib/console/queries/pipelines';
import { createQueryWindow, rangeFor, type PanelQuery } from '../src/lib/console/queries/window';
import { reachFromDisk, sliceFromDisk } from '../src/lib/server/ledger-disk';
import { consoleConfig } from '../src/lib/server/config';
import { backendPython } from './support/backend-python';
import { runTimeline } from '../src/lib/console/pipelines/run-timeline';
import { timelineGeometry, timelineItems } from '../src/lib/console/pipelines/run-timeline-geometry';
import { DEFAULT_CHART_LABELS } from '../src/lib/charts/frame';
import { seconds } from '../src/lib/charts/machine';
import { nativeFailureMix } from '../src/lib/console/pipelines/failure-mix';
import { failureRuleRows } from '../src/lib/console/failure-rules';
import { siteCostPoints } from '../src/lib/console/pipelines/site-cost-per-item';
import { articleAge } from '../src/lib/console/pipelines/article-age';
import { slowerOnSameWork } from '../src/lib/console/pipelines/slower-on-same-work';
import { nativeStageTimings } from '../src/lib/console/pipelines/stage-timings';
import { nativeItemCost } from '../src/lib/console/pipelines/item-cost';
import { nativeTimeSplit, timeSplitReadout } from '../src/lib/console/pipelines/item-time-split';
import { pipelinesRecord, retryReach } from '../src/lib/console/pipelines/record-window';
import { chartFlow, visualsPublished } from '../src/lib/console/pipelines/chart-drawing';
import type { Row, SliceResult } from '../src/lib/data/ledger';
import { numberFormat } from './support/number-format';

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const ALL = Object.values(queries) as PanelQuery[];
const answers = new Map<string, SliceResult>();
let state: string;

test.beforeAll(async ({}, info) => {
	const root = info.outputPath('native-pipelines');
	state = join(root, 'state');
	execFileSync(backendPython(REPO), [join(REPO, 'backend', 'utilities', 'build_canary_day.py'),
		'--out', join(root, 'digest'), '--state', state], {
		cwd: REPO, env: { ...process.env, PYTHONPATH: join(REPO, 'backend') }, encoding: 'utf8'
	});
	execFileSync(process.execPath, [join(REPO, 'frontend', 'scripts', 'build-canary.mjs'),
		'--fixtures-only', '--fixture-root', root], {
		cwd: join(REPO, 'frontend'), env: { ...process.env, IDHAZH_PYTHON: backendPython(REPO) }, encoding: 'utf8'
	});
	const window = createQueryWindow({
		reach: (ledger) => reachFromDisk(state, ledger),
		rows: (ledger, options) => sliceFromDisk(state, ledger, options)
	});
	const reach = await window.routeReach(ALL.map((query) => query.ledger));
	const knobs = consoleConfig();
	for (const query of ALL) {
		const range = rangeFor(query, knobs.default_window_days, reach, knobs.window_presets);
		if (!('from' in range)) throw new Error(`${query.name} has no real canary range`);
		const first = window.sliceOnce(query, range);
		expect(window.sliceOnce(query, range)).toBe(first);
		answers.set(query.name, await first);
	}
});

function rows(query: PanelQuery): Row[] {
	const answer = answers.get(query.name);
	if (answer?.state !== 'ok') throw new Error(`${query.name} has no native rows`);
	return answer.rows;
}

test('every declared native answer matches its independently committed slice', () => {
	for (const query of ALL) {
		const expected = JSON.parse(readFileSync(join(REPO, 'tests', 'fixtures', 'console', 'pipelines', `${query.name}.json`), 'utf8'));
		const actual = answers.get(query.name);
		if (actual?.state !== 'ok') throw new Error(`${query.name} is not ready`);
		expect({ ...actual, rows: [...actual.rows].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))) }).toEqual(expected);
	}
});

test('the identity-free ranking accepts the native nullable codes without changing recorded rows', () => {
	const recorded = rows(queries.failedRuleQuery);
	expect(recorded).toHaveLength(76);
	expect(recorded.filter((row) => row.code === null)).toHaveLength(71);
	expect(recorded.filter((row) => row.outcome === 'failed')).toHaveLength(1);
	expect(failureRuleRows(recorded)).toEqual(recorded);
});

test('private date axes retain missing days without inventing zero readings', () => {
	const window = { start: '2030-06-01', end: '2030-06-03' };
	expect(siteCostPoints({ days: [
		{ date: '2030-06-02', bytesPerItem: -4 },
		{ date: '2030-06-03', bytesPerItem: 0 }
	] } as Parameters<typeof siteCostPoints>[0], window)).toEqual([
		{ date: '2030-06-01', value: null }, { date: '2030-06-02', value: null }, { date: '2030-06-03', value: 0 }
	]);
});

test('recorded endpoints determine elapsed geometry; parked costs and nested calls cannot extend it', () => {
	const item = (fields: Row = {}): Row => ({
		run_id: '2030-06-01-2', item_id: 'first', machine_shard: 0,
		item_started_at: '2030-06-01T00:00:00Z', item_ended_at: '2030-06-01T00:02:00Z',
		item_total_ms: 1000, queue_wait_ms: 119000, fetch_ms: 100, extract_ms: 50,
		summarize_ms: 800, faithfulness_ms: 20, stage_gap_ms: 30,
		label_ms: 250, summary_ms: 550, visual_plan_ms: 100, visual_plan_ms_is_estimate: true, ...fields
	});
	const view = runTimeline([
		item(), item({ item_id: 'second', machine_shard: 1, item_started_at: '2030-06-01T00:00:30Z',
			item_ended_at: '2030-06-01T00:02:30Z', item_total_ms: 2000, summarize_ms: 1800 })
	], 20);
	expect(view).toMatchObject({ spanMs: 150000, workMs: 3000, timedCount: 2, workCount: 2, itemsPerMinute: 0.8 });
	const geometry = (measure: 'elapsed' | 'work') => timelineGeometry(view, measure, 5, 800, DEFAULT_CHART_LABELS, String);
	const elapsed = geometry('elapsed');
	expect(elapsed.domainMs).toBe(150000);
	expect(elapsed.bars.map(({ shard, ms, offset, width }) => ({ shard: shard.shard, ms, offset, width })))
		.toEqual([{ shard: 0, ms: 120000, offset: '0.0000%', width: '80.0000%' },
			{ shard: 1, ms: 120000, offset: '20.0000%', width: '80.0000%' }]);
	const work = geometry('work');
	expect(work.domainMs).toBe(2000);
	expect(work.bars.map(({ shard, ms, offset, width }) => ({ shard: shard.shard, ms, offset, width })))
		.toEqual([{ shard: 1, ms: 2000, offset: '0.0000%', width: '100.0000%' },
			{ shard: 0, ms: 1000, offset: '0.0000%', width: '50.0000%' }]);
	expect(view.shards[0].breakdown.stages.map((stage) => stage.value)).toEqual([100, 50, 800, 20]);
	expect(view.shards[0].breakdown.unattributed).toBe(30);
	expect(view.items[0].calls.map((call) => call.ms)).toEqual([250, 550, 100]);
	expect(view.items[0].planEstimated).toBe(true);
});

test('incomplete clocks, zero work and article limits cannot silently drop measured run costs', () => {
	const item = (suffix: string, fields: Row = {}): Row => ({
		run_id: `2030-06-01-${suffix}`, item_id: suffix, machine_shard: 0,
		item_started_at: '2030-06-01T00:00:01Z', item_ended_at: '2030-06-01T00:00:01Z',
		item_total_ms: 0, fetch_ms: 0, ...fields
	});
	const newest = '900719925474099312345';
	const answer = runTimeline([
		item('9'), item('10'), item('900719925474099312344'), item(newest, { item_id: 'zero' }),
		item(newest, { item_id: 'no-end', item_ended_at: null, machine_shard: 1, item_total_ms: 30 }),
		item(newest, { item_id: 'no-cost', machine_shard: 2, item_total_ms: null,
			item_started_at: '2030-06-01T00:00:02Z', item_ended_at: '2030-06-01T00:00:04Z' }),
		item(newest, { item_id: 'reversed', machine_shard: 1, item_total_ms: 40,
			item_started_at: '2030-06-01T00:00:09Z', item_ended_at: '2030-06-01T00:00:05Z' }),
		item(newest, { item_id: 'no-shard', machine_shard: null, item_total_ms: 50,
			item_started_at: '2030-06-01T00:00:00Z', item_ended_at: '2030-06-01T00:00:06Z' })
	], 1);
	expect(answer).toMatchObject({ runId: `2030-06-01-${newest}`, detailLimit: 1,
		itemCount: 5, workMs: 120, workCount: 4, timedCount: 3, spanMs: 6000, unassigned: 1, itemsPerMinute: null });
	expect(answer.shards.map(({ shard, elapsedMs, workMs }) => ({ shard, elapsedMs, workMs }))).toEqual([
		{ shard: 0, elapsedMs: 0, workMs: 0 }, { shard: 1, elapsedMs: null, workMs: 70 },
		{ shard: 2, elapsedMs: 2000, workMs: null }
	]);
	expect(answer.shards[1].items).toHaveLength(2);
	expect(timelineItems(answer.items, 'cost').map((item) => item.itemId))
		.toEqual(['no-shard', 'reversed', 'no-end', 'zero', 'no-cost']);
	expect(timelineItems(answer.items, 'start').map((item) => item.itemId))
		.toEqual(['no-shard', 'no-end', 'zero', 'no-cost', 'reversed']);
	expect(runTimeline([], 1)).toMatchObject({ empty: true, spanMs: null, workMs: null, itemsPerMinute: null });
});

test('duration readings carry rounded minutes and retain seconds for inspected long clocks', () => {
	expect(seconds(419.8, numberFormat, true)).toBe('7 m 0 s');
	expect(seconds(3599.8, numberFormat, true)).toBe('1 h 0 m 0 s');
	expect(seconds(6729, numberFormat, true)).toBe('1 h 52 m 9 s');
	expect(seconds(6729, numberFormat)).toBe('1 h 52 m');
});

test('failure stacks account for every failed native item, with the largest stage chosen', () => {
	const own = rows(queries.failureMixQuery);
	const mix = nativeFailureMix(own);
	expect(mix.series.reduce((sum, series) => sum + series.points.reduce((n, point) => n + (point.value ?? 0), 0), 0))
		.toBe(own.filter((row) => row.outcome === 'failed').length);
	const stageCounts = new Map<string, number>();
	for (const row of own.filter((row) => row.outcome === 'failed')) {
		stageCounts.set(String(row.stage), (stageCounts.get(String(row.stage)) ?? 0) + 1);
	}
	expect(mix.chosenStage).toBe([...stageCounts].sort(([a, n], [b, m]) => m - n || a.localeCompare(b))[0]?.[0] ?? null);
	const ranked = nativeFailureMix([
		{ date: '2030-06-01', stage: 'extract', outcome: 'failed', code: 'same', failed_rule: 'B' },
		{ date: '2030-06-02', stage: 'extract', outcome: 'failed', code: 'same', failed_rule: 'A' },
		{ date: '2030-06-02', stage: 'extract', outcome: 'failed', code: 'same', failed_rule: 'B' },
		{ date: '2030-06-02', stage: 'fetch', outcome: 'failed', code: 'other', failed_rule: null }
	]);
	expect(ranked.chosenStage).toBe('extract');
	expect(ranked.rules[0].rules).toEqual([{ rule: 'B', count: 2 }, { rule: 'A', count: 1 }]);
	expect(ranked.rules[1].unknown).toBe(1);
	const gap = nativeFailureMix([{ date: '2030-06-01', stage: 'fetch', outcome: 'ok' }],
		['2030-06-01', '2030-06-02']);
	expect(gap.series[0].points).toEqual([{ date: '2030-06-01', value: 0 }, { date: '2030-06-02', value: null }]);
});

test('one fixed reference prices the same typical work independently on every day', () => {
	const own = rows(queries.slowerOnSameWorkQuery);
	const work = slowerOnSameWork(own);
	const qualified = own.filter((row) => ['prefill_ms', 'input_tokens', 'cached_tokens', 'decode_ms', 'output_tokens']
		.every((cell) => typeof row[cell] === 'number') && Number(row.input_tokens) > Number(row.cached_tokens) &&
		Number(row.output_tokens) > 0 && Number(row.prefill_ms) >= 0 && Number(row.decode_ms) >= 0);
	const upperMiddle = (values: number[]) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
	for (const day of work.days) {
		const same = qualified.filter((row) => row.date === day.date && row.cpu_model === work.reference.cpuModel);
		if (same.length === 0) { expect(day.seconds).toBeNull(); continue; }
		const read = upperMiddle(same.map((row) => Number(row.prefill_ms) / (Number(row.input_tokens) - Number(row.cached_tokens))));
		const write = upperMiddle(same.map((row) => Number(row.decode_ms) / Number(row.output_tokens)));
		expect(day.seconds).toBe((read * work.reference.freshInput! + write * work.reference.output!) / 1000);
	}
	expect(work.reference.qualifying).toBe(qualified.length);
});

test('source-stated ages exclude inferred, invalid and future instants without losing zero', () => {
	const age = articleAge(rows(queries.articleAgeQuery));
	expect(age.inferred).toBeGreaterThan(0);
	const result = articleAge([
		{ outcome: 'ok', time_source: 'feed', published_at: '2030-06-01T00:00:00Z', item_started_at: '2030-06-01T00:00:00Z' },
		{ outcome: 'ok', time_source: 'first_seen', published_at: '2030-06-01T00:00:00Z', item_started_at: '2030-06-02T00:00:00Z' },
		{ outcome: 'ok', time_source: 'feed', published_at: null, item_started_at: '2030-06-01T00:00:00Z' },
		{ outcome: 'ok', time_source: 'feed', published_at: '2030-06-02T00:00:00Z', item_started_at: '2030-06-01T00:00:00Z' }
	]);
	expect(result.hours).toEqual([0]);
	expect([result.inferred, result.unknown, result.future]).toEqual([1, 1, 1]);
	expect(result.lede).toContain('1 of 4 successful items have inferred times');
	expect(result.lede).not.toContain('Every publication time');
});

test('stage clocks, signed gaps and independent cost pairs never fill unknown cells with zero', () => {
	expect(nativeStageTimings(rows(queries.stageTimingsQuery)).length).toBeGreaterThan(0);
	expect(nativeTimeSplit(rows(queries.itemTimeSplitQuery)).days.some((day) => day.overlapping > 0)).toBe(true);
	const stage = nativeStageTimings([{ date: '2030-06-01', fetch_ms: 0, extract_ms: null, summarize_ms: 10 }])[0];
	expect(stage.fetch).toEqual({ ms: 0, timed: 1, total: 1 });
	expect(stage.extract).toEqual({ ms: null, timed: 0, total: 1 });
	const cost = nativeItemCost([
		{ prefill_ms: 10, input_tokens: 20, cached_tokens: null, decode_ms: 20, output_tokens: 2 },
		{ prefill_ms: 0, input_tokens: 20, cached_tokens: 0, decode_ms: null, output_tokens: null }
	]);
	expect(cost.msPerReadToken).toBe(0);
	expect(cost.readPairs).toBe(1);
	expect(cost.msPerWrittenToken).toBe(10);
	expect(cost.unknownCache).toBe(1);
	expect(cost.writeCostRatio).toBeNull();
	const clock = { date: '2030-06-01', item_total_ms: 800, fetch_ms: 100, extract_ms: 20,
		summarize_ms: 600, label_ms: 150, summary_ms: 430, visual_plan_ms: 60, faithfulness_ms: 30, stage_gap_ms: 50 };
	const split = nativeTimeSplit([clock, { ...clock, summary_ms: null }]);
	expect(split.days[0].recorded).toBe(2);
	expect(split.days[0].count).toBe(2);
	expect(split.days[0].stages.map((part) => part.value)).toEqual([100, 20, 600, 30]);
	expect(split.days[0].stages.reduce((sum, part) => sum + part.value!, 0) + split.days[0].unattributed! - split.days[0].overlap!)
		.toBe(split.days[0].elapsed);
	expect(split.days[0].details.find((part) => part.cell === 'summary_ms')).toEqual({
		cell: 'summary_ms', label: 'Summary call, including visual plan', value: null, timed: 1
	});
	expect(timeSplitReadout(split, numberFormat).series.find((part) => part.label === 'Elapsed time')?.values).toEqual(['0.8 s']);
});

test('positive gaps and overlap cannot cancel away; calls are never extra durations', () => {
	const clock = { date: '2030-06-01', item_total_ms: 800, fetch_ms: 100, extract_ms: 20,
		summarize_ms: 600, faithfulness_ms: 30, stage_gap_ms: 50, label_ms: 0, summary_ms: null, visual_plan_ms: null };
	const split = nativeTimeSplit([clock, { ...clock, item_total_ms: 700, stage_gap_ms: -50 },
		{ ...clock, fetch_ms: null }, { ...clock, item_total_ms: 1 }], ['2030-06-01', '2030-06-02']);
	expect(split.days[0]).toMatchObject({ recorded: 4, count: 2, missing: 1, inconsistent: 1,
		unattributed: 25, overlap: 25, signedGap: 0, elapsed: 750 });
	expect(split.series.map((series) => series.points[0].value)).toEqual([100, 20, 600, 30, 25]);
	expect(split.days[0].details[0]).toMatchObject({ value: 0, timed: 2 });
	expect(split.days[1]).toMatchObject({ count: 0, elapsed: null, overlap: null });
	expect(timeSplitReadout(split, numberFormat).series.find((series) => series.label === 'Overlap')?.values).toEqual(['0.025 s', null]);
});

test('the record starts at the actual ledger beginning, and retry pins the endpoint', () => {
	const previous = { through: '2030-06-10', ledgers: {
		'item-health': { state: 'ok', first: '2030-01-01', through: '2030-06-10', lastRows: null, fault: null },
		'summary-quality-evals': { state: 'missing', fault: 'not-packed' }
	} } as const;
	const refreshed = { through: '2030-06-11', ledgers: {
		'item-health': { state: 'ok', first: '2030-01-01', through: '2030-06-11', lastRows: null, fault: null },
		'summary-quality-evals': { state: 'ok', first: '2030-06-11', through: '2030-06-11', lastRows: null, fault: null }
	} } as const;
	expect(pipelinesRecord(previous, 7)).toEqual({ first: '2030-01-01', through: '2030-06-10', asked: 7 });
	expect(retryReach(previous, refreshed).through).toBe('2030-06-10');
	expect(pipelinesRecord(null, 7)).toBeNull();
});

test('an undrawable flow retains the recorded published visual count', () => {
	const days = [{ reached: 1, asked: 1, drafted: 1, published: 2 }];
	expect(chartFlow(days).empty).toBe(true);
	expect(chartFlow(days).steps).toEqual([]);
	expect(visualsPublished(days)).toBe(2);
	expect(visualsPublished([...days, { reached: 2, asked: 2, drafted: 2, published: 3 }])).toBe(5);
});
