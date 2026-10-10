/** The judge plot separates eligible dots, gaps, dates and limit marks. */
import { expect, test, type Page } from './support/browser';

import { resolve } from 'node:path';

import type { JudgeDay } from '../src/lib/console/merge-line';

import { windowed } from './support/console-window/controls';
import { said } from './support/console-window/readout';
import { JUDGED_THROUGH, judgeDay, propsOf } from './support/console-window/judgement-fixtures';

import { serverPanels } from './support/console-window/server-panels';

const DOT_FILL = { disagreement: 'var(--chart-1)', unclear: 'var(--chart-3)' } as const;

/** The rule under the agreement chart, in Reader's words, at a floor of 5. */
const FLOOR_RULE =
	'A day has no "disagreed" dot if fewer than 5 pairs were read twice, and no "could not tell" dot if fewer than 5 pairs agreed.';

/** What the agreement chart draws for each day at one window. Each rate is
 * judged by the pairs its share is taken over: "disagreed" by every pair read
 * twice, "could not tell" by the pairs whose two readings agreed. Under
 * `SHARE_FLOOR` of them that rate gets no dot and its line breaks there, while
 * the day keeps its column. A measured day with no measured neighbour is a dot
 * with no line. Jony's ruling; the note's words are Reader's. */
const DOT_CASES: {
	preset: number;
	state: string;
	days: JudgeDay[];
	/** Each column's dots, named by the axis label each sits on. */
	dots: Record<string, Partial<Record<keyof typeof DOT_FILL, string>>>;
	/** Each rate's line, as the days each of its runs joins. */
	lines: Record<keyof typeof DOT_FILL, string[][]>;
	/** The note after the sentence, or null where none prints. */
	note: string | null;
	/** The readout's total column count, checked only where a case names one:
	 * every day of the window, including a day with no reading. */
	columns?: number;
}[] = [
	{
		preset: 7,
		state: 'days of 40, 1 and 4 pairs read twice sit beside a day of 5 where only 4 agreed',
		days: [
			judgeDay('2030-06-10', { pairsJudged: 40, pairsUsable: 36, disagreementRate: 0.1 }),
			judgeDay('2030-06-12', { pairsJudged: 1, pairsUsable: 0, disagreementRate: 1 }),
			judgeDay('2030-06-13', {
				pairsJudged: 50,
				pairsUsable: 45,
				disagreementRate: 0.1,
				unclearRate: 0.2
			}),
			judgeDay('2030-06-14', { pairsJudged: 5, pairsUsable: 4, disagreementRate: 0.2 }),
			judgeDay('2030-06-15', {
				pairsJudged: 4,
				pairsUsable: 3,
				disagreementRate: 0.25,
				unclearRate: 1 / 3
			})
		],
		dots: {
			'2030-06-10': { disagreement: '10%', unclear: '0%' },
			'2030-06-12': {},
			'2030-06-13': { disagreement: '10%', unclear: '20%' },
			'2030-06-14': { disagreement: '20%' },
			'2030-06-15': {}
		},
		lines: { disagreement: [['2030-06-13', '2030-06-14']], unclear: [] },
		note: `${FLOOR_RULE} The chart shows a gap where a dot is left out, and that day's counts are still above.`
	},
	{
		preset: 7,
		state: 'every day read fewer than 5 pairs twice, and the window read 5',
		days: [
			judgeDay('2030-06-12', { pairsJudged: 2, pairsUsable: 2 }),
			judgeDay('2030-06-13', { pairsJudged: 2, pairsUsable: 2 }),
			judgeDay('2030-06-15', { pairsJudged: 1, pairsUsable: 1 })
		],
		dots: { '2030-06-12': {}, '2030-06-13': {}, '2030-06-15': {} },
		lines: { disagreement: [], unclear: [] },
		note: `${FLOOR_RULE} So the chart has no dots, and each day's counts are still above.`
	},
	{
		preset: 7,
		state: 'two adjacent days each read 5 pairs or more, and 5 or more agreed',
		days: [
			judgeDay('2030-06-14', { pairsJudged: 40, pairsUsable: 36, disagreementRate: 0.1 }),
			judgeDay('2030-06-15', {
				pairsJudged: 50,
				pairsUsable: 45,
				disagreementRate: 0.1,
				unclearRate: 0.2
			})
		],
		dots: {
			'2030-06-14': { disagreement: '10%', unclear: '0%' },
			'2030-06-15': { disagreement: '10%', unclear: '20%' }
		},
		lines: {
			disagreement: [['2030-06-14', '2030-06-15']],
			unclear: [['2030-06-14', '2030-06-15']]
		},
		note: null
	},
	{
		preset: 1,
		state: 'its day read 5 pairs, and the 4 that agreed are too few for a dot',
		days: [judgeDay('2030-06-15', { pairsJudged: 5, pairsUsable: 4, disagreementRate: 0.2 })],
		dots: { '2030-06-15': { disagreement: '20%' } },
		lines: { disagreement: [], unclear: [] },
		note: FLOOR_RULE
	},
	{
		preset: 1,
		state: 'its day read 4 pairs, too few for either dot',
		days: [
			judgeDay('2030-06-15', {
				pairsJudged: 4,
				pairsUsable: 3,
				disagreementRate: 0.25,
				unclearRate: 1 / 3
			})
		],
		dots: { '2030-06-15': {} },
		lines: { disagreement: [], unclear: [] },
		note: null
	}
];

/** What the agreement chart draws for a share above the axis's old fixed top,
 * and for a day that holds no reading between two that do. Jony's ruling
 * (row L55): the axis nices from every drawn share as well as the two marks,
 * so a share past the old top widens it rather than drawing pinned to a mark;
 * and every day of the window is a column, so a day with no row at all and a
 * day whose row read no pair both keep their place, drawing no dot and
 * joining no line across them. */
const AXIS_AND_GAP_CASES: {
	preset: number;
	state: string;
	days: JudgeDay[];
	dots: Record<string, Partial<Record<keyof typeof DOT_FILL, string>>>;
	lines: Record<keyof typeof DOT_FILL, string[][]>;
	/** The readout's total column count: every day of the window, a day with no
	 * reading included. */
	columns: number;
}[] = [
	{
		preset: 1,
		state: 'its day disagreed on 40%, past the old fixed 35% top',
		days: [judgeDay('2030-06-15', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.4 })],
		dots: { '2030-06-15': { disagreement: '40%', unclear: '0%' } },
		lines: { disagreement: [], unclear: [] },
		columns: 1
	},
	{
		preset: 1,
		state: 'every pair that agreed could not tell, widening the axis to 100%',
		days: [judgeDay('2030-06-15', { pairsJudged: 40, pairsUsable: 38, unclearRate: 1 })],
		dots: { '2030-06-15': { disagreement: '0%', unclear: '100%' } },
		lines: { disagreement: [], unclear: [] },
		columns: 1
	},
	{
		preset: 7,
		state: 'a day with no row and a day that read no pair sit between two measured days',
		days: [
			judgeDay('2030-06-09', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.1 }),
			// 10 Jun carries no row at all. 11 Jun carries a row that read no pair.
			judgeDay('2030-06-11', { pairsJudged: 0, pairsUsable: 0 }),
			// 12 to 14 Jun carry no row at all.
			judgeDay('2030-06-15', {
				pairsJudged: 45,
				pairsUsable: 40,
				disagreementRate: 0.2,
				unclearRate: 0.1
			})
		],
		dots: {
			'2030-06-09': { disagreement: '10%', unclear: '0%' },
			'2030-06-15': { disagreement: '20%', unclear: '10%' }
		},
		lines: { disagreement: [], unclear: [] },
		columns: 7
	}
];

/** The agreement chart's dots, each named by the axis label it sits on, and each
 * rate's lines, each named by the days whose dots it joins. A dot is told by the
 * colour its rate is drawn in. */
async function agreementMarks(page: Page): Promise<{
	dots: Record<string, Record<string, string>>;
	lines: Record<string, string[][]>;
}> {
	return page.locator('[data-windowed="judge-agreement"] svg[aria-label]').evaluate((svg, fills) => {
		const axis = [...svg.querySelectorAll('[data-tick="y"]')].map((tick) => ({
			label: (tick.textContent ?? '').trim(),
			y: Math.round(Number(tick.getAttribute('y')) * 10) / 10
		}));
		const rates = Object.entries(fills);
		const dots: Record<string, Record<string, string>> = {};
		const dayAt: Record<string, Record<string, string>> = {};
		for (const day of svg.querySelectorAll('[data-agreement-day]')) {
			const date = day.getAttribute('data-agreement-day') ?? '';
			dots[date] = {};
			for (const dot of day.querySelectorAll('circle')) {
				const rate = rates.find(([, fill]) => fill === dot.getAttribute('fill'))?.[0] ?? 'unknown';
				const y = Number(dot.getAttribute('cy'));
				dots[date][rate] = axis.find((tick) => tick.y === y)?.label ?? `off every axis label, at y ${y}`;
				(dayAt[rate] ??= {})[`${dot.getAttribute('cx')},${dot.getAttribute('cy')}`] = date;
			}
		}
		const lines = Object.fromEntries(
			rates.map(([rate]) => [
				rate,
				[...svg.querySelectorAll(`[data-agreement-series="${rate}"]`)].map((line) =>
					(line.getAttribute('points') ?? '')
						.split(' ')
						.map((point) => dayAt[rate]?.[point] ?? `no dot at ${point}`)
				)
			])
		);
		return { dots, lines };
	}, DOT_FILL);
}
test.describe("the Judgement panels name their span in every state, on days the test builds", () => {

const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "JudgeAgreement", String(testInfo.workerIndex)), [['src/routes/console/judgement/JudgeAgreement.svelte', 'JudgeAgreement']]);
  Object.assign(drawn, panels.drawn);
  drawn['judge-agreement'] = drawn.JudgeAgreement;
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

for (const one of DOT_CASES) {
	test(`THE ORACLE: judge-agreement draws no dot for a rate under the floor at the ${one.preset}-day window, when ${one.state}`, async ({
		page
	}) => {
		await page.setContent(
			`<main>${drawn['judge-agreement'](propsOf({ surface: 'judge-agreement', words: '', ...one }))}</main>`
		);

		const marks = await agreementMarks(page);
		expect(marks.dots, 'a dot is drawn at a share the strip calls too few to report').toEqual(
			one.dots
		);
		expect(marks.lines, 'a line joins across a day its rate has no dot on').toEqual(one.lines);
		if (one.note === null) {
			await expect(page.locator('[data-agreement-floor-note]')).toHaveCount(0);
		} else {
			expect(await said(page, '[data-agreement-floor-note]')).toBe(one.note);
		}
	});
}

for (const one of AXIS_AND_GAP_CASES) {
	test(`THE ORACLE: judge-agreement's axis and columns, at the ${one.preset}-day window, when ${one.state}`, async ({
		page
	}) => {
		await page.setContent(
			`<main>${drawn['judge-agreement'](propsOf({ surface: 'judge-agreement', words: '', ...one }))}</main>`
		);

		await expect(
			page.locator('[data-windowed="judge-agreement"]'),
			'the readout holds a different column than the window'
		).toHaveAttribute('data-readout-columns', String(one.columns));
		const marks = await agreementMarks(page);
		expect(marks.dots, 'a share draws pinned to a mark instead of its true height').toEqual(
			one.dots
		);
		expect(marks.lines, 'a line joins across a day with no reading').toEqual(one.lines);
	});
}

test('THE ORACLE: a day with a dot but no axis tick, beside a day with no reading, carries its own date', async ({
	page
}) => {
	// 7 days at a tick density of 6 always drops one day's axis tick - here
	// 12 Jun, the 4th of the 7 (Susan and Jony, 2026-10-09). 13 Jun holds no
	// reading, so 12 Jun has no tick of its own and no neighbouring tick on
	// that side either, which is the one case a glancing reader has no
	// nearby date to read off of.
	const days = [
		judgeDay('2030-06-09', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.1 }),
		judgeDay('2030-06-10', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.1 }),
		judgeDay('2030-06-11', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.1 }),
		judgeDay('2030-06-12', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.2 }),
		judgeDay('2030-06-14', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.1 }),
		judgeDay(JUDGED_THROUGH, { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.1 })
	];
	await page.setContent(
		`<main>${drawn['judge-agreement'](propsOf({ surface: 'judge-agreement', preset: 7, state: '', days, words: '' }))}</main>`
	);

	const tickedDays = await page
		.locator('[data-day-tick]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-day-tick')));
	expect(tickedDays, "the day with no reading's own axis tick is unaffected").toEqual([
		'2030-06-09',
		'2030-06-10',
		'2030-06-11',
		'2030-06-13',
		'2030-06-14',
		'2030-06-15'
	]);
	const stranded = await page
		.locator('[data-agreement-stranded-label]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-agreement-stranded-label')));
	expect(stranded, 'only the dropped tick beside a day with no reading gets its own label').toEqual([
		'2030-06-12'
	]);
	await expect(
		page.locator('[data-agreement-stranded-label="2030-06-12"]'),
		"the label repeats the day's own accessible name, so it carries none of its own"
	).toHaveAttribute('aria-hidden', 'true');
	expect(await said(page, '[data-agreement-stranded-label="2030-06-12"]')).toBe('12 Jun');
});

test('THE ORACLE: a stranded label at a mark\'s own height, near the right edge, does not sit on that mark\'s label', async ({
	page
}) => {
	// 14 days at a tick density of 6 drops index 12 - the day right before
	// the always-kept newest day. Its reading sits exactly on the
	// "disagreed" mark, and the newest day holds no row, so this is the
	// tightest case the two labels can meet in: one stranded day, one
	// mark, both reaching for the same corner (Jony, 2026-10-09).
	const days = [
		judgeDay('2030-06-02', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.1 }),
		judgeDay('2030-06-14', { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.15 })
	];
	await page.setContent(
		`<main>${drawn['judge-agreement'](propsOf({ surface: 'judge-agreement', preset: 14, state: '', days, words: '' }))}</main>`
	);

	const stranded = page.locator('[data-agreement-stranded-label="2030-06-14"]');
	await expect(stranded).toHaveCount(1);
	const markLabel = page.locator('[data-agreement-marker-label="disagreement"]');
	await expect(markLabel).toHaveCount(1);
	const strandedBox = await stranded.evaluate((node) => {
		const { x, y, width, height } = (node as SVGTextElement).getBBox();
		return { x, y, width, height };
	});
	const markBox = await markLabel.evaluate((node) => {
		const { x, y, width, height } = (node as SVGTextElement).getBBox();
		return { x, y, width, height };
	});
	for (const box of [strandedBox, markBox]) {
		expect(Object.values(box).every(Number.isFinite), 'label coordinates must be finite').toBe(true);
		expect(box.width).toBeGreaterThan(0);
		expect(box.height).toBeGreaterThan(0);
	}
	const overlap =
		strandedBox.x < markBox.x + markBox.width &&
		strandedBox.x + strandedBox.width > markBox.x &&
		strandedBox.y < markBox.y + markBox.height &&
		strandedBox.y + strandedBox.height > markBox.y;
	expect(overlap, 'the stranded label sits on top of the mark label at the right edge').toBe(false);
});

for (const width of [390, 1280]) {
	for (const theme of ['light', 'dark']) {
		test(`THE ORACLE: near-top date and mark labels stay separate at ${width}px in ${theme}`, async ({
			page
		}) => {
			await page.setViewportSize({ width, height: 800 });
			const days = [
				judgeDay('2030-06-02', { pairsJudged: 100, pairsUsable: 90, disagreementRate: 0.1 }),
				judgeDay('2030-06-14', {
					pairsJudged: 100, pairsUsable: 90, disagreementRate: 0.1, unclearRate: 0.39
				})
			];
			await page.setContent(
				`<html data-theme="${theme}"><body><main>${drawn['judge-agreement']({
					...propsOf({ surface: 'judge-agreement', preset: 14, state: '', days, words: '' }),
					width: width - 32,
					limits: { disagreementMax: 0.15, unclearMax: 0.39 }
				})}</main></body></html>`
			);
			const date = page.locator('[data-agreement-stranded-label="2030-06-14"]');
			await expect(date).toHaveText('14 Jun');
			await expect(date).toHaveAttribute('aria-hidden', 'true');
			const dateBox = await date.evaluate((node) => {
				const { x, y, width, height } = (node as SVGTextElement).getBBox();
				return { x, y, width, height };
			});
			const markBoxes = await page.locator('[data-agreement-marker-label]').evaluateAll(
				(nodes) => nodes.map((node) => {
					const { x, y, width, height } = (node as SVGTextElement).getBBox();
					return { x, y, width, height };
				})
			);
			for (const markBox of markBoxes) {
				for (const box of [dateBox, markBox]) {
					expect(Object.values(box).every(Number.isFinite), 'label coordinates must be finite').toBe(true);
					expect(box.width).toBeGreaterThan(0);
					expect(box.height).toBeGreaterThan(0);
				}
				expect(
					dateBox.x < markBox.x + markBox.width &&
					dateBox.x + dateBox.width > markBox.x &&
					dateBox.y < markBox.y + markBox.height &&
					dateBox.y + dateBox.height > markBox.y,
					'the top clamp pulls the date back into a mark label'
				).toBe(false);
			}
			const plot = await page.locator('[data-windowed="judge-agreement"] svg > line').first()
				.evaluate((node) => ({
					left: Number(node.getAttribute('x1')),
					right: Number(node.getAttribute('x2')),
					bottom: Number(node.getAttribute('y1'))
				}));
			const top = await page.locator('[data-windowed="judge-agreement"] svg > line').nth(1)
				.getAttribute('y1');
			expect(dateBox.x).toBeGreaterThanOrEqual(plot.left);
			expect(dateBox.x + dateBox.width).toBeLessThanOrEqual(plot.right);
			expect(dateBox.y).toBeGreaterThanOrEqual(Number(top));
			expect(dateBox.y + dateBox.height).toBeLessThanOrEqual(plot.bottom);
			const dotX = await page.locator('[data-agreement-day="2030-06-14"] circle').first()
				.getAttribute('cx');
			expect(Number(await date.getAttribute('x')), 'the date stays over its own day').toBe(Number(dotX));
		});
	}
}

for (const preset of [1, 7]) {
	test(`THE ORACLE: judge-agreement's note and plot labels call each dashed line a mark, and keep "line" for the merge line, at the ${preset}-day window`, async ({
		page
	}) => {
		const days = [
			judgeDay(JUDGED_THROUGH, { pairsJudged: 40, pairsUsable: 38, disagreementRate: 0.05 })
		];
		await page.setContent(
			`<main>${drawn['judge-agreement'](propsOf({ surface: 'judge-agreement', preset, state: '', days, words: '' }))}</main>`
		);

		// One word for each thing: a dashed limit is a mark, and a line is the
		// merge line and nothing else. The words are Reader's, the same at every window.
		expect(
			await said(page, '[data-console-panel="Whether the judge agrees with itself"] .panel-note')
		).toBe(
			'Every pair is read twice, with the two summaries swapped. A "disagreed" dot shows how often a pair\'s two readings disagreed. A "could not tell" dot shows how often the pairs whose two readings agreed could not tell. When a day\'s rate is past its own dashed mark, the run does not move the merge line that day.'
		);
		const labels = await page
			.locator('[data-agreement-marker-label]')
			.evaluateAll((nodes) =>
				nodes.map((node) => (node.textContent ?? '').replace(/\s+/g, ' ').trim())
			);
		expect(labels).toEqual(['15% - the "disagreed" mark', '35% - the "could not tell" mark']);
	});
}
});
