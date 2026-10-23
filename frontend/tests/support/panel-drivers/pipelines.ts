/** Which judged Pipelines panels have state drivers or build-time inputs? */

import type { BasicNothing, Driver } from '../panel-gates';
import type { Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { dayBefore, nativeRow, timedRow, packedPipelines, servePipelines } from '../pipelines-ledgers';

let populated: Promise<string> | undefined;
export async function populatedPanels(page: Page, worker: number): Promise<void> {
	const through = '2026-08-20';
	const floor = JSON.parse(readFileSync(resolve('..', 'config', 'appearance.json'), 'utf8')).console.fleet_min_rows;
	const itemsPerDay = Math.max(8, Math.ceil(floor / 8));
	populated ??= packedPipelines(`sufficiency-${worker}`, Array.from({ length: 90 }, (_, index) => {
		const date = dayBefore(through, 89 - index);
		return { covers: date, rows: index < 82 ? [] : [
			...Array.from({ length: itemsPerDay }, (_, item) => timedRow(date, {
				item_id: `article-${item}`, url_key: `article-${date}-${item}`, machine_shard: item % 2,
				item_index: item, item_started_at: `${date}T12:00:${String(item).padStart(2, '0')}Z`,
				item_ended_at: `${date}T12:00:${String(item).padStart(2, '0')}.800Z`,
				cpu_model: 'fixture-reference-cpu',
				prefill_ms: 100 + item, decode_ms: 400 + item, input_tokens: 100, cached_tokens: 10,
				output_tokens: 40, published_at: `${date}T00:00:00Z`, time_source: 'feed',
				element_class: 'narrative', span_integrity: true, elements_found: item
			})),
			nativeRow(date, { item_id: 'failed', url_key: `failed-${date}`, stage: 'fetch', outcome: 'failed', code: 'timeout', failed_rule: 'timeout' })
		] };
	}));
	await servePipelines(page, await populated);
}

async function recordState(page: Page, state: BasicNothing): Promise<void> {
	await page.route('**/state/compact/{item-health,summary-quality-evals}/index/*.json', async (route) => {
		if (state === 'loading') return;
		if (state === 'missing') { await route.fulfill({ status: 404, body: '' }); return; }
		if (state === 'unreachable') { await route.abort('failed'); return; }
		const url = new URL(route.request().url());
		const ledger = url.pathname.includes('/item-health/') ? 'item-health' : 'summary-quality-evals';
		const period = url.pathname.split('/').at(-1)!;
		const index = JSON.parse(readFileSync(resolve('build', 'state', 'compact', ledger, 'index', period), 'utf8'));
		await route.fulfill({ json: {
			...index, entries: index.entries.map((entry: Record<string, unknown>) => ({ ...entry, rows: 0, bytes: 0, state: 'empty' }))
		} });
	});
}
const states: Readonly<Record<BasicNothing, Driver>> = {
	loading: (page) => recordState(page, 'loading'), missing: (page) => recordState(page, 'missing'),
	quiet: (page) => recordState(page, 'quiet'), unreachable: (page) => recordState(page, 'unreachable')
};
export const stateSelector = (id: string, state: BasicNothing): string =>
	`[data-reserved="${id}"][data-panel-state="${state}"]`;
export const DRIVERS: Readonly<Record<string, Readonly<Record<BasicNothing, Driver>>>> = {
	'failure-mix': states, 'item-time-split': states, 'slower-on-same-work': states,
	'stage-timings': states, 'item-cost': states, 'run-timeline': states, 'article-age': states
};
export const BUILD_TIME: readonly string[] = [
	'at-a-glance', 'run-health', 'site-cost-per-item', 'chart-drawing', 'extraction'
];