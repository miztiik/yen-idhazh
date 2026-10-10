/** The day strip's shared words and observed readout contract. */
import { expect, type Page } from '../browser';

import { daysInWindow, windowOfDays } from '../../../src/lib/charts/viewport';
import { readoutOf, type Readout } from '../../../src/lib/charts/readout';

import { shortDate } from '../../../src/lib/format';

export const DRAWN_THROUGH = '2030-06-15';
export const DRAWN_AT = { height: 220, width: 760, tickDensity: 6, readoutMaxShare: 1 };
export const STEP_KEYS =
	'Point at a day to read it. Left and Right step through the days, Escape returns to the newest.';

/** The keys the shared strip prints for a chart that names none of its own. */
export const DEFAULT_KEYS =
	'Point at a column to read it. Left and Right step through them, Escape returns to the newest.';

/** The days of a window that ends on the pinned day, oldest first. */
export function windowDates(preset: number): string[] {
	return daysInWindow(windowOfDays(DRAWN_THROUGH, preset, 'right'));
}

/** A strip of one count a column, headed as the console heads a day. */
export function dayStrip(dates: readonly string[]): Readout {
	return readoutOf({
		type: 'dateSeries',
		columns: dates.map((date) => shortDate(date)),
		series: [
			{
				label: 'Published',
				swatch: null,
				values: dates.map(() => 12),
				format: (count: number) => String(count)
			}
		],
		notMeasured: 'Nothing was published on this day',
		resting: 'last'
	});
}
export async function said(page: Page, selector: string): Promise<string> {
	const node = page.locator(selector);
	await expect(node, `nothing on the panel matches ${selector}`).toHaveCount(1);
	return ((await node.textContent()) ?? '').replace(/\s+/g, ' ').trim();
}
export async function labelOf(page: Page, selector: string, name = 'aria-label'): Promise<string> {
	const node = page.locator(selector);
	await expect(node, `nothing on the panel matches ${selector}`).toHaveCount(1);
	return (await node.getAttribute(name)) ?? '';
}

/** A strip's heading, and its hint line's words, or null where the line keeps
 * its room blank. Every strip below prints one of the two, never both. */
export async function stripOf(page: Page, name: string): Promise<{ heading: string; hint: string | null }> {
	const heading = await said(page, `[data-readout="${name}"] [data-readout-day]`);
	const hints = await page.locator(`[data-readout-hint="${name}"]`).count();
	const held = await page.locator(`[data-readout-hint-held="${name}"]`).count();
	expect(hints + held, `the ${name} strip has no hint line, or two`).toBe(1);
	return { heading, hint: hints === 0 ? null : await said(page, `[data-readout-hint="${name}"]`) };
}
