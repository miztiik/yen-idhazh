/** The current cut predicate retains measured absence and length semantics, not retired run attribution. */
import { expect, test } from '@playwright/test';
import { cutWords, wasCut } from '../src/lib/console/model/work';

test('a cut is measured length removed, not an absent length or a run identity', () => {
	expect(cutWords(5000, 2100)).toBe(2900);
	expect(cutWords(3000, 2100)).toBe(900);
	expect(cutWords(800, 800)).toBeNull();
	expect(cutWords(null, 2100)).toBeNull();
	expect(cutWords(4000, null)).toBeNull();
	expect(wasCut({ source_words_before_cap: '5000', source_words: '2100' })).toBe(true);
	expect(wasCut({ source_words_before_cap: '800', source_words: '800' })).toBe(false);
	expect(wasCut({ source_words_before_cap: '', source_words: '2100' })).toBe(false);
	expect(wasCut({ source_words: '2100' })).toBe(false);
});
