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
import { costLabel, costShapeOptions } from '../src/lib/charts/cost';
import { extractionLabel } from '../src/lib/charts/extraction-trend';
import { FLEET_HINT, fleetHintOne } from '../src/lib/charts/fleet';
import { coverage, coverageSentence, noModelRuleNote } from '../src/lib/charts/frame';
import {
	chartRule,
	horizonRate,
	publishedSkyline,
	ruleTrendLabel,
	siteCostLabel,
	siteCostMeasure,
	skylineLabel,
	type GlanceDay
} from '../src/lib/charts/glance';
import { dailyFiguresPointer, dailyFiguresRows, dailyFiguresSummary } from '../src/lib/console/daily-figures';
import {
	neverSeenNote,
	reasonDays,
	reasonHeadline,
	reasonsLabel,
	unexplainedNote
} from '../src/lib/console/doubt-reasons';
import { EVAL_PANELS, matchHeadline, matchLabel, matchPoints, matchTitle, type EvalDay } from '../src/lib/console/eval-instruments';
import {
	clampNote,
	heldNote,
	mergeNote,
	mergeRate,
	mergeTotals,
	type LineDay
} from '../src/lib/console/merge-line';
import { quietSentence } from '../src/lib/console/waiting';

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

test('the counterfactual cost chart names the days it prices', () => {
	// A column a day and a total added day by day both need a second day, so one
	// day is one column, or its total.
	const owed = "What the work would have cost at a hosted provider's rate, never an amount owed.";
	expect(costLabel('daily', 1)).toBe(
		`The counterfactual cost of this one day, one column, reading at the bottom and writing on top. ${owed}`
	);
	expect(costLabel('daily', 7)).toBe(
		`The counterfactual cost of these 7 days, one column a day, reading at the bottom and writing on top. ${owed}`
	);
	expect(costLabel('running', 1)).toBe(`The counterfactual cost of this one day, in total. ${owed}`);
	expect(costLabel('running', 7)).toBe(
		`The counterfactual cost of these 7 days, added up day by day. ${owed}`
	);
});

test('THE ORACLE: one-day titles and cost choices name one day, while seven-day words stay unchanged', () => {
	expect(matchTitle(1)).toBe('Summary faithfulness for this one day');
	expect(matchTitle(7)).toBe('Summary faithfulness, day by day');
	expect(EVAL_PANELS.find((panel) => panel.id === 'faithfulness')?.title).toBe(matchTitle(7));
	expect(costShapeOptions(1)).toEqual([
		{ value: 'daily', text: 'This one day' },
		{ value: 'running', text: 'Running total' }
	]);
	expect(costShapeOptions(7)).toEqual([
		{ value: 'daily', text: 'Day by day' },
		{ value: 'running', text: 'Running total' }
	]);
});

test('the chart-drawing verdict names the one day, since one day has no median day', () => {
	const thresholds = { ruleDays: 1, minutesTarget: 6, coveragePct: 50 };
	const day: GlanceDay = { date: '2026-10-06', published: 4, items: 10, minutesPerChart: 4.2 };
	expect(chartRule([day], thresholds, 1).verdict).toBe(
		'This one day spends 4.2 minutes per visual, inside the 6 that retires chart drawing, and puts a visual on 40% of what it published, below the 50% floor.'
	);
	expect(chartRule([day], thresholds, 7).verdict).toBe(
		'The median day spends 4.2 minutes per visual, inside the 6 that retires chart drawing, and puts a visual on 40% of what it published, below the 50% floor.'
	);

	// Nothing published: one day did not, and no day of seven did.
	const quiet: GlanceDay = { date: '2026-10-06', published: 0, items: 0, minutesPerChart: null };
	expect(chartRule([quiet], thresholds, 1).verdict).toBe(
		'This one day has no minutes on record, and did not publish anything to put a visual on.'
	);
	expect(chartRule([quiet], thresholds, 7).verdict).toBe(
		'The median day has no minutes on record over these 7 days, and no day published anything to put a visual on.'
	);
});

/** One day of the chart-drawing record: articles published, visuals on some. */
function glanceDay(date: string, items: number, published = 0): GlanceDay {
	return { date, published, items, minutesPerChart: null };
}

test('a card skyline gives one day its count, and seven days their total and busiest day', () => {
	const oneDay = { start: '2026-10-06', end: '2026-10-06' };
	const days = [glanceDay('2026-10-06', 300, 4)];
	expect(skylineLabel('Articles published', publishedSkyline(days, oneDay, 'items'), 1)).toBe(
		'Articles published in this one day, 300'
	);
	expect(skylineLabel('Visuals published', publishedSkyline(days, oneDay, 'published'), 1)).toBe(
		'Visuals published in this one day, 4'
	);

	const sevenDays = { start: '2026-09-30', end: '2026-10-06' };
	const week = [glanceDay('2026-10-01', 1200), glanceDay('2026-10-06', 300)];
	expect(skylineLabel('Articles published', publishedSkyline(week, sevenDays, 'items'), 7)).toBe(
		'Articles published each day over 7 days, 1,500 over the window, 1,200 on the busiest day'
	);
});

test('a trend of the chart-drawing rule counts its measured days, and one is not day by day', () => {
	expect(ruleTrendLabel('Minutes per visual', 1)).toBe('Minutes per visual, over 1 measured day');
	expect(ruleTrendLabel('Share of published articles carrying a visual', 1)).toBe(
		'Share of published articles carrying a visual, over 1 measured day'
	);
	expect(ruleTrendLabel('Minutes per visual', 9)).toBe(
		'Minutes per visual, day by day, over 9 measured days'
	);
});

test('the extraction trend has one point for one day, and one a day over seven', () => {
	const lead =
		'Articles the reading found enough figures of one kind in, against published articles carrying a chart';
	expect(extractionLabel(1)).toBe(`${lead}, one point for this one day`);
	expect(extractionLabel(7)).toBe(`${lead}, one point a day over 7 days`);
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

test('the per-article cost names one day, and over seven each published day and its spread', () => {
	expect(siteCostLabel(1)).toBe('Payload bytes per article in this one day');
	expect(siteCostLabel(7)).toBe(
		'Payload bytes per article on each published day, over 7 days, against the median and one standard deviation either side of it'
	);
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
