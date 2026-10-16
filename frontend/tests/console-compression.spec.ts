/** The live Model length reader chooses the band each recorded article reaches. */
import { expect, test } from '@playwright/test';
import { summaryLength } from '../src/lib/console/model/summary-length';
import type { SummaryBand } from '../src/lib/server/config';

test('the longest reached band wins, including each exact boundary and an unsorted ladder', () => {
	const bands: SummaryBand[] = [
		{ min_source_words: 700, target_words_min: 70, target_words_max: 150 },
		{ min_source_words: 0, target_words_min: 30, target_words_max: 45 },
		{ min_source_words: 60, target_words_min: 50, target_words_max: 90 }
	];
	const original = bands.map((band) => ({ ...band }));
	const runs = summaryLength([0, 59, 60, 699, 700, 90_000].map((source_words, index) => ({
		date: '2026-08-28', run_id: `2026-08-28-${index}`, source_words, summary_words: 45
	})), bands);
	expect(runs.map((run) => [run.askLow, run.askHigh])).toEqual([
		[30, 45], [30, 45], [50, 90], [50, 90], [70, 150], [70, 150]
	]);
	expect(bands).toEqual(original);
});

test('a missing ladder or unreached first rung supplies no invented bounds', () => {
	const rows = [{ date: '2026-08-28', run_id: 'r', source_words: 40, summary_words: 45 }];
	expect(summaryLength(rows, [])[0]).toMatchObject({ items: 1, low: 45, high: 45, askLow: null, askHigh: null });
	expect(summaryLength(rows, [
		{ min_source_words: 60, target_words_min: 50, target_words_max: 90 }
	])[0]).toMatchObject({ askLow: null, askHigh: null });
});
