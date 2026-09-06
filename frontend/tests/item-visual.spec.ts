import { expect, test, type Page } from '@playwright/test';
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { keepDrawings } from '../src/lib/day-shape';
import { publishedVisual, refusedDrawing } from '../src/lib/payload/drawing';
import { projectDay } from '../src/lib/payload/project';
import { whenNear } from '../src/lib/reveal';
import { dayShell, publishedDates } from '../src/lib/server/payload';
import type { DigestItem, SeededVisual } from '../src/lib/payload/types';

/**
 * A published drawing has to read the page it is printed on.
 *
 * Until 2026-09-05 every chart shipped inside an `img`. That is a separate
 * document: it reads none of the page's custom properties, so the renderer's
 * baked colours were the only colours it could ever have - black axis type on a
 * near-black card. The stories a prerendered document carries now hold the
 * drawing itself, and the page repaints it from its own tokens.
 *
 * **The grid-line arm below is the one part of this file no reader has ever
 * needed.** Counted 2026-09-05 over all 351 drawings the 15 committed days
 * hold: every one carries a bar, an axis label and an axis line, and none
 * carries a grid line, because `chart_spec()` writes `"axis": {"grid": false}`
 * on every spec it builds. The canary fixture's spec is hand-written and leaves
 * the grid at the renderer's default, so this file is the only place
 * `--chart-grid` is exercised at all. It is checked anyway, as insurance for
 * the day a renderer starts emitting a grid - baked at #ddd, that grid would be
 * near-white across the bars on the dark theme.
 *
 * **The `img` is gone rather than kept for the stories past that seed.** Those
 * fetch the same file and inline the same markup, so one scroll shows one
 * treatment; a drawing that does not arrive leaves the story shorter and draws
 * nothing at all. The canary day is eight stories against a seed of fifteen, so
 * nothing here can reach that fetch in a browser - what this file holds is the
 * refusal the browser runs before the fetched markup is allowed into the
 * document, and the page-wide assertion that no story is left on an image.
 *
 * **The oracle is an equality against a token, never against a hex.** Each test
 * below plants a probe element, sets its `background-color` to the same custom
 * property the stylesheet routes the mark to, and reads what the document
 * computed. The two themes give that property two different values, so a
 * drawing that kept a baked colour fails one arm whichever colour it kept - and
 * a test written against a literal would have to be edited every time the
 * palette moves, which is how a colour test stops being one.
 *
 * **The watcher arm at the foot of this file is driven directly rather than in
 * a browser, for the same reason the fetch is not exercised here.** A waiting
 * story is one past the document's seed, the seed is fifteen and the canary day
 * is eight, so a canary page holds no waiting story and a count taken there
 * would read zero however many watchers the page builds. The reveal is a rule
 * the fixture cannot stress, so it lives in its own module and the test drives
 * it with a stand-in watcher; the browser half is the section 12 smoke on the
 * real build, where a day has stories past the seed.
 */

const ROOT = resolve(process.cwd(), '..');
const CANARY = resolve(ROOT, 'backend', 'var', 'canary', 'digest');

/** The canary day, which publishes one chart and one diagram. */
const DAY = '/2026-08-20/';

const THEMES = ['light', 'dark'] as const;

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
			[...document.querySelectorAll(`main figure ${query}`)].map(
				(node) => getComputedStyle(node).getPropertyValue(name)
			),
		{ selector, property }
	);
}

async function wearing(page: Page, theme: string): Promise<void> {
	await page.evaluate((chosen) => document.documentElement.setAttribute('data-theme', chosen), theme);
	// A locator assertion rather than a polled evaluate: the client router does
	// its own first navigation, and an evaluate under a poll loses its context to
	// it (docs/reference/agent-notes.md).
	await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
}

test.describe('the drawing is in the document', () => {
	test('a seeded story carries one svg and no image', async ({ page }) => {
		await page.goto(DAY);
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
			expect(figure.img, 'a seeded story is still on the image carrier').toBe(0);
		}
	});

	test('no story anywhere on the page is left on an image', async ({ page }) => {
		// The half of row 2's oracle a canary day can answer. The carrier is gone
		// rather than kept for the stories past the seed, so the page-wide count is
		// zero and not "zero among the seeded ones" - two treatments on one scroll
		// is what reads as a broken site.
		await page.goto(DAY);
		await expect(page.locator('main img')).toHaveCount(0);
	});

	test('the drawing keeps the sentence that repeats its numbers', async ({ page }) => {
		// The visual is never the only carrier of a fact, and an inlined svg has
		// no `alt` to carry it. The label moves to the figure, which `role="img"`
		// makes one named image rather than a tree of unnamed marks.
		await page.goto(DAY);
		const labels = await page
			.locator('main article figure[role="img"]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('aria-label') ?? ''));
		expect(labels.length).toBeGreaterThan(0);
		for (const label of labels) expect(label.length).toBeGreaterThan(0);
	});

	test('no drawing is fetched for a story the document already carries', async ({ page }) => {
		// One fewer request per seeded story is the other half of what inlining
		// bought. A drawing that is still requested is one that did not inline.
		const asked: string[] = [];
		page.on('request', (request) => {
			if (request.url().endsWith('.svg')) asked.push(request.url());
		});
		await page.goto(DAY, { waitUntil: 'networkidle' });
		expect(asked).toEqual([]);
	});
});

test.describe('THE ORACLE: every drawn colour comes from a token', () => {
	test('a bar takes the page own chart colour, in both themes', async ({ page }) => {
		await page.goto(DAY);
		const seen: Record<string, string> = {};
		for (const theme of THEMES) {
			await wearing(page, theme);
			const token = await tokenColour(page, '--chart-1');
			const bars = await painted(page, '.mark-rect > path', 'fill');
			expect(bars.length, `${theme}: the canary chart drew no bar`).toBeGreaterThan(0);
			for (const bar of bars) expect(bar, `${theme}: a bar kept a baked colour`).toBe(token);
			seen[theme] = token;
		}
		// The half a literal cannot pass. One hex satisfies one arm at most.
		expect(seen.light, 'the two themes paint --chart-1 the same').not.toBe(seen.dark);
	});

	test('the axis type takes the page own text colour, in both themes', async ({ page }) => {
		await page.goto(DAY);
		for (const theme of THEMES) {
			await wearing(page, theme);
			const token = await tokenColour(page, '--color-text-secondary');
			const labels = await painted(page, '.mark-text text', 'fill');
			expect(labels.length, `${theme}: the canary chart drew no axis type`).toBeGreaterThan(0);
			for (const label of labels) {
				expect(label, `${theme}: axis type kept the renderer's black`).toBe(token);
			}
		}
	});

	test('the axis lines and the grid take their own tokens, in both themes', async ({ page }) => {
		await page.goto(DAY);
		for (const theme of THEMES) {
			await wearing(page, theme);
			const axis = await tokenColour(page, '--chart-axis');
			const grid = await tokenColour(page, '--chart-grid');
			expect(axis, `${theme}: an axis and its grid are the same colour`).not.toBe(grid);

			const rules = await painted(page, '.mark-rule:not(.role-axis-grid) line', 'stroke');
			expect(rules.length, `${theme}: the canary chart drew no axis line`).toBeGreaterThan(0);
			for (const rule of rules) expect(rule, `${theme}: an axis line kept its baked grey`).toBe(axis);

			const grids = await painted(page, '.role-axis-grid line', 'stroke');
			expect(grids.length, `${theme}: the canary chart drew no grid line`).toBeGreaterThan(0);
			for (const line of grids) expect(line, `${theme}: a grid line kept its baked grey`).toBe(grid);
		}
	});

	test('a drawing that paints itself in currentColor takes the page ink', async ({ page }) => {
		// The diagram, which is not a chart and carries no class to aim at. Inside
		// an `img` its `currentColor` could only ever resolve to black; in the
		// document it is whatever the card is printing in.
		await page.goto(DAY);
		for (const theme of THEMES) {
			await wearing(page, theme);
			const ink = await tokenColour(page, '--color-text');
			const colours = await page.evaluate(() =>
				[...document.querySelectorAll('main article figure svg')].map(
					(node) => getComputedStyle(node).color
				)
			);
			expect(colours.length).toBeGreaterThan(0);
			for (const colour of colours) expect(colour, `${theme}: the drawing is not inheriting the page ink`).toBe(ink);
		}
	});
});

test.describe('the drawing survives the rest of the day arriving', () => {
	/** What a reading route hands `keepDrawings`: the day it seeded, and the same
	 * day as the served copy carries it - which is to say without the drawings,
	 * because `project.ts` keeps three named fields of a visual and this is not
	 * one of them. */
	function seededAndServed(): { seeded: DigestItem[]; served: DigestItem[] } {
		for (const date of publishedDates(CANARY)) {
			const shell = dayShell(date, 500, { root: CANARY });
			const seeded = shell?.seed ?? [];
			if (!seeded.some((item) => (item.visual as SeededVisual | null)?.markup)) continue;
			const served = JSON.parse(projectDay(JSON.stringify({ items: seeded }))).items as DigestItem[];
			return { seeded, served };
		}
		throw new Error('no canary day seeds a drawing');
	}

	test('a served story gets the drawing its seeded copy came with', () => {
		// The defect this closes: `arrived = whole.items` swaps the seed out for
		// the fetched copy, so a day page inlined its drawing and then replaced it
		// with an image a second later.
		const { seeded, served } = seededAndServed();
		expect(
			served.some((item) => (item.visual as SeededVisual | null)?.markup),
			'the served projection is carrying markup, which is the byte cost the seed exists to avoid'
		).toBe(false);

		const kept = keepDrawings(seeded, served);
		const drawn = seeded.filter((item) => (item.visual as SeededVisual | null)?.markup);
		expect(drawn.length).toBeGreaterThan(0);
		for (const item of drawn) {
			const after = kept.find((story) => story.item_id === item.item_id);
			expect((after?.visual as SeededVisual | null)?.markup, `${item.item_id} lost its drawing`).toBe(
				(item.visual as SeededVisual).markup
			);
		}
		expect(kept.map((item) => item.item_id), 'the swap changed the list').toEqual(
			served.map((item) => item.item_id)
		);
	});

	test('a story the document never seeded is handed back untouched', () => {
		const { served } = seededAndServed();
		expect(keepDrawings([], served)).toBe(served);
	});
});

test.describe('what may not be drawn, on either side of the move', () => {
	/** The canary's first published drawing: the day it is on, the story it
	 * belongs to, and the path it is served from. */
	function drawn(): { date: string; itemId: string; path: string } {
		for (const date of publishedDates(CANARY)) {
			for (const item of dayShell(date, 500, { root: CANARY })?.seed ?? []) {
				if (item.visual?.state === 'rendered' && item.visual.path) {
					return { date, itemId: item.item_id, path: item.visual.path };
				}
			}
		}
		throw new Error('no canary day publishes a rendered visual');
	}

	/** That drawing's visual, after the file behind it was replaced.
	 *
	 * The whole canary tree is copied first, so the planted bytes can never
	 * reach the tree a build reads.
	 */
	function planted(markup: string): SeededVisual | null {
		const { date, itemId, path } = drawn();
		const root = mkdtempSync(join(tmpdir(), 'item-visual-'));
		try {
			cpSync(CANARY, join(root, 'digest'), { recursive: true });
			writeFileSync(join(root, path), markup, 'utf8');
			const shell = dayShell(date, 500, { root: join(root, 'digest') })!;
			return shell.seed.find((item) => item.item_id === itemId)?.visual ?? null;
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	}

	test('the ordinary drawing does inline, so the refusals below mean something', () => {
		const source = readFileSync(join(CANARY, '..', drawn().path), 'utf8');
		expect(planted(source)?.markup, 'a clean drawing was refused, so every case below is vacuous').toBe(
			source
		);
		expect(refusedDrawing(source), 'the browser would refuse a drawing the build accepted').toBeNull();
		expect(publishedVisual(drawn().path), 'a published path was not recognised as one').toBe(true);
	});

	for (const [name, path] of [
		['a walk out of the digest tree', 'digest/2026/08/20/../../../../etc/passwd'],
		['an address somewhere else', 'https://example.invalid/x.svg'],
		['a file that is not a drawing', 'digest/2026/08/20/ai.js'],
		['a date that is not one', 'digest/20xx/08/20/ai.svg']
	] as const) {
		test(`${name} is never asked for`, () => {
			// The path is about to be joined onto a directory and read, or onto
			// `base` and fetched. It came off a committed payload rather than off the
			// web and it is still matched rather than trusted (Rule #11).
			expect(publishedVisual(path), `${path} was accepted as a published drawing`).toBe(false);
		});
	}

	for (const [name, markup] of [
		['a script element', '<svg xmlns="http://www.w3.org/2000/svg"><script>fetch("//x")</script></svg>'],
		['an inline handler', '<svg xmlns="http://www.w3.org/2000/svg"><rect onload="fetch(\'//x\')"/></svg>'],
		['embedded html', '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><b>x</b></foreignObject></svg>'],
		['a link out', '<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript:fetch(1)"><rect/></a></svg>'],
		['a fetched image', '<svg xmlns="http://www.w3.org/2000/svg"><image href="//x/y.png"/></svg>'],
		['something that is not a drawing at all', '<!doctype html><html><body>hi</body></html>']
	] as const) {
		test(`${name} is not drawn`, () => {
			// Rule #11. A chart's labels are written by a model that read a
			// stranger's page, so the moment the drawing stops being an `img` it is
			// markup in our own origin and the check is the control, not a promise.
			const visual = planted(markup);
			expect(visual?.markup ?? null, `${name} reached the document`).toBeNull();
			// The story keeps its `path`, because that is a committed field and this
			// build does not rewrite the day. What it does not keep is a picture: the
			// browser asks for the same file and runs the line below over the answer,
			// so a story whose drawing is refused is a shorter story and never a
			// broken-image glyph.
			expect(visual?.path, `${name} rewrote the committed payload`).toBeTruthy();
			expect(
				refusedDrawing(markup),
				`${name} would reach the document through the fetch instead`
			).not.toBeNull();
		});
	}
});

/** A stand-in for the browser's watcher that counts what the page built.
 *
 * The page never builds one of these in a browser - it builds the browser's
 * own. What this class adds is a count, a record of which stories are being
 * watched, and a way to say "this story just crossed" without a viewport.
 */
class Watching {
	/** How many watchers the page has built. The number this row is about. */
	static built = 0;
	/** Every watcher built, so a test can deliver a crossing through the live one. */
	static all: Watching[] = [];

	readonly watched = new Set<Element>();
	readonly margin: string;

	constructor(
		private readonly report: (entries: IntersectionObserverEntry[]) => void,
		options?: IntersectionObserverInit
	) {
		Watching.built += 1;
		Watching.all.push(this);
		this.margin = options?.rootMargin ?? '';
	}

	observe(node: Element): void {
		this.watched.add(node);
	}

	unobserve(node: Element): void {
		this.watched.delete(node);
	}

	disconnect(): void {
		this.watched.clear();
	}

	/** What the browser does when stories cross the margin, or leave it. */
	crosses(nodes: Element[], near = true): void {
		this.report(
			nodes.map((target) => ({ target, isIntersecting: near }) as IntersectionObserverEntry)
		);
	}
}

test.describe('THE ORACLE: one watcher, however many stories are waiting', () => {
	test.beforeAll(() => {
		// Node has no watcher of its own, so this installs one rather than
		// replacing one. Removed again below so nothing else in the process
		// inherits it.
		globalThis.IntersectionObserver = Watching as unknown as typeof IntersectionObserver;
	});

	test.afterAll(() => {
		Reflect.deleteProperty(globalThis, 'IntersectionObserver');
	});

	/** One waiting story's slot. The module only ever uses it as a key. */
	function slot(name: string): Element {
		return { nodeName: name } as unknown as Element;
	}

	/** The one watcher the page is allowed to hold. */
	function watcher(): Watching {
		expect(Watching.all.length, 'the page is holding more than one watcher').toBe(1);
		return Watching.all[0];
	}

	test('one watcher serves every waiting story, however many are waiting', () => {
		// Until 2026-09-06 each waiting story built its own watcher, so this count
		// was the number of stories: a day that published more drawings held more
		// watchers, for the life of the page. That is a cost that rises because a
		// run published more, which CLAUDE.md Rule #12 refuses.
		const drawn: string[] = [];
		const forget: Array<() => void> = [];
		const waitFor = (stories: number): void => {
			for (let n = 0; n < stories; n += 1) {
				const name = `story-${forget.length}`;
				forget.push(whenNear(slot(name), () => drawn.push(name)));
			}
		};

		waitFor(1);
		expect(Watching.built, 'one waiting story built no watcher').toBe(1);
		waitFor(49);
		expect(Watching.built, '50 waiting stories built more than one watcher').toBe(1);
		waitFor(450);
		expect(Watching.built, '500 waiting stories built more than one watcher').toBe(1);

		expect(watcher().watched.size, 'the one watcher is not watching every waiting story').toBe(500);
		expect(watcher().margin, 'the shared watcher lost the one-screen margin').toBe('100% 0px');
		expect(drawn, 'a story asked for its drawing before it was anywhere near').toEqual([]);

		for (const stop of forget) stop();
		expect(watcher().watched.size, 'a story that left the page is still watched').toBe(0);
	});

	test('a story that comes near draws, once, and its neighbours do not', () => {
		const drawn: string[] = [];
		const names = ['first', 'second', 'third'];
		const slots = names.map((name) => slot(name));
		const forget = slots.map((node, index) => whenNear(node, () => drawn.push(names[index])));
		try {
			watcher().crosses([slots[1]]);
			expect(drawn, 'the crossing drew the wrong story, or drew more than one').toEqual(['second']);
			expect(watcher().watched.has(slots[1]), 'a story that drew is still watched').toBe(false);
			expect(watcher().watched.has(slots[0]), 'a story that did not cross was dropped').toBe(true);
			expect(watcher().watched.has(slots[2]), 'a story that did not cross was dropped').toBe(true);

			// The reader scrolls it past and back. The story already has its answer.
			watcher().crosses([slots[1]]);
			expect(drawn, 'a story asked for the same drawing twice').toEqual(['second']);
		} finally {
			for (const stop of forget) stop();
		}
	});

	test('a story reported as not near keeps waiting', () => {
		const drawn: string[] = [];
		const node = slot('below the fold');
		const stop = whenNear(node, () => drawn.push('below the fold'));
		try {
			watcher().crosses([node], false);
			expect(drawn, 'a story drew on a report that it is not near').toEqual([]);
			expect(watcher().watched.has(node), 'a story still below the fold stopped being watched').toBe(
				true
			);
		} finally {
			stop();
		}
	});

	test('a story that leaves the page is neither watched nor drawn', () => {
		const drawn: string[] = [];
		const node = slot('gone');
		whenNear(node, () => drawn.push('gone'))();
		expect(watcher().watched.has(node), 'a story that left the page is still watched').toBe(false);
		// A browser can still deliver a crossing it recorded before the unwatch.
		watcher().crosses([node]);
		expect(drawn, 'a story that left the page still asked for its drawing').toEqual([]);
	});
});
