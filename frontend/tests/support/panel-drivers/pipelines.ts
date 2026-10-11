/** Which judged Pipelines panels have state drivers or build-time inputs? */

import type { BasicNothing, Driver } from '../panel-gates';
import type { Page } from '@playwright/test';

async function recordState(page: Page, state: BasicNothing): Promise<void> {
	await page.route('**/state/compact/{item-health,summary-quality-evals}/index/*.json', async (route) => {
		if (state === 'loading') return;
		if (state === 'missing') { await route.fulfill({ status: 404, body: '' }); return; }
		if (state === 'unreachable') { await route.abort('failed'); return; }
		const response = await route.fetch();
		const index = await response.json();
		await route.fulfill({ response, json: {
			...index, entries: index.entries.map((entry: Record<string, unknown>) => ({ ...entry, rows: 0 }))
		} });
	});
}
const states: Readonly<Record<BasicNothing, Driver>> = {
	loading: (page) => recordState(page, 'loading'), missing: (page) => recordState(page, 'missing'),
	quiet: (page) => recordState(page, 'quiet'), unreachable: (page) => recordState(page, 'unreachable')
};
export const DRIVERS: Readonly<Record<string, Readonly<Record<BasicNothing, Driver>>>> = {
	'failure-mix': states, 'item-time-split': states, 'slower-on-same-work': states,
	'stage-timings': states, 'item-cost': states, 'run-timeline': states, 'article-age': states
};
export const BUILD_TIME: readonly string[] = [
	'at-a-glance', 'run-health', 'site-cost-per-item', 'chart-drawing', 'extraction'
];