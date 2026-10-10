/** Reveal every lazy drawing on one ready day. */
import { expect, type Page } from '@playwright/test';

export async function revealDayDrawings(page: Page): Promise<number> {
	const candidates = await page.locator('main article[data-visual="rendered"]').all();
	for (const article of candidates) {
		if (await article.locator('figure').count()) continue;
		const slot = article.locator('.slot');
		if (await slot.count()) {
			await slot.scrollIntoViewIfNeeded();
			await expect(article).toBeInViewport();
		}
	}
	await page.evaluate(() => window.scrollTo(0, 0));
	await page.waitForLoadState('networkidle');
	let previous = -1;
	await expect.poll(async () => {
		const count = await page.locator('main figure svg').count();
		const settled = count === previous;
		previous = count;
		return settled;
	}).toBe(true);
	return candidates.length;
}
