/** Native Model run lengths retain measured endpoints without retired distance columns. */
import { expect, test } from '@playwright/test';
import { summaryLength } from '../src/lib/console/model/summary-length';
import type { Row } from '../src/lib/data/ledger';
import type { SummaryBand } from '../src/lib/server/config';

const bands: SummaryBand[] = [
	{ min_source_words: 0, target_words_min: 50, target_words_max: 90 },
	{ min_source_words: 700, target_words_min: 70, target_words_max: 150 }
];

test('the actual native run cohort keeps both length endpoints and does not collapse different runs', () => {
	const rows: Row[] = [
		{ date: '2026-08-28', run_id: '2026-08-28-1', item_id: 'low', source_words: 400, summary_words: 50 },
		{ date: '2026-08-28', run_id: '2026-08-28-1', item_id: 'high', source_words: 400, summary_words: 90 },
		{ date: '2026-08-28', run_id: '2026-08-28-1', item_id: 'short', source_words: 400, summary_words: 49 },
		{ date: '2026-08-28', run_id: '2026-08-28-1', item_id: 'long', source_words: 2500, summary_words: 151 },
		{ date: '2026-08-28', run_id: '2026-08-28-2', item_id: 'low', source_words: 300, summary_words: 590 },
		{ date: '2026-08-28', run_id: '2026-08-28-1', source_words: null, summary_words: null },
		{ date: '2026-08-26', run_id: '2026-08-26-1', source_words: 400, summary_words: 49 },
		{ date: '2026-08-26', run_id: '2026-08-26-1', source_words: 400, summary_words: 50 }
	];
	const lengths = summaryLength(rows, bands);
	expect(lengths.map(({ runId, date, items, low, median, high, askLow, askHigh }) =>
		({ runId, date, items, low, median, high, askLow, askHigh }))).toEqual([
		{ runId: '2026-08-26-1', date: '2026-08-26', items: 2, low: 49, median: 50, high: 50, askLow: 50, askHigh: 90 },
		{ runId: '2026-08-28-1', date: '2026-08-28', items: 4, low: 49, median: 90, high: 151, askLow: 50, askHigh: 150 },
		{ runId: '2026-08-28-2', date: '2026-08-28', items: 1, low: 590, median: 590, high: 590, askLow: 50, askHigh: 90 }
	]);
	expect(summaryLength([...rows].reverse(), bands)).toEqual(lengths);
});

test('zero length is measured, unknown length is not, and compression keeps its own numeric reading', () => {
	const lengths = summaryLength([
		{ date: '2026-08-28', run_id: 'zero', summary_words: 0, source_words: 400, compression: 0 },
		{ date: '2026-08-28', run_id: 'unknown', summary_words: null, source_words: 400, compression: null },
		{ date: '2026-08-28', run_id: 'ratio', summary_words: 49, source_words: 400, compression: 0.1225 },
		{ date: '2026-08-28', run_id: 'ratio', summary_words: 151, source_words: 2500, compression: 0.0604 }
	], bands);
	expect(lengths.map((run) => run.runId)).toEqual(['ratio', 'zero']);
	expect(lengths[0]).toMatchObject({ items: 2, low: 49, median: 151, high: 151, compression: 0.1225 });
	expect(lengths[1]).toMatchObject({ items: 1, low: 0, median: 0, high: 0, compression: 0 });
});
