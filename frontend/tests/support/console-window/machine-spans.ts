/** Hardware's observed content span, for its tests and cross-route navigation. */
import type { Page } from '../browser';
export async function machineSpan(page: Page) {
	const said = (await page.locator('[data-windowed="machine-runs"]').innerText())
		.replace(/\s+/g, ' ')
		.trim();
	const dates = /(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})/.exec(said);
	return {
		runs: Number(/^(\d+) runs? in these/.exec(said)?.[1] ?? 0),
		start: dates?.[1] ?? '',
		end: dates?.[2] ?? '',
		bars: await page.locator('[data-context-run]').count()
	};
}
