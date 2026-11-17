/** Native reuse readings keep requests separate and unknown distinct from zero. */
import { expect, test } from '@playwright/test';
import { reuseDays } from '../src/lib/console/machine/prompt-reuse';
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
	const label = reuseDays(rows, 'label');
	const summary = reuseDays(rows, 'summary');
	expect(label).toEqual([{ date: DATE, input: 1100, cached: 100, articles: 2, share: 100 * 100 / 1100 }]);
	expect(summary).toEqual([{ date: DATE, input: 3000, cached: 2990, articles: 2, share: 100 * 2990 / 3000 }]);
	// The two recorded percentages, 0 and 100, would average to 50.
	expect(label[0].share).not.toBe(50);
});

test('unknown requests stay unknown while real zero reuse remains measured', () => {
	const rows: Row[] = [{ date: DATE, label_input_tokens: 1000, label_cached_tokens: 0, label_cache_pct: 0 }];
	expect(reuseDays(rows, 'label')).toEqual([{ date: DATE, input: 1000, cached: 0, articles: 1, share: 0 }]);
	expect(reuseDays(rows, 'summary')).toEqual([]);
	expect(reuseDays([], 'label')).toEqual([]);
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
	expect(reuseDays(rows, 'label')).toEqual([]);
	expect(reuseDays([
		{ date: DATE, summary_input_tokens: 100, summary_cached_tokens: 101 },
		{ date: DATE, summary_input_tokens: 100, summary_cached_tokens: -1 },
		{ date: DATE, summary_input_tokens: 'Infinity', summary_cached_tokens: 0 },
		{ date: DATE, summary_input_tokens: 100, summary_cached_tokens: null }
	], 'summary')).toEqual([]);
});

test('the current query declares the paired prompt and cached cells of both calls', () => {
	expect(promptReuseQuery.columns).toEqual([
		'date', 'label_input_tokens', 'label_cached_tokens', 'summary_input_tokens', 'summary_cached_tokens'
	]);
});
