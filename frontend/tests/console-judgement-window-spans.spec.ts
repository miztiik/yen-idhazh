/** Each Judgement state names the selected window and the recorded build line. */
import { expect, test, type Page } from './support/browser';

import { ONE_DAYS, spanSaid } from './support/span-said';

import { resolve } from 'node:path';

import { build } from 'esbuild';

import { windowOfDays } from '../src/lib/charts/viewport';

import { windowed } from './support/console-window/controls';
import { said } from './support/console-window/readout';
import { JUDGED_THROUGH, DRAWN_AT, FILLED, FILLING, judgeDay, lineDay, LINE_KNOBS, propsOf, appliedOn, SAID, type SpanCase } from './support/console-window/judgement-fixtures';

import { serverPanels } from './support/console-window/server-panels';

const SPAN_CASES: SpanCase[] = [
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'no pair was read twice',
		days: [],
		words: 'No pair was read twice in these 7 days, so there is nothing to compare.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'no pair was read twice in it, though some were the day before',
		days: [judgeDay('2030-06-14', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.05 })],
		words: 'No pair was read twice in this one day, so there is nothing to compare.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'three pairs were read twice, too few for a share',
		days: [
			judgeDay('2030-06-12', { pairsJudged: 2, pairsUsable: 2 }),
			judgeDay('2030-06-15', { pairsJudged: 1, pairsUsable: 1 })
		],
		words:
			'3 pairs were read twice in these 7 days. That is too few to report a share, so the counts are above.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'one pair was read twice',
		days: [judgeDay('2030-06-15', { pairsJudged: 1, pairsUsable: 1 })],
		words:
			'1 pair was read twice in these 7 days. That is too few to report a share, so the counts are above.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'three pairs were read twice, too few for a share',
		days: [judgeDay('2030-06-15', { pairsJudged: 3, pairsUsable: 3 })],
		words:
			'3 pairs were read twice in this one day. That is too few to report a share, so the counts are above.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'one pair was read twice',
		days: [judgeDay('2030-06-15', { pairsJudged: 1, pairsUsable: 1 })],
		words:
			'1 pair was read twice in this one day. That is too few to report a share, so the counts are above.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'two days were held because the judge was unreliable',
		days: [
			judgeDay('2030-06-13', {
				pairsJudged: 40,
				pairsUsable: 32,
				disagreementRate: 0.2,
				heldReason: 'judge_unstable'
			}),
			judgeDay('2030-06-15', {
				pairsJudged: 60,
				pairsUsable: 57,
				disagreementRate: 0.05,
				unclearRate: 23 / 57,
				heldReason: 'judge_uncertain'
			})
		],
		words:
			'The two readings disagreed on 11% of 100 pairs in these 7 days. No line was fitted on 2 of 7 days, because a rate was past its mark on those days.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'one day was held because the judge was unreliable',
		days: [
			judgeDay('2030-06-14', { pairsJudged: 50, pairsUsable: 48, disagreementRate: 0.04 }),
			judgeDay('2030-06-15', {
				pairsJudged: 50,
				pairsUsable: 35,
				disagreementRate: 0.3,
				heldReason: 'judge_unstable'
			})
		],
		words:
			'The two readings disagreed on 17% of 100 pairs in these 7 days. No line was fitted on 1 of 7 days, because a rate was past its mark on that day.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'its day was held because the judge was unreliable',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 40,
				pairsUsable: 30,
				disagreementRate: 0.25,
				heldReason: 'judge_unstable'
			})
		],
		words:
			'The two readings disagreed on 25% of 40 pairs in this one day. No line was fitted on 1 of 1 day, because a rate was past its mark on that day.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'both rates are inside the marks',
		days: [
			judgeDay('2030-06-10', {
				pairsJudged: 200,
				pairsUsable: 194,
				disagreementRate: 0.03,
				unclearRate: 2 / 194
			}),
			judgeDay('2030-06-15', {
				pairsJudged: 200,
				pairsUsable: 194,
				disagreementRate: 0.03,
				unclearRate: 2 / 194
			})
		],
		words:
			'In these 7 days, 3% of 400 pairs disagreed with their own second reading, and 1% of the 388 that agreed could not tell. Both rates are inside the marks.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'both rates are inside the marks',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 40,
				pairsUsable: 38,
				disagreementRate: 0.05,
				unclearRate: 4 / 38
			})
		],
		words:
			'In this one day, 5% of 40 pairs disagreed with their own second reading, and 11% of the 38 that agreed could not tell. Both rates are inside the marks.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'nothing was judged',
		days: [],
		words:
			'Nothing was judged in these 7 days. The three bars are what the record needs before a line may be fitted at all.'
	},
	{
		surface: 'record-gates',
		preset: 1,
		state: 'nothing was judged in it, though the record has a row the day before',
		days: [judgeDay('2030-06-14', FILLING)],
		words:
			'The bars show what the record held on 14 Jun 2030, before this one day. No run has recorded anything since.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'nothing was judged in them, though the record has a row before them',
		days: [judgeDay('2030-06-01', FILLING)],
		words:
			'The bars show what the record held on 1 Jun 2030, before these 7 days. No run has recorded anything since.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'the record is still filling and no line was fitted',
		days: [judgeDay('2030-06-12', { ...FILLING, negativesOnRecord: 100 }), judgeDay('2030-06-15', FILLING)],
		words:
			'The record has 120 readings, 6 days, and 12 pairs above the line; it needs at least 200 readings, 10 days, and 30 pairs above the line. No line was fitted in these 7 days.'
	},
	{
		surface: 'record-gates',
		preset: 1,
		state: 'the record is still filling and no line was fitted',
		days: [judgeDay('2030-06-15', FILLING)],
		words:
			'The record has 120 readings, 6 days, and 12 pairs above the line; it needs at least 200 readings, 10 days, and 30 pairs above the line. No line was fitted in this one day.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'the newest four days counted nothing and no line was fitted',
		days: [judgeDay('2030-06-11', { ...FILLED, heldReason: 'judge_unstable' })],
		words: 'Nothing has been counted for 4 days. No line was fitted in these 7 days.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'the newest day counted nothing and no line was fitted',
		days: [judgeDay('2030-06-14', { ...FILLED, heldReason: 'judge_uncertain' })],
		words: 'Nothing has been counted for 1 day. No line was fitted in these 7 days.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'the record has what it needs and every day was held',
		days: [
			judgeDay('2030-06-13', { ...FILLED, heldReason: 'judge_unstable' }),
			judgeDay('2030-06-15', { ...FILLED, heldReason: 'shards_missing' })
		],
		words:
			'The record has what it needs. These three bars stay so a record that empties is visible. No line was fitted in these 7 days.'
	},
	{
		surface: 'record-gates',
		preset: 1,
		state: 'the record has what it needs and its day was held',
		days: [judgeDay('2030-06-15', { ...FILLED, heldReason: 'judge_uncertain' })],
		words:
			'The record has what it needs. These three bars stay so a record that empties is visible. No line was fitted in this one day.'
	},
	{
		// The other side of the same choice: a fitted day replaces the sentence
		// that says none was, rather than standing beside it.
		surface: 'record-gates',
		preset: 7,
		state: 'a line was fitted on one day',
		days: [
			judgeDay('2030-06-14', FILLED),
			judgeDay('2030-06-15', { ...FILLED, heldReason: 'judge_unstable' })
		],
		words:
			'The record has what it needs. These three bars stay so a record that empties is visible. A line was fitted on 1 of 7 days.'
	},
	{
		surface: 'merge-line',
		preset: 7,
		state: 'no line was ever fitted',
		days: [],
		words:
			'No line was fitted in these 7 days. The rule is the line the newest day was built with, and the scale is the whole range a fitted line may take.',
		label: 'The line the newest day was built with'
	},
	{
		surface: 'merge-line',
		preset: 1,
		state: 'no line was fitted in it, though one was the day before',
		days: [lineDay('2030-06-14')],
		words:
			'No line was fitted in this one day. The rule is the line this one day was built with, and the scale is the whole range a fitted line may take.',
		label: 'The line this one day was built with'
	}
];
test.describe("the Judgement panels name their span in every state, on days the test builds", () => {

const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "JudgeAgreement-RecordGates-MergeLinePlot", String(testInfo.workerIndex)), ["JudgeAgreement","RecordGates","MergeLinePlot"]);
  Object.assign(drawn, panels.drawn);
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

for (const one of SPAN_CASES) {
	test(`THE ORACLE: ${one.surface} names the ${one.preset}-day window when ${one.state}`, async ({
		page
	}) => {
		await page.setContent(`<main>${drawn[one.surface](propsOf(one))}</main>`);

		const [surface] = await windowed(page);
		expect(surface.name, 'the case drew a different panel').toBe(one.surface);
		expect(surface.days, `${one.surface} is drawing a different window`).toBe(one.preset);
		expect(surface.says, `${one.surface} never says how many days it is showing`).toMatch(
			spanSaid(one.preset)
		);
		expect(surface.says, `${one.surface} says "1 days"`).not.toMatch(ONE_DAYS);
		expect(await said(page, SAID[one.surface])).toBe(one.words);
		if (one.surface === 'merge-line') {
			expect(await said(page, '[data-line-rule-label]')).toBe(one.label);
		}
	});
}

test('THE ORACLE: merge-line draws its rule at the line the newest day was built with, never at one it works out from the rows', async ({
	page
}) => {
	// The rows, the switch and the lookback say a build on 15 Jun would have
	// grouped at 0.937, the line a fit applied 3 days before. The day was
	// built with 0.940, and that is the line the panel is handed.
	const props = {
		days: [appliedOn('2030-06-12', 0.937)],
		knobs: { ...LINE_KNOBS, enabled: true },
		builtWith: 0.94,
		markedApart: null,
		viewport: windowOfDays(JUDGED_THROUGH, 1, 'right'),
		...DRAWN_AT
	};
	await page.setContent(`<main>${drawn['merge-line'](props)}</main>`);

	await expect(page.locator('[data-line-rule]')).toHaveAttribute('data-line-rule', '0.940');
	expect(await said(page, '[data-line-rule-label]')).toBe('The line this one day was built with');
	expect(await said(page, '[data-line-state]')).toBe(
		'No line was fitted in this one day. The rule is the line this one day was built with, and the scale is the whole range a fitted line may take.'
	);
});
});
