/** Judgement charts name one day without claiming a second. */
import { expect, test, type Page } from './support/browser';

import { resolve } from 'node:path';

import { build } from 'esbuild';

import { daysInWindow, windowOfDays } from '../src/lib/charts/viewport';

import type { JudgeDay } from '../src/lib/console/merge-line';

import { windowed } from './support/console-window/controls';
import { DEFAULT_KEYS, labelOf, stripOf, said } from './support/console-window/readout';
import { JUDGED_THROUGH, GATES, LIMITS, SHARE_FLOOR, DRAWN_AT, FILLING, judgeDay, lineDay, LINE_KNOBS, propsOf } from './support/console-window/judgement-fixtures';

import { serverPanels } from './support/console-window/server-panels';

test.describe("at one day no sentence needs a second day, on days the test builds", () => {

const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "MergedStoriesPanel-JudgeAgreement-MergeLinePlot-RecordGates", String(testInfo.workerIndex)), [['src/routes/console/judgement/MergedStoriesPanel.svelte', 'MergedStoriesPanel'], ['src/routes/console/judgement/JudgeAgreement.svelte', 'JudgeAgreement'], ['src/routes/console/judgement/MergeLinePlot.svelte', 'MergeLinePlot'], ['src/routes/console/judgement/RecordGates.svelte', 'RecordGates']]);
  Object.assign(drawn, panels.drawn);
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

function mergeProps(preset: number, dates: readonly string[]): Record<string, unknown> {
	return {
		days: dates.map((date) => ({ date, published: 10, merges: 2, groups: 1, largest: 3 })),
		viewport: windowOfDays(JUDGED_THROUGH, preset, 'right'),
		height: DRAWN_AT.height,
		width: DRAWN_AT.width,
		tickDensity: DRAWN_AT.tickDensity,
		readoutMaxShare: DRAWN_AT.readoutMaxShare
	};
}

test('THE ORACLE: the merged stories chart is of this one day, and its strip heads the day alone', async ({
	page
}) => {
	await draw(page, 'MergedStoriesPanel', mergeProps(1, [JUDGED_THROUGH]));
	expect(await labelOf(page, '[data-windowed="merged-stories"] svg[aria-label]')).toBe(
		'Stories folded into another in this one day'
	);
	expect(await stripOf(page, 'merged-stories')).toEqual({ heading: '15 Jun', hint: null });
});

test('the merged stories chart is a day over seven days, and its strip rests on the newest', async ({
	page
}) => {
	await draw(page, 'MergedStoriesPanel', mergeProps(7, ['2030-06-10', JUDGED_THROUGH]));
	expect(await labelOf(page, '[data-windowed="merged-stories"] svg[aria-label]')).toBe(
		'Stories folded into another a day, over 7 days'
	);
	expect(await stripOf(page, 'merged-stories')).toEqual({
		heading: '15 Jun, the newest published day',
		hint: DEFAULT_KEYS
	});
});

/** The judge panel's props around the days a case builds, at one window. */
function judgeProps(preset: number, days: JudgeDay[]): Record<string, unknown> {
	return {
		days,
		limits: LIMITS,
		attemptsFloor: SHARE_FLOOR,
		viewport: windowOfDays(JUDGED_THROUGH, preset, 'right'),
		...DRAWN_AT
	};
}

test('THE ORACLE: the judge chart is of this one day, and its strip heads the day alone', async ({
	page
}) => {
	await draw(
		page,
		'JudgeAgreement',
		judgeProps(1, [
			judgeDay(JUDGED_THROUGH, { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.05 })
		])
	);
	expect(await labelOf(page, '[data-windowed="judge-agreement"] svg[aria-label]')).toBe(
		'How often the judge disagreed with its own second reading, in this one day'
	);
	expect(await stripOf(page, 'judge-agreement')).toEqual({ heading: '15 Jun', hint: null });
});

test('the judge chart is a day over seven days, and its strip rests on the newest', async ({ page }) => {
	await draw(
		page,
		'JudgeAgreement',
		judgeProps(7, [
			judgeDay('2030-06-10', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.05 }),
			judgeDay(JUDGED_THROUGH, { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.05 })
		])
	);
	expect(await labelOf(page, '[data-windowed="judge-agreement"] svg[aria-label]')).toBe(
		'How often the judge disagreed with its own second reading, a day'
	);
	expect(await stripOf(page, 'judge-agreement')).toEqual({
		heading: '15 Jun, the newest day with numbers',
		hint: DEFAULT_KEYS
	});
});

/** The merge line's props around the fitted days a case builds, at one window. */
function lineProps(preset: number, dates: readonly string[]): Record<string, unknown> {
	return {
		days: dates.map(lineDay),
		knobs: LINE_KNOBS,
		builtWith: 0.94,
		markedApart: null,
		viewport: windowOfDays(JUDGED_THROUGH, preset, 'right'),
		...DRAWN_AT
	};
}

const LINE_NOTE =
	"The solid line is the nightly calculation's final score for grouping two stories as one, after limits on its change. The dotted line is the proposed score before those limits. The shaded band shows how far the calculated line was allowed to fall each day. A build may have used a different line.";
const ONE_LINE_NOTE =
	"The applied reading is the nightly calculation's final score for grouping two stories as one, after limits on its change. The proposed reading is the score before those limits. The shaded band shows how far the calculated line was allowed to fall that day. A build may have used a different line.";

test('THE ORACLE: the merge line is for this one day, its band is that day, and its strip heads the day alone', async ({
	page
}) => {
	await draw(page, 'MergeLinePlot', lineProps(1, [JUDGED_THROUGH]));
	expect(await labelOf(page, '[data-windowed="merge-line"] svg[aria-label]')).toBe(
		'Nightly calculated merge readings for this one day, on the full allowed score range. A build may have used a different line.'
	);
	expect(await said(page, '[data-console-panel="Where the merge line sits"] .panel-note')).toBe(
		ONE_LINE_NOTE
	);
	expect(await stripOf(page, 'merge-line')).toEqual({ heading: '15 Jun', hint: null });
});

test('THE ORACLE: the merge note names a reading inside the tinted strip at one day, without changing seven-day words', async ({ page }) => {
	for (const preset of [1, 7]) {
		await draw(page, 'MergeLinePlot', {
			...lineProps(preset, [JUDGED_THROUGH]),
			markedApart: { low: 0.94, high: 0.95, count: 3 }
		});
		expect(await said(page, '[data-console-panel="Where the merge line sits"] .panel-note')).toBe(
			(preset === 1 ? ONE_LINE_NOTE : LINE_NOTE) +
			(preset === 1
				? ' The tinted strip shows the part of the score range inside this plot for 3 pairs a person marked as two stories. Their scores run from 0.9400 to 0.9500. If used to group stories, an applied reading inside this strip would clear the score threshold for at least one of those pairs. This does not show that a build grouped them.'
				: ' The tinted strip shows the part of the score range inside this plot for 3 pairs a person marked as two stories. Their scores run from 0.9400 to 0.9500. If used to group stories, a calculated line inside this strip would clear the score threshold for at least one of those pairs. This does not show that a build grouped them.')
		);
	}
});

test('the merge line is a day over seven days, with a band at each day', async ({ page }) => {
	await draw(page, 'MergeLinePlot', lineProps(7, ['2030-06-10', JUDGED_THROUGH]));
	expect(await labelOf(page, '[data-windowed="merge-line"] svg[aria-label]')).toBe(
		'Nightly calculated merge lines, on the full allowed score range. Builds may have used different lines.'
	);
	expect(await said(page, '[data-console-panel="Where the merge line sits"] .panel-note')).toBe(
		LINE_NOTE
	);
	expect(await stripOf(page, 'merge-line')).toEqual({
		heading: '15 Jun, the newest recorded day shown',
		hint: DEFAULT_KEYS
	});
});

test('THE ORACLE L45: a held row and six unrecorded days imply no fit', async ({ page }) => {
	await draw(page, 'MergeLinePlot', {
		...lineProps(7, []),
		days: [{ ...lineDay('2030-06-14'), proposed: null, heldReason: 'sheet_too_small' }]
	});
	expect(await said(page, '[data-line-held-note]')).toBe(
		'Nothing was fitted on 1 recorded day in this 7-day window.'
	);
	await draw(page, 'RecordGates', propsOf({
		surface: 'record-gates', preset: 7, state: 'one held row and six silent days',
		days: [judgeDay('2030-06-14', FILLING)], words: ''
	}));
	expect(await said(page, '[data-counted-fitted]')).toBe('No line was fitted in these 7 days.');
	await expect(page.locator('[data-counted-state="silent"]')).toHaveCount(6);
});

test('THE ORACLE L45: filling counts may exceed their requirements without becoming shares', async ({ page }) => {
	for (const [counts, words] of [
		[{ ...FILLING, aboveLineOnRecord: 49 },
			'The record has 120 readings, 6 days, and 49 pairs above the line; it needs at least 200 readings, 10 days, and 30 pairs above the line.'],
		[{ ...FILLING, negativesOnRecord: 1234, daysOnRecord: 14 },
			'The record has 1,234 readings, 14 days, and 12 pairs above the line; it needs at least 200 readings, 10 days, and 30 pairs above the line.'],
		[{ ...FILLING, daysOnRecord: 1 },
			'The record has 120 readings, 1 day, and 12 pairs above the line; it needs at least 200 readings, 10 days, and 30 pairs above the line.']
	] as const) {
		await draw(page, 'RecordGates', propsOf({
			surface: 'record-gates', preset: 7, state: 'counts fill independently',
			days: [judgeDay(JUDGED_THROUGH, counts)], words: ''
		}));
		expect(await said(page, '[data-gates-state="filling"]')).toBe(words);
	}
});

for (const preset of [14, 30]) {
	test(`THE ORACLE L45: the ${preset}-day strip names its newest recorded day, not the window end`, async ({ page }) => {
		for (const heldReason of ['none', 'sheet_too_small']) {
			await draw(page, 'MergeLinePlot', {
				...lineProps(preset, []),
				days: [
					lineDay('2030-06-12'),
					{ ...lineDay('2030-06-14'), heldReason, proposed: heldReason === 'none' ? 0.95 : null }
				]
			});
			expect(await said(page, '[data-readout="merge-line"] [data-readout-day]')).toBe(
				'14 Jun, the newest recorded day shown'
			);
			await expect(page.locator('[data-windowed="merge-line"]')).toHaveAttribute('data-window-days', String(preset));
		}
	});
}

function gatesProps(preset: number, days: JudgeDay[]): Record<string, unknown> {
	const viewport = windowOfDays(JUDGED_THROUGH, preset, 'right');
	return { days, dates: daysInWindow(viewport), gates: GATES, viewport, readoutMaxShare: 1 };
}

const GATES_LEAD = 'Three counts have to be reached before the line may move at all.';

test('THE ORACLE: the record has one square, for this one day, and its strip heads the day alone', async ({
	page
}) => {
	await draw(page, 'RecordGates', gatesProps(1, [judgeDay(JUDGED_THROUGH, FILLING)]));
	expect(await said(page, '[data-console-panel="What the record still needs"] .panel-note')).toBe(
		`${GATES_LEAD} The square is what the record did with this one day.`
	);
	expect(await labelOf(page, '[data-counted-strip]')).toBe('What the record did with this one day.');
	expect(await stripOf(page, 'record-gates')).toEqual({ heading: '15 Jun 2030', hint: null });
});

test('the record has a square a day over seven days, and its strip names its keys', async ({ page }) => {
	await draw(page, 'RecordGates', gatesProps(7, [judgeDay(JUDGED_THROUGH, FILLING)]));
	expect(await said(page, '[data-console-panel="What the record still needs"] .panel-note')).toBe(
		`${GATES_LEAD} The squares are one a day: what the record did with that day.`
	);
	expect(await labelOf(page, '[data-counted-strip]')).toBe(
		'What the record did with each day. Left and Right read a day, Escape returns to the newest.'
	);
	expect(await stripOf(page, 'record-gates')).toEqual({
		heading: '15 Jun 2030, the newest day',
		hint: 'Point at a square to read its day. Left and Right step through the days, Escape returns to the newest.'
	});
});
});
