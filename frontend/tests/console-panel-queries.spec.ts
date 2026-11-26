/** Declared panel questions cross the real disk door; windows and retries never invent evidence. */
import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { FLEET_COLUMNS } from '../src/lib/charts/fleet';
import { platformMixQuery, runShardsQuery, slowerOnSameWorkQuery } from '../src/lib/console/queries/machine';
import { summaryLengthQuery } from '../src/lib/console/queries/model';
import { compareRuns, failedRuleQuery, hostKey, joinItemHosts, newestRunRows } from '../src/lib/console/queries/shared';
import { feedsFailedQuery } from '../src/lib/console/queries/voices';
import { judgeDayQuery, judgeHistoryQuery } from '../src/lib/console/queries/judgement';
import {
	exactJudgeDay, judgeCoverage, judgeRange, latestJudgeReadings, selectedJudgeDate
} from '../src/lib/console/judge-observations';
import { modelThroughput } from '../src/lib/console/model/model-throughput';
import { throughputWithin } from '../src/lib/server/model-work';
import {
	createQueryWindow, rangeFor, tallyAsks, windowRange,
	type PanelDoor, type Range, type RouteReach
} from '../src/lib/console/queries/window';
import { finiteCell, itemRates, nearestRank, qualifyingWork, referenceWork, typicalSeconds } from '../src/lib/console/rates';
import type { Row, SliceResult } from '../src/lib/data/ledger';
import type { LedgerReach } from '../src/lib/data/ledger-reach';
import { reachFromDisk, sliceFromDisk } from '../src/lib/server/ledger-disk';
import { buildRows } from './support/ledger-lifecycle';
import { readSession, renewReadSession } from '../src/lib/data/read-session';
import { panelQueries as modelPanels } from '../src/lib/console/model/panels';
import { failedRuleQuery as pipelinesFailedRuleQuery } from '../src/lib/console/queries/pipelines';
import { nativeFailureMix } from '../src/lib/console/pipelines/failure-mix';
import { failureRuleRows, failureRules } from '../src/lib/console/failure-rules';
import { PIPELINES_QUERY_GROUPS } from '../src/lib/console/pipelines/query-groups';
import { slowestArticles } from '../src/lib/console/pipelines/slowest-articles';
import { PANEL_QUERIES } from '../src/lib/console/machine/records';
import { rankedList } from '../src/lib/charts/d3/rankedList';
import { numberFormat } from './support/number-format';
import { councilAttemptLink, councilJudges, councilHistory, councilPartCounts } from '../src/lib/console/council-runs';
import { compactActivity } from '../src/lib/console/operations/gardener-activity';
import { gardenerOutcomeLanes, gardenerReports } from '../src/lib/console/operations/gardener-reports';
import type { CompactWriteTrack } from '../src/lib/data/compact-file-writes';

const PRESETS = [3, 7, 30] as const;

test('Council keeps judge widths, older digests and retries separate on the UTC execution axis', () => {
	const prep: Row = {
		date: '2026-11-23', run_id: '2026-11-24-45335697395', attempt: 2, job: 'save_council_results',
		judge_id: 'example-judge', started_at: '2026-11-24T23:57:00Z', evaluation_step: 'select_judge_work',
		work_part_index: null, work_part_count: 2, outcome: 'completed'
	};
	const part = { ...prep, evaluation_step: 'evaluate_work_part', work_part_index: 0 };
	const older = { ...prep, date: '2026-11-20', started_at: '2026-11-25T00:01:00Z',
		evaluation_step: 'combine_judge_results', outcome: 'nothing_to_do' };
	const history = councilHistory([prep, part, part, older,
		{ ...part, attempt: 1, work_part_index: 1, started_at: '2026-11-24T00:02:00Z' },
		{ ...prep, judge_id: 'other-judge', work_part_count: 3 },
		{ ...part, judge_id: 'other-judge', work_part_count: 3, work_part_index: 2, outcome: 'stopped_on_deadline' },
		{ ...prep, judge_id: 'quiet-judge', work_part_count: 0, outcome: 'nothing_to_do' }
	]);
	const judges = councilJudges(history.attempts, { start: '2026-11-24', end: '2026-11-25' });
	expect(judges.map(({ judge }) => judge)).toEqual(['example-judge', 'other-judge', 'quiet-judge']);
	const [retryOne, retryTwo] = judges[0].days.get('2026-11-24')!;
	expect([retryOne.attempt.attempt, retryTwo.attempt.attempt]).toEqual([1, 2]);
	expect(councilPartCounts(retryTwo)).toMatchObject({ completed: 1, reported: 1, unreported: 1 });
	expect(judges[0].days.get('2026-11-25')).toMatchObject([{ digest: older.date, combine: 'nothing_to_do' }]);
	const anotherJudge = judges[1].days.get('2026-11-24')![0];
	expect(anotherJudge.expected).toBe(3);
	expect(councilPartCounts(anotherJudge)).toMatchObject({ stopped_on_deadline: 1, unreported: 2 });
	expect(judges[2].days.get('2026-11-24')).toMatchObject([{ expected: 0, noWork: true }]);
	expect(councilJudges(history.attempts, { start: '2026-11-25', end: '2026-11-25' }).map(({ judge }) => judge))
		.toEqual(['example-judge']);
	const chosen = retryTwo.attempt;
	expect(councilAttemptLink(chosen, 'https://code.example/project/source')).toBe('https://code.example/project/source/actions/runs/45335697395/attempts/2');
	expect(councilAttemptLink({ ...chosen, saveJob: false }, 'https://code.example/project/source')).toBeNull();
});

test('the compaction grid keeps the full UTC window and clips milestones by write date', () => {
	const track = (period: CompactWriteTrack['period'], date: string, covers: string): CompactWriteTrack => ({
		period, candidates: 1, days: 7, spans: [], omitted: false, issues: [],
		writes: [{ ledger: 'gardener', period, covers, writtenAt: Date.parse(date), runId: '2026-11-15-43688487431',
			attempt: 1, shard: 4, inputs: 2, rows: 18, bytes: 12_536 }]
	});
	const monthly = track('monthly', '2026-11-15T07:09:25Z', '2026-09');
	const daily = track('daily', '2026-11-17T02:00:00Z', '2026-11-15');
	const yearly = track('yearly', '2026-11-17T22:00:00Z', '2025');
	const viewport = { start: '2026-11-13', end: '2026-11-19' };
	const view = compactActivity({ daily: { ...daily, days: 1 }, monthly, yearly }, viewport, 7);
	expect(view.monthly?.covers).toBe('2026-09');
	expect(view.calendar).toHaveLength(7);
	expect(view.calendar[0]).toBe(viewport.start);
	expect(view.lanes[0].cells[0]).toMatchObject({ state: 'unavailable', draw: true });
	expect(view.lanes[1].cells[0].draw).toBe(false);
	expect(view.lanes[1].cells[2]).toMatchObject({ state: 'written', draw: true });
	expect(view.lanes[2].cells[4]).toMatchObject({ state: 'written', draw: true });
	const narrow = { start: '2026-11-16', end: '2026-11-17' };
	expect(compactActivity({ daily, monthly, yearly }, narrow, 2).monthly).toBeNull();
	expect(compactActivity({}, narrow, 2).calendar).toEqual([narrow.start, narrow.end]);
});

test('Gardener links only observed consecutive deferrals and does not plot a cleanup preview as a stop', () => {
	const artifact: Row = {
		date: '2026-11-15', run_id: '2026-11-15-43688487431', attempt: 1, job: 'run-tasks', shard: 4,
		task: 'workflow-artifacts', dry_run: true, stopped_because: 'ceiling', selected: 25, deleted: 10,
		work_ended_at: '2026-11-15T07:12:00Z', candidates_seen: 33, recovered: '[]'
	};
	const compact = { ...artifact, task: 'compact-gardener', dry_run: false,
		stopped_because: 'deferred', fault: 'packed-file-unreadable', resume_from: '2026-11-08',
		work_ended_at: '2026-11-16T00:01:00Z' };
	const { byDay } = gardenerReports([artifact, compact,
		{ ...compact, work_ended_at: '2026-11-17T00:01:00Z' },
		{ ...compact, work_ended_at: '2026-11-19T00:01:00Z', stopped_because: 'exhausted',
			recovered: '[{"note":"index-rebuilt","subject":"2026-09"}]' }
	]);
	const [, deferred, recovery] = gardenerOutcomeLanes(
		['2026-11-15', '2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19'], byDay);
	expect(deferred.cells.map(({ draw, links }) => [draw, links?.after])).toEqual([
		[false, false], [true, true], [true, false], [false, false], [false, false]
	]);
	expect(byDay.get('2026-11-15')).toMatchObject([{ dryRun: true, checked: 33, selected: 25, deleted: 10 }]);
	expect(recovery.cells[4].draw).toBe(true);
});

test('Judgement intersects the displayed digest window with packed history and opens only the selected run and attempt', async ({}, info) => {
	const root = info.outputPath('judge-history');
	const date = '2026-08-18';
	const legacy = { date: '2026-08-17', run_id: '2026-08-20-1', attempt: 1 };
	const currentRun = { date, run_id: '2026-08-20-10' };
	const staleAttempt = { ...currentRun, attempt: 1, pairs_drawn: 11, pairs_returned: 7 };
	const selectedRow = {
		...currentRun, attempt: 2, pairs_drawn: 8, pairs_returned: 6,
		sample_tp: 2, sample_fp: 1, sample_fn: 0, sample_tn: 1, score_psi: 0, runners_reported: 1
	};
	const olderRun = {
		...selectedRow, run_id: '2026-08-20-9', attempt: 4, pairs_drawn: 50, pairs_returned: 46,
		sample_tp: null, sample_fp: null, sample_fn: null, sample_tn: null, score_psi: null, runners_reported: null
	};
	await buildRows(root, 'threshold-history', [
		{ covers: legacy.date, rows: [legacy] },
		{ covers: date, rows: [olderRun, selectedRow] },
		{ covers: '2026-08-19', rows: [] },
		{ covers: '2026-08-20', rows: [] },
		{ covers: '2026-08-21', rows: [{ date: '2026-08-21', run_id: '2026-08-21-1', attempt: 1, score_psi: 0.8 }] }
	]);
	const queries = createQueryWindow(diskDoor(root), PRESETS.length);
	const ledger = judgeHistoryQuery.ledger;
	const reach = (await queries.routeReach([ledger])).ledgers[ledger]!;
	const range = judgeRange({ start: '2026-08-16', end: '2026-08-20' }, reach)!;
	expect(range).toEqual({ from: legacy.date, to: '2026-08-20', days: 4, asked: 5 });
	const history = await queries.sliceOnce(judgeHistoryQuery, range);
	expect(history.state).toBe('ok');
	const readings = latestJudgeReadings([...history.rows, staleAttempt]);
	expect([...readings.keys()].sort()).toEqual([legacy.date, date]);
	const calendar = [legacy.date, date, '2026-08-19', '2026-08-20'];
	expect(selectedJudgeDate(calendar, null, readings)).toBe(date);
	expect(selectedJudgeDate(calendar, legacy.date, readings)).toBe(legacy.date);
	expect(selectedJudgeDate(calendar.slice(1), legacy.date, readings)).toBe(date);
	const selected = readings.get(date)!;
	expect(selected.identity).toEqual({ date, run: currentRun.run_id, attempt: 2 });
	expect(judgeCoverage(selected.cells).stack).toEqual([4, 2, 2]);
	expect(selected.cells.score_psi).toBe(0);
	expect(judgeCoverage(readings.get(legacy.date)!.cells).stack).toBeNull();
	const details = await queries.sliceOnce(judgeDayQuery, { from: date, to: date, days: 1, asked: 1 });
	expect(exactJudgeDay([...details.rows, staleAttempt], selected.identity)?.runners_reported).toBe(1);
	expect(exactJudgeDay([olderRun, staleAttempt], selected.identity)).toBeNull();
});

test('only Pipelines asks the shared failed-rule question and retains every recorded model stage', () => {
	expect(modelPanels).not.toHaveProperty('refusing-rule');
	expect(Object.values(modelPanels).flat().map((query) => query.name)).not.toContain('failedRuleQuery');
	expect(pipelinesFailedRuleQuery).toBe(failedRuleQuery);
	const rows: Row[] = ['summarize', 'label', 'visual-plan'].map((stage) => ({
		date: '2030-06-14', stage, outcome: 'failed', code: 'model_reply', failed_rule: `${stage}-shape`
	}));
	const mix = nativeFailureMix(rows);
	expect(mix.stages).toEqual(['label', 'summarize', 'visual-plan']);
	for (const stage of mix.stages) {
		const ranking = failureRules(failureRuleRows(rows), { start: '2030-06-14', end: '2030-06-14' }, stage);
		expect(ranking.failed).toBe(1);
		expect(ranking.rules).toEqual([{ label: `${stage}-shape`, count: 1, daily: [1], last: '2030-06-14' }]);
	}
});

test('native throughput uses the same nearest-rank readings for a day and its single run', () => {
	const date = '2030-06-14';
	const rows: Row[] = [10, 100].map((rate) => ({
		date, run_id: `${date}-1`, input_tokens: 100, cached_tokens: 0,
		output_tokens: 100, prefill_ms: 100_000 / rate, decode_ms: 200_000 / rate
	}));
	const [day] = modelThroughput(rows, { start: date, end: date });
	expect(day.items).toBe(2);
	expect(day.read).toEqual({ min: 10, p25: 10, median: 100, p75: 100, max: 100 });
	expect(day.write).toEqual({ min: 5, p25: 5, median: 50, p75: 50, max: 50 });
	expect(day.runs).toEqual([{ runId: `${date}-1`, read: 100, write: 50 }]);
	expect(day.readTps).toBeCloseTo(200 / 11);
	expect(day.writeTps).toBeCloseTo(200 / 22);
});

test('native throughput keeps separate run populations and excludes an incomplete paired reading', () => {
	const date = '2030-06-14';
	const rows: Row[] = [10, 100, 20, 200].map((rate, index) => ({
		date, run_id: `${date}-${index < 2 ? 1 : 2}`, input_tokens: 100, cached_tokens: 0,
		output_tokens: 100, prefill_ms: 100_000 / rate, decode_ms: 200_000 / rate
	}));
	rows.push({ ...rows[0], prefill_ms: 1, decode_ms: null });
	const [day] = modelThroughput(rows, { start: date, end: date });
	expect(day.items).toBe(4);
	expect(day.read.median).toBe(100);
	expect(day.write.median).toBe(50);
	expect(day.runs).toEqual([
		{ runId: `${date}-1`, read: 100, write: 50 },
		{ runId: `${date}-2`, read: 200, write: 100 }
	]);
	expect(modelThroughput(rows, { start: '2030-06-15', end: '2030-06-15' })).toEqual([]);
});

test('build-time throughput keeps interpolated readings without changing its weighted totals', () => {
	const date = '2030-06-14';
	const row = (run: string, prefill: string, input: string, decode: string, output: string) => ({
		date, run_id: run, prefill_ms: prefill, input_tokens: input,
		cached_tokens: '100', decode_ms: decode, output_tokens: output
	});
	const [day] = throughputWithin(new Map([[date, [
		row(`${date}-1`, '1000', '1100', '2000', '100'),
		row(`${date}-1`, '3000', '1600', '1000', '100'),
		row(`${date}-2`, '1000', '600', '1000', '50')
	]]]), new Map(), { start: date, end: date });
	expect(day.readTps).toBe(600);
	expect(day.writeTps).toBe(62.5);
	expect(day.items).toBe(3);
	expect(day.read).toEqual({ min: 500, p25: 500, median: 500, p75: 750, max: 1000 });
	expect(day.write).toEqual({ min: 50, p25: 50, median: 50, p75: 75, max: 100 });
	expect(day.runs).toEqual([
		{ runId: `${date}-1`, read: 750, write: 75 },
		{ runId: `${date}-2`, read: 500, write: 50 }
	]);
});

/** A named, bounded day fixture; numeric and boolean cells really enter Parquet. */
function item(day: string, cpu = 'machine-a'): Row {
	return {
		date: day, run_id: `${day}-10`, machine_job: null, machine_shard: 0,
		cpu_model: cpu, prefill_ms: 1000, input_tokens: 300, cached_tokens: 100,
		decode_ms: 2000, output_tokens: 80,
		stage: 'fetch', outcome: 'failed', code: 'http_rate_limited', failed_rule: 'reply_shape',
		source_id: 'fixture-source', http_status: 429, source_form: 'article', tier: 1
	};
}

function host(day: string): Row {
	return {
		version: '2026-10-10', date: day, run_id: `${day}-10`, job: 'work',
		pipeline_name: null, task_name: null, shard: 0,
		fingerprint: '0123456789abcdef', fingerprint_version: 2,
		unit_id: 'e0d16ee0-85e9-54c9-8581-855fe862dc20', attempt: 1,
		cpu_model: 'machine-a', l3_cache_bytes: 32 * 2 ** 20, cpu_logical_processors: 8,
		server_prompt_tokens: 200, server_prompt_seconds: 1,
		cores: null, threads: null, mhz_max: null, mhz_at_probe: null
	};
}

async function writeWindowLedgers(root: string): Promise<void> {
	await buildRows(root, 'item-health', [
		{ covers: '2026-09-24', rows: [item('2026-09-24')] },
		{ covers: '2026-09-25', rows: [item('2026-09-25')] },
		{ covers: '2026-09-26', rows: [item('2026-09-26', 'machine-b')] }
	]);
	await buildRows(root, 'host-fingerprint', [
		{ covers: '2026-09-24', rows: [host('2026-09-24')] },
		{ covers: '2026-09-25', rows: [host('2026-09-25')] }
	]);
	await buildRows(root, 'summary-quality-evals', [
		{
			covers: '2026-09-25', rows: [{
				date: '2026-09-25', run_id: '2026-09-25-10', model_id: 'fixture-model',
				summary_words: 80, source_words_before_cap: 600, source_words: 400, compression: 0.2
			}]
		},
		{
			covers: '2026-09-26', rows: [{
				date: '2026-09-26', run_id: '2026-09-26-10', model_id: 'fixture-model',
				summary_words: 90, source_words_before_cap: 800, source_words: 600, compression: 0.15
			}]
		}
	]);
}

function diskDoor(root: string): PanelDoor {
	return {
		reach: (ledger) => reachFromDisk(root, ledger),
		rows: (ledger, options) => sliceFromDisk(root, ledger, options)
	};
}

function asRange(value: Range | LedgerReach): Range {
	expect('from' in value).toBe(true);
	if (!('from' in value)) throw new Error(`expected a range, got ${value.state}`);
	return value;
}

test('the count capability reads numeric and unknown rows and keeps unavailable states distinct', async ({}, info) => {
	const root = info.outputPath('manifest-counts');
	const options = { columns: ['date', 'run_id', 'shards'], from: '2026-10-11', to: '2026-10-11' };
	expect(await sliceFromDisk(root, 'run-shards', options)).toEqual({
		state: 'missing', rows: [], fault: 'not-packed'
	});
	await buildRows(root, 'run-shards', []);
	expect((await sliceFromDisk(root, 'run-shards', options)).state).toBe('quiet');
	const rows = [
		{ date: '2026-10-11', run_id: '2026-10-11-1', shards: 3 },
		{ date: '2026-10-11', run_id: '2026-10-11-2', shards: null }
	];
	await buildRows(root, 'run-shards', [{ covers: '2026-10-11', rows }]);
	const answer = await sliceFromDisk(root, 'run-shards', options);
	expect(answer.state).toBe('ok');
	expect(answer.rows).toEqual(rows);
	const file = path.join(root, 'compact', 'run-shards', 'daily', '2026', '10', '11.parquet');
	rmSync(file);
	expect(await sliceFromDisk(root, 'run-shards', options)).toEqual({
		state: 'unreachable', rows: [], at: '2026-10-11', fault: 'file-missing'
	});
});

test('UTC windows are inclusive across leap days and clamp at the ledger first day', () => {
	expect(windowRange(3, '2024-03-01', '2024-02-01')).toEqual({
		from: '2024-02-28', to: '2024-03-01', days: 3, asked: 3
	});
	expect(windowRange(30, '2026-01-02', '2025-12-31')).toEqual({
		from: '2025-12-31', to: '2026-01-02', days: 3, asked: 30
	});
	for (const asked of [0, -1, 1.5, NaN, Infinity]) {
		expect(() => windowRange(asked, '2026-09-26', '2026-09-24')).toThrow('asked');
	}
	expect(() => windowRange(2, '2026-02-30', '2026-01-01')).toThrow('through');
	expect(() => windowRange(2, '2026-03-01', '2026-02-30')).toThrow('first');
	expect(() => windowRange(2, '2026-09-24', '2026-09-25')).toThrow('first');
});

test('each span uses the shared data end and widest takes the explicitly passed presets', () => {
	const reach: RouteReach = {
		through: '2026-09-26',
		ledgers: {
			'run-shards': { state: 'ok', first: '2026-08-01', through: '2026-09-28', lastRows: null, fault: null },
			'item-health': { state: 'ok', first: '2026-08-01', through: '2026-09-26', lastRows: null, fault: null },
			'summary-quality-evals': { state: 'ok', first: '2026-08-01', through: '2026-09-28', lastRows: null, fault: null }
		}
	};
	expect(rangeFor(slowerOnSameWorkQuery, 3, reach, PRESETS)).toEqual({
		from: '2026-09-24', to: '2026-09-26', days: 3, asked: 3
	});
	expect(rangeFor({ ...slowerOnSameWorkQuery, span: 'newest-day' }, 3, reach, PRESETS)).toEqual({
		from: '2026-09-26', to: '2026-09-26', days: 1, asked: 1
	});
	expect(rangeFor(runShardsQuery, 3, reach, [7, 14])).toEqual({
		from: '2026-09-13', to: '2026-09-26', days: 14, asked: 14
	});
	expect(rangeFor(runShardsQuery, 3, reach, [4, 21])).toEqual({
		from: '2026-09-06', to: '2026-09-26', days: 21, asked: 21
	});
	expect(() => rangeFor(runShardsQuery, 3, reach, [])).toThrow('window_presets');
	expect(() => rangeFor(runShardsQuery, 3, reach, [0])).toThrow('window_presets');
	expect(() => rangeFor(runShardsQuery, 0, reach, PRESETS)).toThrow('preset');
	expect(() => rangeFor(platformMixQuery, 3, reach, PRESETS)).toThrow('host-fingerprint');
});

test('the real three-ledger door anchors at the oldest end and asks each ledger only from its first', async ({}, info) => {
	const root = info.outputPath('window-ledgers');
	await writeWindowLedgers(root);
	const reader = createQueryWindow(diskDoor(root));
	const reach = await reader.routeReach(['item-health', 'host-fingerprint', 'summary-quality-evals']);
	expect(reach.through).toBe('2026-09-25');
	const healthRange = asRange(rangeFor(slowerOnSameWorkQuery, 3, reach, PRESETS));
	const scoreRange = asRange(rangeFor(summaryLengthQuery, 3, reach, PRESETS));
	expect(healthRange).toEqual({ from: '2026-09-24', to: '2026-09-25', days: 2, asked: 3 });
	expect(scoreRange).toEqual({ from: '2026-09-25', to: '2026-09-25', days: 1, asked: 3 });
	const health = await reader.sliceOnce(slowerOnSameWorkQuery, healthRange);
	const score = await reader.sliceOnce(summaryLengthQuery, scoreRange);
	const machines = await reader.sliceOnce(platformMixQuery, asRange(rangeFor(platformMixQuery, 3, reach, PRESETS)));
	expect(health.state).toBe('ok');
	expect(health.rows).toEqual(['2026-09-24', '2026-09-25'].map((date) => ({
		date, cpu_model: 'machine-a', prefill_ms: 1000, input_tokens: 300,
		cached_tokens: 100, decode_ms: 2000, output_tokens: 80
	})));
	expect(score.rows).toEqual([{
		date: '2026-09-25', run_id: '2026-09-25-10', model_id: 'fixture-model',
		summary_words: 80, compression: 0.2
	}]);
	expect(machines.rows).toEqual(['2026-09-24', '2026-09-25'].map(host));
	expect(platformMixQuery.columns).toEqual([
		'version', 'date', 'run_id', 'job', 'pipeline_name', 'task_name', 'shard', 'fingerprint', 'fingerprint_version',
		'unit_id', 'attempt', 'cpu_model', 'l3_cache_bytes', 'cpu_logical_processors',
		'server_prompt_tokens', 'server_prompt_seconds',
		'cores', 'threads', 'mhz_max', 'mhz_at_probe'
	]);
	expect(platformMixQuery.columns).toEqual(expect.arrayContaining([...FLEET_COLUMNS]));
});

test('item-only timing panels share the newest article day despite lagging hardware records', async ({}, info) => {
	const root = info.outputPath('consistent-article-window');
	const day = '2026-09-26';
	const article = (run: string, item: string, shard: number, ms: number | null): Row => ({
		date: day, run_id: `${day}-${run}`, item_id: item, source_id: 'source', machine_shard: shard, item_total_ms: ms,
		fetch_ms: null, extract_ms: null, summarize_ms: null, faithfulness_ms: null, stage_gap_ms: null, queue_wait_ms: null
	});
	await buildRows(root, 'item-health', [
		{ covers: '2026-09-24', rows: [item('2026-09-24')] },
		{ covers: '2026-09-25', rows: [item('2026-09-25')] },
		{ covers: day, rows: [article('9', 'older', 0, 99000), article('10', 'short', 0, 2000),
			article('10', 'long', 1, 4000), article('10', 'missing', 2, null)] }
	]);
	await buildRows(root, 'host-fingerprint', [{ covers: '2026-09-25', rows: [host('2026-09-25')] }]);
	await buildRows(root, 'run-shards', [{
		covers: '2026-09-24', rows: [{ date: '2026-09-24', run_id: '2026-09-24-10', shards: 3 }]
	}]);
	await buildRows(root, 'summary-quality-evals', [{
		covers: '2026-09-25', rows: [{ date: '2026-09-25', run_id: '2026-09-25-10', model_id: 'fixture-model' }]
	}]);
	const reader = createQueryWindow(diskDoor(root));
	const reaches = await Promise.all(PIPELINES_QUERY_GROUPS.map((group) => reader.routeReach(group.ledgers)));
	const timeline = PIPELINES_QUERY_GROUPS[0].queries.find((query) => query.name === 'runTimelineQuery')!;
	const ranking = PIPELINES_QUERY_GROUPS[1].queries[0];
	const timelineRange = asRange(rangeFor(timeline, 7, reaches[0], PRESETS));
	const rankingRange = asRange(rangeFor(ranking, 7, reaches[1], PRESETS));
	const tailRange = asRange(rangeFor(PIPELINES_QUERY_GROUPS[1].queries[1], 7, reaches[1], PRESETS));
	const writeRange = asRange(rangeFor(PIPELINES_QUERY_GROUPS[2].queries[0], 7, reaches[2], PRESETS));
	expect(timelineRange.to).toBe(day);
	expect(rankingRange).toEqual({ from: day, to: day, days: 1, asked: 1 });
	expect(tailRange).toEqual({ from: '2026-09-24', to: day, days: 3, asked: 7 });
	expect(writeRange.to).toBe('2026-09-25');
	const answer = await reader.sliceOnce(ranking, rankingRange);
	expect(answer.state).toBe('ok');
	const view = slowestArticles(answer.rows, numberFormat);
	expect(view.run).toBe(`${day}-10`);
	expect(view.unmeasured).toBe(1);
	expect(view).toMatchObject({ medianSeconds: 3, measured: 2 });
	expect(view.rows.map((row) => [row.label, row.value])).toEqual([['long - source', 4]]);
	expect(rankedList(view.rows, { max: 1 })?.rows.map((row) => row.label)).toEqual(['long - source']);
	expect(view.rows.every((row) => row.segments === undefined)).toBe(true);
	for (const id of ['machine-cards', 'processor-lost', 'disk-reads', 'slowest-articles']) expect(PANEL_QUERIES).not.toHaveProperty(id);
	expect(PANEL_QUERIES['article-cost'].map((query) => query.name)).toEqual(['articleCostQuery', 'articleCostHostsQuery']);
});

test('structured fetch predicates cross the real door rather than filtering the answer afterward', async ({}, info) => {
	const root = info.outputPath('fetch-predicate');
	await buildRows(root, 'item-health', [{
		covers: '2026-09-25',
		rows: [item('2026-09-25'), { ...item('2026-09-25'), stage: 'publish', outcome: 'ok', code: null }]
	}]);
	const reader = createQueryWindow(diskDoor(root));
	const reach = await reader.routeReach(['item-health']);
	const answer = await reader.sliceOnce(feedsFailedQuery, asRange(rangeFor(feedsFailedQuery, 3, reach, PRESETS)));
	expect(answer.rows).toEqual([{
		date: '2026-09-25', source_id: 'fixture-source', stage: 'fetch', outcome: 'failed',
		code: 'http_rate_limited', http_status: 429, source_form: 'article', tier: 1
	}]);
});

test('unavailable reaches have no day and lead to no slice; empty and missing ledgers are distinct', async ({}, info) => {
	const root = info.outputPath('unavailable-reaches');
	await buildRows(root, 'host-fingerprint', []);
	await buildRows(root, 'item-health', [{ covers: '2026-09-25', rows: [item('2026-09-25')] }]);
	const index = path.join(root, 'compact', 'item-health', 'index', 'daily.json');
	writeFileSync(index, '{not valid JSON}\n');
	let calls = 0;
	const door = diskDoor(root);
	const reader = createQueryWindow({
		reach: door.reach,
		rows: (ledger, options) => { calls += 1; return door.rows(ledger, options); }
	});
	const reach = await reader.routeReach(['item-health', 'host-fingerprint', 'summary-quality-evals']);
	expect(reach.through).toBeNull();
	expect(reach.ledgers['item-health']).toEqual({ state: 'unreachable' });
	expect(reach.ledgers['host-fingerprint']).toEqual({ state: 'quiet' });
	expect(reach.ledgers['summary-quality-evals']).toEqual({ state: 'missing', fault: 'not-packed' });
	for (const query of [slowerOnSameWorkQuery, platformMixQuery, summaryLengthQuery]) {
		const range = rangeFor(query, 3, reach, PRESETS);
		if ('from' in range) await reader.sliceOnce(query, range);
		expect(range).toEqual(reach.ledgers[query.ledger]);
		expect('at' in range).toBe(false);
	}
	expect(calls).toBe(0);
});

test('a ledger starting after the common data end is quiet rather than an inverted range', () => {
	const reach: RouteReach = {
		through: '2026-09-24',
		ledgers: { 'item-health': { state: 'ok', first: '2026-09-25', through: '2026-09-26', lastRows: null, fault: null } }
	};
	expect(rangeFor(slowerOnSameWorkQuery, 3, reach, PRESETS)).toEqual({ state: 'quiet' });
});

test('recent windows survive tab and preset changes; eviction and explicit retry read again', async ({}, info) => {
	const root = info.outputPath('held-range');
	await writeWindowLedgers(root);
	const door = diskDoor(root);
	let calls = 0;
	const reader = createQueryWindow({
		reach: door.reach,
		rows: (ledger, options) => { calls += 1; return door.rows(ledger, options); }
	}, 2);
	const wide = windowRange(3, '2026-09-26', '2026-09-24');
	const narrow = windowRange(1, '2026-09-26', '2026-09-24');
	const first = reader.sliceOnce(slowerOnSameWorkQuery, wide);
	expect(reader.sliceOnce(slowerOnSameWorkQuery, wide)).toBe(first);
	expect((await first).rows).toHaveLength(3);
	const next = reader.sliceOnce(slowerOnSameWorkQuery, narrow);
	expect(next).not.toBe(first);
	expect((await next).rows).toHaveLength(1);
	const back = reader.sliceOnce(slowerOnSameWorkQuery, wide);
	expect(back).toBe(first);
	await back;
	expect(calls).toBe(2);
	const otherShape = { ...slowerOnSameWorkQuery, columns: ['cpu_model'] };
	expect((await reader.sliceOnce(otherShape, wide)).rows[0]).toEqual({ cpu_model: 'machine-a' });
	expect(reader.sliceOnce(slowerOnSameWorkQuery, wide)).toBe(first);
	expect(calls).toBe(3);
	const middle = windowRange(2, '2026-09-26', '2026-09-24');
	await reader.sliceOnce(slowerOnSameWorkQuery, middle);
	const evicted = reader.sliceOnce(slowerOnSameWorkQuery, narrow);
	expect(evicted).not.toBe(next);
	await evicted;
	expect(calls).toBe(5);
	reader.retryAsks([slowerOnSameWorkQuery]);
	const retried = reader.sliceOnce(slowerOnSameWorkQuery, wide);
	expect(retried).not.toBe(back);
	await retried;
	expect(calls).toBe(6);
	reader.retryAsks();
	await reader.sliceOnce(slowerOnSameWorkQuery, wide);
	expect(calls).toBe(7);
});

test('missing and unreachable slices are retried using real repaired files, not cached empty successes', async ({}, info) => {
	const root = info.outputPath('repair-ledger');
	const reader = createQueryWindow(diskDoor(root));
	const range = windowRange(1, '2026-09-25', '2026-09-25');
	const missing = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(await missing).toEqual({ state: 'missing', rows: [], fault: 'not-packed' });
	await buildRows(root, 'item-health', [{ covers: '2026-09-25', rows: [item('2026-09-25')] }]);
	const file = path.join(root, 'compact', 'item-health', 'daily', '2026', '09', '25.parquet');
	const bytes = readFileSync(file);
	rmSync(file);
	const unreachable = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(unreachable).not.toBe(missing);
	expect(await unreachable).toEqual({ state: 'unreachable', rows: [], at: '2026-09-25', fault: 'file-missing' });
	writeFileSync(file, bytes);
	const repaired = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(repaired).not.toBe(unreachable);
	expect((await repaired).rows).toHaveLength(1);
	expect(reader.sliceOnce(slowerOnSameWorkQuery, range)).toBe(repaired);
	expect((await reader.routeReach(['item-health'])).through).toBe('2026-09-25');
});

test('an explicit new read session invalidates same-endpoint answers and preserves new promises against old completions', async ({}, info) => {
	const root = info.outputPath('refreshed-rows');
	const refreshedRoot = info.outputPath('new-session-rows');
	await writeWindowLedgers(root);
	await buildRows(refreshedRoot, 'item-health', [{ covers: '2026-09-26', rows: [item('2026-09-26', 'refreshed-machine')] }]);
	let currentRoot = root;
	const door: PanelDoor = {
		reach: (ledger) => reachFromDisk(currentRoot, ledger),
		rows: (ledger, options) => sliceFromDisk(currentRoot, ledger, options)
	};
	const range = windowRange(1, '2026-09-26', '2026-09-24');
	let release: () => void = () => { throw new Error('no held read'); };
	let hold = false;
	let waiting = false;
	const reader = createQueryWindow({
		...door,
		currentSession: readSession,
		rows: async (ledger, options) => {
			const rows = await door.rows(ledger, options);
			if (hold) await new Promise<void>((resolve) => { release = resolve; waiting = true; });
			return rows;
		}
	});
	const first = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect((await first).rows[0].cpu_model).toBe('machine-b');
	currentRoot = refreshedRoot;
	expect(reader.sliceOnce(slowerOnSameWorkQuery, range)).toBe(first);
	renewReadSession();
	const refreshed = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(refreshed).not.toBe(first);
	expect((await refreshed).rows[0].cpu_model).toBe('refreshed-machine');

	reader.retryAsks();
	hold = true;
	const old = reader.sliceOnce(slowerOnSameWorkQuery, range);
	await expect.poll(() => waiting).toBe(true);
	hold = false;
	renewReadSession();
	const newSession = reader.sliceOnce(slowerOnSameWorkQuery, range);
	await newSession;
	release();
	await old;
	expect(reader.sliceOnce(slowerOnSameWorkQuery, range)).toBe(newSession);
});

test('rejected promises preserve the real I/O error and do not poison a later ask', async ({}, info) => {
	const root = info.outputPath('rejected-promise');
	await writeWindowLedgers(root);
	const required = info.outputPath('required.txt');
	const door = diskDoor(root);
	const reader = createQueryWindow({
		reach: door.reach,
		rows: async (ledger, options) => { await readFile(required); return door.rows(ledger, options); }
	});
	const range = windowRange(1, '2026-09-25', '2026-09-25');
	const rejected = reader.sliceOnce(slowerOnSameWorkQuery, range);
	await expect(rejected).rejects.toThrow('ENOENT');
	mkdirSync(path.dirname(required), { recursive: true });
	writeFileSync(required, 'ready\n');
	const repaired = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(repaired).not.toBe(rejected);
	expect((await repaired).rows).toHaveLength(1);
});

for (const failOld of [false, true]) {
	test(`an old range completing late cannot replace or evict the new promise (${failOld ? 'I/O error' : 'answer'})`, async ({}, info) => {
		const root = info.outputPath('overlapping-ranges');
		await writeWindowLedgers(root);
		const required = info.outputPath('required.txt');
		writeFileSync(required, 'ready\n');
		let release!: () => void;
		const gate = new Promise<void>((resolve) => { release = resolve; });
		const door = diskDoor(root);
		const reader = createQueryWindow({
			reach: door.reach,
			rows: async (ledger, options) => {
				const answer = await door.rows(ledger, options);
				if (options.from === '2026-09-24') {
					await gate;
					await readFile(required);
				}
				return answer;
			}
		});
		const wide = windowRange(3, '2026-09-26', '2026-09-24');
		const narrow = windowRange(1, '2026-09-26', '2026-09-24');
		const old = reader.sliceOnce(slowerOnSameWorkQuery, wide);
		const current = reader.sliceOnce(slowerOnSameWorkQuery, narrow);
		expect((await current).rows).toEqual([{
			date: '2026-09-26', cpu_model: 'machine-b', prefill_ms: 1000,
			input_tokens: 300, cached_tokens: 100, decode_ms: 2000, output_tokens: 80
		}]);
		if (failOld) rmSync(required);
		release();
		if (failOld) await expect(old).rejects.toThrow('ENOENT');
		else expect((await old).rows).toHaveLength(3);
		expect(reader.sliceOnce(slowerOnSameWorkQuery, narrow)).toBe(current);
		expect((await current).rows[0]?.date).toBe('2026-09-26');
	});
}

test('tally precedence keeps truthful partial missing and unreachable counts even while pending', () => {
	const quiet: LedgerReach = { state: 'quiet' };
	const missing: LedgerReach = { state: 'missing', fault: 'not-packed' };
	const unreachable: LedgerReach = { state: 'unreachable' };
	const ok: SliceResult = {
		state: 'ok', rows: [item('2026-09-25')], first: '2026-09-25', through: '2026-09-25', lostDays: [], setAside: {}
	};
	expect(tallyAsks(['pending', unreachable, missing, missing])).toEqual({ state: 'loading', missing: 2, unreachable: 1 });
	expect(tallyAsks([ok, unreachable, missing])).toEqual({ state: 'unreachable', missing: 1, unreachable: 1 });
	expect(tallyAsks([ok, quiet, missing])).toEqual({ state: 'missing', missing: 1, unreachable: 0 });
	expect(tallyAsks([quiet, quiet])).toEqual({ state: 'quiet', missing: 0, unreachable: 0 });
	expect(tallyAsks([quiet, ok])).toEqual({ state: 'ok', missing: 0, unreachable: 0 });
	expect(tallyAsks([])).toEqual({ state: 'quiet', missing: 0, unreachable: 0 });
});

test('newest run is dated and numerically ordered, including run ids beyond safe JS integers', () => {
	const rows: Row[] = [
		{ run_id: '2026-09-25-999' }, { run_id: '2026-09-26-9' },
		{ run_id: '2026-09-26-10' }, { run_id: '2026-09-26-10' }
	];
	expect(newestRunRows(rows)).toEqual(rows.slice(2));
	expect(compareRuns('2026-09-26-9007199254740993', '2026-09-26-9007199254740992')).toBe(1);
	expect(compareRuns('2026-09-27-1', '2026-09-26-100')).toBe(1);
	expect(() => compareRuns('2026-02-30-1', '2026-09-26-1')).toThrow('run_id');
	expect(newestRunRows([])).toEqual([]);
});

test('item-host joins use the execution keys, default only the empty legacy job, and count unmatched items', () => {
	const base = { ...item('2026-09-25'), attempt: 1 };
	const hosts = [
		host('2026-09-25'),
		{ ...host('2026-09-25'), job: 'assemble', server_prompt_tokens: 999 }
	];
	const items = [
		base, { ...base, machine_job: '' },
		{ ...base, machine_job: 'assemble' },
		{ ...base, machine_shard: 1 }, { ...base, machine_shard: null },
		{ ...base, date: '2026-09-26' }, { ...base, run_id: '2026-09-25-9' }
	];
	const joined = joinItemHosts(items, hosts);
	expect(joined.rows).toHaveLength(7);
	expect(joined.unmatched).toBe(4);
	expect(joined.rows.slice(0, 3).map((row) => row.host?.server_prompt_tokens)).toEqual([200, 200, 999]);
	expect(hostKey(base, true)).toBe(hostKey(hosts[0]));
	expect(() => hostKey({ ...base, machine_shard: false }, true)).toThrow('shard');
});

test('item-host joins keep task and attempt separate from the actual job, with a finite digest alias', () => {
	const day = '2026-09-25';
	const legacy = { ...host(day), attempt: 1 };
	const native = { ...host(day), pipeline_name: 'digest', task_name: 'work', job: 'actual-runner-job', attempt: 2 };
	const other = { ...native, pipeline_name: 'other', task_name: 'work' };
	const itemRow = { ...item(day), machine_pipeline_name: 'digest', machine_task_name: 'work' };
	const { rows } = joinItemHosts([
		{ ...itemRow, attempt: 1 }, { ...itemRow, attempt: 2 }, { ...itemRow, attempt: 3 },
		{ ...itemRow, attempt: 2, machine_pipeline_name: 'other' },
		{ ...itemRow, attempt: 1, machine_pipeline_name: 'other' }
	], [legacy, native, other]);
	expect(rows.map(row => row.host)).toEqual([legacy, native, null, other, null]);
});

test('legacy itemRates keeps independent read and write evidence and its absent-cache behavior', () => {
	expect(itemRates({ prefill_ms: '1000', input_tokens: '300', cached_tokens: '100', decode_ms: '2000', output_tokens: '80' }))
		.toEqual({ read: 200, write: 40 });
	expect(itemRates({ prefill_ms: '1000', input_tokens: '300', decode_ms: '', output_tokens: '80' }))
		.toEqual({ read: 300, write: null });
	expect(itemRates({ prefill_ms: '', input_tokens: '300', cached_tokens: '100', decode_ms: '2000', output_tokens: '80' }))
		.toEqual({ read: null, write: 40 });
	expect(itemRates({ prefill_ms: 'NaN', input_tokens: '300', decode_ms: 'Infinity', output_tokens: '80' }))
		.toEqual({ read: null, write: null });
});

test('comparable rates require all five cells, finite evidence and positive fresh input and output', () => {
	const row = item('2026-09-25');
	expect(qualifyingWork(row)).toEqual({ freshInput: 200, output: 80, readMsPerToken: 5, writeMsPerToken: 25 });
	for (const column of ['prefill_ms', 'input_tokens', 'cached_tokens', 'decode_ms', 'output_tokens']) {
		for (const absent of [null, '', ' ', Infinity, NaN, false]) {
			expect(qualifyingWork({ ...row, [column]: absent })).toBeNull();
		}
	}
	expect(qualifyingWork({ ...row, cached_tokens: 300 })).toBeNull();
	expect(qualifyingWork({ ...row, output_tokens: 0 })).toBeNull();
	expect(qualifyingWork({ ...row, prefill_ms: 0, decode_ms: 0 }))
		.toEqual({ freshInput: 200, output: 80, readMsPerToken: 0, writeMsPerToken: 0 });
	expect(finiteCell('0')).toBe(0);
	expect(finiteCell('')).toBeNull();
	expect(finiteCell(false)).toBeNull();
	expect(nearestRank([1, 2, 8, 10], 0.5)).toBe(8);
	expect(nearestRank([1, 2, 8, 10], 0.9)).toBe(10);
	expect(nearestRank([], 0.5)).toBeNull();
});

test('the reference wins by qualifying count then name, and fixed median work is priced without interpolation', () => {
	const base = item('2026-09-25');
	const rows: Row[] = [
		{ ...base, cpu_model: 'z-machine', input_tokens: 200, output_tokens: 20 },
		{ ...base, cpu_model: 'a-machine', input_tokens: 300, output_tokens: 30 },
		{ ...base, cpu_model: 'z-machine', input_tokens: 500, output_tokens: 50 },
		{ ...base, cpu_model: 'a-machine', input_tokens: 900, output_tokens: 90 },
		{ ...base, cpu_model: 'z-machine', cached_tokens: null },
		{ ...base, cpu_model: null, input_tokens: 400, output_tokens: 40 }
	];
	const reference = referenceWork(rows);
	expect(reference).toEqual({
		cpuModel: 'a-machine', referenceRows: 2, qualifying: 5, unqualified: 1, unnamedMachine: 1,
		freshInput: 300, output: 40
	});
	const priced = typicalSeconds(rows, reference);
	expect(priced.from).toBe(2);
	expect(priced.outOf).toBe(6);
	expect(priced.read).toBe(1.5);
	expect(priced.write).toBeCloseTo(8 / 3);
	expect(typicalSeconds(rows.filter((row) => row.cpu_model === 'z-machine'), reference))
		.toEqual({ read: null, write: null, from: 0, outOf: 3 });
	expect(referenceWork([])).toEqual({
		cpuModel: null, referenceRows: 0, qualifying: 0, unqualified: 0, unnamedMachine: 0,
		freshInput: null, output: null
	});
	expect(failedRuleQuery.columns).toEqual(['date', 'stage', 'outcome', 'code', 'failed_rule']);
});
