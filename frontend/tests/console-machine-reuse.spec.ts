/** A resize reuses the query rows and keeps context distributions and tail readings. */
import { expect, test } from './support/door-page';

test('resizing preserves the readings and performs no second record fetch', async ({ page }) => {
	let parquet = 0;
	page.on('request', (request) => { if (request.url().includes('.parquet')) parquet++; });
	await page.goto('/console/machine/');
	await expect(page.locator('[data-console-panels="machine"]')).not.toHaveAttribute('data-route-state', 'loading');
	const context = page.locator('[data-console-panel-id="context-headroom"]');
	const tail = page.locator('[data-console-panel-id="tail-trend"]');
	const before = [await context.innerText(), await tail.innerText()];
	const requests = parquet;
	await page.setViewportSize({ width: 390, height: 844 });
	await expect(context).toHaveText(before[0], { useInnerText: true });
	await expect(tail).toHaveText(before[1], { useInnerText: true });
	expect(parquet).toBe(requests);
});
