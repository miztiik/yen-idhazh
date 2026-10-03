/** Reveal every lazy drawing on one ready day. */
import { expect, type Page } from '@playwright/test';

export async function revealDayDrawings(page: Page): Promise<number> {
	const steps = await page.evaluate(async () => {
		const settle = () =>
			new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => done())));
		const step = Math.max(window.innerHeight, 1);
		window.scrollTo(0, 0);
		await settle();
		let at = 0;
		let steps = 0;
		while (at < document.documentElement.scrollHeight && steps < 2000) {
			at += step;
			steps += 1;
			window.scrollTo(0, at);
			await settle();
		}
		window.scrollTo(0, 0);
		await settle();
		return steps;
	});
	await page.waitForLoadState('networkidle');
	let previous = -1;
	await expect.poll(async () => {
		const count = await page.locator('main figure svg').count();
		const settled = count === previous;
		previous = count;
		return settled;
	}).toBe(true);
	return steps;
}
