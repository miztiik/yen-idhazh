/** Hardware's observed content span, for its tests and cross-route navigation. */
import type { Page } from '../browser';
export async function machineSpan(page: Page) {
	const record = page.locator('[data-machine-run-count]');
	await page.waitForFunction(() => {
		const route = document.querySelector('[data-console-panels="machine"]');
		return route?.getAttribute('data-route-state') !== 'loading' && document.querySelector('[data-machine-run-count]') !== null;
	});
	return {
		runs: Number(await record.getAttribute('data-machine-run-count')),
		start: await record.getAttribute('data-machine-start') ?? '',
		end: await record.getAttribute('data-machine-end') ?? '',
		bars: await page.locator('[data-console-panel-id="tail-trend"] [data-tail-run]').count()
	};
}
