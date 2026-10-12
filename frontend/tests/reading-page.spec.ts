import { expect, test } from '@playwright/test';
import { dayReady } from './support/day-ready';

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

	await page.locator('#page-filter').fill(title);
	await expect.poll(() => stories.count()).toBeLessThan(before);
	await expect(stories.first().getByRole('heading')).toHaveText(title);
	await page.locator('#page-filter').fill('');
	await expect(stories.first()).toBeVisible();

	await page.setViewportSize({ width: 390, height: 844 });
	await expect(page.locator('#page-filter')).toBeVisible();
	await expect.poll(() => page.evaluate(
		() => document.documentElement.scrollWidth <= document.documentElement.clientWidth
	)).toBe(true);
	expect(errors).toEqual([]);
});
