/** Real packed native ledgers for Pipelines' route-only browser cases. */
import { expect, type Page } from './door-page';
import { resolve } from 'node:path';
import { buildRows, daysBefore, serveToPage, type BuiltCell, type BuiltRowsDay } from './ledger-lifecycle';

export const THROUGH = '2030-06-15';
export const FIRST = '2030-03-01';
export const dayBefore = daysBefore;

export function nativeRow(date: string, over: Record<string, BuiltCell> = {}): Record<string, BuiltCell> {
	return {
		date, run_id: `${date}-1`, item_id: 'fixture-article', source_id: 'fixture-source',
		stage: 'publish', outcome: 'ok', code: '', failed_rule: null, url_key: 'fixture-url',
		machine_shard: null, item_index: null, item_started_at: null, item_ended_at: null,
		queue_wait_ms: null, robots_ms: null, fetch_ms: null, extract_ms: null, summarize_ms: null,
		label_ms: null, summary_ms: null, visual_plan_ms: null, faithfulness_ms: null,
		stage_gap_ms: null, item_total_ms: null, cpu_model: null, prefill_ms: null, decode_ms: null,
		input_tokens: null, output_tokens: null, cached_tokens: null,
		label_input_tokens: null, label_cached_tokens: null,
		element_class: null, span_integrity: null, elements_found: null,
		published_at: null, time_source: null, ...over
	};
}

export function timedRow(date: string, over: Record<string, BuiltCell> = {}): Record<string, BuiltCell> {
	return nativeRow(date, {
		fetch_ms: 100, extract_ms: 20, summarize_ms: 600, label_ms: 150, summary_ms: 430,
		visual_plan_ms: 60, faithfulness_ms: 30, item_total_ms: 800, stage_gap_ms: 50, ...over
	});
}

export async function packedPipelines(
	name: string,
	days: readonly BuiltRowsDay[],
	evaluations: readonly BuiltRowsDay[] = days.map((day) => ({ covers: day.covers, rows: [] }))
): Promise<string> {
	const root = resolve('test-results', 'pipelines-ledgers', name);
	await buildRows(root, 'item-health', days);
	await buildRows(root, 'summary-quality-evals', evaluations);
	return root;
}

export async function servePipelines(page: Page, root: string): Promise<void> {
	await serveToPage(page.context(), root, 'item-health');
	await serveToPage(page.context(), root, 'summary-quality-evals');
}

export async function settled(page: Page): Promise<void> {
	await expect(page.locator('[data-console-panels="pipelines"]')).not.toHaveAttribute('data-route-state', 'loading');
}
