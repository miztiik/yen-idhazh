import { expect, test, type Page } from '@playwright/test';

/**
 * THE ORACLE for one date axis: no two dates touch, and none is cut off.
 *
 * The console grew four date-axis rules - one in `frame.ts`, one in
 * `run-history.ts`, one inside `FailurePanels.svelte` and one echarts owns -
 * and three of them thinned by a count rather than by a measurement. A count
 * cannot hold at two widths. Measured 2026-08-31 at 390px on the built console,
 * before this row: `Summary length against the length asked for` overlapped
 * `2 Aug 2026` and `8 Aug` by 13.6px, `Time per item, by stage` by 7.4px,
 * `Model tokens per second per day` by 26.1px and `Summary length per run` by
 * 1.9px. `What the cap cost, by source` drew `10,000` 3.2px outside its own
 * `svg` at every width, so it read `10,00`.
 *
 * So the test is geometric and reads the page rather than the rule: it collects
 * the box of every date-axis label at three widths and asserts they do not
 * touch and are not cut off. A rule that satisfies this test is correct
 * whatever arithmetic it used, and one that does not is wrong however good the
 * arithmetic looked.
 *
 * The bite, run 2026-08-31: set `LABEL_ADVANCE_EM` in `frame.ts` to 0.05, so
 * the fit believes a date is a twelfth of its real width, rebuild, and this
 * file goes red - two of its nine cases fail on exactly the overlap above. Put
 * the constant back and `git diff --numstat` on the file is unchanged. A test
 * that cannot be made to fail is not measuring anything.
 */

const ROUTES = ['/console/', '/console/model/', '/console/machine/'];
const WIDTHS = [1440, 768, 390];

/** Which routes draw a date axis of their own.
 *
 * The Machine route draws none: every chart on it is engine-drawn, and the one
 * that carries days hands its labels to the engine's own overlap rule. That is
 * stated here rather than discovered, so a route that stops declaring one fails
 * this file instead of passing it with an empty scan.
 */
const DECLARES: Record<string, boolean> = {
	'/console/': true,
	'/console/model/': true,
	'/console/machine/': false
};

/** A label's box, and the box of the `svg` that may clip it. */
interface Label {
	chart: string;
	text: string;
	left: number;
	right: number;
	top: number;
	bottom: number;
	/** Null where the label is HTML rather than SVG - a grid-placed strip has no
	 * clipping frame, so only the overlap half of the oracle applies to it. */
	frame: { left: number; right: number; top: number; bottom: number } | null;
	/** Which axis this label belongs to. Labels share one when they share one
	 * owning element, which is what makes "two labels on one axis" a fact about
	 * the page rather than a guess from their positions. */
	axis: string;
}

async function labelsOn(page: Page): Promise<Label[]> {
	return page.evaluate(() => {
		const box = (element: Element) => {
			const rect = element.getBoundingClientRect();
			return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
		};
		return [...document.querySelectorAll('[data-day-axis]')].map((node, at) => {
			const svg = node.closest('svg');
			const owner = svg ?? node.closest('[data-feed-axis], .feed-axis, [data-console-panel]');
			const name =
				svg?.getAttribute('aria-label') ??
				node.closest('[data-console-panel]')?.getAttribute('data-console-panel') ??
				'a date strip';
			return {
				chart: String(name).slice(0, 60),
				text: (node.textContent ?? '').trim(),
				...box(node),
				frame: svg === null ? null : box(svg),
				axis: owner === null ? `orphan-${at}` : `${name}#${[...document.querySelectorAll('svg, .feed-axis, [data-console-panel]')].indexOf(owner)}`
			};
		});
	});
}

async function load(page: Page, route: string, width: number): Promise<void> {
	await page.setViewportSize({ width, height: 900 });
	await page.goto(route);
	// The server draws at `chart.width_px` and the client redraws once it has
	// measured the column. Reading before that measures the wrong axis.
	await page.waitForTimeout(700);
}

for (const width of WIDTHS) {
	test.describe(`the date axis at ${width}px`, () => {
		for (const route of ROUTES) {
			test(`THE ORACLE: no two dates touch and none is cut off on ${route}`, async ({ page }) => {
				await load(page, route, width);
				const labels = await labelsOn(page);
				if (DECLARES[route]) {
					expect(
						labels.length,
						`${route} declares no date axis - the scan is broken`
					).toBeGreaterThan(0);
				} else {
					expect(
						labels,
						`${route} now draws a date axis of its own - say so in DECLARES`
					).toEqual([]);
				}

				const axes = new Map<string, Label[]>();
				for (const label of labels) {
					if (!axes.has(label.axis)) axes.set(label.axis, []);
					axes.get(label.axis)?.push(label);
				}

				const touching: string[] = [];
				for (const [, group] of axes) {
					const row = [...group].sort((a, b) => a.left - b.left);
					for (let n = 0; n + 1 < row.length; n += 1) {
						// Half a pixel, because a browser rounds a box and a rule cannot be
						// held to a precision the measurement does not have.
						if (row[n].right > row[n + 1].left + 0.5) {
							touching.push(
								`[${row[n].chart}] "${row[n].text}" and "${row[n + 1].text}" share ${(
									row[n].right - row[n + 1].left
								).toFixed(1)}px`
							);
						}
					}
				}
				expect(touching, 'two dates on one axis are drawn over each other').toEqual([]);

				const cut = labels
					.filter((label) => label.frame !== null && label.right - label.left > 0)
					.filter((label) => {
						const frame = label.frame as NonNullable<Label['frame']>;
						return (
							label.left < frame.left - 0.5 ||
							label.right > frame.right + 0.5 ||
							label.top < frame.top - 0.5 ||
							label.bottom > frame.bottom + 0.5
						);
					})
					.map((label) => `[${label.chart}] "${label.text}"`);
				expect(cut, 'these labels are drawn outside the svg that clips them').toEqual([]);
			});
		}
	});
}

test('every column the ceiling allows keeps its mark, even where the date went', async ({
	page
}) => {
	// A reader counting columns needs the grid whether or not the label survived
	// the fit, so the marks are drawn from the ceiling and only the dates thin.
	await load(page, '/console/', 390);

	const plots = await page.evaluate(() =>
		[...document.querySelectorAll('svg')]
			.filter((svg) => svg.querySelector('[data-day-tick]') !== null)
			.map((svg) => ({
				name: (svg.getAttribute('aria-label') ?? 'unnamed').slice(0, 60),
				marks: svg.querySelectorAll('[data-day-tick]').length,
				dates: svg.querySelectorAll('[data-day-axis]').length
			}))
	);

	expect(plots.length, 'no chart draws a day axis - the scan is broken').toBeGreaterThan(0);
	for (const plot of plots) {
		expect(plot.marks, `${plot.name} drew a date with no mark under it`).toBeGreaterThanOrEqual(
			plot.dates
		);
		expect(plot.dates, `${plot.name} lost both ends of its own span`).toBeGreaterThanOrEqual(1);
	}
	// At least one chart must have dropped a date on a phone. If none did, the
	// fit never bit and this file proves nothing about the rule it exists for.
	expect(
		plots.some((plot) => plot.marks > plot.dates),
		'the fit dropped nothing at 390px, so the oracle above is a tautology'
	).toBe(true);
});

test('a date on the console is written the way a reader reads one', async ({ page }) => {
	// `2026-08-25` is how the ledger spells a day and `08-25` is how it spelled
	// one on two engine-drawn axes. A term from a subsystem is not a term for a
	// user (CLAUDE.md section 0b), and a page with three date grammars on it
	// makes a reader learn which chart they are looking at first.
	for (const route of ROUTES) {
		await load(page, route, 1440);
		const ledgerish = await page.evaluate(() =>
			[...document.querySelectorAll('svg text')]
				.map((node) => (node.textContent ?? '').trim())
				.filter((text) => /^\d{4}-\d{2}-\d{2}$/.test(text) || /^\d{2}-\d{2}$/.test(text))
		);
		expect(ledgerish, `${route} prints a ledger date on a chart`).toEqual([]);
	}
});
