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
import { nativeFailureMix } from '../src/lib/console/pipelines/failure-mix';
import { failureRuleRows } from '../src/lib/console/failure-rules';
import { nativeExtraction, extractionYield } from '../src/lib/console/pipelines/extraction';
import { siteCostPoints } from '../src/lib/console/pipelines/site-cost-per-item';
import { articleAge } from '../src/lib/console/pipelines/article-age';
import { slowerOnSameWork } from '../src/lib/console/pipelines/slower-on-same-work';
import { nativeStageTimings } from '../src/lib/console/pipelines/stage-timings';
import { nativeItemCost } from '../src/lib/console/pipelines/item-cost';
import { nativeTimeSplit, timeSplitReadout } from '../src/lib/console/pipelines/item-time-split';
import { pipelinesRecord, publishedShareFor, retryReach } from '../src/lib/console/pipelines/record-window';
import { chartFlow, visualsPublished } from '../src/lib/console/pipelines/chart-drawing';
import { windowOfDays } from '../src/lib/charts/viewport';
import type { Row, SliceResult } from '../src/lib/data/ledger';

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
	const yieldSeries = extractionYield([{ date: '2030-06-02', chartable: 4, charted: 0 }], window);
	expect(yieldSeries.map((series) => series.points)).toEqual([
		[{ date: '2030-06-01', value: null }, { date: '2030-06-02', value: 4 }, { date: '2030-06-03', value: null }],
		[{ date: '2030-06-01', value: null }, { date: '2030-06-02', value: 0 }, { date: '2030-06-03', value: null }]
	]);
	expect(siteCostPoints({ days: [
		{ date: '2030-06-02', bytesPerItem: -4 },
		{ date: '2030-06-03', bytesPerItem: 0 }
	] } as Parameters<typeof siteCostPoints>[0], window)).toEqual([
		{ date: '2030-06-01', value: null }, { date: '2030-06-02', value: null }, { date: '2030-06-03', value: 0 }
	]);
});

test('native timeline offsets and six-step residuals match the actual Python producer', () => {
	const own = rows(queries.runTimelineQuery);
	const native = runTimeline(own, consoleConfig().timeline_bars);
	const source = own.map((row) => ({ ...Object.fromEntries(Object.entries(row).map(([key, value]) =>
		[key, value === null ? '' : String(value)])), date: String(row.run_id).slice(0, 10) }));
	const produced = JSON.parse(execFileSync(backendPython(REPO), ['-c', [
		'import json, sys',
		'from idhazh.telemetry.publish.run_timeline import project',
		'print(json.dumps([row.csv_row() for row in project(json.load(sys.stdin))]))'
	].join('\n')], { cwd: REPO, env: { ...process.env, PYTHONPATH: join(REPO, 'backend') },
		input: JSON.stringify(source), encoding: 'utf8' }));
	const chosen = produced.filter((row: Record<string, string>) => row.run_id === native.view.runId);
	expect(native.run?.rows.length).toBe(chosen.length);
	for (const row of native.run!.rows) {
		const expected = chosen.find((one: Record<string, string>) => one.item_id === row.itemId);
		expect(row.startOffsetMs).toBe(Number(expected.start_offset_ms));
		expect(row.totalMs).toBe(Number(expected.item_total_ms));
		const sum = ['fetch_ms', 'extract_ms', 'label_ms', 'summary_ms', 'visual_plan_ms', 'score_ms']
			.reduce((total, step) => total + (expected[step] === '' ? 0 : Number(expected[step])), 0);
		expect(row.residualMs).toBe(row.totalMs - sum);
	}
});

test('huge numeric run suffixes, missing shard/start, zero and capped totals remain honest', () => {
	const item = (suffix: string, fields: Row = {}): Row => ({
		run_id: `2030-06-01-${suffix}`, item_id: suffix, machine_shard: 0,
		item_started_at: '2030-06-01T00:00:02Z', item_total_ms: 10, fetch_ms: 0, ...fields
	});
	const newest = '900719925474099312345';
	const answer = runTimeline([
		item('9'), item('10'), item('900719925474099312344'), item(newest),
		item(newest, { item_id: 'later', item_started_at: '2030-06-01T00:00:03Z', machine_shard: 1 }),
		item(newest, { item_id: 'no-shard', machine_shard: null, item_started_at: '2030-06-01T00:00:00Z' }),
		item(newest, { item_id: 'no-start', item_started_at: null })
	], 1);
	expect(answer.view.runId).toBe(`2030-06-01-${newest}`);
	expect(answer.view.bars).toHaveLength(1);
	expect(answer.view.itemCount).toBe(2);
	expect(answer.view.workMs).toBe(20);
	expect(answer.unplaced).toBe(2);
	expect(answer.view.bars[0].startOffsetMs).toBe(0);
	expect(answer.view.bars[0].segments[0].ms).toBe(0);
	expect(answer.view.shardBars.reduce((sum, bar) => sum + bar.workMs, 0)).toBe(20);
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

test('extraction retains useful partial readings and counts distinct evaluator articles', () => {
	const extraction = nativeExtraction(rows(queries.extractionQuery), rows(queries.extractionScoresQuery));
	expect(extraction.wouldNotReslice).toBeGreaterThan(0);
	const partial = nativeExtraction([
		{ date: '2030-06-01', url_key: 'a', code: 'not_prose', element_class: 'narrative', elements_found: 0, span_integrity: true },
		{ date: '2030-06-02', url_key: 'a', code: 'contaminated', element_class: null, elements_found: null, span_integrity: false }
	], [{ date: '2030-06-01', url_key: 'a', extraction_suspect: true }, { date: '2030-06-02', url_key: 'a', extraction_suspect: false },
		{ date: '2030-06-02', url_key: 'b', extraction_suspect: null }]);
	expect([partial.articles, partial.notProse, partial.contaminated, partial.checked, partial.suspect]).toEqual([1, 1, 1, 2, 0]);
	expect(partial.elementsFound).toBe(0);
	expect(partial.classes).toContainEqual({ label: 'narrative', count: 1 });
	expect(partial.suspectShare).toBeNull();
	expect(nativeExtraction([], null).suspect).toBeNull();
	const conflict = [{ date: '2030-06-02', url_key: 'a', extraction_suspect: true },
		{ date: '2030-06-02', url_key: 'a', extraction_suspect: false }];
	expect(nativeExtraction([], conflict).suspectShare).toBeNull();
	expect(nativeExtraction([], [...conflict].reverse()).suspectShare).toBeNull();
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
	expect(timeSplitReadout(split).series.find((part) => part.label === 'Elapsed time')?.values).toEqual(['0.80 s']);
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
	expect(timeSplitReadout(split).series.find((series) => series.label === 'Overlap')?.values).toEqual(['0.03 s', null]);
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

test('centred windows select private totals by the same anchor that shaped them', () => {
	const anchor = '2030-06-15';
	const window = windowOfDays(anchor, 7, 'centre');
	expect(window).toEqual({ start: '2030-06-12', end: '2030-06-18' });
	const spans = [
		{ through: anchor, days: 7, measuredDays: 7, unused: 2 },
		{ through: window.end, days: 7, measuredDays: 7, unused: 9 },
		{ through: anchor, days: 1, measuredDays: 1, unused: 0 }
	];
	expect(publishedShareFor(spans, anchor, 7)?.unused).toBe(2);
	expect(publishedShareFor(spans, anchor, 1)?.unused).toBe(0);
	expect(publishedShareFor(spans, '2030-06-16', 7)).toBeUndefined();
});
