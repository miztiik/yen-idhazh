import { expect, test } from './support/browser';
import { Intercepted, loaderSource, servedDayUrl, type Loader } from './support/day-loader';

const DATE = '2026-08-30';
const WANTED = servedDayUrl(DATE);
const PATTERN = `**${WANTED}`;
const DAY = JSON.stringify({
	version: '2026-09-01T09:00',
	generated_at: '2026-08-30T06:00',
	items: [
		{ item_id: 'ai-1', title: 'A story', summary: 'A readable summary.' },
		{ item_id: 'ai-2', title: 'An incomplete story' },
		{ item_id: 'ai-3', title: 'Another story', summary: 'Another readable summary.' }
	]
});

test('a reader keeps renderable stories when a served day has one malformed story', async ({ page }) => {
	await page.addInitScript({ content: await loaderSource('malformed-day') });
	const served = new Intercepted();
	const uncaught: string[] = [];
	page.on('pageerror', (error) => uncaught.push(String(error)));
	await page.route(PATTERN, async (route) => {
		served.take(route.request().url());
		await route.fulfill({ contentType: 'application/json', body: DAY });
	});
	await page.goto('/');

	const result = await page.evaluate(async (date: string) => {
		const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
		const states: string[] = [];
		const day = await loader.watchDay(date, {
			slowMs: 30000,
			onStatus: (status: string) => states.push(status)
		});
		return { states, items: day === null ? null : day.items.length };
	}, DATE);

	expect(result.states).toEqual(['loading', 'ready']);
	expect(result.items).toBe(2);
	await expect(page.locator('main').first()).toBeVisible();
	expect(uncaught).toEqual([]);
	expect(served.count).toBe(1);
	expect(served.urls).toEqual([WANTED]);
});
