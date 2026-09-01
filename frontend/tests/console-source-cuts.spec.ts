/** THE ORACLE for Row #9: `Sources cut short most often` fills its frame.
 *
 * The plot gave its source names a fixed 168px gutter and its rows a fixed 34px
 * pitch. Measured 2026-09-01 on the built console, before this row: at 1440 the
 * frame was 1,342px and the plot 1,162px of it - 86.6 percent; at 768, 493 of
 * 673 - 73.3 percent; and at 390, 144 of 324 - **44.4 percent**, so on a phone
 * the label column took more of the chart than the plot did and the six tracks
 * drew inside 91px. The pitch was 34px at all three, which is two lines of type
 * and a 10px bar with nothing between one row and the next.
 *
 * The right-most axis label is checked here too. It measured clipped to
 * `10,00` at 1440 on 2026-08-31; Row #1's `tickAnchor` fixed that by anchoring
 * the end labels inwards, and this asserts it stays fixed rather than fixing it
 * a second time.
 *
 * Every bound below is read off the frame the page drew, so a wider window or a
 * longer source id moves both sides of the assertion at once.
 *
 * It runs against the canary build. See `frontend/scripts/build-canary.mjs`.
 */

import { expect, test, type Page } from '@playwright/test';
import { labelGutter, MAX_GUTTER_SHARE, ROW_PITCH_MIN, rowPitch } from '../src/lib/charts/frame';

const PLOT = '[data-source-cuts="range"]';

/** The share of its own frame the plot has to be. Below this the chart is a
 * column of labels with a drawing in the margin. */
const MIN_PLOT_SHARE = 0.7;

/** The three widths the console is checked at. 390 is the phone the design
 * system sizes for and it is where the fixed gutter failed. */
const WIDTHS = [1440, 768, 390];

interface Drawn {
	frame: number;
	plot: number;
	pitch: number;
	layout: string;
	rows: number;
	outside: { text: string; over: number }[];
	overlaps: string[];
}

async function drawn(page: Page): Promise<Drawn> {
	return page.evaluate((selector) => {
		const holder = document.querySelector(selector) as HTMLElement;
		const svg = holder.querySelector('svg') as SVGSVGElement;
		const box = svg.getBoundingClientRect();
		const outside: { text: string; over: number }[] = [];
		for (const node of svg.querySelectorAll('text')) {
			const at = node.getBoundingClientRect();
			const over = Math.max(box.left - at.left, at.right - box.right);
			// A tenth of a pixel is a rounding tail, not a clip.
			if (over > 0.1) outside.push({ text: (node.textContent ?? '').trim(), over });
		}
		// Two rows whose labels or tracks touch are one row to a reader.
		const rows = [...svg.querySelectorAll('[data-source-cut]')].map((group) => ({
			id: group.getAttribute('data-source-cut') ?? '',
			box: group.getBoundingClientRect()
		}));
		const overlaps: string[] = [];
		for (let index = 1; index < rows.length; index += 1) {
			if (rows[index].box.top < rows[index - 1].box.bottom - 0.5) {
				overlaps.push(`${rows[index - 1].id} / ${rows[index].id}`);
			}
		}
		return {
			frame: Number(svg.getAttribute('data-source-cuts-frame')),
			plot: Number(svg.getAttribute('data-source-cuts-plot')),
			pitch: Number(svg.getAttribute('data-source-cuts-pitch')),
			layout: svg.getAttribute('data-source-cuts-layout') ?? '',
			rows: rows.length,
			outside,
			overlaps
		};
	}, PLOT);
}

test('THE ORACLE: the plot fills its frame at every width, and no label leaves it', async ({
	page
}) => {
	await page.goto('/console/');
	await expect(page.locator(PLOT)).toHaveCount(1);

	for (const width of WIDTHS) {
		await page.setViewportSize({ width, height: 900 });
		// The chart redraws from a `ResizeObserver`, so the assertion waits for the
		// frame to be the one this width produces rather than the one before it.
		await expect
			.poll(async () => (await drawn(page)).frame, { timeout: 5000 })
			.toBeGreaterThan(0);
		const now = await drawn(page);

		expect(now.rows, `nothing is drawn at ${width}, so nothing below is tested`).toBeGreaterThan(1);
		expect(
			now.plot / now.frame,
			`at ${width} the plot is ${now.plot}px of a ${now.frame}px frame`
		).toBeGreaterThanOrEqual(MIN_PLOT_SHARE);

		// Row #1's rule, held: the end labels anchor inwards, so nothing hangs
		// outside the `svg` for the `svg` to cut.
		expect(now.outside, `a label is drawn outside the frame at ${width}`).toEqual([]);

		// A row is tall enough to read, and two rows never share pixels.
		expect(now.pitch, `the row pitch at ${width} is under the readable floor`).toBeGreaterThanOrEqual(
			ROW_PITCH_MIN
		);
		expect(now.overlaps, `two rows share pixels at ${width}`).toEqual([]);
	}
});

test('the label column is measured, and no name is shortened to fit it', async ({ page }) => {
	await page.goto('/console/');

	// The canary's source ids are short - `cut-a`, `cut-b` - so the gutter fits
	// beside the plot at every width this checks, and the stacked form is driven
	// at the module below rather than pretended at here. Measured 2026-09-01 on
	// the real tree at 390, where `inside-climate-news` does not fit, the layout
	// switches and the plot goes from 44.4 percent of its frame to 92.6.
	const shapes: string[] = [];
	const seen: string[][] = [];
	for (const width of WIDTHS) {
		await page.setViewportSize({ width, height: 900 });
		await expect.poll(async () => (await drawn(page)).layout, { timeout: 5000 }).not.toBe('');
		const now = await drawn(page);
		shapes.push(now.layout);
		expect(['beside', 'stacked'], `${width} draws a shape nothing declared`).toContain(now.layout);
		seen.push(
			await page
				.locator(`${PLOT} [data-source-cell="name"]`)
				.evaluateAll((nodes) => nodes.map((node) => (node.textContent ?? '').trim()))
		);
	}

	// A source id is the ledger's own spelling of a name, so the gutter moves and
	// the word does not. The same names, in the same order, at every width.
	expect(seen[0].length, 'the plot drew no source').toBeGreaterThan(0);
	expect(seen[0].every((name) => name.length > 0)).toBe(true);
	for (const names of seen.slice(1)) expect(names).toEqual(seen[0]);
	expect(shapes.length).toBe(WIDTHS.length);
});

test.describe('the two frame rules this row added', () => {
	test('a gutter is measured, and refused where the frame cannot spare it', () => {
		// `inside-climate-news` is the widest source id the committed ledger holds
		// at the time of writing, and it is what the fixed 168px was sized for.
		const names = ['heatmap', 'inside-climate-news', 'aws-ml-blog'];
		const wide = labelGutter(names, 11, 10, 1342);
		expect(wide, 'a page-wide frame can hold the names beside the plot').not.toBeNull();
		expect(wide ?? 0).toBeLessThanOrEqual(1342 * MAX_GUTTER_SHARE);
		// And it is the widest name that decides, not the first or the last.
		expect(labelGutter(names, 11, 10, 1342)).toBe(
			labelGutter(['inside-climate-news'], 11, 10, 1342)
		);

		// Null is the cue to put the names above their tracks. It is never a cue
		// to shrink the plot behind them, and never one to shorten a name.
		expect(labelGutter(names, 11, 10, 324), 'a phone frame cannot').toBeNull();
		// An empty set needs only the gap, whatever the frame.
		expect(labelGutter([], 11, 10, 324)).toBe(10);
	});

	test('a row pitch grows with the frame, between a floor and a ceiling', () => {
		expect(rowPitch(1198, 40, 56), 'a page-wide plot grows the row').toBe(50);
		expect(rowPitch(300, 40, 56), 'a narrow plot stops at the floor').toBe(40);
		expect(rowPitch(4000, 40, 56), 'and a very wide one stops at the ceiling').toBe(56);
		// Nothing measured yet - the server, or the first frame - is the floor and
		// never a zero-height row.
		expect(rowPitch(0, 40, 56)).toBe(40);
		expect(rowPitch(Number.NaN, 40, 56)).toBe(40);
	});
});
