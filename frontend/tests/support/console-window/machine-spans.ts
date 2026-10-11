/** Hardware's observed content span, for its tests and cross-route navigation. */
import type { Page } from '../browser';
export async function machineSpan(page: Page) {
	const route = page.locator('[data-console-panels="machine"]');
	await page.waitForFunction(() => {
		const route = document.querySelector('[data-console-panels="machine"]');
		return route?.getAttribute('data-route-state') !== 'loading' && route?.hasAttribute('data-machine-run-count');
	});
	return {
		runs: Number(await route.getAttribute('data-machine-run-count')),
		start: await route.getAttribute('data-machine-start') ?? '',
		end: await route.getAttribute('data-machine-end') ?? '',
		bars: await page.locator('[data-console-panel-id="tail-trend"] [data-tail-run]').count()
	};
}
