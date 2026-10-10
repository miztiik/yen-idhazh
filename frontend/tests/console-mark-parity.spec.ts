/** THE ORACLE for Row #12: the six charts redraw on a resize and a window
 * change without moving a value the data decided.
 *
 * The row turns per-render recomputation into memoised passes: the stage-timing
 * runs, marks and zeros, the band's stacked segments, and the axis extents of
 * the run, source, swap and histogram charts stop being rebuilt every time a
 * pointer moves or the panel is resized. None of that may change a drawn mark -
 * a resize moves pixels, a window change moves data, and neither may move the
 * numbers behind the marks in any other way.
 *
 * Each chart now publishes its data-only extent - `data-*-domain` - which is
 * bound to a derived that reads the data alone and structurally cannot depend
 * on the plot box. That attribute is the seam the split opened, so this file
 * holds two things about it: it never moves across a resize, and it is still
 * there after the window changes. A picture-only parity test would pass on the
 * tree before this row and prove nothing; the published extent is what lets the
 * oracle fail there.
 *
 * The bite. On the tree before Row #12 none of the charts publishes a
 * `data-*-domain`, so `getAttribute` returns null and every case that draws
 * fails at its first assertion - "must publish its data-only extent". Restore
 * the components and they pass. That is the RED before the GREEN: the oracle
 * cannot pass without the split it is named for.
 *
 * Five of the six draw on the canary. The swap panel draws only where the
 * ledger recorded a model change, and the canary runs one model start to
 * finish, so its case draws `SwapDots.svelte` on swaps built from rows the test
 * writes - the swap `console-model-panels.spec.ts` draws, from
 * `support/model-swap.ts` - and checks the extent and the marks against the
 * values those rows make. A server render draws once, so that case holds the
 * split across two renders at the two widths, not across a live resize; the
 * live resize stays with the other five.
 *
 * Both routes ship every preset's aggregate inline, so a window change costs no
 * fetch here (`console/+page.svelte`), which is why the case can read the new
 * window's marks the moment the control moves.
 */

import { expect, test, type Page } from '@playwright/test';
import { buildSwap, pair, renderSwap, swapFixture, timedPair } from './support/model-swap';
import { BAND_UNREAD } from '../src/lib/console/band';
import { BY_ROUTE, type Chart } from './support/console-expect/console-mark-parity';

/** Two widths far enough apart that the frame is bound to change and the gutter
 * charts cross from beside to stacked - which moves the layout and must not
 * move the data. Both are real console widths. */
const WIDE = { width: 1400, height: 1200 };
const NARROW = { width: 560, height: 1200 };

/** A preset that is narrower than the default 30 and always drawn in the
 * canary, so the window change costs no fetch and leaves data on every chart. */
const OTHER_WINDOW = 7;

const CHARTS = BAND_UNREAD.routes.flatMap((route) => {
	const expected = BY_ROUTE[route.id];
	return expected === null ? [] : expected.charts.map((chart) => ({ ...chart, route: route.href }));
});

/** The swap panel, read the way the other five are. It draws only where the
 * ledger recorded a model change, and the canary runs one model start to
 * finish, so its case draws it on swaps the test builds rather than on a route. */
const SWAP: Chart = {
	name: 'swap dots',
	root: '[data-model-swap-plot]',
	domainAttr: 'data-swap-domain',
	frame: '[data-model-swap-plot] svg',
	itemSel: '[data-swap-row]',
	attrs: [
		'data-swap-row',
		'data-swap-pct',
		'data-swap-before',
		'data-swap-after',
		'data-movement',
		'data-polarity',
		'data-movement-verdict'
	]
};

/** Move the window preset the way the control does, and wait for the page to
 * agree it moved. */
async function setWindow(page: Page, days: number): Promise<void> {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** The width the chart last drew to, read off its own viewBox. It changes when
 * `observeWidth` redraws, so a case can wait on it rather than guess a timeout. */
async function frameWidth(page: Page, chart: Chart): Promise<number> {
	return page.evaluate((sel) => {
		const svg = document.querySelector(sel);
		const parts = (svg?.getAttribute('viewBox') ?? '').split(/\s+/);
		return parts.length === 4 ? Math.round(Number(parts[2])) : 0;
	}, chart.frame);
}

interface Drawn {
	domain: string | null;
	marks: string[];
	frame: number;
}

/** The extent, the marks and the frame once they have stopped moving. A resize
 * and a window change both redraw, and one read can catch the chart a frame
 * early. The marks are a sorted set of the data behind each mark, so a
 * reordering by the layout is not read as a change. */
async function settled(page: Page, chart: Chart): Promise<Drawn> {
	let last = '';
	let snapshot: Drawn = { domain: null, marks: [], frame: 0 };
	for (let tries = 0; tries < 60; tries += 1) {
		const domain = await page.locator(chart.root).first().getAttribute(chart.domainAttr);
		const marks = await page.evaluate(
			({ root, itemSel, attrs }) => {
				const host = document.querySelector(root);
				if (host === null) return [];
				return [...host.querySelectorAll(itemSel)]
					.map((el) => attrs.map((a) => el.getAttribute(a) ?? '').join('|'))
					.sort();
			},
			{ root: chart.root, itemSel: chart.itemSel, attrs: chart.attrs }
		);
		const frame = await frameWidth(page, chart);
		const key = `${domain}::${frame}::${marks.join('\n')}`;
		if (key === last) return { domain, marks, frame };
		last = key;
		snapshot = { domain, marks, frame };
		await page.waitForTimeout(150);
	}
	return snapshot;
}

for (const chart of CHARTS) {
	test(`${chart.name}: the drawn marks survive a window change and a resize`, async ({ page }) => {
		await page.setViewportSize(WIDE);
		await page.goto(chart.route);
		await expect(page.locator(chart.root).first(), `${chart.name} never drew`).toBeVisible();

		// The extent the split publishes. Absent on the tree before this row, so
		// this is the assertion that fails there rather than passing for the wrong
		// reason.
		const wide = await settled(page, chart);
		expect(wide.domain, `${chart.name} must publish its data-only extent`).not.toBeNull();
		expect(wide.domain, `${chart.name} published an empty extent`).not.toBe('');
		expect(wide.marks.length, `${chart.name} drew no marks to compare`).toBeGreaterThan(0);

		// A resize moves the frame and must move nothing the data decided.
		await page.setViewportSize(NARROW);
		await expect
			.poll(() => frameWidth(page, chart), { timeout: 10_000 })
			.not.toBe(wide.frame);
		const narrow = await settled(page, chart);
		expect(narrow.domain, `${chart.name} recomputed its extent on a resize`).toBe(wide.domain);
		expect(narrow.marks, `${chart.name} moved a drawn value on a resize`).toEqual(wide.marks);

		// A window change moves the data. The extent may move with it and must
		// still be published, and the split still has to hold across a resize at
		// the new window.
		await setWindow(page, OTHER_WINDOW);
		const opened = await settled(page, chart);
		expect(opened.domain, `${chart.name} dropped its extent on a window change`).not.toBeNull();
		expect(opened.domain, `${chart.name} published an empty extent at ${OTHER_WINDOW} days`).not.toBe(
			''
		);
		expect(
			opened.marks.length,
			`${chart.name} drew nothing at ${OTHER_WINDOW} days`
		).toBeGreaterThan(0);

		await page.setViewportSize(WIDE);
		await expect
			.poll(() => frameWidth(page, chart), { timeout: 10_000 })
			.not.toBe(opened.frame);
		const reopened = await settled(page, chart);
		expect(reopened.domain, `${chart.name} recomputed its extent on a resize at ${OTHER_WINDOW} days`).toBe(
			opened.domain
		);
		expect(reopened.marks, `${chart.name} moved a drawn value on a resize at ${OTHER_WINDOW} days`).toEqual(
			opened.marks
		);
	});
}

test(`${SWAP.name}: the drawn marks survive a window change and a resize`, async ({
	page
}, testInfo) => {
	// The swap `console-model-panels.spec.ts` draws. Nine of its ten measures are
	// drawn: time and length halve to 50 percent, the five rows that counted all
	// ten of the older model's summaries fall to 0, and the two token rates stay
	// at 100. The copying row starts from nothing on both sides, so it is named
	// rather than drawn. A mark reads
	// `label|percent|before|after|move|polarity|verdict`.
	const built = swapFixture();
	const builtMarks = [
		'"Maybe" told as fact|0|100|0|-1.0000|lower-is-better|good',
		'Marked "not sure"|0|100|0|-1.0000|lower-is-better|good',
		'Numbers not in the article|0|100|0|-1.0000|lower-is-better|good',
		'Outside the length we asked for|0|100|0|-1.0000|lower-is-better|good',
		'Reading the article|100|1000|1000|0.0000|no-agreed-direction|neutral',
		'Summaries the checker doubted|0|100|0|-1.0000|lower-is-better|good',
		'Summary length|50|200|100|-0.5000|no-agreed-direction|neutral',
		'Time to write one|50|4|2|-0.5000|lower-is-better|good',
		'Writing the summary|100|100|100|0.0000|no-agreed-direction|neutral'
	];

	await renderSwap(page, testInfo, WIDE.width, built);
	const wide = await settled(page, SWAP);
	expect(wide.domain, `${SWAP.name} must publish its data-only extent`).toBe('0,100');
	expect(wide.marks, `${SWAP.name} drew values its rows do not hold`).toEqual(builtMarks);
	expect(wide.frame, `${SWAP.name} drew to another width than it was given`).toBe(WIDE.width);

	// A resize moves the frame and must move nothing the data decided. A server
	// render draws once, so the narrow width is a second render of the same swap.
	await renderSwap(page, testInfo, NARROW.width, built);
	const narrow = await settled(page, SWAP);
	expect(narrow.domain, `${SWAP.name} recomputed its extent on a resize`).toBe('0,100');
	expect(narrow.marks, `${SWAP.name} moved a drawn value on a resize`).toEqual(builtMarks);
	expect(narrow.frame, `${SWAP.name} drew to another width than it was given`).toBe(NARROW.width);

	// A window change moves the data. The model route does not window its swap -
	// each side is however much ran on each model - so a swap built from other
	// rows stands for it. The newer model wrote a fifth longer and took half as
	// long again. The checker doubted no summary on either side, and neither
	// model copied or wrote outside the length asked for, so the six rows that
	// measure those start from nothing and are named rather than drawn.
	const other = buildSwap(
		[...pair(10, '2026-08-20', 'old'), ...pair(10, '2026-08-21', 'new', { summary_words: '120' })],
		[...timedPair(10, '2026-08-20', 2000), ...timedPair(10, '2026-08-21', 3000)]
	);
	const otherMarks = [
		'Reading the article|100|1000|1000|0.0000|no-agreed-direction|neutral',
		'Summary length|120|100|120|0.2000|no-agreed-direction|neutral',
		'Time to write one|150|2|3|0.5000|lower-is-better|bad',
		'Writing the summary|100|100|100|0.0000|no-agreed-direction|neutral'
	];

	await renderSwap(page, testInfo, NARROW.width, other);
	const opened = await settled(page, SWAP);
	expect(opened.domain, `${SWAP.name} published another extent than its new rows make`).toBe(
		'100,150'
	);
	expect(opened.marks, `${SWAP.name} drew values its new rows do not hold`).toEqual(otherMarks);
	expect(opened.frame, `${SWAP.name} drew to another width than it was given`).toBe(NARROW.width);

	await renderSwap(page, testInfo, WIDE.width, other);
	const reopened = await settled(page, SWAP);
	expect(reopened.domain, `${SWAP.name} recomputed its extent on a resize at its new rows`).toBe(
		'100,150'
	);
	expect(reopened.marks, `${SWAP.name} moved a drawn value on a resize at its new rows`).toEqual(
		otherMarks
	);
	expect(reopened.frame, `${SWAP.name} drew to another width than it was given`).toBe(WIDE.width);
});
