import { expect, test } from '@playwright/test';

test('one archive form preserves drafts, constrains the list by date and links to a story', async ({ page }) => {
	await page.addInitScript(() => {
		Object.defineProperty(globalThis, 'WebAssembly', { value: undefined });
	});
	await page.goto('/archive/');
	await expect(page.getByRole('heading', { name: 'Search our archives', exact: true })).toBeVisible();
	const first = page.locator('[data-story-list="rows"] li a').first();
	await expect(first).toBeVisible();
	await expect(page.locator('[data-topic-row], [data-day-row], footer')).toHaveCount(0);
	await expect(page.locator('[data-search-state]')).toContainText('this browser cannot run it');
	const field = page.locator('#archive-query');
	await field.click();
	const original = await field.elementHandle();
	const position = await field.boundingBox();
	const title = await first.innerText();
	for (const character of 'a different question') {
		await page.keyboard.insertText(character);
		await expect(field).toBeFocused();
		expect(await field.evaluate((node, initial) => node === initial, original)).toBe(true);
		expect((await field.boundingBox())?.y).toBe(position?.y);
	}
	await expect(first).toHaveText(title);
	await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeDisabled();
	const date = await page.locator('[data-story-date]').first().getAttribute('data-story-date');
	expect(date).not.toBeNull();
	await page.locator('.dates > summary').click();
	await page.getByLabel('From (UTC)').fill(date!);
	await page.getByLabel('To (UTC)').fill(date!);
	await page.getByRole('button', { name: 'Clear search', exact: true }).click();
	await expect(field).toBeFocused();
	await page.getByRole('button', { name: 'Search', exact: true }).click();
	await expect(page.locator('[data-story-list="rows"]')).toBeVisible();
	expect(await page.locator('[data-story-date]').evaluateAll(
		(nodes) => nodes.map((node) => node.getAttribute('data-story-date'))
	)).toEqual(expect.arrayContaining([date]));
	await expect(page.locator(`[data-story-date]:not([data-story-date="${date}"])`)).toHaveCount(0);
	const link = page.locator('[data-story-list="rows"] li a').first();
	expect(await link.getAttribute('href')).toMatch(/\/\d{4}-\d{2}-\d{2}\/#[a-z0-9-]+$/);
	await link.click();
	await expect(page.locator('article').first()).toBeVisible();
	await expect(page.locator('footer')).toBeVisible();
});
