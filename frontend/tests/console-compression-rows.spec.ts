/** The live Model reader uses measured pre-cap lengths and refuses missing summaries. */
import { expect, test } from '@playwright/test';
import { summaryLength } from '../src/lib/console/model/summary-length';
import { cutWords, wasCut } from '../src/lib/console/model/work';

const bands = [
	{ min_source_words: 0, target_words_min: 50, target_words_max: 90 },
	{ min_source_words: 2000, target_words_min: 100, target_words_max: 200 }
];

test('the pre-cap article length chooses the ask, with the surviving length used only when it is absent', () => {
	const lengths = summaryLength([
		{ date: '2026-08-28', run_id: 'cut', source_words_before_cap: 4200, source_words: 1923, summary_words: 205 },
		{ date: '2026-08-28', run_id: 'whole', source_words_before_cap: null, source_words: 880, summary_words: 205 },
		{ date: '2026-08-28', run_id: 'no-source', source_words_before_cap: null, source_words: null, summary_words: 205 },
		{ date: '2026-08-28', run_id: 'no-summary', source_words: 400, summary_words: null },
		{ date: '2026-08-28', run_id: '', source_words: 400, summary_words: 9000 }
	], bands);
	expect(lengths.map((run) => [run.runId, run.items, run.askLow, run.askHigh])).toEqual([
		['cut', 1, 100, 200], ['no-source', 1, null, null], ['whole', 1, 50, 90]
	]);
});

test('a cut remains a fact about two lengths, never a ledger flag or stamp', () => {
	expect(cutWords(4200, 1923)).toBe(2277);
	expect(cutWords(2000, 2000)).toBeNull();
	expect(cutWords(null, 880)).toBeNull();
	expect(cutWords(4200, null)).toBeNull();
	for (const version of ['2026-08-01', '2026-08-28', '2026-09-01']) {
		expect(wasCut({ version, truncation_flagged: 'False', source_words_before_cap: '4200', source_words: '1923' })).toBe(true);
		expect(wasCut({ version, truncation_flagged: 'True', source_words_before_cap: '2000', source_words: '2000' })).toBe(false);
		expect(wasCut({ version, truncation_flagged: 'True', source_words_before_cap: '', source_words: '880' })).toBe(false);
	}
});
