import { expect, test } from '@playwright/test';

test('one archive form preserves drafts, constrains the list by date and links to a story', async ({ page }) => {
	await page.addInitScript(() => {
		Object.defineProperty(globalThis, 'WebAssembly', { value: undefined });
	});
	await page.goto('/archive/');
	const heading = page.getByRole('heading', { name: 'Search our archives', exact: true });
	await expect(heading).toBeVisible();
	await expect(page.locator('.search-info')).toHaveCount(0);
	await expect(page.locator('body')).not.toContainText(
		/On-device search|Nothing you type leaves your browser|Date changes apply with Search|Leave both dates empty/
	);
	await expect(page.getByRole('button', { name: 'Search', exact: true }).locator('svg')).toBeVisible();
	await expect(page.locator('.dates > summary')).toHaveText('Dates');
	await expect(page.locator('.dates > summary svg')).toBeVisible();
	const first = page.locator('[data-story-list="rows"] li a').first();
	await expect(first).toBeVisible();
	await expect(page.locator('[data-topic-row], [data-day-row], footer')).toHaveCount(0);
	await expect(page.locator('[data-search-state]')).toContainText('this browser cannot run it');
	const field = page.locator('#archive-query');
	const fieldFrame = page.locator('[data-archive-form] .field');
	const position = await field.boundingBox();
	await heading.focus();
	await page.keyboard.press('Tab');
	await expect(field).toBeFocused();
	expect(await field.evaluate((node) => node.matches(':focus-visible'))).toBe(true);
	await expect(field).toHaveCSS('outline-style', 'none');
	await expect(fieldFrame).toHaveCSS('outline-style', 'solid');
	await expect(fieldFrame).toHaveCSS('outline-offset', '2px');
	const original = await field.elementHandle();
	const title = await first.innerText();
	const draft = 'a different question';
	for (const character of draft) {
		await page.keyboard.insertText(character);
		await expect(field).toBeFocused();
		expect(await field.evaluate((node, initial) => node === initial, original)).toBe(true);
		expect(await field.boundingBox()).toEqual(position);
	}
	await page.keyboard.press('Home');
	await page.keyboard.press('ArrowRight');
	await page.keyboard.insertText('x');
	expect(await field.evaluate((node: HTMLInputElement) => node.selectionStart)).toBe(2);
	await page.keyboard.press('Backspace');
	await expect(field).toHaveValue(draft);
	const clear = page.getByRole('button', { name: 'Clear search', exact: true });
	await expect(clear).toHaveText('');
	await expect(clear.locator('svg')).toBeVisible();
	await page.keyboard.press('Tab');
	await expect(clear).toBeFocused();
	await expect(clear).toHaveCSS('outline-style', 'solid');
	await expect(fieldFrame).toHaveCSS('outline-style', 'none');
	await expect(first).toHaveText(title);
	await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeDisabled();
	const date = await page.locator('[data-story-date]').first().getAttribute('data-story-date');
	expect(date).not.toBeNull();
	await page.locator('.dates > summary').click();
	await page.getByLabel('From (UTC)').fill(date!);
	await page.getByLabel('To (UTC)').fill(date!);
	await clear.click();
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
