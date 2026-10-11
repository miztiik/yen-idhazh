/** The fetched population changes with the preset; newest-day snapshots do not. */
import { expect, test } from './support/browser';
import { hydrated, setWindow, routeHref } from './support/console-window/controls';
import { machineSpan } from './support/console-window/machine-spans';

test('the widest window reaches more actual records than seven days', async ({ page }) => {
	await page.goto(routeHref('machine'));
	await hydrated(page);
	await setWindow(page, 90);
	const wide = await machineSpan(page);
	await setWindow(page, 7);
	const narrow = await machineSpan(page);
	expect(narrow.end).toBe(wide.end);
	expect(narrow.start > wide.start).toBe(true);
	expect(wide.runs).toBeGreaterThan(narrow.runs);
});

test('all newest-day snapshots hold still while the window moves', async ({ page }) => {
	await page.goto(routeHref('machine'));
	await hydrated(page);
	await machineSpan(page);
	const panels = ['two-clocks', 'machine-cards', 'slowest-articles', 'memory-held'];
	const before = await Promise.all(panels.map((id) => page.locator(`[data-console-panel-id="${id}"]`).innerText()));
	await setWindow(page, 7);
	await machineSpan(page);
	expect(await Promise.all(panels.map((id) => page.locator(`[data-console-panel-id="${id}"]`).innerText()))).toEqual(before);
	await setWindow(page, 90);
	await machineSpan(page);
	expect(await Promise.all(panels.map((id) => page.locator(`[data-console-panel-id="${id}"]`).innerText()))).toEqual(before);
});
