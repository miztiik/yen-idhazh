/** What does each windowed sentence a console function writes say at one day, and at seven?
 *
 * Every sentence below names the days of its window, and each is called on inputs
 * this file builds, at one day and at seven, against whole sentences written out
 * here. The words are Reader's: the days on screen are "this one day" or "these 7
 * days", a count over the window is "1 of 1 day" or "2 of 7 days", and at one day
 * a sentence that would need a second day names the day itself. That holds for a
 * sentence that prints no day count as well: at one day it orders no days, ranges
 * over none, waits for none and says no "each day". No sentence here may say
 * "1 days".
 */

import { expect, test } from '@playwright/test';
import {
	coverage,
	coverageSentence as coverageSentenceWithFormat,
	noModelRuleNote
} from '../src/lib/charts/frame';
import {
	chartRule,
	horizonRate as horizonRateWithFormat,
	siteCostMeasure,
	type GlanceDay
} from '../src/lib/charts/glance';
import { dailyFiguresPointer, dailyFiguresRows, dailyFiguresSummary } from '../src/lib/console/daily-figures';
import {
	clampNote,
	heldNote,
	mergeNote as mergeNoteWithFormat,
	mergeRate as mergeRateWithFormat,
	mergeTotals,
	type LineDay
} from '../src/lib/console/merge-line';
import { quietSentence } from '../src/lib/console/waiting';
import { numberFormat } from './support/number-format';

const coverageSentence = (found: Parameters<typeof coverageSentenceWithFormat>[0], lead: string) =>
	coverageSentenceWithFormat(found, lead, numberFormat);
const horizonRate = (rate: number, days: number) => horizonRateWithFormat(rate, days, numberFormat);
const mergeNote = (totals: Parameters<typeof mergeNoteWithFormat>[0], span: number) =>
	mergeNoteWithFormat(totals, span, numberFormat);
const mergeRate = (totals: Parameters<typeof mergeRateWithFormat>[0], span: number) =>
	mergeRateWithFormat(totals, span, numberFormat);

/** One day of the merge line, the line held back by the daily cap or not. */
function lineDay(date: string, over: Partial<LineDay> = {}): LineDay {
	return {
		date,
		previous: 0.94,
		proposed: 0.95,
		applied: 0.943,
		clampKind: 'none',
		heldReason: 'none',
		maxDownStep: 0.01,
		maxUpStep: 0.003,
		...over
	};
}

test('a quiet panel says the days it read held nothing', () => {
	expect(quietSentence(1, null)).toBe(
		'Nothing was recorded in this one day. No wider window reaches a day that has anything.'
	);
	expect(quietSentence(7, 14)).toBe(
		'Nothing was recorded in these 7 days. The 14-day window reaches back to months that do.'
	);
});

test('a chart that drew no model change says so over its own days', () => {
	expect(noModelRuleNote(1)).toBe('Nothing changed about how the summaries are written inside this one day.');
	expect(noModelRuleNote(7)).toBe('Nothing changed about how the summaries are written inside these 7 days.');
});

test('a sparse chart counts its measured days over the days it drew', () => {
	// One measured column of seven is under half, so the chart names the gap.
	expect(coverageSentence(coverage([true, false, false, false, false, false, false]), 'We timed')).toBe(
		'We timed 1 of 7 days. The tinted span is days nothing recorded, not quiet days.'
	);
	// One day measured in full is never sparse, so no sentence is printed.
	expect(coverageSentence(coverage([true]), 'We timed')).toBeNull();
});

test('the chart-drawing verdict names the one day, since one day has no median day', () => {
	const thresholds = { ruleDays: 1, minutesTarget: 6, coveragePct: 50 };
	const day: GlanceDay = { date: '2026-10-06', published: 4, items: 10, minutesPerChart: 4.2 };
	expect(chartRule([day], thresholds, 1, numberFormat).verdict).toBe(
		'This one day spends 4.2 minutes per visual, inside the 6 that retires chart drawing, and puts a visual on 40% of what it published, below the 50% floor.'
	);
	expect(chartRule([day], thresholds, 7, numberFormat).verdict).toBe(
		'The median day spends 4.2 minutes per visual, inside the 6 that retires chart drawing, and puts a visual on 40% of what it published, below the 50% floor.'
	);

	// Nothing published: one day did not, and no day of seven did.
	const quiet: GlanceDay = { date: '2026-10-06', published: 0, items: 0, minutesPerChart: null };
	expect(chartRule([quiet], thresholds, 1, numberFormat).verdict).toBe(
		'This one day has no minutes on record, and did not publish anything to put a visual on.'
	);
	expect(chartRule([quiet], thresholds, 7, numberFormat).verdict).toBe(
		'The median day has no minutes on record over these 7 days, and no day published anything to put a visual on.'
	);
});

test('a table of daily figures opens on one day, and on seven day by day, newest first', () => {
	expect(dailyFiguresSummary(1)).toBe('Show these figures for this one day');
	expect(dailyFiguresSummary(7)).toBe('Show these figures day by day, over these 7 days');
	expect(dailyFiguresRows(1)).toBe('One row for this one day.');
	expect(dailyFiguresRows(7)).toBe('One row per day in the open window, newest first.');
	expect(dailyFiguresPointer(1)).toBe(
		`Open "Show these figures for this one day" below for each stage's count.`
	);
	expect(dailyFiguresPointer(7)).toBe(
		`Open "Show these figures day by day" below for each stage's count on every day.`
	);
});

test('the per-article measurement names the published articles and payload days it counts', () => {
	expect(siteCostMeasure(1)).toBe(
		'Bytes the committed payload tree gained in this one day, over the articles the day published.'
	);
	expect(siteCostMeasure(7)).toBe(
		'Bytes the committed payload tree gained on each published day, over the articles that day published. Over 7 days.'
	);
	// The rate stays a rate at one day; it is that day's own count.
	expect(horizonRate(300, 1)).toBe("300 articles a published day, this one day's count");
	expect(horizonRate(334.4, 7)).toBe('a median of 334 articles a published day');
});

test('the merge sentences name the days they counted', () => {
	const quiet = mergeTotals([{ date: '2026-10-06', published: 10, merges: 0, groups: 0, largest: 0 }]);
	expect(mergeNote(quiet, 1)).toBe('No story in this one day was grouped with another. Every one ran on its own.');
	expect(mergeNote(quiet, 7)).toBe('No story in these 7 days was grouped with another. Every one ran on its own.');

	const folded = mergeTotals([{ date: '2026-10-06', published: 10, merges: 1, groups: 1, largest: 2 }]);
	expect(mergeRate(folded, 1)).toBe('That is 10% of the 10 stories this one day published.');
	expect(mergeRate(folded, 7)).toBe('That is 10% of the 10 stories these 7 days published.');
});

test('the clamp and fitting sentences count over the days on screen', () => {
	const calm = [lineDay('2026-10-06')];
	expect(clampNote(calm, 1)).toBe('The clamp has not held the line back in this one day.');
	expect(clampNote(calm, 7)).toBe('The clamp has not held the line back in these 7 days.');

	const held = [lineDay('2026-10-06', { clampKind: 'daily_up' })];
	expect(clampNote(held, 1)).toBe('The clamp held the line back on 1 of 1 day.');
	expect(clampNote([...held, lineDay('2026-10-05', { clampKind: 'guard' })], 7)).toBe(
		'The clamp held the line back on 2 of 7 days.'
	);

	const unfitted = [lineDay('2026-10-06', { heldReason: 'sheet_too_small', proposed: null })];
	expect(heldNote(unfitted, 1)).toBe('Nothing was fitted on 1 recorded day in this 1-day window.');
	expect(heldNote(unfitted, 7)).toBe('Nothing was fitted on 1 recorded day in this 7-day window.');
});
