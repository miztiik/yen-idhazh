import { expect, test } from '@playwright/test';
import { dayReady } from './support/day-ready';
import { uiConfig } from '../src/lib/server/config';

/** One reading journey covers the shared shell; never expand it into route or presentation matrices. */
test('a reader can load stories, filter the day and keep the layout usable on a phone', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));
	await page.goto('/');
	await dayReady(page);
	const stories = page.locator('article.item');
	await expect(stories.first()).toBeVisible();
	await expect(stories.first().locator('[data-item-summary]').first()).not.toBeEmpty();
	const before = await stories.count();
	expect(before).toBeGreaterThan(1);
	const title = await stories.first().getByRole('heading').innerText();
	expect(title.trim()).not.toBe('');

	await expect(page.locator('[data-leading]')).toBeVisible();
	const field = page.locator('#page-filter');
	await field.click();
	const original = await field.elementHandle();
	const position = await field.boundingBox();
	async function stableField() {
		await expect(field).toBeFocused();
		expect(await field.evaluate((node, first) => node === first, original)).toBe(true);
		const current = await field.boundingBox();
		expect(current?.x).toBe(position?.x);
		expect(current?.y).toBe(position?.y);
	}
	const prefix = title.slice(0, uiConfig().filter_min_chars + 1);
	for (const character of prefix) {
		await page.keyboard.insertText(character);
		await stableField();
	}
	await expect(page.locator('[data-leading]')).toHaveCount(0);
	await page.keyboard.insertText(title.slice(prefix.length));
	await expect.poll(() => stories.count()).toBeLessThan(before);
	await expect(stories.first().getByRole('heading')).toHaveText(title);
	await page.keyboard.press('Home');
	await page.keyboard.press('ArrowRight');
	await page.keyboard.insertText('x');
	await stableField();
	expect(await field.evaluate((node: HTMLInputElement) => node.selectionStart)).toBe(2);
	await page.keyboard.press('Backspace');
	await page.keyboard.press('ControlOrMeta+A');
	await page.keyboard.press('Backspace');
	await stableField();
	await expect(page.locator('[data-leading]')).toBeVisible();
	await expect(stories.first()).toBeVisible();

	await page.setViewportSize({ width: 390, height: 844 });
	await expect(page.locator('#page-filter')).toBeVisible();
	await expect.poll(() => page.evaluate(
		() => document.documentElement.scrollWidth <= document.documentElement.clientWidth
	)).toBe(true);
	expect(errors).toEqual([]);
});
