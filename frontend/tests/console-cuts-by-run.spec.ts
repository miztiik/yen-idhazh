/** The current cut predicate retains measured absence and length semantics, not retired run attribution. */
import { expect, test } from '@playwright/test';
import { cutWords, wasCut } from '../src/lib/console/model/work';

test('a cut is measured length removed, not an absent length, a run identity or a ledger flag', () => {
	expect(cutWords(5000, 2100)).toBe(2900);
	expect(cutWords(3000, 2100)).toBe(900);
	expect(cutWords(800, 800)).toBeNull();
	expect(cutWords(null, 2100)).toBeNull();
	expect(cutWords(4000, null)).toBeNull();
	expect(wasCut({ source_words_before_cap: '5000', source_words: '2100' })).toBe(true);
	expect(wasCut({ source_words_before_cap: '800', source_words: '800' })).toBe(false);
	expect(wasCut({ source_words_before_cap: '', source_words: '2100' })).toBe(false);
	expect(wasCut({ source_words: '2100' })).toBe(false);
	expect(wasCut({ version: '2026-08-01', truncation_flagged: 'False', source_words_before_cap: '4200', source_words: '1923' })).toBe(true);
	expect(wasCut({ version: '2026-09-01', truncation_flagged: 'True', source_words_before_cap: '2000', source_words: '2000' })).toBe(false);
});
