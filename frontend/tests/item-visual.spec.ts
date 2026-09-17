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
 * whole of what such a reader receives - and the case below reads it back off a
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
 * day where nothing was refused, which is the one case the refusal tests are not
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
 * Read off the committed canary payload rather than off the page, so a case
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
 * two lists are not the same order - and a case that assumed they were would
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
		// day where nothing drew is equally consistent with the case never having
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

test.describe('THE ORACLE: every fact is reachable without a mouse', () => {
	/**
	 * No fact exists only on hover, and the check is a comparison of two SETS.
	 *
	 * **Asserting that some keyboard route exists is not the check.** The defect
	 * this row hunts is always one fact that only a pointer reaches, so a case
	 * that stops at "the figure has a name" passes on the day a bar goes missing
	 * from that name. Both sides are enumerated and compared whole, and both are
	 * printed when they differ.
	 *
	 * **The pointer side is read off the drawn DOM**, node by node - the names,
	 * the figures and the unit the browser actually painted. **The keyboard side
	 * is read by pressing Tab**, from the top of the document, taking what each
	 * stop announces. Neither side is computed from the other.
	 *
	 * Two things this catches that the page passed before 2026-09-14: a figure
	 * that is not in the tab order at all, and an announcement cut short so the
	 * last bars are drawn and never spoken.
	 */

	/** Every fact the drawing paints, per figure, in document order.
	 *
	 * A fact is what one bar says: its name, its figure, and the unit the axis
	 * counts. The three come off three separate nodes the browser placed.
	 */
	function byPointer(page: Page): Promise<string[][]> {
		return page.evaluate(() =>
			[...document.querySelectorAll('main article figure svg')].map((svg) => {
				const names = [...svg.querySelectorAll('text.name')].map((node) => node.textContent ?? '');
				const figures = [...svg.querySelectorAll('text.figure')].map(
					(node) => node.textContent ?? ''
				);
				const unit = svg.querySelector('text.unit')?.textContent ?? '';
				return names.map(
					(name, at) => `${name} ${figures[at] ?? ''}${unit ? ` ${unit}` : ''}`
				);
			})
		);
	}

	/** What one announcement lists, split back into the facts a reader hears. */
	function heard(announced: string): string[] {
		return announced
			.replace(/^Bar chart\.\s*/, '')
			.replace(/\.\s*$/, '')
			.split(';')
			.map((clause) => clause.trim())
			.filter((clause) => clause.length > 0);
	}

	/** Tab from the top of the document and take what every figure announces.
	 *
	 * It walks until focus leaves the document, which is what tabbing past the
	 * last stop does, so a figure missing from the tab order returns one fewer
	 * list rather than an exception. The bound is a stop against a page that
	 * cycles focus rather than a count anybody measured.
	 */
	async function byKeyboard(page: Page): Promise<string[][]> {
		await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
		const reached: string[][] = [];
		for (let press = 0; press < 500; press += 1) {
			await page.keyboard.press('Tab');
			const stop = await page.evaluate(() => {
				const node = document.activeElement;
				if (!(node instanceof Element) || node === document.body) return null;
				return node.matches('main article figure') ? (node.getAttribute('aria-label') ?? '') : '';
			});
			if (stop === null) break;
			if (stop !== '') reached.push(heard(stop));
		}
		return reached;
	}

	test('the set a keyboard reaches is the set a pointer reaches', async ({ page }) => {
		await drawnDay(page);
		const drawn = await byPointer(page);
		expect(drawn.flat().length, 'the canary day drew no fact to compare').toBeGreaterThan(0);

		const tabbed = await byKeyboard(page);
		expect(
			tabbed,
			`by pointer: ${JSON.stringify(drawn)}\nby keyboard: ${JSON.stringify(tabbed)}`
		).toEqual(drawn);
	});

	test('a figure announces every string it painted and invents none', async ({ page }) => {
		// The same comparison without the sentence's own shape in it: every string
		// the browser put on screen, against the characters the announcement
		// carries. This is the case that catches a figure re-written on its way to
		// the announcement - `1,200` spoken for a `1200` drawn.
		await drawnDay(page);
		const figures = await page.evaluate(() =>
			[...document.querySelectorAll('main article figure')].map((figure) => ({
				announced: figure.getAttribute('aria-label') ?? '',
				painted: [...figure.querySelectorAll('svg text')].map((node) => node.textContent ?? '')
			}))
		);
		expect(figures.length, 'the canary day drew no figure').toBeGreaterThan(0);
		for (const figure of figures) {
			for (const string of figure.painted) {
				expect(
					figure.announced,
					`"${string}" is drawn and not announced: ${JSON.stringify(figure.announced)}`
				).toContain(string);
			}
			// A decimal part only counts when a digit follows the point, or the full
			// stop that ends the sentence joins the last figure.
			const spoken = figure.announced.match(/\d[\d,]*(?:\.\d+)?/g) ?? [];
			for (const number of spoken) {
				expect(
					figure.painted,
					`${number} is announced and never drawn: ${JSON.stringify(figure.painted)}`
				).toContain(number);
			}
		}
	});

	test('the platform reads the figure by the sentence, not by its marks', async ({ page }) => {
		// The accessible name as the browser computes it rather than as we wrote
		// it, so a role that swallowed the name would show here.
		await drawnDay(page);
		const drawn = (await byPointer(page))[0];
		await expect(page.locator('main article figure[role="img"]').first()).toHaveAccessibleName(
			`Bar chart. ${drawn.join('; ')}.`
		);
	});

	test('a chart at the mark ceiling is announced whole', async ({ page }) => {
		// **Built rather than found.** The canary's charts carry four bars and
		// three, and the case that breaks is the one the archive has never
		// produced: `visuals.max_chart_points` is 8 and a bar name may run to 40
		// characters, so eight ordinary names pass 300 characters - the cap the
		// compiled sentence was cut at. The bars all draw; before 2026-09-14 the
		// last of them were drawn and never spoken.
		await drawnDay(page);
		const target = fileDrawing((await drawnCharts(page))[0]);
		const names = [
			'Northern offshore wind consortium',
			'Southern coastal generation trust',
			'Eastern estuary tidal partnership',
			'Western highland hydro authority',
			'Central lowland solar cooperative',
			'Coastal interconnector operator',
			'National grid balancing reserve',
			'Island community microgrid'
		];
		await page.route(`**/${target}`, async (route) => {
			const data = (await (await route.fetch()).json()) as VisualData;
			data.marks = [
				...names.map((text, at) => ({
					mark_id: `c${at}`,
					text,
					value: null,
					unit: null,
					element_id: `e${at}`,
					derived: null
				})),
				...names.map((_, at) => ({
					mark_id: `q${at}`,
					text: null,
					value: String(1100 + at * 370),
					unit: 'mw',
					element_id: `f${at}`,
					derived: null
				}))
			];
			data.encoding.category = names.map((_, at) => `c${at}`);
			data.encoding.quantity = names.map((_, at) => `q${at}`);
			return route.fulfill({ json: data });
		});
		await drawnDay(page);

		const drawn = await byPointer(page);
		const wide = drawn.find((facts) => facts.length === names.length);
		expect(wide, `no figure drew ${names.length} bars: ${JSON.stringify(drawn)}`).toBeDefined();

		const tabbed = await byKeyboard(page);
		expect(
			tabbed,
			`by pointer: ${JSON.stringify(drawn)}\nby keyboard: ${JSON.stringify(tabbed)}`
		).toEqual(drawn);
	});
});

test.describe('THE ORACLE: a drawn string can be measured against the floor', () => {
	/**
	 * The second oracle, because the first one cannot see the reader. This
	 * asserts only that the browser path can be MEASURED at all - enforcing the
	 * legibility floor is a separate job, and it cannot start until something
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

test.describe('THE ORACLE: the drawing takes the width it is given', () => {
	/**
	 * Row #2's oracle. At three widths the drawn plot is as wide as the box the
	 * card gave it, and it was laid out at that width rather than laid out at a
	 * fixed one and stretched to fit - both read off the elements the browser
	 * placed, never back out of the stylesheet that set them.
	 *
	 * **The second half is the half that bites, and the first half alone would be
	 * vacuous.** An svg with `width: 100%` fills its card whatever its `viewBox`
	 * says, so "the plot is as wide as its card" passed before this row as well
	 * as after it - the old drawing was 720 units stretched onto a 343 px phone
	 * and its ELEMENT still measured 343. What changed is the scale between the
	 * two, so the assertion that can fail is that one drawn unit is one CSS
	 * pixel. That is still a browser measurement: `drawn` comes from layout and
	 * the `viewBox` is what the drawing asked for, so the ratio says whether the
	 * browser had to resize what the drawing placed.
	 *
	 * **The width tolerance is one CSS pixel and it is one-sided.** The room is
	 * floored to whole pixels before the marks are placed (`$lib/visual/width`
	 * says why: a drawing rounded up is wider than the box it was measured in,
	 * which resizes the box, which reports a new width). So the honest bound is
	 * that the plot is never wider than its container and never more than one
	 * pixel narrower. A tolerance stated as a percentage would pass a drawing 14
	 * pixels short at 1440 and fail the same drawing 4 pixels short at 360, which
	 * is the wrong way round: the defect this row removes is a fixed box
	 * stretched to fit, and a fixed box is off by hundreds of pixels or by none.
	 *
	 * **The scale tolerance is half a percent**, which is the fractional pixel
	 * the flooring leaves: at the narrowest width a card is about 300 px, so one
	 * floored pixel is a third of a percent.
	 *
	 * **Three widths rather than one, because one cannot see a fixed box.** A
	 * drawing that is always 720 units wide reports one drawn width at every
	 * viewport, so the last case reads the placed geometry at the narrowest and
	 * the widest and says they differ.
	 */

	/** Every chart on the page: how wide it drew, what it asked for, and what it was given. */
	function plots(
		page: Page
	): Promise<{ drawn: number; units: number; room: number; viewport: number }[]> {
		return page.evaluate(() =>
			[...document.querySelectorAll('main article figure')].flatMap((figure) => {
				const svg = figure.querySelector('svg');
				if (!svg) return [];
				const style = getComputedStyle(figure);
				// The content box, taken off the fractional border-box rather than
				// off `clientWidth`, which a browser rounds to a whole pixel and
				// would spend the whole tolerance before the drawing is looked at.
				const room =
					figure.getBoundingClientRect().width -
					parseFloat(style.paddingLeft) -
					parseFloat(style.paddingRight) -
					parseFloat(style.borderLeftWidth) -
					parseFloat(style.borderRightWidth);
				return [
					{
						drawn: svg.getBoundingClientRect().width,
						units: svg.viewBox.baseVal.width,
						room,
						viewport: window.innerWidth
					}
				];
			})
		);
	}

	/** The widths a reader actually holds: a small phone, a common phone, a desktop. */
	const WIDTHS = [360, 390, 1440] as const;

	/** How far from one pixel a unit may resolve, as a share. */
	const SCALE_TOLERANCE = 0.005;

	/**
	 * Whether the page has finished answering a viewport change.
	 *
	 * **Both readings are taken inside the page, a rendering frame apart**, and
	 * that is the whole of the fix for a wait that used to pass over a drawing
	 * which had not moved yet. The width reaches the drawing through a resize
	 * watcher, which the browser delivers in the rendering update that follows
	 * the layout change - so a reading taken before that frame and a reading
	 * taken after it cannot agree, and two that do agree are both past it.
	 *
	 * **A reading pair separated by a round trip instead cannot see a widening
	 * resize at all.** The card is CSS and grows the moment the viewport does;
	 * the svg carries its own `width` and `max-width: 100%` clamps a drawing too
	 * wide for its card but never stretches one too narrow. So when the viewport
	 * grows, nothing but the redraw moves the drawn width - and a loop whose
	 * condition is "this reading equals the one before the resize" is satisfied
	 * by exactly the state it exists to wait out. That is the defect CI caught on
	 * pull request #784: at 390 px the card had grown to 282 and the drawing was
	 * still the 252 it drew at 360.
	 *
	 * **The viewport is part of the reading**, so a pair taken before the resize
	 * reached the renderer cannot settle either.
	 *
	 * **It compares the geometry rather than judging it, so it is not the oracle
	 * wearing a timeout.** A drawing that never answers its card settles at once
	 * on the wrong numbers and fails below with its own message, which is what a
	 * fixed box stretched to fit has to do here.
	 */
	function quiet(page: Page, width: number): Promise<boolean> {
		return page.evaluate(async (asked) => {
			const geometry = () =>
				[...document.querySelectorAll('main article figure')]
					.map((figure) => {
						const svg = figure.querySelector('svg');
						return [
							figure.getBoundingClientRect().width,
							svg?.getBoundingClientRect().width ?? '',
							svg?.viewBox.baseVal.width ?? ''
						].join(':');
					})
					.join(',');
			const before = geometry();
			await new Promise((wake) => requestAnimationFrame(() => requestAnimationFrame(wake)));
			return window.innerWidth === asked && geometry() === before;
		}, width);
	}

	test('at three widths the plot is as wide as the card lets it be', async ({ page }) => {
		await drawnDay(page);

		const widest: number[] = [];
		for (const width of WIDTHS) {
			await page.setViewportSize({ width, height: 900 });
			await expect.poll(() => quiet(page, width)).toBe(true);

			const drawn = await plots(page);
			expect(drawn.length, `${width}: the page drew no chart to measure`).toBeGreaterThan(0);
			for (const plot of drawn) {
				expect(
					plot.room - plot.drawn,
					`at ${plot.viewport} CSS px the card gave ${plot.room} and the plot drew ${plot.drawn}, so the drawing is wider than its own container`
				).toBeGreaterThanOrEqual(0);
				expect(
					plot.room - plot.drawn,
					`at ${plot.viewport} CSS px the card gave ${plot.room} and the plot drew ${plot.drawn}, which is ${plot.room - plot.drawn} short of the one pixel the flooring costs`
				).toBeLessThanOrEqual(1);
				expect(plot.units, `at ${plot.viewport} CSS px the plot carries no view box`).toBeGreaterThan(
					0
				);
				expect(
					Math.abs(plot.drawn / plot.units - 1),
					`at ${plot.viewport} CSS px the drawing laid itself out ${plot.units} units wide and the browser drew it ${plot.drawn} px wide, a scale of ${(plot.drawn / plot.units).toFixed(3)} - so it is a fixed box stretched to fit rather than a drawing placed in the width it was given`
				).toBeLessThanOrEqual(SCALE_TOLERANCE);
			}
			widest.push(Math.max(...drawn.map((plot) => plot.drawn)));
		}

		expect(
			widest[widest.length - 1],
			`the plot drew ${widest[0]} at 360 and ${widest[widest.length - 1]} at 1440, so it is one box scaled rather than a drawing that takes the width`
		).toBeGreaterThan(widest[0]);
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
		// The half a literal cannot pass. One hex satisfies one case at most.
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
		expect(drawBars(data, 600).bars.length, 'a clean document drew no bar').toBeGreaterThan(0);
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
