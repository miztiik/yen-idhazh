/** Native reuse readings keep requests separate and unknown distinct from zero. */
import { expect, test } from '@playwright/test';
import { labelHeldMedian, reuseChecks, reuseSeries } from '../src/lib/console/machine/records';
import { promptReuseQuery } from '../src/lib/console/queries/machine';
import type { Row } from '../src/lib/data/ledger';

const DATE = '2026-09-20';

test('pooled shares use paired cells of each call, never a mean across requests or articles', () => {
	const rows: Row[] = [
		{ date: DATE, label_input_tokens: 1000, label_cached_tokens: 0, label_cache_pct: 0,
			summary_input_tokens: 1000, summary_cached_tokens: 990, summary_cache_pct: 99 },
		{ date: DATE, label_input_tokens: 100, label_cached_tokens: 100, label_cache_pct: 100,
			summary_input_tokens: 2000, summary_cached_tokens: 2000, summary_cache_pct: 100 }
	];
	const checks = reuseChecks(rows);
	expect(checks.map((one) => one.call)).toEqual(['label', 'summary']);
	expect(checks[0]).toMatchObject({ ours: 100 * 100 / 1100, server: 100, count: 2 });
	expect(checks[1]).toMatchObject({ ours: 100 * 2990 / 3000, server: 100, count: 2 });
	// The native upper middle of recorded percentages is not recomputed from our cells.
	expect(checks[0].ours).not.toBe(checks[0].server);
	expect(checks[0].ours).not.toBe(50);
});

test('held label text and fresh summary text are two series over the same measured dates', () => {
	const rows: Row[] = [
		{ date: DATE, label_cached_tokens: 0, summary_input_tokens: 1000, summary_cached_tokens: 900 },
		{ date: DATE, label_cached_tokens: 400, summary_input_tokens: 2000, summary_cached_tokens: 1600 },
		{ date: '2026-09-19', label_cached_tokens: 200, summary_input_tokens: 800, summary_cached_tokens: 0 }
	];
	const series = reuseSeries(rows);
	expect(series.map((one) => one.points)).toEqual([
		[{ date: '2026-09-19', value: 200 }, { date: DATE, value: 400 }],
		[{ date: '2026-09-19', value: 800 }, { date: DATE, value: 400 }]
	]);
	expect(labelHeldMedian(rows)).toBe(200);
});

test('unknown requests stay unknown while real zero reuse remains measured', () => {
	const rows: Row[] = [{ date: DATE, label_input_tokens: 1000, label_cached_tokens: 0, label_cache_pct: 0 }];
	expect(reuseChecks(rows)).toEqual([
		{ call: 'label', ours: 0, server: 0, count: 1 },
		{ call: 'summary', ours: null, server: null, count: 0 }
	]);
	expect(reuseSeries(rows).map((one) => one.points)).toEqual([
		[{ date: DATE, value: 0 }], [{ date: DATE, value: null }]
	]);
	expect(labelHeldMedian([{ date: DATE }])).toBeNull();
	expect(reuseChecks([]).every((one) => one.ours === null && one.server === null && one.count === 0)).toBe(true);
	expect(reuseSeries([]).every((one) => one.points.length === 0)).toBe(true);
});

test('equal unpaired counts and invalid numbers cannot invent reuse', () => {
	const rows: Row[] = [
		{ date: DATE, label_input_tokens: 1000, label_cached_tokens: null },
		{ date: DATE, label_input_tokens: null, label_cached_tokens: 900 },
		{ date: DATE, label_input_tokens: 'Infinity', label_cached_tokens: 100, label_cache_pct: 'NaN' },
		{ date: DATE, label_input_tokens: 100, label_cached_tokens: 101, label_cache_pct: 101 },
		{ date: DATE, label_input_tokens: 100, label_cached_tokens: -1, label_cache_pct: -1 },
		{ date: DATE, label_input_tokens: 0, label_cached_tokens: 0 }
	];
	expect(reuseChecks(rows)[0]).toEqual({ call: 'label', ours: null, server: null, count: 0 });
	expect(reuseSeries([
		{ date: DATE, summary_input_tokens: 100, summary_cached_tokens: 101 },
		{ date: DATE, summary_input_tokens: 100, summary_cached_tokens: -1 },
		{ date: DATE, summary_input_tokens: 'Infinity', summary_cached_tokens: 0 },
		{ date: DATE, summary_input_tokens: 100, summary_cached_tokens: null }
	])[1].points).toEqual([{ date: DATE, value: null }]);
});

test('the current query declares the cells that independently compare both calls', () => {
	expect(promptReuseQuery.columns).toEqual([
		'date', 'label_input_tokens', 'label_cached_tokens', 'label_cache_pct', 'label_prefill_tokens_per_s',
		'summary_input_tokens', 'summary_cached_tokens', 'summary_cache_pct', 'summary_prefill_tokens_per_s'
	]);
});
