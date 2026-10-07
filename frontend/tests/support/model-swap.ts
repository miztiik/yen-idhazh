/** The model change two console specs build from rows they write, and draw.
 *
 * The swap panel draws only where the score ledger recorded a change of model,
 * and the canary runs one model start to finish, so no built console page draws
 * one. A spec that checks the panel builds the swap from rows it writes,
 * through the `modelSwap` the model route calls, and draws `SwapDots.svelte` on
 * it with no build. `console-model-panels.spec.ts` checks the panel's layout and
 * `console-mark-parity.spec.ts` checks the extent it publishes, so the swap is
 * written once, here, and both draw the same one.
 */

import { expect, type Locator, type Page, type TestInfo } from '@playwright/test';
import { pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import { modelSwap, type ModelSwap } from '../../src/lib/server/model-work';
import { serverCompiler } from './server-render';

/** The three bands the committed config carries at the ends of its range, so a
 * fixture article picks an ask the way a real one does. */
export const BANDS = [
	{ min_source_words: 0, target_words_min: 30, target_words_max: 45 },
	{ min_source_words: 60, target_words_min: 50, target_words_max: 90 },
	{ min_source_words: 700, target_words_min: 70, target_words_max: 150 }
];

function row(date: string, model: string, extra: Record<string, string> = {}) {
	return { date, model_id: model, summary_words: '100', source_words_before_cap: '800', ...extra };
}

/** `count` summaries `model` wrote on `date`. Each read 800 words of its article
 * and wrote 100, unless `extra` says otherwise. */
export function pair(count: number, date: string, model: string, extra: Record<string, string> = {}) {
	return Array.from({ length: count }, () => row(date, model, extra));
}

/** `count` item-health rows on `date` whose summary took `ms` to write. Each
 * read 1,000 prompt tokens in a second and wrote 100 tokens in a second. */
export function timedPair(count: number, date: string, ms: number) {
	return Array.from({ length: count }, (_, index) => ({
		date,
		run_id: `${date}-${index}`,
		summarize_ms: String(ms),
		prefill_ms: '1000',
		decode_ms: '1000',
		input_tokens: '1000',
		output_tokens: '100',
		cached_tokens: '0'
	}));
}

/** The swap `scores` and `health` make, checked to be one the model route draws:
 * a change of model, with enough summaries on each side of it. */
export function buildSwap(
	scores: Record<string, string>[],
	health: Record<string, string>[]
): ModelSwap {
	const swap = modelSwap(scores, health, BANDS, 5);
	expect(swap, 'the written rows did not create a model-change panel').not.toBeNull();
	expect(swap?.enough, 'the written rows made a thin model-change panel').toBe(true);
	return swap as ModelSwap;
}

/** The swap both specs draw. The checker doubted all ten of the older model's
 * summaries, which ran to 200 words where 70 to 150 were asked for and took 4
 * seconds each. It doubted none of the newer model's, which ran to 100 words
 * and took 2 seconds each. Both models read and wrote tokens at the same rates. */
export function swapFixture(): ModelSwap {
	return buildSwap(
		[
			...pair(10, '2026-08-20', 'old', {
				summary_words: '200',
				band: 'low',
				unsupported_numbers: '1',
				hedge_dropped: 'True'
			}),
			...pair(10, '2026-08-21', 'new', { summary_words: '100' })
		],
		[...timedPair(10, '2026-08-20', 4000), ...timedPair(10, '2026-08-21', 2000)]
	);
}

/** Draw `SwapDots.svelte` on `swap` at `width`, with its real readout and its
 * own styles, and return the plot.
 *
 * A server render draws once, at the width it is handed: the width the panel
 * measures for itself comes only from a script, and no script runs here. */
export async function renderSwap(
	page: Page,
	testInfo: TestInfo,
	width: number,
	swap: ModelSwap
): Promise<Locator> {
	const compiled = serverCompiler(testInfo.outputPath(`swap-dots-${width}`));
	const readout = await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', []);
	const module = await compiled('src/lib/components/SwapDots.svelte', 'SwapDots', [
		['./ChartReadout.svelte', pathToFileURL(readout).href]
	]);
	const component = (await import(pathToFileURL(module).href)).default;
	const markup = render(component, { props: { swap, width, readoutMaxShare: 1 } }).body;
	await page.setContent(
		`<style>${[...compiled.css.values()].join('\n')}</style><main style="width: ${width}px">${markup}</main>`
	);
	return page.locator('[data-model-swap-plot]');
}
