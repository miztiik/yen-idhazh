/** Each judge day keeps its counts, rate floor, and exact readout. */
import { expect, test, type Page } from './support/browser';

import { resolve } from 'node:path';

import type { JudgeDay } from '../src/lib/console/merge-line';

import { said } from './support/console-window/readout';
import { judgeDay, propsOf, SAID } from './support/console-window/judgement-fixtures';

import { serverPanels } from './support/console-window/server-panels';

const STRIP_CASES: {
	preset: number;
	state: string;
	days: JudgeDay[];
	/** The two marks, where a case moves them. */
	limits?: { disagreementMax: number; unclearMax: number };
	heading: string;
	entries: string[];
	dots: Record<string, string>;
	words: string;
}[] = [
	{
		preset: 7,
		state: 'a share just above its mark must not print as the mark itself',
		days: [
			judgeDay('2030-06-15', { pairsJudged: 46, pairsUsable: 39, disagreementRate: 7 / 46 })
		],
		heading: '15 Jun, the newest day with numbers',
		entries: [
			'Disagreed with the second reading just above 15% of 46 pairs',
			'Could not tell 0% of the 39 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: just above 15% of 46 pairs disagreed with the second reading, and 0% of the 39 that agreed could not tell.'
		},
		words:
			'In these 7 days, just above 15% of 46 pairs disagreed with their own second reading, and 0% of the 39 that agreed could not tell. The share that disagreed is just above its 15% mark.'
	},
	{
		preset: 7,
		state: 'a held day prints a share just above its mark without rounding it onto the mark',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 46,
				pairsUsable: 39,
				disagreementRate: 7 / 46,
				heldReason: 'judge_unstable'
			})
		],
		heading: '15 Jun, the newest day with numbers',
		entries: [
			'Disagreed with the second reading just above 15% of 46 pairs',
			'Could not tell 0% of the 39 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: just above 15% of 46 pairs disagreed with the second reading, and 0% of the 39 that agreed could not tell.'
		},
		words:
			'The two readings disagreed on just above 15% of 46 pairs in these 7 days. No line was fitted on 1 of 7 days, because a rate was past its mark on that day.'
	},
	{
		preset: 1,
		state: 'agreement counts of a thousand or more print with separators',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 1390,
				pairsUsable: 1118,
				disagreementRate: 272 / 1390,
				unclearRate: 56 / 1118
			})
		],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 20% of 1,390 pairs',
			'Could not tell 5% of the 1,118 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 20% of 1,390 pairs disagreed with the second reading, and 5% of the 1,118 that agreed could not tell.'
		},
		words:
			'In this one day, 20% of 1,390 pairs disagreed with their own second reading, and 5% of the 1,118 that agreed could not tell. The 20% that disagreed is past its mark.'
	},
	{
		preset: 1,
		state: 'could not tell just above its own mark keeps the agreed denominator',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 40,
				pairsUsable: 37,
				disagreementRate: 3 / 40,
				unclearRate: 13 / 37
			})
		],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 8% of 40 pairs',
			'Could not tell just above 35% of the 37 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 8% of 40 pairs disagreed with the second reading, and just above 35% of the 37 that agreed could not tell.'
		},
		words:
			'In this one day, 8% of 40 pairs disagreed with their own second reading, and just above 35% of the 37 that agreed could not tell. The share that could not tell is just above its 35% mark.'
	},
	{
		preset: 1,
		state: 'its day read 4 pairs, too few for a share',
		days: [judgeDay('2030-06-15', { pairsJudged: 4, pairsUsable: 3, disagreementRate: 0.25 })],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 1 of 4 pairs',
			'Could not tell 0 of the 3 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 1 of 4 pairs disagreed with the second reading, and 0 of the 3 that agreed could not tell.'
		},
		words:
			'4 pairs were read twice in this one day. That is too few to report a share, so the counts are above.'
	},
	{
		preset: 1,
		state: 'its day read 5 pairs, enough for a share',
		days: [judgeDay('2030-06-15', { pairsJudged: 5, pairsUsable: 5, unclearRate: 0.2 })],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 0% of 5 pairs',
			'Could not tell 20% of the 5 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 0% of 5 pairs disagreed with the second reading, and 20% of the 5 that agreed could not tell.'
		},
		words:
			'In this one day, 0% of 5 pairs disagreed with their own second reading, and 20% of the 5 that agreed could not tell. Both rates are inside the marks.'
	},
	{
		preset: 1,
		state: "its one pair's two readings disagreed, so no pair agreed",
		days: [judgeDay('2030-06-15', { pairsJudged: 1, pairsUsable: 0, disagreementRate: 1 })],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 1 of 1 pair',
			'Could not tell not counted, no pair agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 1 of 1 pair disagreed with the second reading. Could not tell: not counted, no pair agreed.'
		},
		words:
			'1 pair was read twice in this one day. That is too few to report a share, so the counts are above.'
	},
	{
		preset: 1,
		state: 'its day read 4 pairs, and 1 of the 2 that agreed could not tell',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 4,
				pairsUsable: 2,
				disagreementRate: 0.5,
				unclearRate: 0.5
			})
		],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 2 of 4 pairs',
			'Could not tell 1 of the 2 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 2 of 4 pairs disagreed with the second reading, and 1 of the 2 that agreed could not tell.'
		},
		words:
			'4 pairs were read twice in this one day. That is too few to report a share, so the counts are above.'
	},
	{
		preset: 7,
		state: 'its newest day read 4 pairs, while the window read enough for a share',
		days: [
			judgeDay('2030-06-10', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.05 }),
			judgeDay('2030-06-15', { pairsJudged: 4, pairsUsable: 3, disagreementRate: 0.25 })
		],
		heading: '15 Jun, the newest day with numbers',
		entries: [
			'Disagreed with the second reading 1 of 4 pairs',
			'Could not tell 0 of the 3 that agreed'
		],
		dots: {
			'2030-06-10':
				'10 Jun: 5% of 40 pairs disagreed with the second reading, and 0% of the 38 that agreed could not tell.',
			'2030-06-15':
				'15 Jun: 1 of 4 pairs disagreed with the second reading, and 0 of the 3 that agreed could not tell.'
		},
		words:
			'In these 7 days, 7% of 44 pairs disagreed with their own second reading, and 0% of the 41 that agreed could not tell. Both rates are inside the marks.'
	},
	{
		preset: 7,
		state: 'the window read 3 pairs, too few for a share',
		days: [
			judgeDay('2030-06-12', { pairsJudged: 2, pairsUsable: 2 }),
			judgeDay('2030-06-15', { pairsJudged: 1, pairsUsable: 1 })
		],
		heading: '15 Jun, the newest day with numbers',
		entries: [
			'Disagreed with the second reading 0 of 1 pair',
			'Could not tell 0 of the 1 that agreed'
		],
		dots: {
			'2030-06-12':
				'12 Jun: 0 of 2 pairs disagreed with the second reading, and 0 of the 2 that agreed could not tell.',
			'2030-06-15':
				'15 Jun: 0 of 1 pair disagreed with the second reading, and 0 of the 1 that agreed could not tell.'
		},
		words:
			'3 pairs were read twice in these 7 days. That is too few to report a share, so the counts are above.'
	},
	{
		preset: 1,
		state: 'its day read 40 pairs, and none of the 38 that agreed could not tell',
		days: [judgeDay('2030-06-15', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.05 })],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 5% of 40 pairs',
			'Could not tell 0% of the 38 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 5% of 40 pairs disagreed with the second reading, and 0% of the 38 that agreed could not tell.'
		},
		words:
			'In this one day, 5% of 40 pairs disagreed with their own second reading, and 0% of the 38 that agreed could not tell. Both rates are inside the marks.'
	},
	{
		// Row L32's smoke days. The record was too small to fit on, so no day was
		// held because of the judge.
		preset: 7,
		state: '41 of the 45 pairs read twice agreed, and 1 of them could not tell',
		days: [
			judgeDay('2030-06-10', {
				pairsJudged: 40,
				pairsUsable: 38,
				disagreementRate: 0.05,
				heldReason: 'sheet_too_small'
			}),
			judgeDay('2030-06-13', {
				pairsJudged: 1,
				pairsUsable: 0,
				disagreementRate: 1,
				heldReason: 'sheet_too_small'
			}),
			judgeDay('2030-06-15', {
				pairsJudged: 4,
				pairsUsable: 3,
				disagreementRate: 0.25,
				unclearRate: 1 / 3,
				heldReason: 'sheet_too_small'
			})
		],
		heading: '15 Jun, the newest day with numbers',
		entries: [
			'Disagreed with the second reading 1 of 4 pairs',
			'Could not tell 1 of the 3 that agreed'
		],
		dots: {
			'2030-06-10':
				'10 Jun: 5% of 40 pairs disagreed with the second reading, and 0% of the 38 that agreed could not tell.',
			'2030-06-13':
				'13 Jun: 1 of 1 pair disagreed with the second reading. Could not tell: not counted, no pair agreed.',
			'2030-06-15':
				'15 Jun: 1 of 4 pairs disagreed with the second reading, and 1 of the 3 that agreed could not tell.'
		},
		words:
			'In these 7 days, 9% of 45 pairs disagreed with their own second reading, and 2% of the 41 that agreed could not tell. Both rates are inside the marks.'
	},
	{
		preset: 1,
		state: 'its day read 5 pairs, and the 3 that agreed are too few for a share of them',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 5,
				pairsUsable: 3,
				disagreementRate: 0.4,
				heldReason: 'sheet_too_small'
			})
		],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 40% of 5 pairs',
			'Could not tell 0 of the 3 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 40% of 5 pairs disagreed with the second reading, and 0 of the 3 that agreed could not tell.'
		},
		words:
			'In this one day, 40% of 5 pairs disagreed with their own second reading, and 0 of the 3 that agreed could not tell. The 40% that disagreed is past its mark, and 3 is too few to report a share.'
	},
	{
		preset: 7,
		state: 'the window read 5 pairs, and the 3 that agreed are too few for a share of them',
		days: [
			judgeDay('2030-06-12', {
				pairsJudged: 1,
				pairsUsable: 0,
				disagreementRate: 1,
				heldReason: 'sheet_too_small'
			}),
			judgeDay('2030-06-15', {
				pairsJudged: 4,
				pairsUsable: 3,
				disagreementRate: 0.25,
				heldReason: 'sheet_too_small'
			})
		],
		heading: '15 Jun, the newest day with numbers',
		entries: [
			'Disagreed with the second reading 1 of 4 pairs',
			'Could not tell 0 of the 3 that agreed'
		],
		dots: {
			'2030-06-12':
				'12 Jun: 1 of 1 pair disagreed with the second reading. Could not tell: not counted, no pair agreed.',
			'2030-06-15':
				'15 Jun: 1 of 4 pairs disagreed with the second reading, and 0 of the 3 that agreed could not tell.'
		},
		words:
			'In these 7 days, 40% of 5 pairs disagreed with their own second reading, and 0 of the 3 that agreed could not tell. The 40% that disagreed is past its mark, and 3 is too few to report a share.'
	},
	{
		// The verdict follows the rate against its mark, so a mark moved past the
		// rate turns it.
		preset: 1,
		state: 'the 4 that agreed are too few for a share of them, and the disagreed mark is 25%',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 5,
				pairsUsable: 4,
				disagreementRate: 0.2,
				heldReason: 'sheet_too_small'
			})
		],
		limits: { disagreementMax: 0.25, unclearMax: 0.35 },
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 20% of 5 pairs',
			'Could not tell 0 of the 4 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 20% of 5 pairs disagreed with the second reading, and 0 of the 4 that agreed could not tell.'
		},
		words:
			'In this one day, 20% of 5 pairs disagreed with their own second reading, and 0 of the 4 that agreed could not tell. The 20% that disagreed is inside its mark, and 4 is too few to report a share.'
	},
	{
		preset: 1,
		state: 'its 5 pairs all disagreed, so no pair agreed',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 5,
				pairsUsable: 0,
				disagreementRate: 1,
				heldReason: 'sheet_too_small'
			})
		],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 100% of 5 pairs',
			'Could not tell not counted, no pair agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 100% of 5 pairs disagreed with the second reading. Could not tell: not counted, no pair agreed.'
		},
		words:
			'In this one day, 100% of 5 pairs disagreed with their own second reading. Could not tell: not counted, no pair agreed. The 100% that disagreed is past its mark.'
	},
	{
		// The verdict follows the shares it judges, never why a day was held. The
		// run checks first whether the record holds enough to fit on, so these
		// days were held for that, with a share past its mark.
		preset: 7,
		state: 'no day was held for the judge, and the 20% that disagreed is past its mark',
		days: [
			judgeDay('2030-06-10', {
				pairsJudged: 40,
				pairsUsable: 32,
				disagreementRate: 0.2,
				unclearRate: 1 / 32,
				heldReason: 'sheet_too_small'
			}),
			judgeDay('2030-06-15', {
				pairsJudged: 5,
				pairsUsable: 4,
				disagreementRate: 0.2,
				heldReason: 'sheet_too_small'
			})
		],
		heading: '15 Jun, the newest day with numbers',
		entries: [
			'Disagreed with the second reading 20% of 5 pairs',
			'Could not tell 0 of the 4 that agreed'
		],
		dots: {
			'2030-06-10':
				'10 Jun: 20% of 40 pairs disagreed with the second reading, and 3% of the 32 that agreed could not tell.',
			'2030-06-15':
				'15 Jun: 20% of 5 pairs disagreed with the second reading, and 0 of the 4 that agreed could not tell.'
		},
		words:
			'In these 7 days, 20% of 45 pairs disagreed with their own second reading, and 3% of the 36 that agreed could not tell. The 20% that disagreed is past its mark.'
	},
	{
		preset: 1,
		state: 'its day was not held for the judge, and the 39% that could not tell is past its mark',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 40,
				pairsUsable: 38,
				disagreementRate: 0.05,
				unclearRate: 15 / 38,
				heldReason: 'sheet_too_small'
			})
		],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading 5% of 40 pairs',
			'Could not tell 39% of the 38 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: 5% of 40 pairs disagreed with the second reading, and 39% of the 38 that agreed could not tell.'
		},
		words:
			'In this one day, 5% of 40 pairs disagreed with their own second reading, and 39% of the 38 that agreed could not tell. The 39% that could not tell is past its mark.'
	},
	{
		preset: 7,
		state: 'no day was held for the judge, and both rates are past their marks',
		days: [
			judgeDay('2030-06-11', {
				pairsJudged: 30,
				pairsUsable: 24,
				disagreementRate: 0.2,
				unclearRate: 8 / 24,
				heldReason: 'sheet_too_small'
			}),
			judgeDay('2030-06-15', {
				pairsJudged: 20,
				pairsUsable: 16,
				disagreementRate: 0.2,
				unclearRate: 0.5,
				heldReason: 'sheet_too_small'
			})
		],
		heading: '15 Jun, the newest day with numbers',
		entries: [
			'Disagreed with the second reading 20% of 20 pairs',
			'Could not tell 50% of the 16 that agreed'
		],
		dots: {
			'2030-06-11':
				'11 Jun: 20% of 30 pairs disagreed with the second reading, and 33% of the 24 that agreed could not tell.',
			'2030-06-15':
				'15 Jun: 20% of 20 pairs disagreed with the second reading, and 50% of the 16 that agreed could not tell.'
		},
		words:
			'In these 7 days, 20% of 50 pairs disagreed with their own second reading, and 40% of the 40 that agreed could not tell. Both rates are past their marks.'
	},
	{
		// A share that is not zero and rounds below one percent prints under one.
		// A 0 would say no pair disagreed, and one did.
		preset: 1,
		state: '1 of its 300 pairs disagreed, a share that rounds below one percent',
		days: [
			judgeDay('2030-06-15', { pairsJudged: 300, pairsUsable: 299, disagreementRate: 1 / 300 })
		],
		heading: '15 Jun',
		entries: [
			'Disagreed with the second reading <1% of 300 pairs',
			'Could not tell 0% of the 299 that agreed'
		],
		dots: {
			'2030-06-15':
				'15 Jun: <1% of 300 pairs disagreed with the second reading, and 0% of the 299 that agreed could not tell.'
		},
		words:
			'In this one day, <1% of 300 pairs disagreed with their own second reading, and 0% of the 299 that agreed could not tell. Both rates are inside the marks.'
	}
];
test.describe("the Judgement panels name their span in every state, on days the test builds", () => {

const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "JudgeAgreement", String(testInfo.workerIndex)), ["JudgeAgreement"]);
  Object.assign(drawn, panels.drawn);
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

for (const one of STRIP_CASES) {
	test(`THE ORACLE: judge-agreement's strip at the ${one.preset}-day window, when ${one.state}`, async ({
		page
	}) => {
		const props = propsOf({ surface: 'judge-agreement', ...one });
		await page.setContent(
			`<main>${drawn['judge-agreement'](one.limits ? { ...props, limits: one.limits } : props)}</main>`
		);

		expect(await said(page, '[data-readout="judge-agreement"] [data-readout-day]')).toBe(
			one.heading
		);
		const entries = await page
			.locator('[data-readout="judge-agreement"] [data-readout-row]')
			.evaluateAll((nodes) =>
				nodes.map((node) => (node.textContent ?? '').replace(/\s+/g, ' ').trim())
			);
		expect(entries).toEqual(one.entries);
		const dots = await page
			.locator('[data-agreement-day]')
			.evaluateAll((nodes) =>
				Object.fromEntries(
					nodes.map((node) => [
						node.getAttribute('data-agreement-day'),
						node.getAttribute('aria-label')
					])
				)
			);
		expect(dots).toEqual(one.dots);
		expect(await said(page, SAID['judge-agreement'])).toBe(one.words);
	});
}
});
