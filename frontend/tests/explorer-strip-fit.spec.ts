import { expect, test } from '@playwright/test';
import { chipsThatFit, type StripWidths } from '../src/lib/console/explorer/strip-fit';

/** Every width here is a literal the test chose; the function is asked how many chips fit. */
const EXAMPLES_ONLY: StripWidths = { savedLabel: 50, examplesLabel: 70, more: 80, gap: 8, chips: [100, 100, 100] };
const ONE_SAVED: StripWidths = { savedLabel: 50, examplesLabel: 70, more: 80, gap: 8, chips: [120, 100, 100] };

test('every chip shows when the line holds them all, with no fold', () => {
	// 70 + 3 x 100 + 3 gaps of 8 = 394
	expect(chipsThatFit(EXAMPLES_ONLY, 394, 0, 6)).toBe(3);
	expect(chipsThatFit(EXAMPLES_ONLY, 1000, 0, 6)).toBe(3);
});

test('a chip that does not fit folds, and the fold takes its own room on the line', () => {
	// Three chips need 394; two chips and the fold need 70 + 200 + 80 + 3 x 8 = 374.
	expect(chipsThatFit(EXAMPLES_ONLY, 393, 0, 6)).toBe(2);
	expect(chipsThatFit(EXAMPLES_ONLY, 374, 0, 6)).toBe(2);
	// One chip and the fold need 70 + 100 + 80 + 2 x 8 = 266.
	expect(chipsThatFit(EXAMPLES_ONLY, 373, 0, 6)).toBe(1);
	expect(chipsThatFit(EXAMPLES_ONLY, 266, 0, 6)).toBe(1);
	expect(chipsThatFit(EXAMPLES_ONLY, 265, 0, 6)).toBe(0);
});

test('the configured limit caps the line however much room it has', () => {
	expect(chipsThatFit(EXAMPLES_ONLY, 1000, 0, 2)).toBe(2);
	expect(chipsThatFit(EXAMPLES_ONLY, 1000, 0, 0)).toBe(0);
});

test('a saved question stands before the examples, under its own label', () => {
	// All three: 50 + 120 + 70 + 200 + 4 gaps = 472.
	expect(chipsThatFit(ONE_SAVED, 472, 1, 6)).toBe(3);
	// The saved chip and one example with the fold: 50 + 120 + 70 + 100 + 80 + 4 gaps = 452.
	expect(chipsThatFit(ONE_SAVED, 452, 1, 6)).toBe(2);
	// The saved chip alone with the fold: 50 + 120 + 80 + 2 gaps = 266.
	expect(chipsThatFit(ONE_SAVED, 451, 1, 6)).toBe(1);
	expect(chipsThatFit(ONE_SAVED, 266, 1, 6)).toBe(1);
});

test('saving a question never asks the line for more room than it has', () => {
	const before = chipsThatFit(EXAMPLES_ONLY, 400, 0, 6);
	const after = chipsThatFit(ONE_SAVED, 400, 1, 6);
	expect(before).toBe(3);
	// The saved chip takes the room of two examples, which fold.
	expect(after).toBe(1);
});
