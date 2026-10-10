/** The common window control, its named config inputs, and declared surfaces. */
import { expect, type Page } from '../browser';
import { BAND_UNREAD, type RouteId } from '../../../src/lib/console/band';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
export function config() { return JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as {
	console?: {
		window_presets?: number[];
		default_window_days?: number;
		max_window_days?: number;
		today_anchor?: 'right' | 'centre';
	};
}; }
export function telemetry() { return JSON.parse(
	readFileSync(
		resolve(process.cwd(), '..', 'config', 'gardener', 'telemetry-aggregate.json'),
		'utf8'
	)
) as {
	series?: Record<string, { unit: string; value?: number }>;
}; }
export function presets() { return config().console?.window_presets ?? [1, 7, 14, 30, 90]; }
export function defaultDays() { return config().console?.default_window_days ?? 14; }
export function routeHref(id: RouteId): string {
	const route = BAND_UNREAD.routes.find((route) => route.id === id);
	if (!route) throw new Error(`The console names no route ${id}`);
	return route.href;
}

/** N days earlier, in UTC, so the suite cannot drift west. */
export function minus(date: string, days: number): string {
	const at = new Date(`${date}T00:00:00Z`);
	at.setUTCDate(at.getUTCDate() - days);
	return at.toISOString().slice(0, 10);
}
export async function hydrated(page: Page) {
	// Disabled in the prerendered document and enabled on mount, so waiting for
	// it is waiting for the control to be able to do anything at all.
	await expect(page.locator(`[data-window-preset="${defaultDays()}"] input`)).toBeEnabled();
}

export async function setWindow(page: Page, days: number) {
	// The label is the target, not the 1px input inside it - that is what a
	// person clicks and what a thumb can hit.
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** Every surface that claims to follow the window, and what it says it shows. */
export async function windowed(page: Page) {
	return page.locator('[data-windowed]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			name: node.getAttribute('data-windowed') ?? '',
			days: Number(node.getAttribute('data-window-days')),
			// A label where there is one, and the words on the surface otherwise.
			// Both are what somebody reading the page is given.
			says: `${node.getAttribute('aria-label') ?? ''} ${node.textContent ?? ''}`.replace(
				/\s+/g,
				' '
			)
		}))
	);
}
