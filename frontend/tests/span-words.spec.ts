/** What words does the console's one helper give a window of one day and of seven? */

import { expect, test } from '@playwright/test';
import { countDays, nameSpan, openWithSpan } from '../src/lib/console/span-words';

test('the days on screen are "this one day" at one day and "these 7 days" at seven', () => {
	expect(nameSpan(1)).toBe('this one day');
	expect(nameSpan(7)).toBe('these 7 days');
	expect(nameSpan(90)).toBe('these 90 days');
});

test('a sentence or a row label opens on the same words, capitalised', () => {
	expect(openWithSpan(1)).toBe('This one day');
	expect(openWithSpan(7)).toBe('These 7 days');
});

test('a bare count is "1 day" at one day and "7 days" at seven, as the days control says', () => {
	expect(countDays(1)).toBe('1 day');
	expect(countDays(7)).toBe('7 days');
});

test('a count of some of the days says which, and still says "1 day" at one', () => {
	expect(countDays(1, 'measured')).toBe('1 measured day');
	expect(countDays(9, 'measured')).toBe('9 measured days');
});
