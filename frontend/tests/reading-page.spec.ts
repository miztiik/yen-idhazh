import { expect, test } from '@playwright/test';
import { dayReady } from './support/day-ready';
import { frameConfig, uiConfig } from '../src/lib/server/config';

/** One reading journey covers the shared shell; never expand it into route or presentation matrices. */
test('a reader can load stories, filter the day and keep the layout usable on a phone', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));
	await page.setViewportSize({ width: 1920, height: 1080 });
	await page.goto('/');
	await dayReady(page);
	const stories = page.locator('article.item');
	await expect(stories.first()).toBeVisible();
	await expect(stories.first().locator('[data-item-summary]').first()).not.toBeEmpty();
	const before = await stories.count();
	expect(before).toBeGreaterThan(1);
	const title = await stories.first().getByRole('heading').innerText();
	expect(title.trim()).not.toBe('');
	const widths = await page.evaluate(() => {
		const frame = document.querySelector<HTMLElement>('.frame')!;
		const prose = document.querySelector<HTMLElement>('article.item .prose')!;
		return {
			frame: frame.getBoundingClientRect().width,
			viewport: document.documentElement.clientWidth,
			prose: prose.getBoundingClientRect().width,
			measure: Number.parseFloat(getComputedStyle(prose).maxWidth)
		};
	});
	expect(widths.frame).toBeCloseTo(widths.viewport, 0);
	expect(widths.prose).toBeLessThanOrEqual(widths.measure + 1);
	await expect(page.locator('[data-time-note]')).toHaveCount(0);
	await expect(stories.locator('[data-item-time]').first()).toContainText('UTC');

	await expect(page.locator('[data-leading]')).toBeVisible();
	const edition = page.getByRole('region', { name: 'About today' });
	await expect(edition.getByRole('heading', { level: 1 })).toBeVisible();
	await expect(edition).toContainText(/\d+ stories/);
	await expect(edition).toContainText(/Updated \d{2}:\d{2} UTC/);
	await expect(edition).not.toContainText('did not finish');
	await expect(edition).not.toContainText('added after');
	const editionText = await edition.innerText();
	await expect(page.locator('[data-site-tagline]')).toHaveCount(0);
	await expect(page.locator('[data-filter-note]')).toHaveCount(0);
	const searchOtherDays = page.getByRole('button', { name: 'Search other days' });
	await expect(searchOtherDays).toHaveCSS('clip-path', 'inset(50%)');
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
	for (const [index, character] of [...prefix].entries()) {
		await page.keyboard.insertText(character);
		await stableField();
		if (index === 0) {
			await expect(searchOtherDays).toBeVisible();
			await expect(page.locator('[data-search-block="day"]'))
				.toContainText('Searching other days downloads');
		}
	}
	await expect(page.locator('[data-leading]')).toHaveCount(0);
	await page.keyboard.insertText(title.slice(prefix.length));
	await expect.poll(() => stories.count()).toBeLessThan(before);
	await expect(stories.first().getByRole('heading')).toHaveText(title);
	await expect(searchOtherDays).toBeVisible();
	await expect(searchOtherDays).toHaveCSS('clip-path', 'none');
	await expect(page.locator('[data-filter-note]')).not.toContainText('Press Enter');
	await expect(edition).toHaveText(editionText);
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
	await expect(searchOtherDays).toHaveCSS('clip-path', 'inset(50%)');
	await expect(page.locator('[data-filter-note]')).toHaveCount(0);

	await page.setViewportSize({ width: 390, height: 844 });
	await expect(page.locator('#page-filter')).toBeVisible();
	await expect.poll(() => page.evaluate(
		() => document.documentElement.scrollWidth <= document.documentElement.clientWidth
	)).toBe(true);

	await page.setViewportSize({ width: 1920, height: 1080 });
	await page.goto('/archive/');
	expect(await page.locator('.frame').evaluate((node) => node.getBoundingClientRect().width))
		.toBe(frameConfig().reading_max_px);
	expect(errors).toEqual([]);
});
