/** The frame's oracle: the shell widens and the measure does not.
 *
 * This is the defect the whole plan exists to fix, so the test is written to
 * fail in BOTH directions rather than in one:
 *
 * - A commit that widens the shell without moving the measure onto the text
 *   makes the digest worse. 1280px of unbroken summary prose is the exact
 *   failure the original reading-measure rule was protecting against, and it
 *   is the reason `max-w-2xl` cannot simply be given a bigger number.
 * - A commit that caps the measure without widening the shell changes nothing:
 *   the page still uses 40.6 percent of a 1536px screen.
 *
 * Both assertions live in the same test so neither can be satisfied alone.
 */

import { expect, test, type Page } from '@playwright/test';

/** Measured 2026-08-28 on the live site, before this row. */
const BEFORE_PX = 624;

/** The reading measure's bounds, from `config/appearance.json`. Below about 52
 * characters the eye returns too often; above about 80 it loses the line on the
 * way back. */
const MEASURE_MIN_CH = 52;
const MEASURE_MAX_CH = 80;

async function frameWidth(page: Page): Promise<number> {
	return page.evaluate(() => {
		const frame = document.querySelector('.frame');
		return frame ? Math.round(frame.getBoundingClientRect().width) : 0;
	});
}

/** The rendered line length of a paragraph, in characters.
 *
 * Measured off the element's own font rather than assumed: `ch` is the width of
 * a "0" in the current face, and the display face and the reading face do not
 * agree on it.
 */
async function measureCh(page: Page, selector: string): Promise<number> {
	return page.evaluate((sel) => {
		const el = document.querySelector(sel);
		if (!el) return -1;
		const width = el.getBoundingClientRect().width;
		const canvas = document.createElement('canvas');
		const ctx = canvas.getContext('2d');
		if (!ctx) return -1;
		const style = getComputedStyle(el);
		ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
		const zero = ctx.measureText('0').width;
		return zero > 0 ? Math.round(width / zero) : -1;
	}, selector);
}

/** Elements that genuinely scroll sideways.
 *
 * "Content wider than its box" is NOT the defect. An axis label is deliberately
 * wider than the 16px grid cell it is anchored to, and it is positioned
 * absolutely so it never pushes layout; an SVG child reports clientWidth 0 and
 * has no scroll box at all. Neither produces a scrollbar.
 *
 * The defect measured on 2026-08-28 was seven `overflow-x-auto` containers
 * scrolling on a 1209px screen with 582px empty beside them, so that is what
 * this looks for: a box that can scroll AND has something to scroll.
 */
async function overflowing(page: Page): Promise<string[]> {
	return page.evaluate(() =>
		[...document.querySelectorAll('*')]
			.filter((el): el is HTMLElement => el instanceof HTMLElement)
			.filter((el) => {
				const overflowX = getComputedStyle(el).overflowX;
				return overflowX === 'auto' || overflowX === 'scroll';
			})
			.filter((el) => el.scrollWidth > el.clientWidth + 4)
			.map((el) => `${el.tagName.toLowerCase()}.${el.className.toString().slice(0, 40)}`)
	);
}

test.describe('the frame', () => {
	test('widens with the screen, and the measure does not go with it', async ({ page }) => {
		await page.setViewportSize({ width: 1512, height: 950 });
		await page.goto('/');

		const frame = await frameWidth(page);
		// Half the assertion: the shell is no longer a paragraph's width.
		expect(frame, `the frame is still near the old ${BEFORE_PX}px cap`).toBeGreaterThan(1000);

		// The other half: the prose did not stretch with it.
		const ch = await measureCh(page, 'article.item p.measure');
		expect(ch, 'no measured paragraph found').toBeGreaterThan(0);
		expect(ch, `summary line is ${ch} characters`).toBeGreaterThanOrEqual(MEASURE_MIN_CH);
		expect(ch, `summary line is ${ch} characters`).toBeLessThanOrEqual(MEASURE_MAX_CH);
	});

	test('uses most of the screen it is on, at every width', async ({ page }) => {
		// The number nobody measured for eleven months. Rule #10 was applied to
		// everything the runner touches and to nothing the reader sees.
		const floors: Array<[number, number]> = [
			[390, 0.86],
			[768, 0.9],
			[1024, 0.9],
			[1280, 0.9],
			[1512, 0.82]
		];
		for (const [width, floor] of floors) {
			await page.setViewportSize({ width, height: 900 });
			await page.goto('/');
			const frame = await frameWidth(page);
			const share = frame / width;
			expect(
				share,
				`at ${width}px the frame is ${frame}px, ${Math.round(share * 100)} percent of the screen`
			).toBeGreaterThanOrEqual(floor);
		}
	});

	test('the operator route gets a wider frame than the reading route', async ({ page }) => {
		await page.setViewportSize({ width: 1920, height: 950 });
		await page.goto('/');
		const reading = await frameWidth(page);
		await page.goto('/console/');
		const console_ = await frameWidth(page);
		expect(
			console_,
			'the console frame is no wider than the reading frame'
		).toBeGreaterThan(reading);
	});

	test('nothing scrolls sideways at or above 1024', async ({ page }) => {
		// Measured 2026-08-28: seven elements overflowed on the console while
		// 582px of screen sat empty beside them. A table that overflows at the
		// frame width is a column-count decision, not a scrollbar.
		await page.setViewportSize({ width: 1512, height: 950 });
		for (const route of ['/', '/console/', '/archive/']) {
			await page.goto(route);
			await page.waitForTimeout(150);
			const bad = await overflowing(page);
			expect(bad, `${route} scrolls sideways: ${bad.join(', ')}`).toEqual([]);
		}
	});

	test('the phone is one column and keeps its gutter small', async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		await page.goto('/');
		const gutter = await page.evaluate(() => {
			const frame = document.querySelector('.frame');
			return frame ? parseFloat(getComputedStyle(frame).paddingLeft) : -1;
		});
		// A 312px window spent 52px of its width on gutter before this row -
		// about two words a line, on the surface with the fewest to spare.
		expect(gutter).toBeGreaterThan(0);
		expect(gutter).toBeLessThanOrEqual(32);

		// One column: the meta rail follows the body rather than sitting beside it.
		const columns = await page.evaluate(() => {
			const item = document.querySelector('article.item');
			return item ? getComputedStyle(item).gridTemplateColumns.split(' ').length : -1;
		});
		expect(columns).toBe(1);
	});

	test('the page still renders when its payload is absent', async ({ page }) => {
		// CLAUDE.md section 12 step 5. A wider frame must not turn a designed
		// empty state into a white screen.
		await page.setViewportSize({ width: 1512, height: 950 });
		await page.goto('/9999-01-01/');
		const body = await page.evaluate(() => document.body.innerText.trim().length);
		expect(body, 'the missing-day page rendered nothing').toBeGreaterThan(0);
	});
});
