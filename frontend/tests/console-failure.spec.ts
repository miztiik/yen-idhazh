/** Native failures keep recorded-row divisors, unknown days and stage-owned rules. */
import { expect, test } from '@playwright/test';
import { nativeFailureMix } from '../src/lib/console/pipelines/failure-mix';
import { failureRuleRows, failureRules } from '../src/lib/console/failure-rules';
import { failureMixQuery } from '../src/lib/console/queries/pipelines';
import type { Row } from '../src/lib/data/ledger';

function row(date: string, stage: string, outcome = 'failed', failed_rule: string | null = null): Row {
	return { date, stage, outcome, code: null, failed_rule };
}

test('the failure share divides recorded rows, without inferred article or stage attempts', () => {
	const date = '2026-08-20';
	const rows = [
		...Array.from({ length: 4 }, () => row(date, 'fetch')),
		...Array.from({ length: 2 }, () => row(date, 'extract')),
		row(date, 'summarize'),
		...Array.from({ length: 3 }, () => row(date, 'publish', 'ok'))
	];
	const mix = nativeFailureMix(rows);
	expect(failureMixQuery.columns).toEqual(['date', 'stage', 'outcome', 'code', 'failed_rule']);
	expect(mix).toMatchObject({ recorded: 10, failures: 7, share: 0.7 });
	expect(mix.series.map((stage) => stage.points[0].value)).toEqual([4, 2, 1]);
	expect(nativeFailureMix([...rows, row(date, 'plan')])).toMatchObject({
		recorded: 11, failures: 8, share: 8 / 11
	});
});

test('a recorded zero and an absent divisor are different answers, even for a single row', () => {
	const date = '2026-08-20';
	expect(nativeFailureMix([row(date, 'publish', 'ok')])).toMatchObject({
		recorded: 1, failures: 0, share: 0
	});
	expect(nativeFailureMix([row(date, 'fetch')])).toMatchObject({
		recorded: 1, failures: 1, share: 1
	});
	const absent = nativeFailureMix([], [date]);
	expect(absent).toMatchObject({ recorded: 0, failures: 0, share: null, chosenStage: null });
	expect(absent.series.map((stage) => stage.points[0].value)).toEqual([null, null, null]);
});

test('the stage stack conserves all recorded failures, including stages outside the named three', () => {
	const date = '2026-08-20';
	const mix = nativeFailureMix([
		row(date, 'fetch'), row(date, 'extract'), row(date, 'summarize'),
		row(date, 'plan'), row(date, 'publish'), row(date, 'publish', 'ok')
	]);
	expect(mix).toMatchObject({ recorded: 6, failures: 5, share: 5 / 6 });
	expect(mix.series.map((stage) => [stage.label, stage.points[0].value])).toEqual([
		['Fetch', 1], ['Extract', 1], ['Summarize', 1], ['Other stages', 2]
	]);
	expect(mix.series.reduce((sum, stage) => sum + stage.points[0].value!, 0)).toBe(5);
});

test('a complete calendar preserves missing days without suppressing a small measured cohort', () => {
	const calendar = ['2026-08-18', '2026-08-19', '2026-08-20'];
	const mix = nativeFailureMix([
		row(calendar[0], 'fetch'),
		...Array.from({ length: 8 }, () => row(calendar[2], 'publish', 'ok'))
	], calendar);
	expect(mix.series.map((stage) => stage.points.map((point) => point.value))).toEqual([
		[1, null, 0], [0, null, 0], [0, null, 0]
	]);
	expect(mix.series[0].points.map((point) => point.date)).toEqual(calendar);
	expect(mix.share).toBe(1 / 9);
});

test('failed rules belong to their selected stage, with unknown failures kept in its divisor', () => {
	const date = '2026-08-20';
	const rows = [
		row(date, 'fetch', 'failed', 'b'), row(date, 'fetch', 'failed', 'a'),
		row(date, 'fetch'), row(date, 'fetch', 'ok', 'not-a-failure'),
		row(date, 'extract', 'failed', 'b'), row(date, 'extract', 'failed', 'b'),
		row(date, 'extract', 'failed', 'b'),
		row('2026-08-19', 'fetch', 'failed', 'outside')
	];
	const mix = nativeFailureMix(rows.filter((entry) => entry.date === date));
	expect(mix.stages).toEqual(['extract', 'fetch']);
	expect(mix.chosenStage).toBe('extract');
	expect(mix.rules).toEqual([
		{ stage: 'extract', failures: 3, unknown: 0, rules: [{ rule: 'b', count: 3 }] },
		{ stage: 'fetch', failures: 3, unknown: 1, rules: [{ rule: 'a', count: 1 }, { rule: 'b', count: 1 }] }
	]);
	expect(nativeFailureMix([...rows.filter((entry) => entry.date === date)].reverse()).rules).toEqual(mix.rules);
	const chosen = failureRules(failureRuleRows(rows), { start: date, end: date }, 'fetch');
	expect(chosen).toMatchObject({ dates: [date], rows: 4, failed: 3, unknown: 1 });
	expect(chosen.rules.map((rule) => [rule.label, rule.count, rule.daily, rule.last])
		.sort(([a], [b]) => String(a).localeCompare(String(b)))).toEqual([
		['a', 1, [1], date], ['b', 1, [1], date]
	]);
});
