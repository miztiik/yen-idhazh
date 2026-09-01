import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compile, preprocess } from 'svelte/compiler';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { render } from 'svelte/server';
import type { LeadingStory } from '../src/lib/day-shape';

/**
 * The day's leading block, rendered on its own.
 *
 * It cannot be driven through a page here. The canary day has one desk and
 * eight stories, and the block allows at most two stories per desk, so the
 * fixture can never fill it - and weakening the per-desk cap to make a test
 * pass would be testing a page nobody ships. So the component is compiled in
 * place and handed props, which is the same route the console's shared
 * components take before their call sites land.
 *
 * What that leaves to the manual smoke is colour and type: the utility layer
 * is a Tailwind build that this harness does not run. What it can answer, and
 * what matters most, is the structure - every entry is an anchor into the
 * stream, no entry carries a numeral, and nothing overflows a phone.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');
const built = path.join(frontend, 'test-results', 'rendered');

type Rendered = { body: string; css: string };

async function renderer(name: string): Promise<(props: Record<string, unknown>) => Rendered> {
	const filename = path.join(frontend, 'src', 'lib', 'components', `${name}.svelte`);
	const source = readFileSync(filename, 'utf8');
	const pre = await preprocess(source, vitePreprocess(), { filename });
	const result = compile(pre.code, { generate: 'server', filename, name });
	mkdirSync(built, { recursive: true });
	const module = path.join(built, `${name}.server.mjs`);
	writeFileSync(module, result.js.code, 'utf8');
	const loaded = await import(pathToFileURL(module).href);
	const css = result.css?.code ?? '';
	return (props) => ({ body: render(loaded.default, { props }).body, css });
}

const tokens = readFileSync(path.join(frontend, 'src', 'styles', 'tokens.css'), 'utf8');

async function show(
	page: import('@playwright/test').Page,
	out: Rendered,
	width: number
): Promise<void> {
	await page.setContent(
		`<!doctype html><html><head><style>${tokens}</style><style>${out.css}</style>` +
			`<style>body{margin:0}#host{inline-size:${width}px}</style></head>` +
			`<body><div id="host">${out.body}</div></body></html>`,
		{ waitUntil: 'domcontentloaded' }
	);
}

const FIVE: LeadingStory[] = [
	{
		item_id: 'india-0000000001',
		title: 'Mahanagar Gas raises CNG prices by two rupees a kilogram',
		reason: 'The same report reached us through three of our feeds.'
	},
	{
		item_id: 'ai-0000000002',
		title: 'Amazon wires an agent runtime into its hosted tooling',
		reason: "15 of today's stories are about Amazon."
	},
	{
		item_id: 'ai-0000000003',
		title: 'Nvidia adapts a perception stack across vehicle platforms',
		reason: "Ten of today's stories are about Nvidia."
	},
	{
		item_id: 'business-economy-0000000004',
		title: 'A bank names the five states that cost a newcomer most',
		reason: "28 of today's stories are about OpenAI."
	},
	{
		item_id: 'energy-0000000005',
		title: 'A grid operator orders four small modular reactors',
		reason: 'The lead story on our Energy desk.'
	}
];

test.describe('the day gets its first screen from the block it was handed', () => {
	test('every lead is an anchor into the stream, and the order is the payload order', async ({
		page
	}) => {
		const draw = await renderer('LeadingStories');
		await show(page, draw({ stories: FIVE }), 1000);

		const links = page.locator('[data-leading] a');
		await expect(links, 'the block draws one link per lead').toHaveCount(FIVE.length);
		expect(await links.evaluateAll((nodes) => nodes.map((n) => n.getAttribute('href')))).toEqual(
			FIVE.map((story) => `#${story.item_id}`)
		);
		// Not a copy of the story: the stream below still carries all of them in
		// the published order, and this is the way in.
		for (const story of FIVE) {
			await expect(page.locator(`[data-lead="${story.item_id}"]`)).toContainText(story.title);
			await expect(page.locator(`[data-lead="${story.item_id}"]`)).toContainText(story.reason);
		}
	});

	test('no lead carries a rank numeral', async ({ page }) => {
		const draw = await renderer('LeadingStories');
		await show(page, draw({ stories: FIVE }), 1000);

		// A number beside a story implies a score we would then owe the reader an
		// explanation for. The list markers are what would put one there without
		// anybody writing it, so the list is unordered and unmarked.
		const markers = await page.locator('[data-leading] ul').evaluate((node) => {
			const style = getComputedStyle(node);
			return { type: style.listStyleType, position: style.listStylePosition };
		});
		expect(markers.type).toBe('none');

		const opening = await page
			.locator('[data-leading] [data-lead]')
			.first()
			.evaluate((node) => (node.textContent ?? '').trim());
		expect(opening.startsWith(FIVE[0].title)).toBe(true);
	});

	test('an empty block draws nothing at all, not an empty heading', async ({ page }) => {
		const draw = await renderer('LeadingStories');
		await show(page, draw({ stories: [] }), 1000);

		await expect(page.locator('[data-leading]')).toHaveCount(0);
	});

	test('the block fits a phone, with no horizontal scrollbar', async ({ page }) => {
		const draw = await renderer('LeadingStories');
		const long: LeadingStory[] = [
			{
				item_id: 'ai-0000000001',
				// One unbroken token is the case that forces a scrollbar, and no
				// reader-facing surface may carry one.
				title: 'Supercalifragilisticexpialidociousantidisestablishmentarianismfloccinaucinihilipilification',
				reason: 'The lead story on our AI desk.'
			},
			...FIVE
		];
		await show(page, draw({ stories: long }), 360);

		const overflow = await page.evaluate(() => {
			const host = document.querySelector('#host') as HTMLElement;
			return host.scrollWidth - host.clientWidth;
		});
		expect(overflow, 'the block overflowed a 360px viewport').toBeLessThanOrEqual(0);
	});
});
