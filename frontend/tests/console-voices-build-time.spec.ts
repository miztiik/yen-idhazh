/** Real server/client components preserve the unpublished source view's decisions and empties. */
import { expect, test } from './support/door-page';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { compile, preprocess } from 'svelte/compiler';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { render } from 'svelte/server';
import type { SourceHealthView, SourceHealthRow } from '../src/lib/server/payload';
import { sourceHealth } from '../src/lib/console/voices/source-health';
import { rankingDiscount } from '../src/lib/console/voices/ranking-discount';
import { retirementDrawing } from '../src/lib/console/voices/retiring';
import { retiring } from '../src/lib/server/source-retiring';
import { clientCode } from './support/console-window/client-render';
import { readPanel, judgeSettled } from './support/panel-gates';
import { consolePanels } from './support/console-panels';
import { consoleConfig } from '../src/lib/server/config';

const COMPONENTS = [
	['SourceHealth', './src/lib/console/voices/SourceHealthPanel.svelte'],
	['Retiring', './src/lib/console/voices/RetiringPanel.svelte'],
	['RankingDiscount', './src/lib/console/voices/RankingDiscountPanel.svelte']
] as const;
function row(over: Partial<SourceHealthRow>): SourceHealthRow {
	return { source_id: 'falling', title: 'Falling desk', vertical: 'world', permission: 'allowed', availability: 'failing', retired: false, retired_on: null,
		opportunities: 45, publications: 12, source_failures: 28, reliability: 0.5, reliability_reads: 4,
		recent_days: ['2030-06-13', '2030-06-14', '2030-06-15'].map((date) => ({ date, opportunities: 10, publications: 1, source_failures: 9 })),
		days_under_the_mark: 3, retires_on: '2030-06-26', ...over };
}
function view(sources = [row({}), row({ source_id: 'thin', title: 'Thin desk', availability: 'answering', opportunities: 9, publications: 2, source_failures: 3, reliability: 1, reliability_reads: 0, recent_days: [], days_under_the_mark: 0, retires_on: null })]): SourceHealthView {
	return { generated_at: '2030-06-15T19:00:00Z', run_id: '2030-06-15-1', headline_sentence: 'Two sources were read.',
		reliability_floor: 0.5, reliability_window_days: 30, min_complete_days: 7, complete_dates: 20, yield_readable: true,
		first_date: '2030-05-27', last_date: '2030-06-15', yield_alarm_point: 0.5, yield_alarm_min_decisions: 30,
		dwell_days: 14, auto_retire: false, dwell_dates: ['2030-06-13', '2030-06-14', '2030-06-15'], sources };
}
function props(source: SourceHealthView | null) {
	const strip = retiring(source, 10);
	const config = consoleConfig();
	const frame = { width: config.chart_width, height: config.chart_height };
	return {
		SourceHealth: { ...frame, census: sourceHealth(source, 10) },
		RankingDiscount: { ...frame, discount: rankingDiscount(source, 10) },
		Retiring: { ...frame, strip, drawing: retirementDrawing(strip, 6), cap: 10, readoutMaxShare: 1 }
	};
}
let server: Record<string, any>;
let client: string;
test.beforeAll(async ({}, info) => {
	client = await clientCode(COMPONENTS);
	const bundled = await build({
		stdin: { contents: COMPONENTS.map(([name, file]) => `export { default as ${name} } from '${file}';`).join('\n'), resolveDir: process.cwd() },
		bundle: true, platform: 'node', format: 'esm', write: false, external: ['svelte', 'svelte/*'],
		alias: { $lib: resolve('src/lib') },
		plugins: [{ name: 'real-voices-server-components', setup(builder) {
			builder.onLoad({ filter: /\.svelte$/ }, async ({ path }) => {
				const prepared = await preprocess(readFileSync(path, 'utf8'), vitePreprocess(), { filename: path });
				return { contents: compile(prepared.code, { filename: path, generate: 'server' }).js.code, resolveDir: dirname(path) };
			});
		} }]
	});
	const module = info.outputPath('voices-components.server.mjs');
	mkdirSync(dirname(module), { recursive: true });
	writeFileSync(module, bundled.outputFiles[0].text);
	server = await import(pathToFileURL(module).href);
});
test('real SSR distinguishes a missing census from an arrived empty census on all three build-time panels', () => {
	const missing = props(null), empty = props(view([]));
	for (const [name] of COMPONENTS) {
		const absent = render(server[name], { props: missing[name] }).body;
		const quiet = render(server[name], { props: empty[name] }).body;
		expect(absent).not.toBe(quiet);
		expect(absent).toContain('Not published yet.');
		expect(quiet).toContain('Nothing recorded.');
		expect(quiet).not.toMatch(/data-retiring="absent"|data-source-health="absent"/);
		expect(absent).not.toContain('data-ranked-row=');
		expect(quiet).not.toContain('data-ranked-row=');
	}
});
test('real SSR preserves recorded dwell, unjudged floors, full-weight defaults and categorical census counts', () => {
	const models = props(view());
	const census = render(server.SourceHealth, { props: models.SourceHealth }).body;
	const strip = render(server.Retiring, { props: models.Retiring }).body;
	const discount = render(server.RankingDiscount, { props: models.RankingDiscount }).body;
	expect(census).toContain('Two sources were read.');
	expect(census.match(/data-source-state=/g)).toHaveLength(9);
	expect(strip).toContain('data-retiring-days-under="3"');
	expect(strip).toContain('data-retiring-on="2030-06-26"');
	expect(strip).toContain('data-retiring-dwell-rule');
	expect(strip).toContain('data-retiring-unjudged-row="thin"');
	expect(strip).toContain('watching only');
	expect(discount).toContain('data-ranked-row="falling"');
	expect(discount).not.toContain('data-ranked-row="thin"');
	expect(discount).toContain('1 unread feeds keep full weight');
});
test.describe('compiled real build-time components', () => {
	// The lab mounts compiled components, not the site's script delivery policy.
	test.use({ bypassCSP: true });
test('real client source panels clear sufficiency in both themes at every approved width and keep the recorded square readout', async ({ page }) => {
	for (const theme of ['light', 'dark']) for (const width of [390, 768, 1440]) {
		await page.setViewportSize({ width, height: 1000 });
		await page.addInitScript((value) => localStorage.setItem('idhazh:theme', value), theme);
		await page.goto('/console/voices/');
		await page.addScriptTag({ content: client });
		const models = props(view());
		for (const [name] of COMPONENTS) {
			const value = models[name];
			const index = name === 'Retiring' ? [...models.Retiring.drawing.index] : [];
			await page.evaluate(({ name, value, index }) => {
				document.querySelector('[data-component-lab]')?.remove();
				const target = document.createElement('main');
				target.dataset.componentLab = 'voices';
				document.body.prepend(target);
				if (name === 'Retiring') (value as any).drawing.index = new Map(index);
				window.oneDayWords.draw(name, value);
			}, { name, value, index });
			const lab = page.locator('[data-component-lab] [data-console-panel-id]');
			await lab.scrollIntoViewIfNeeded();
			for (const verdict of judgeSettled(await readPanel(lab), consolePanels().fillFloor)) expect(verdict.pass, `${name}, ${width}, ${theme}: ${verdict.says}`).toBe(true);
			if (name === 'Retiring') {
				await expect(lab.locator('[data-readout]')).toContainText('2030');
				await lab.locator('[data-retiring="table"]').focus();
				await page.keyboard.press('ArrowLeft');
				await expect(lab.locator('[data-readout]')).toContainText('2030');
			}
		}
	}
});
test('real client build-time quiet and missing states keep the same chart room and remain distinct', async ({ page }) => {
	await page.goto('/console/voices/');
	await page.addScriptTag({ content: client });
	for (const state of ['quiet', 'missing'] as const) {
		const models = props(state === 'quiet' ? view([]) : null);
		for (const [name] of COMPONENTS) {
			const value = models[name];
			await page.evaluate(({ name, value }) => {
				document.querySelector('[data-component-lab]')?.remove();
				const target = document.createElement('main');
				target.dataset.componentLab = 'voices';
				document.body.prepend(target);
				if (name === 'Retiring') (value as any).drawing.index = new Map();
				window.oneDayWords.draw(name, value);
			}, { name, value });
			const lab = page.locator('[data-component-lab] [data-console-panel-id]');
			await expect(lab.locator(`[data-empty-state="${state}"]`)).toHaveCount(1);
			await expect(lab).toContainText(state === 'quiet' ? 'Nothing recorded.' : 'Not published yet.');
			await expect(lab.locator('[data-ranked-row], [data-retiring-day]')).toHaveCount(0);
			for (const verdict of judgeSettled(await readPanel(lab), consolePanels().fillFloor)) expect(verdict.pass, `${name}, ${state}: ${verdict.says}`).toBe(true);
		}
	}
});
});
