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
import { FLEET_HINT, fleetHintOne } from '../src/lib/charts/fleet';
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
	neverSeenNote,
	reasonDays,
	reasonHeadline as reasonHeadlineWithFormat,
	reasonsLabel,
	unexplainedNote as unexplainedNoteWithFormat
} from '../src/lib/console/doubt-reasons';
import { EVAL_PANELS, matchLabel, matchPoints, matchTitle, type EvalDay } from '../src/lib/console/eval-instruments';
import {
	clampNote,
	heldNote,
	mergeNote as mergeNoteWithFormat,
	mergeRate as mergeRateWithFormat,
	mergeTotals,
	type LineDay
} from '../src/lib/console/merge-line';
import { quietSentence } from '../src/lib/console/waiting';
import { matchHeadline, numberFormat } from './support/number-format';

const coverageSentence = (found: Parameters<typeof coverageSentenceWithFormat>[0], lead: string) =>
	coverageSentenceWithFormat(found, lead, numberFormat);
const horizonRate = (rate: number, days: number) => horizonRateWithFormat(rate, days, numberFormat);
const reasonHeadline = (days: Parameters<typeof reasonHeadlineWithFormat>[0], span: number) =>
	reasonHeadlineWithFormat(days, span, numberFormat);
const unexplainedNote = (days: Parameters<typeof unexplainedNoteWithFormat>[0], span: number) =>
	unexplainedNoteWithFormat(days, span, numberFormat);
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

/** One day of faithfulness scores: half its summaries above 82, a quarter under 70. */
function evalDay(date: string): EvalDay {
	return {
		date,
		scored: 412,
		matched: 412,
		matchLow: 70,
		matchMid: 82,
		matchHigh: 91,
		widerDiffers: 0,
		widestGap: 0,
		recorded: {},
		fired: {}
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

test('one-day titles name one day, while seven-day words stay unchanged', () => {
	expect(matchTitle(1)).toBe('Summary faithfulness for this one day');
	expect(matchTitle(7)).toBe('Summary faithfulness, day by day');
	expect(EVAL_PANELS.find((panel) => panel.id === 'faithfulness')?.title).toBe(matchTitle(7));
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

test('the doubt-reasons chart describes its one column at one day', () => {
	expect(reasonsLabel(1)).toBe(
		"Why summaries were doubted in this one day. The column's height is the summaries the checker wrote a reason on, and the bands are the five reasons it can give. Drawn as lines instead, each reason is its own count and the total is not shown."
	);
	expect(reasonsLabel(7)).toBe(
		'Why summaries were doubted, per day, over 7 days. One column is one day, its height is the summaries the checker wrote a reason on, and the bands are the five reasons it can give. Drawn as lines instead, each reason is its own count a day and the total is not shown.'
	);
});

test('the faithfulness plot names its two points at one day, and its lines over seven', () => {
	const lower = 'the other is the summary a quarter of the way up from the bottom.';
	expect(matchLabel(1, [])).toBe(
		`Summary faithfulness in this one day, as a percentage. One point is the day's middle summary and ${lower}`
	);
	expect(matchLabel(7, [70, 82])).toBe(
		`Summary faithfulness per day over 7 days, as a percentage. One line is each day's middle summary and ${lower} A line crosses the plot at 70 and 82 percent, the scores a published story is banded on.`
	);
	expect(matchPoints(1)).toBe('Both points are this one day.');
	expect(matchPoints(7)).toBe('One point is one day over these 7 days.');
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

test("the machines' strip says what one column still offers: the day's jobs", () => {
	expect(fleetHintOne(1)).toBe("Click or Enter lists this one day's jobs.");
	expect(fleetHintOne(7)).toBe("Click or Enter lists the day's jobs.");
	expect(FLEET_HINT).toBe(
		"Point at a day to read every kind on it. Left and Right step through them, Escape returns to the newest. Click or Enter lists that day's jobs."
	);
});

test('the doubt sentences name the days they counted', () => {
	const doubted = reasonDays([
		{
			date: '2026-10-06',
			items: [
				{ band: 'medium', reason: 'faithfulness' },
				{ band: 'low', reason: 'faithfulness' }
			]
		}
	]);
	expect(reasonHeadline(doubted, 1)).toBe(
		'The reason given most often is "Does not match the article": 2 summaries in this one day.'
	);
	expect(reasonHeadline(doubted, 7)).toBe(
		'The reason given most often is "Does not match the article": 2 summaries in these 7 days.'
	);

	const unexplained = reasonDays([
		{
			date: '2026-10-06',
			items: [
				{ band: 'medium', reason: 'faithfulness' },
				{ band: 'medium', reason: null }
			]
		}
	]);
	expect(unexplainedNote(unexplained, 1)).toBe(
		'1 of the 2 doubted summaries in this one day have no reason written down, on 1 day. Those columns are short by that much: the reason is missing from our record, not from the summary.'
	);

	const clean = reasonDays([{ date: '2026-10-06', items: [{ band: 'high', reason: null }] }]);
	const five =
		'"Numbers not in the article", "Does not match the article", "Never checked", "Left out the opening facts" and ""Maybe" told as fact" are reasons the checker can give and did not give once in';
	expect(neverSeenNote(clean, 1)).toBe(`${five} this one day, so they have no line on the chart.`);
	expect(neverSeenNote(clean, 7)).toBe(`${five} these 7 days, so they have no line on the chart.`);
});

test('the faithfulness headline names the one day, since one day has no middle day', () => {
	const days = [evalDay('2026-10-06')];
	expect(matchHeadline(days, 1)).toBe(
		'This one day put half its summaries above 82 percent, and a quarter of them under 70 percent, on 412 summaries checked.'
	);
	expect(matchHeadline(days, 7)).toBe(
		'Over these 7 days the middle day put half its summaries above 82 percent, and a quarter of them under 70 percent, on 412 summaries checked.'
	);
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
