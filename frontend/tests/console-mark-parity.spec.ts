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
 * The bite. On the tree before Row #12 none of the six charts publishes a
 * `data-*-domain`, so `getAttribute` returns null and every case fails at its
 * first assertion - "must publish its data-only extent". Restore the six
 * components and all six pass. That is the RED before the GREEN: the oracle
 * cannot pass without the split it is named for.
 *
 * Both routes ship every preset's aggregate inline, so a window change costs no
 * fetch here (`console/+page.svelte`), which is why the case can read the new
 * window's marks the moment the control moves.
 */

import { expect, test, type Page } from '@playwright/test';

/** Two widths far enough apart that the frame is bound to change and the gutter
 * charts cross from beside to stacked - which moves the layout and must not
 * move the data. Both are real console widths. */
const WIDE = { width: 1400, height: 1200 };
const NARROW = { width: 560, height: 1200 };

/** A preset that is narrower than the default 30 and always drawn in the
 * canary, so the window change costs no fetch and leaves data on every chart. */
const OTHER_WINDOW = 7;

interface Chart {
	name: string;
	route: string;
	/** The element carrying the data-only extent this row publishes, and the
	 * root the marks are read from. */
	root: string;
	domainAttr: string;
	/** The element whose viewBox says which frame the chart last drew to. */
	frame: string;
	/** The drawn marks, and the data attributes a resize must leave alone. */
	itemSel: string;
	attrs: string[];
}

const CHARTS: Chart[] = [
	{
		name: 'stage timings',
		route: '/console/',
		root: '[data-timing="plot"]',
		domainAttr: 'data-timing-domain',
		frame: '[data-timing="plot"]',
		itemSel: 'polyline[data-stage-mark], circle[data-stage-mark], circle[data-stage-zero]',
		attrs: ['data-stage-mark', 'data-stage-zero']
	},
	{
		name: 'band distance',
		route: '/console/',
		root: '[data-band-distance]',
		domainAttr: 'data-band-domain',
		frame: '[data-band-distance] svg',
		itemSel: '[data-band-day]',
		attrs: ['data-band-day', 'data-band-inside', 'data-band-short', 'data-band-long', 'data-band-items']
	},
	{
		name: 'source cut range',
		route: '/console/',
		root: '[data-source-cuts="range"] svg',
		domainAttr: 'data-source-domain',
		frame: '[data-source-cuts="range"] svg',
		itemSel: '[data-source-cut]',
		attrs: ['data-source-cut', 'data-range-min', 'data-range-median', 'data-range-max', 'data-range-past']
	},
	{
		name: 'run lengths',
		route: '/console/model/',
		root: '[data-run-lengths="chart"]',
		domainAttr: 'data-run-domain',
		frame: '[data-run-lengths="chart"] svg',
		itemSel: '[data-run-length]',
		attrs: ['data-run-length', 'data-run-low', 'data-run-median', 'data-run-high', 'data-run-items']
	},
	{
		name: 'swap dots',
		route: '/console/model/',
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
	},
	{
		name: 'time histogram',
		route: '/console/model/',
		// Two histograms draw on this route; the first is enough to hold the split.
		root: '[data-histogram-n]',
		domainAttr: 'data-hist-domain',
		frame: '[data-histogram-n] svg',
		itemSel: '[data-hist-bin]',
		attrs: ['data-hist-bin', 'data-hist-bin-n']
	}
];

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
