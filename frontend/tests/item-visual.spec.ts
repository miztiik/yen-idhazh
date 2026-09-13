import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { publishedVisualData, refusedVisualData } from '../src/lib/payload/drawing';
import { drawBars } from '../src/lib/visual/bar';
import type { VisualData } from '../src/lib/payload/types';
import { dayReady } from './support/day-ready';

/**
 * The reader's browser draws the chart, and the pipeline never draws one.
 *
 * Owner ruling, 2026-09-13. Until then the chart was an SVG the pipeline
 * rendered at build time, committed, and the page inlined so it could be
 * repainted from the page's own tokens. Now the payload carries a pointer, the
 * browser fetches the marks, and `$lib/visual/bar` decides where every one of
 * them sits.
 *
 * **What the reader gives up is asserted here rather than described.** A page
 * that never runs a script draws no chart, so the figure's `aria-label` is the
 * whole of what such a reader receives - and the arm below reads it back off a
 * real page to say it is there.
 *
 * Driven from the canary day, never from `frontend/public/digest/` - the cost of
 * this file may not rise because a run published more (Guardrail #12).
 */

const ROOT = resolve(process.cwd(), '..');
const CANARY = resolve(ROOT, 'backend', 'var', 'canary', 'digest');

/** The canary day, which publishes two charts and one that never landed. */
const DAY = '/2026-08-20/';

const THEMES = ['light', 'dark'] as const;

/** One mark as the page drew it, in the drawing's own coordinate space. */
interface DrawnBar {
	name: string;
	stated: string;
	x: number;
	y: number;
	width: number;
	height: number;
}

/** Every bar on the page, read off the elements the browser actually placed. */
function drawnBars(page: Page): Promise<DrawnBar[][]> {
	return page.evaluate(() =>
		[...document.querySelectorAll('main article figure svg')].map((svg) => {
			const names = [...svg.querySelectorAll('text.name')].map((node) => node.textContent ?? '');
			const figures = [...svg.querySelectorAll('text.figure')].map(
				(node) => node.textContent ?? ''
			);
			return [...svg.querySelectorAll('rect.bar')].map((rect, at) => ({
				name: names[at] ?? '',
				stated: figures[at] ?? '',
				x: Number(rect.getAttribute('x')),
				y: Number(rect.getAttribute('y')),
				width: Number(rect.getAttribute('width')),
				height: Number(rect.getAttribute('height'))
			}));
		})
	);
}

/** What the document computes for a token, read the way the page reads it.
 *
 * `background-color` rather than `fill` because every element has one, so the
 * probe needs no shape and no namespace - and both properties resolve the same
 * custom property through the same cascade.
 */
function tokenColour(page: Page, token: string): Promise<string> {
	return page.evaluate((name) => {
		const probe = document.createElement('div');
		probe.style.backgroundColor = `var(${name})`;
		document.body.append(probe);
		const painted = getComputedStyle(probe).backgroundColor;
		probe.remove();
		return painted;
	}, token);
}

/** Every value the page painted a drawn part with, for one CSS property. */
function painted(page: Page, selector: string, property: 'fill' | 'stroke'): Promise<string[]> {
	return page.evaluate(
		({ selector: query, property: name }) =>
			[...document.querySelectorAll(`main figure ${query}`)].map((node) =>
				getComputedStyle(node).getPropertyValue(name)
			),
		{ selector, property }
	);
}

async function wearing(page: Page, theme: string): Promise<void> {
	await page.evaluate(
		(chosen) => document.documentElement.setAttribute('data-theme', chosen),
		theme
	);
	// A locator assertion rather than a polled evaluate: the client router does
	// its own first navigation, and an evaluate under a poll loses its context to
	// it (docs/reference/agent-notes.md).
	await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
}

/** The day, with every chart it is going to draw already drawn.
 *
 * **The scroll is not optional.** A story asks for its marks when it is nearly
 * on screen, so a `goto` and a wait draws whatever happened to start near the
 * top - and a comparison taken over that is a comparison over a different set
 * of stories each time. One viewport at a time, because a jump to the bottom
 * steps over every slot in between
 * (`docs/reference/agent-notes/browser.md`).
 *
 * **It waits for the count to settle rather than for the slots to empty.** A
 * story whose marks were refused keeps its zero-height slot for ever, which is
 * the degrade rule working - so a wait on "no slot is left" can only pass on a
 * day where nothing was refused, which is the one case the refusal arms are not
 * testing.
 */
async function drawnDay(page: Page, route = DAY): Promise<void> {
	await page.goto(route);
	await dayReady(page);
	await page.evaluate(async () => {
		for (let at = 0; at < document.body.scrollHeight; at += window.innerHeight) {
			window.scrollTo(0, at);
			await new Promise((wake) => setTimeout(wake, 60));
		}
		window.scrollTo(0, 0);
	});
	let settled = -1;
	await expect
		.poll(async () => {
			const now = await page.locator('main article figure svg').count();
			const same = now === settled;
			settled = now;
			return same;
		})
		.toBe(true);
}

/** Every marks file the canary day declares, in payload order.
 *
 * Read off the committed canary payload rather than off the page, so an arm
 * that stops a fetch still knows what the day promised.
 */
function declared(): string[] {
	const day = join(CANARY, '2026', '08', '20');
	const payload = JSON.parse(readFileSync(join(day, 'digest.json'), 'utf8')) as {
		items: { visual: { state: string; data_path?: string | null } | null }[];
	};
	const paths: string[] = [];
	for (const item of payload.items) {
		if (item.visual?.state === 'rendered' && item.visual.data_path) paths.push(item.visual.data_path);
	}
	return paths;
}

/** The first bar name of every chart the page drew, which names the chart. */
function drawnCharts(page: Page): Promise<string[]> {
	return page.evaluate(() =>
		[...document.querySelectorAll('main article figure svg')].map(
			(svg) => svg.querySelector('text.name')?.textContent ?? ''
		)
	);
}

/** The marks file behind a chart the page drew, found by its first bar name.
 *
 * The page runs newest first and the payload publishes in scored order, so the
 * two lists are not the same order - and an arm that assumed they were would
 * refuse the wrong file and pass for the wrong reason.
 */
function fileDrawing(name: string): string {
	for (const path of declared()) {
		const data = JSON.parse(readFileSync(join(CANARY, '..', path), 'utf8')) as VisualData;
		const first = data.marks.find((mark) => mark.mark_id === data.encoding.category[0]);
		if ((first?.text ?? '') === name) return path;
	}
	throw new Error(`no canary marks file draws a first bar called ${JSON.stringify(name)}`);
}

test.describe('the browser draws the chart', () => {
	test('a story with marks carries one drawing and no image', async ({ page }) => {
		await drawnDay(page);
		const figures = await page.evaluate(() =>
			[...document.querySelectorAll('main article figure')].map((figure) => ({
				svg: figure.querySelectorAll('svg').length,
				img: figure.querySelectorAll('img').length,
				label: figure.getAttribute('aria-label') ?? ''
			}))
		);
		expect(figures.length, 'the canary day drew no visual at all').toBeGreaterThan(0);
		for (const figure of figures) {
			expect(figure.svg, 'a figure holds none or more than one drawing').toBe(1);
			expect(figure.img, 'a story arrived on the image carrier').toBe(0);
		}
	});

	test('no story anywhere on the page is left on an image', async ({ page }) => {
		await drawnDay(page);
		await expect(page.locator('main img')).toHaveCount(0);
	});

	test('the drawing keeps the sentence that repeats its numbers', async ({ page }) => {
		// The visual is never the only carrier of a fact, and it is the WHOLE of
		// what a reader with JavaScript off receives - the drawing is built by a
		// script now, and this sentence is not.
		await drawnDay(page);
		const labels = await page
			.locator('main article figure[role="img"]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('aria-label') ?? ''));
		expect(labels.length).toBeGreaterThan(0);
		for (const label of labels) expect(label.length).toBeGreaterThan(0);
	});

	test('a visual is asked for once, as data rather than as a picture', async ({ page }) => {
		const asked: string[] = [];
		page.on('request', (request) => {
			const url = request.url();
			if (/\/digest\/\d{4}\/\d{2}\/\d{2}\/[a-z0-9-]+\.json$/.test(url)) asked.push(url);
		});
		await page.goto(DAY, { waitUntil: 'networkidle' });

		expect(asked.length, 'no story asked for its marks').toBeGreaterThan(0);
		expect(asked.length, 'a visual was asked for more than once').toBe(new Set(asked).size);
		await expect(page.locator('main img'), 'a drawing arrived on an image').toHaveCount(0);
		expect(
			await page.locator('main article figure svg rect.bar').count(),
			'nothing was drawn from what arrived'
		).toBeGreaterThan(0);
	});

	test('a story whose marks never arrive is simply shorter', async ({ page }) => {
		// The degrade rule, made to fire on a real page.
		//
		// **One story's file is refused and its sibling is left alone**, because a
		// day where nothing drew is equally consistent with the arm never having
		// run (`docs/reference/agent-notes/browser.md`). The control is the other
		// chart, which has to still be there.
		await drawnDay(page);
		const both = await drawnCharts(page);
		expect(both.length, 'the canary day drew fewer than two charts').toBe(2);

		const refused = fileDrawing(both[0]);
		await page.route(`**/${refused}`, (route) => route.fulfill({ status: 404, body: '' }));
		await drawnDay(page);

		const left = await drawnCharts(page);
		expect(left, 'the refused story kept its chart').not.toContain(both[0]);
		expect(left, 'the control story lost its chart too').toContain(both[1]);
		await expect(page.locator('main img')).toHaveCount(0);
		expect(
			await page.locator('main article').count(),
			'the stories went with the chart'
		).toBeGreaterThan(0);
	});

	test('a story whose marks do not fit their type is simply shorter', async ({ page }) => {
		// Four names against three figures: the mis-shaped payload the flat mark
		// pool exists to be able to express, and the one the page has to refuse
		// rather than draw short. Its sibling is the control again.
		await drawnDay(page);
		const both = await drawnCharts(page);
		expect(both.length, 'the canary day drew fewer than two charts').toBe(2);

		const broken = fileDrawing(both[0]);
		await page.route(`**/${broken}`, async (route) => {
			const data = (await (await route.fetch()).json()) as VisualData;
			data.encoding.quantity = data.encoding.quantity.slice(0, -1);
			return route.fulfill({ json: data });
		});
		await drawnDay(page);

		const left = await drawnCharts(page);
		expect(left, 'a mis-shaped document was drawn').not.toContain(both[0]);
		expect(left, 'the control story lost its chart too').toContain(both[1]);
	});
});

test.describe('THE ORACLE: one set of marks draws one picture', () => {
	/**
	 * The row's own oracle: the same data drawn twice in one page session and
	 * once in a fresh page load produces the same marks - same count, same
	 * values, same positions after rounding.
	 *
	 * It replaces a build-time one that compared two renders of a spec for byte
	 * identity. That one passed for the wrong reason - its spec carried no title,
	 * so it emitted no clip path, and the renderer's clip-path counter was
	 * process-global. Determinism moved to the data and the drawing code, and
	 * this is where it is now checked.
	 */

	test('a redraw in one session places every mark where the first draw did', async ({ page }) => {
		await drawnDay(page);
		const first = await drawnBars(page);
		expect(first.flat().length, 'the canary day drew no bar').toBeGreaterThan(0);

		// Away and back through the client router, so the component unmounts, the
		// fetch runs again and the geometry is recomputed inside one page session.
		await page.getByRole('link', { name: /archive/i }).first().click();
		await page.waitForURL(/archive/);
		await drawnDay(page);

		expect(await drawnBars(page)).toEqual(first);
	});

	test('a fresh page load places every mark where the first load did', async ({ page }) => {
		await drawnDay(page);
		const first = await drawnBars(page);

		await page.reload();
		await dayReady(page);
		await expect(page.locator('main article figure svg rect.bar').first()).toBeVisible();

		expect(await drawnBars(page)).toEqual(first);
	});
});

test.describe('THE ORACLE: a drawn bar is a figure the article states', () => {
	/**
	 * The canary day's first visual is compiled rather than written out by hand:
	 * `build_canary_day.py` puts the committed plan below through `compile_bar`
	 * over the committed element table below, and the file the page fetches is
	 * what came out. So the numbers on the page can be re-derived here from the
	 * same table the compiler read, and a chart that shows numbers can be told
	 * from a chart that shows THIS article's numbers.
	 */
	const FIXTURES = resolve(ROOT, 'tests', 'fixtures', 'visual-validator');
	const PLAN = JSON.parse(readFileSync(join(FIXTURES, 'plans', 'passes.json'), 'utf8')) as {
		encodings: { category: string[]; quantity: string[] };
	};
	const TABLE = JSON.parse(readFileSync(join(FIXTURES, 'tables', 'wind.json'), 'utf8')) as {
		elements: { element_id: string; span_excerpt: string; value: string | null }[];
	};
	const STATED = new Map(TABLE.elements.map((element) => [element.element_id, element]));

	/** What the article says each bar is called, in the plan's own channel order. */
	const NAMES = PLAN.encodings.category.map((id) => STATED.get(id)?.span_excerpt ?? '');
	/** And how big each one is, read out of the same table. */
	const FIGURES = PLAN.encodings.quantity.map((id) => Number(STATED.get(id)?.value));

	test('every bar on the page is as long as the figure its element states', async ({ page }) => {
		await drawnDay(page);

		const charts = await drawnBars(page);
		const compiled = charts.find((bars) => bars[0]?.name === NAMES[0]);
		expect(compiled, `no drawing on ${DAY} is the compiled one`).toBeDefined();
		expect(compiled!.map((bar) => bar.name)).toEqual(NAMES);
		expect(compiled!.map((bar) => bar.stated)).toEqual(
			PLAN.encodings.quantity.map((id) => STATED.get(id)?.value)
		);

		// One pixel is the same quantity on every bar. A bar drawn from another
		// story's figure, or a channel read in the wrong order, puts a second
		// entry in this set. The longest bar sets the scale, so it is compared
		// against the longest figure rather than against an invented span.
		const longest = Math.max(...FIGURES);
		const widest = Math.max(...compiled!.map((bar) => bar.width));
		for (const [at, bar] of compiled!.entries()) {
			expect(
				Math.abs(bar.width - Math.round((FIGURES[at] / longest) * widest)),
				`${bar.name} is drawn at ${bar.width} for a figure of ${FIGURES[at]}`
			).toBeLessThanOrEqual(1);
		}
	});
});

test.describe('THE ORACLE: a drawn string can be measured against the floor', () => {
	/**
	 * The second oracle, because the first one cannot see the reader. This row
	 * asserts only that the browser path can be MEASURED at all - enforcing the
	 * legibility floor is row #4's job, and row #4 cannot start until something
	 * measurable is drawing.
	 */
	test.use({ viewport: { width: 390, height: 900 } });

	test('every drawn string resolves to a size on a 390 px screen', async ({ page }) => {
		await drawnDay(page);

		const sizes = await page.evaluate(() => {
			const floor = getComputedStyle(document.documentElement).getPropertyValue('--text-xs');
			const probe = document.createElement('div');
			probe.style.fontSize = floor;
			document.body.append(probe);
			const px = parseFloat(getComputedStyle(probe).fontSize);
			probe.remove();
			const drawn = [...document.querySelectorAll('main figure svg text')].map((node) => {
				const rect = node.getBoundingClientRect();
				return { text: node.textContent ?? '', px: rect.height };
			});
			return { floor: px, drawn };
		});

		expect(sizes.floor, '--text-xs did not resolve to a size').toBeGreaterThan(0);
		expect(sizes.drawn.length, 'the drawing carries no string to measure').toBeGreaterThan(0);
		for (const string of sizes.drawn) {
			expect(string.px, `"${string.text}" has no measurable height`).toBeGreaterThan(0);
		}
	});
});

test.describe('THE ORACLE: every drawn colour comes from a token', () => {
	test('a bar takes the page own chart colour, in both themes', async ({ page }) => {
		await drawnDay(page);
		const seen: Record<string, string> = {};
		for (const theme of THEMES) {
			await wearing(page, theme);
			const token = await tokenColour(page, '--chart-1');
			const bars = await painted(page, 'rect.bar', 'fill');
			expect(bars.length, `${theme}: the canary chart drew no bar`).toBeGreaterThan(0);
			for (const bar of bars) expect(bar, `${theme}: a bar is not on the token`).toBe(token);
			seen[theme] = token;
		}
		// The half a literal cannot pass. One hex satisfies one arm at most.
		expect(seen.light, 'the two themes paint --chart-1 the same').not.toBe(seen.dark);
	});

	test('the drawn type takes the page own text colours, in both themes', async ({ page }) => {
		await drawnDay(page);
		for (const theme of THEMES) {
			await wearing(page, theme);
			const quiet = await tokenColour(page, '--color-text-secondary');
			const ink = await tokenColour(page, '--color-text');
			expect(quiet, `${theme}: the two text tokens are the same colour`).not.toBe(ink);

			const names = await painted(page, 'text.name', 'fill');
			expect(names.length, `${theme}: the chart drew no bar name`).toBeGreaterThan(0);
			for (const name of names) expect(name, `${theme}: a bar name is not on a token`).toBe(quiet);

			const figures = await painted(page, 'text.figure', 'fill');
			expect(figures.length, `${theme}: the chart drew no figure`).toBeGreaterThan(0);
			for (const figure of figures) {
				expect(figure, `${theme}: a figure is not on the page ink`).toBe(ink);
			}
		}
	});

	test('the axis line takes its own token, in both themes', async ({ page }) => {
		await drawnDay(page);
		for (const theme of THEMES) {
			await wearing(page, theme);
			const axis = await tokenColour(page, '--chart-axis');
			const rules = await painted(page, 'line.axis', 'stroke');
			expect(rules.length, `${theme}: the chart drew no axis line`).toBeGreaterThan(0);
			for (const rule of rules) expect(rule, `${theme}: an axis line is not on the token`).toBe(axis);
		}
	});
});

test.describe('what may not be drawn', () => {
	/** The compiled marks the canary publishes, read off disk. */
	function compiled(): VisualData {
		return JSON.parse(readFileSync(join(CANARY, '..', declared()[0]), 'utf8')) as VisualData;
	}

	test('the ordinary document is accepted, so the refusals below mean something', () => {
		const data = compiled();
		expect(
			refusedVisualData(data),
			'a clean document was refused, so every case below is vacuous'
		).toBeNull();
		expect(drawBars(data).bars.length, 'a clean document drew no bar').toBeGreaterThan(0);
	});

	for (const [name, path] of [
		['a walk out of the digest tree', 'digest/2026/08/20/../../../../etc/passwd'],
		['an address somewhere else', 'https://example.invalid/x.json'],
		['a file that is not a visual', 'digest/2026/08/20/ai.js'],
		['the day payload itself', 'digest/2026/08/20/digest.json'],
		['a date that is not one', 'digest/20xx/08/20/ai.json']
	] as const) {
		test(`${name} is never asked for`, () => {
			// The path is about to be joined onto `base` and fetched. It came off a
			// committed payload rather than off the web and it is still matched
			// rather than trusted (Guardrail #11).
			expect(publishedVisualData(path), `${path} was accepted as a published visual`).toBe(false);
		});
	}

	test('a published marks path is recognised as one', () => {
		expect(publishedVisualData('digest/2026/08/20/energy-4821903756.json')).toBe(true);
	});

	for (const [name, breaks] of [
		[
			'a renderer this page does not know',
			(data: VisualData) => {
				data.renderer_version = '2099-01-01';
			}
		],
		[
			'a type this page cannot draw',
			(data: VisualData) => {
				data.type = 'pie';
			}
		],
		[
			'four names against three figures',
			(data: VisualData) => {
				data.encoding.quantity = data.encoding.quantity.slice(0, -1);
			}
		],
		[
			'a channel naming a mark that is not carried',
			(data: VisualData) => {
				data.encoding.category = [...data.encoding.category.slice(1), 'm99'];
			}
		],
		[
			'a bar with no figure',
			(data: VisualData) => {
				const drawn = data.marks.find((mark) => mark.value !== null);
				if (drawn) drawn.value = null;
			}
		],
		[
			'no marks at all',
			(data: VisualData) => {
				data.marks = [];
			}
		]
	] as const) {
		test(`${name} is refused rather than drawn`, () => {
			const data = compiled();
			breaks(data);
			expect(refusedVisualData(data), `${name} was accepted`).not.toBeNull();
		});
	}

	test('a document that is not one at all is refused', () => {
		expect(refusedVisualData(null)).not.toBeNull();
		expect(refusedVisualData('<svg/>')).not.toBeNull();
		expect(refusedVisualData([])).not.toBeNull();
	});
});
