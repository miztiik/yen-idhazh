import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compile, preprocess } from 'svelte/compiler';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { render } from 'svelte/server';
import { sparklineMarks } from '../src/lib/charts/sparkline';

/**
 * `What the model did` is eleven measures, so it is eleven cards.
 *
 * The eleven-column table could not answer the question the operator brings to
 * it. A trend is a vertical scan, and in that table every column beside the one
 * being scanned was a different quantity; at thirty days it was 330 numbers and
 * eleven header paragraphs. The measures did not change and the words did not
 * change - only the container did, and the table is still here, one control
 * away.
 *
 * Two things this file protects that a screenshot cannot. The copy is
 * PROTECTED: all eleven labels ship verbatim, and a card that paraphrases one
 * fails. And every headline is the newest day's own cell, so a card cannot
 * quietly print a different day's figure from the row underneath it.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');
const repo = path.resolve(frontend, '..');
const built = path.join(frontend, 'test-results', 'model-cards');

const CARDS = '[data-model-cards]';

/** The label set, read out of the page's own source.
 *
 * Parsed rather than typed in, because a constant typed into a test is a second
 * copy of the very strings the test exists to protect - and the second copy is
 * the one nobody updates.
 */
function columns(): { key: string; label: string; line: string }[] {
	const source = readFileSync(
		path.join(frontend, 'src', 'routes', 'console', '+page.svelte'),
		'utf8'
	);
	const start = source.indexOf('const COLUMNS');
	expect(start, 'the console page no longer names COLUMNS').toBeGreaterThan(-1);
	const block = source.slice(start, source.indexOf('\n\t];', start));
	// A label is single-quoted and holds no single quote; a line may be quoted
	// either way, because two of them hold an apostrophe.
	const entry =
		/\{\s*key:\s*'([^']*)',\s*label:\s*'([^']*)',\s*line:\s*(?:'([^']*)'|"([^"]*)")\s*\}/g;
	return [...block.matchAll(entry)].map((match) => ({
		key: match[1],
		label: match[2],
		line: match[3] ?? match[4] ?? ''
	}));
}

/** The same eleven, from the doc that rules the copy.
 *
 * Reading both is what makes this a protection rather than the page agreeing
 * with itself: `docs/` is the memory, so the page is held against the written
 * ruling and not against its own last edit.
 */
function documented(): { label: string; line: string }[] {
	const doc = readFileSync(path.join(repo, 'docs', 'concepts', 'design-system.md'), 'utf8');
	const start = doc.indexOf('| Label | The line under it |');
	expect(start, 'design-system.md no longer carries the label set').toBeGreaterThan(-1);
	const found: { label: string; line: string }[] = [];
	for (const row of doc.slice(start).split('\n').slice(2)) {
		if (!row.startsWith('|')) break;
		const cells = row.split('|').slice(1, -1).map((cell) => cell.trim());
		found.push({ label: cells[0], line: cells[1] === '-' ? '' : cells[1] });
	}
	return found;
}

/** No label holds a single quote, so a single-quoted attribute selector carries
 * the two that hold double quotes without escaping either. */
function card(label: string): string {
	return `${CARDS} [data-kpi='${label}']`;
}

/** The daily figures sit behind a disclosure, and opening it is an action.
 *
 * A test that reads a cell takes that action, so "the table is reachable" is
 * proved by the same step that reads it rather than assumed.
 */
async function openDailyFigures(page: Page) {
	const control = page.locator('[data-model-table-control]');
	await expect(control, 'the daily figures have no control to open them').toHaveCount(1);
	await page.locator('[data-model-table-control] > summary').click();
	await expect(page.locator('[data-model="table"]')).toBeVisible();
}

/** One table cell's own figure, without the second figure some cells carry. */
async function cellText(page: Page, day: string, key: string): Promise<string> {
	return page
		.locator(`[data-model-day="${day}"] [data-model-cell="${key}"]`)
		.evaluate((node) => {
			const copy = node.cloneNode(true) as HTMLElement;
			copy.querySelector('[data-model-aside]')?.remove();
			return (copy.textContent ?? '').trim();
		});
}

/** Which day the cards are showing, published by the page so a test reading it
 * cannot rot when the fixture moves. */
async function newestDay(page: Page): Promise<string> {
	const day = await page.locator('[data-model-cards-note]').getAttribute('data-model-newest');
	expect(day, 'the card grid does not publish which day it is showing').toMatch(
		/^\d{4}-\d{2}-\d{2}$/
	);
	return day as string;
}

test.describe('the eleven measures, as cards', () => {
	test('every card carries its label byte for byte', async ({ page }) => {
		const wanted = columns();
		expect(wanted, 'the source no longer holds eleven columns').toHaveLength(11);

		await page.goto('/console/');
		await expect(page.locator(CARDS), 'the model section draws no card grid').toHaveCount(1);

		const drawn = await page.locator(`${CARDS} [data-kpi]`).evaluateAll((cards) =>
			cards.map((node) => ({
				named: node.getAttribute('data-kpi') ?? '',
				printed: (node.querySelector('[data-kpi-label]')?.textContent ?? '').trim()
			}))
		);

		// In order, and every one of them. A paraphrase, a trimmed quotation mark
		// or a dropped card all fail here, which is the whole point of the ruling.
		expect(drawn.map((node) => node.named)).toEqual(wanted.map((column) => column.label));
		expect(drawn.map((node) => node.printed)).toEqual(wanted.map((column) => column.label));
	});

	test('the page, its source and the doc that rules the copy all agree', async ({ page }) => {
		const wanted = columns();
		const ruled = documented();
		expect(ruled, 'the doc no longer lists eleven labels').toHaveLength(11);
		expect(wanted.map((column) => column.label)).toEqual(ruled.map((row) => row.label));
		expect(wanted.map((column) => column.line)).toEqual(ruled.map((row) => row.line));

		await page.goto('/console/');
		for (const column of ruled) {
			const line = page.locator(`${card(column.label)} [data-kpi-line]`);
			if (column.line === '') {
				// Three of them carry no sentence, and an empty paragraph under those
				// three would be three cards taller than they mean anything.
				await expect(line, `${column.label} invented a sentence`).toHaveCount(0);
				continue;
			}
			await expect(line, `${column.label} lost its sentence`).toHaveText(column.line);
		}
	});

	test("every card's figure is the newest day's cell for that key", async ({ page }) => {
		await page.goto('/console/');
		const wanted = columns();
		const newest = await newestDay(page);

		await openDailyFigures(page);

		// The newest day the table holds, read off the page rather than typed, so
		// this cannot pass on a card showing the wrong day.
		const days = await page
			.locator('[data-model-day]')
			.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-model-day') ?? ''));
		expect(days.length, 'the daily table drew no rows').toBeGreaterThan(0);
		expect([...days].sort().at(-1)).toBe(newest);

		for (const column of wanted) {
			const figure = (
				await page.locator(`${card(column.label)} [data-kpi-value]`).innerText()
			).trim();
			expect(figure, `${column.key} does not print the newest day's cell`).toBe(
				await cellText(page, newest, column.key)
			);
		}
	});

	test('a quality figure prints what it is out of, and the timing card keeps its second figure', async ({
		page
	}) => {
		await page.goto('/console/');
		const newest = await newestDay(page);
		await openDailyFigures(page);

		// The count a share divides by used to sit one column away on the same row.
		// A card has no row, so it carries the count or the reader is invited to
		// read a trend that is not there.
		const summaries = await cellText(page, newest, 'summaries');
		for (const key of ['not-sure', 'unsupported', 'hedge', 'copied']) {
			const label = columns().find((column) => column.key === key)?.label ?? '';
			await expect(
				page.locator(`${card(label)} [data-kpi-note]`),
				`${key} hides the count it is out of`
			).toHaveText(`of ${summaries} ${summaries === '1' ? 'summary' : 'summaries'}`);
		}

		// The split the timing column carried is a fact about the day, so where the
		// day has one the card prints it and where it has none nothing is invented.
		// Both sides are read in one pass rather than branched on: a renamed aside
		// then reads as absent against a card that still prints it, and fails.
		const label = columns().find((column) => column.key === 'per-item')?.label ?? '';
		await expect(page.locator(`[data-model-day="${newest}"] [data-model-cell="per-item"]`)).toHaveCount(
			1
		);
		const pair = await page.evaluate(
			([day, cardSelector]) => ({
				aside:
					document
						.querySelector(`[data-model-day="${day}"] [data-model-aside="per-item"]`)
						?.textContent?.trim() ?? null,
				note:
					document.querySelector(`${cardSelector} [data-kpi-note]`)?.textContent?.trim() ?? null
			}),
			[newest, card(label)]
		);
		expect(pair.note, "the timing card and the timing cell disagree about the day's split").toBe(
			pair.aside
		);
	});

	test('no card is tinted', async ({ page }) => {
		await page.goto('/console/');
		// `Copied, not rewritten` reads about 12 percent and nobody has agreed what
		// a bad number would be. A tint would invent that threshold and publish it.
		const tones = await page
			.locator(`${CARDS} [data-kpi]`)
			.evaluateAll((cards) => cards.map((node) => node.getAttribute('data-tone')));
		expect(tones).toHaveLength(11);
		expect(tones.filter((tone) => tone !== 'neutral')).toEqual([]);
	});

	test('the cards are a grid of small multiples, not a stack', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
		await page.goto('/console/');

		const rows = await page.locator(`${CARDS} [data-kpi]`).evaluateAll((cards) =>
			cards.map((node) => Math.round(node.getBoundingClientRect().top))
		);
		// Eleven cards in eleven rows is the table's fault wearing a card's clothes.
		expect(new Set(rows).size, 'the cards laid out one per row').toBeLessThan(rows.length);
	});

	test('every card line is drawn, and stays inside the card that owns it', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
		await page.goto('/console/');

		// `console-frame.spec.ts` excludes every svg inside `[data-kpi]` from its
		// 320px minimum, correctly - a sparkline carries no axis to read a value
		// off. That exclusion means nothing else measures these eleven at all.
		const drawn = await page.locator(`${CARDS} [data-kpi]`).evaluateAll((cards) =>
			cards.map((node) => {
				const spark = node.querySelector('[data-sparkline]');
				const card = node.getBoundingClientRect();
				const box = spark?.getBoundingClientRect();
				return {
					label: node.getAttribute('data-kpi') ?? '',
					drew: Boolean(spark),
					width: box ? Math.round(box.width) : 0,
					overflow: box ? Math.round(box.right - card.right) : 0
				};
			})
		);

		expect(drawn, 'the scan found no cards').toHaveLength(11);
		expect(drawn.filter((entry) => !entry.drew).map((entry) => entry.label)).toEqual([]);
		// A line narrower than this is a smudge, and one wider than its card pushes
		// a scrollbar under the whole grid.
		expect(drawn.filter((entry) => entry.width < 120)).toEqual([]);
		expect(drawn.filter((entry) => entry.overflow > 0)).toEqual([]);
	});
});

test.describe('the daily figures, behind a control', () => {
	test('the table is closed on arrival and its control says what it opens', async ({ page }) => {
		await page.goto('/console/');

		const control = page.locator('[data-model-table-control]');
		await expect(control).toHaveCount(1);
		await expect(page.locator('[data-model-table-control] > summary')).toHaveText(
			'Show the daily figures'
		);
		// Closed, so the section leads with the shape. The rows are in the document
		// either way: this costs no fetch and needs no script.
		expect(await control.evaluate((node) => (node as HTMLDetailsElement).open)).toBe(false);
		await expect(page.locator('[data-model="table"]')).toBeHidden();
		await expect(page.locator('[data-model-day]').first()).toBeAttached();
	});

	test('opening it shows every day, in the order it always had', async ({ page }) => {
		await page.goto('/console/');
		await openDailyFigures(page);

		const days = await page
			.locator('[data-model-day]')
			.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-model-day') ?? ''));
		expect(days.length).toBeGreaterThan(0);
		// Newest first, which is what a log is for and what the cards above are not.
		expect(days).toEqual([...days].sort().reverse());
		await expect(page.locator('[data-model="table"]')).toBeVisible();
	});

	test('the header is the label alone now the sentence lives on the card', async ({ page }) => {
		await page.goto('/console/');
		await openDailyFigures(page);

		const headers = await page
			.locator('[data-model="table"] thead th')
			.evaluateAll((cells) => cells.map((cell) => (cell.textContent ?? '').trim()));
		// The day column, then the eleven. A sentence left in a header as well as
		// on a card is the same words twice on one screen.
		expect(headers).toEqual(['Day', ...columns().map((column) => column.label)]);
	});
});

test.describe('the swap rule, rendered', () => {
	type Rendered = { body: string; css: string };
	let draw: (props: Record<string, unknown>) => Rendered;

	/** The component on its own. The canary fixture ran one model start to
	 * finish, so no swap reaches the built page and the rule has to be measured
	 * where one can be made to exist. */
	test.beforeAll(async () => {
		const filename = path.join(frontend, 'src', 'lib', 'components', 'Sparkline.svelte');
		const source = readFileSync(filename, 'utf8');
		const pre = await preprocess(source, vitePreprocess(), { filename });
		const result = compile(pre.code, { generate: 'server', filename, name: 'Sparkline' });
		mkdirSync(built, { recursive: true });
		const module = path.join(built, 'Sparkline.server.mjs');
		writeFileSync(module, result.js.code, 'utf8');
		const loaded = await import(pathToFileURL(module).href);
		const css = result.css?.code ?? '';
		draw = (props) => ({ body: render(loaded.default, { props }).body, css });
	});

	async function show(page: Page, out: Rendered) {
		await page.setContent(
			`<!doctype html><html><head><style>${out.css}</style>` +
				`<style>body{margin:0}#host{inline-size:400px}</style></head>` +
				`<body><div id="host">${out.body}</div></body></html>`,
			{ waitUntil: 'domcontentloaded' }
		);
	}

	test('the rule lands on the point the swap names, not beside it', async ({ page }) => {
		const marks = sparklineMarks([4, 9, 2, 7, 5]);
		await show(
			page,
			draw({
				marks,
				label: 'a series',
				width: 188,
				height: 36,
				// The third drawn day is the first day on the new model.
				rules: [{ at: 2 / 4, label: 'The model changed to b on 2026-08-27.' }]
			})
		);

		const measured = await page.evaluate(() => {
			const svg = document.querySelector('svg[data-sparkline="line"]');
			const rule = svg?.querySelector('[data-sparkline-rule]');
			const points = (svg?.querySelector('polyline')?.getAttribute('points') ?? '')
				.trim()
				.split(/\s+/)
				.map((pair) => Number(pair.split(',')[0]));
			return {
				x: Number(rule?.getAttribute('x1')),
				title: rule?.querySelector('title')?.textContent ?? '',
				point: points[2],
				points: points.length
			};
		});

		expect(measured.points).toBe(5);
		// One geometry for both, so a rule and the day it names cannot land in two
		// places when the drawn width changes.
		expect(measured.x).toBeCloseTo(measured.point, 2);
		// A date and an id. An arrow or a delta here would claim the swap caused
		// whatever the line then did, and no committed figure says that.
		expect(measured.title).toBe('The model changed to b on 2026-08-27.');
		expect(measured.title).not.toMatch(/%|faster|slower|up |down /);
	});

	test('no swap draws no rule, and nothing to draw draws neither', async ({ page }) => {
		await show(page, draw({ marks: sparklineMarks([3, 6, 4]), label: 'a series', rules: [] }));
		await expect(page.locator('[data-sparkline-rule]')).toHaveCount(0);
		await expect(page.locator('polyline')).toHaveCount(1);

		// One point is a dot, and a rule across a dot says the ground moved under
		// nothing.
		await show(
			page,
			draw({ marks: sparklineMarks([3]), label: 'a series', rules: [{ at: 0.5, label: 'x' }] })
		);
		await expect(page.locator('[data-sparkline-rule]')).toHaveCount(0);
		await expect(page.locator('polyline')).toHaveCount(0);
	});
});
