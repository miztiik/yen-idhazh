import { expect, test, type Page } from './support/browser';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { BAND_UNREAD, readBand, stripRoutes, type RouteId } from '../src/lib/console/band';
import { uiConfig } from '../src/lib/server/config';
import { BY_ROUTE } from './support/console-expect/console-nav';

/**
 * The console is six routes, and this file is why it is routes and not tabs.
 * Data explorer is live and is answered by the fallback document because it fetches
 * all data after JavaScript starts.
 *
 * A tab strip that switches with script fails every assertion here: with
 * JavaScript off it shows one panel set and no way to reach the others, and
 * every panel it hides still ships inside the one document. Five prerendered
 * routes with real anchors pass.
 *
 * Five things this file protects that a screenshot cannot. The labels are the
 * words the owner chose, so a paraphrase fails. The ids and the paths under
 * them did NOT move when two of the labels changed on 2026-08-31, which is what
 * makes that a rename and not a route change. The strip may never take the
 * health ramp: green, amber and red on a label would say a route is failing,
 * and a route is a noun. Since 2026-09-12 the strip has to FIT - six tabs
 * on one row at 1440 and no more than three at 360 and 320, with no box
 * overlapping another. And each route's title in the browser names that route,
 * after a tab click as well as on a page load.
 */

/** The owner's words, and the paths they sit on. Typed out on purpose: this is
 * the copy the file exists to protect, so reading it from the source it guards
 * would only prove the page agrees with itself.
 *
 * `Model` became `Summaries` and `Machine` became `Hardware` on 2026-08-31.
 * Every panel on the middle route is about a published summary and none is
 * about the model as an artefact; `Hardware` is the plainest word for a
 * processor, a memory and a clock, and unlike `Runner` it is not a term the
 * build system uses on itself (CLAUDE.md section 0b).
 *
 * `Judgement` and `Voices` joined on 2026-09-12, opened empty by the row that
 * added them; `Voices` filled on 2026-09-14 when four feed and source panels
 * moved onto it off Pipelines. `Judgement` is singular because the other three
 * name a place and this one names an act; `Voices` is the owner's word over
 * Susan's `Sources`.
 */
const ROUTES = BAND_UNREAD.routes.flatMap((route) => {
	const expected = BY_ROUTE[route.id];
	return expected === null ? [] : [{ ...expected, href: route.href }];
});
const PIPELINES = BAND_UNREAD.routes.find((route) => route.id === 'pipelines')!;
const MACHINE_ROUTES = ROUTES.filter((route) => route.machinePanels !== null);
const FALLBACK_ROUTES = ROUTES.filter((route) => route.fallbackDescription !== null);

/** The routes that still name something they do not draw.
 *
 * A strip that names a page nobody can reach is a strip that lies, so the route
 * answers, names itself, and says in plain words what is still missing.
 *
 * **A route on this list may also draw panels, and Judgement does
 * since 2026-09-17.** The absence there is not the whole page: `Stories the day
 * merged` counts what a day folded together, and the absence is about the desk
 * and the lenses the model chose, which it still does not record. The two are
 * different subjects, so the figure landing does not retire the absence - and
 * an absence that quietly disappears the first time any panel lands on the
 * route is the failure this list exists to catch.
 *
 * **It may not say what is missing by citing a plan.** A reader of this page
 * cannot open `TODO/`, and once a plan is distilled and deleted the pointer
 * names nothing at all - so the absence says what is missing, and the check
 * below refuses a plan filename or a row number instead of demanding one (owner
 * ruling, 2026-09-17).
 *
 * `Voices` was here until 2026-09-14, when the feed and source panels moved onto
 * it off Pipelines and closed its absence outright. Its own absent states are
 * still checked - `console-voices-sources.spec.ts` owns the census half and
 * `console-voices.spec.ts` owns the one-route-per-panel half.
 */
const NAMED_ABSENCES = ROUTES.flatMap((route) =>
	route.namedAbsence === null ? [] : [{ ...route.namedAbsence, href: route.href }]
);

/** What an absence may not name: a plan file, or a row inside one. */
const CITES_A_PLAN = /TODO\/\d|\brows?\s*#?\d|\bplan\s+\d/i;

/** The three verdict colours, as the tokens a stylesheet would have to name. */
const HEALTH_RAMP = ['--fill-high', '--fill-medium', '--fill-low', '--band-high', '--band-medium', '--band-low'];

/** The strip's tabs, as drawn. `evaluateAll` reads at once and never waits, and
 * Data explorer's document has no strip until its script draws one, which can be
 * after `page.goto` returns. So the read waits for the first tab: the strip draws
 * every tab in one pass. */
async function tabs(page: Page) {
	const strip = page.locator('[data-console-nav] [data-console-tab]');
	await expect(
		strip.first(),
		`${new URL(page.url()).pathname}: the strip drew no tab`
	).toBeAttached();
	return strip.evaluateAll((links) =>
		links.map((node) => ({
			id: node.getAttribute('data-console-tab') ?? '',
			href: (node as HTMLAnchorElement).getAttribute('href') ?? '',
			current: node.getAttribute('aria-current'),
			text: (node.textContent ?? '').trim()
		}))
	);
}

test.describe('the strip', () => {
	// One visit per route carries both the strip's own checks (this test) and
	// the standing band's (in "the standing band" below), instead of each
	// describe block re-visiting every route on its own: fifteen page visits
	// for the two concerns, over the original five routes, down to five -
	// with every assertion kept. A sixth route, Data explorer, joined the strip
	// later and rides the same single visit per route.
	test('each route draws the same labels, marks its own, and the band matches across routes', async ({
		page
	}) => {
		const bandByRoute: Record<string, { verdict: string; worst: string; size: string }> = {};

		for (const route of ROUTES) {
			await page.goto(route.href);

			const drawn = await tabs(page);
			expect(
				drawn.map((tab) => tab.id),
				`${route.path}: the strip does not name the same routes in order`
			).toEqual(ROUTES.map((entry) => entry.id));
			// Verbatim. A label that paraphrases the owner's word fails here.
			for (const [index, entry] of ROUTES.entries()) {
				expect(drawn[index].text, `${route.path}: ${entry.id} lost its label`).toContain(
					entry.label
				);
			}
			expect(
				drawn.filter((tab) => tab.current === 'page').map((tab) => tab.id),
				`${route.path}: exactly one label says which route this is`
			).toEqual([route.id]);

			if (!route.hasBand) {
				await expect(page.locator('[data-console-band]')).toHaveCount(0);
				continue;
			}

			// Three facts and no control. A band that grows becomes a fourth page
			// nobody chose to open, and the control governs nothing inside it.
			const facts = await page
				.locator('[data-console-band] [data-band-fact]')
				.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-band-fact') ?? ''));
			expect(facts, `${route.path}: the band does not carry exactly verdict, worst, size`).toEqual([
				'verdict',
				'worst',
				'size'
			]);
			await expect(
				page.locator('[data-console-band] [data-window-control]'),
				`${route.path}: the band carries a control`
			).toHaveCount(0);

			const band = { verdict: '', worst: '', size: '' };
			for (const key of ['verdict', 'worst', 'size'] as const) {
				const text = (
					await page.locator(`[data-console-band] [data-band-${key}]`).innerText()
				).trim();
				expect(text.length, `${route.path} left [data-band-${key}] empty`).toBeGreaterThan(20);
				band[key] = text;
			}
			bandByRoute[route.id] = band;
		}

		// Derived once for every route, so they cannot disagree about which route
		// is worst - which is the failure a per-route band eventually produces.
		const pipelines = bandByRoute[ROUTES[0].id];
		for (const route of ROUTES.slice(1).filter((entry) => entry.hasBand)) {
			expect(bandByRoute[route.id], `the band differs on ${route.path}`).toEqual(pipelines);
		}
	});

	test('THE ORACLE: a label changed and no address moved with it', async ({ page }) => {
		// Two of the three labels were rewritten on 2026-08-31. The whole risk of a
		// rename row is that a word an operator reads and a word a browser resolves
		// are the same string somewhere, so this asserts the second set did not
		// move: the tab ids, the hrefs, and the route markers each page prints.
		await page.goto(PIPELINES.href);
		const drawn = await tabs(page);
		expect(
			drawn.map((tab) => tab.id),
			'a tab id moved, which is an address and not a label'
		).toEqual(ROUTES.map((entry) => entry.id));

		for (const [index, entry] of ROUTES.entries()) {
			expect(drawn[index].href, `${entry.id} no longer points at its own route`).toContain(
				entry.path
			);
		}

		for (const entry of ROUTES.filter((route) => route.hasBand)) {
			const answered = await page.request.get(entry.href);
			expect(answered.status(), `${entry.path} stopped answering`).toBe(200);
			expect(
				await answered.text(),
				`${entry.path} no longer prints its own route marker`
			).toContain(`data-console-route="${entry.id}"`);
		}
		for (const route of FALLBACK_ROUTES) {
			const fallback = await page.request.get(route.href);
			expect([200, 404], `${route.path} is served by the fallback`).toContain(fallback.status());
		}
	});

	test('every label carries a description, and the same words as its tooltip', async ({ page }) => {
		await page.goto(PIPELINES.href);
		const drawn = await page.locator('[data-console-nav] [data-console-tab]').evaluateAll((links) =>
			links.map((node) => ({
				id: node.getAttribute('data-console-tab') ?? '',
				title: node.getAttribute('title') ?? '',
				line: (node.querySelector('.tab-line')?.textContent ?? '').trim()
			}))
		);
		expect(drawn).toHaveLength(6);
		for (const tab of drawn) {
			expect(tab.line.length, `${tab.id} has no description under its label`).toBeGreaterThan(20);
			expect(tab.title, `${tab.id}'s tooltip is not its description`).toBe(tab.line);
		}
	});

	test('every label carries its own worst state', async ({ page }) => {
		await page.goto(PIPELINES.href);
		const worst = await page
			.locator('[data-console-nav] [data-console-tab-worst]')
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					id: node.getAttribute('data-console-tab-worst') ?? '',
					text: (node.textContent ?? '').trim()
				}))
			);
		// Machine reads no ledger yet, so it always has one. A route with nothing
		// wrong carries none, which is a state and not an absence.
		expect(worst.map((entry) => entry.id)).toContain('machine');
		for (const entry of worst) {
			expect(entry.text.length, `${entry.id} carries an empty worst state`).toBeGreaterThan(0);
		}
	});

	test("the band's worst route is the one tab that says so, in a word", async ({ page }) => {
		// Every tab carries its own worst state, so which of them the band means
		// was a thing a reader had to work out by comparing sentences. Once the
		// strip sticks and the band has scrolled away it could not be worked out
		// at all. One word on one tab says it, and a word is not a verdict colour.
		await page.goto(PIPELINES.href);
		const named = await page.locator('[data-band-worst]').getAttribute('data-band-worst-route');
		const marks = page.locator('[data-console-nav] [data-console-tab-worst-mark]');
		if (named === null) {
			await expect(marks, 'a tab says it is worst while the band says nothing is').toHaveCount(0);
			return;
		}
		await expect(marks, 'the band names a worst route and no tab says so').toHaveCount(1);
		await expect(
			page.locator(`[data-console-tab="${named}"] [data-console-tab-worst-mark]`),
			`the mark is not on ${named}, the route the band names`
		).toHaveCount(1);
		expect((await marks.innerText()).trim()).toMatch(/^Worst:?$/);
	});

	test('the health ramp never touches the strip', async ({ page }) => {
		await page.goto(PIPELINES.href);
		// The rule under the active label is the categorical ramp, which names a
		// place and passes no verdict. Read off the computed style rather than the
		// source, so a token reached through a utility class is caught too.
		const painted = await page
			.locator('[data-console-nav] [data-console-tab]')
			.evaluateAll((links) =>
				links.flatMap((node) => {
					const style = getComputedStyle(node);
					return [style.color, style.backgroundColor, style.borderBottomColor];
				})
			);
		const ramp = await page.evaluate((tokens: string[]) => {
			const root = getComputedStyle(document.documentElement);
			return tokens.map((token) => root.getPropertyValue(token).trim()).filter(Boolean);
		}, HEALTH_RAMP);
		expect(ramp.length, 'the health ramp is not declared, so this proves nothing').toBe(
			HEALTH_RAMP.length
		);

		const hex = (value: string) => value.replace(/\s+/g, '').toLowerCase();
		const rgb = await page.evaluate((values: string[]) =>
			values.map((value) => {
				const probe = document.createElement('span');
				probe.style.color = value;
				document.body.appendChild(probe);
				const read = getComputedStyle(probe).color;
				probe.remove();
				return read;
			}), ramp);
		for (const colour of painted) {
			expect(rgb.map(hex), `the strip painted ${colour}, which is a verdict colour`).not.toContain(
				hex(colour)
			);
		}
	});
});

/** Each route's page title, in Reader's words: the label on its tab, then
 * `Console`. The site's own title follows, read from the config the build reads,
 * because it is not this file's copy to protect.
 *
 * Typed out on purpose, like the labels above: read from the pages it guards, it
 * would only prove a page agrees with itself. Every route sets its own, because a
 * tab click moves inside the page, and a route that sets no title keeps the one
 * the route before it set.
 */
/** The whole title a route owes: its own words, then the site's title. */
function titleOf(id: RouteId): string {
	return `${BY_ROUTE[id]!.title} \u2014 ${uiConfig().site_title}`;
}

/** Wait until a script runs the page, so a tab click is a move inside it rather
 * than a page load. The strip is marked live, and the days control enabled, on
 * mount. */
async function hydrated(page: Page) {
	await expect(page.locator('[data-console-strip]')).toHaveAttribute(
		'data-console-strip-live',
		'yes'
	);
	await expect(page.locator('[data-window-preset] input').first()).toBeEnabled();
}

test.describe('the title names the route on screen', () => {
	for (const route of ROUTES) {
		// Every route is reached from Pipelines, where an operator starts, and
		// Pipelines from the tab after it.
		const from = route.id === 'pipelines' ? ROUTES[1] : ROUTES[0];

		test(`THE ORACLE: ${route.path} names itself after a tab click from ${from.label} and on a page load`, async ({
			page
		}) => {
			await page.goto(from.href);
			await hydrated(page);
			const opened = await page.evaluate(() => performance.timeOrigin);

			await page.locator(`[data-console-nav] [data-console-tab="${route.id}"]`).click();
			await expect(page, `the ${route.label} tab did not move to ${route.path}`).toHaveURL(
				new RegExp(`${route.path}(?:[?#].*)?$`)
			);
			await expect(page, `${route.path} after a tab click from ${from.path}`).toHaveTitle(
				titleOf(route.id)
			);
			expect(
				await page.evaluate(() => performance.timeOrigin),
				'the tab loaded a new page, so this was a page load and not a tab click'
			).toBe(opened);

			await page.goto(route.href);
			await expect(page, `${route.path} on a page load`).toHaveTitle(titleOf(route.id));
		});
	}

	test('no two routes share a title', () => {
		// Each route's test above holds its page to its own entry here, so entries
		// that differ are titles that differ on screen.
		const titles = ROUTES.map((route) => titleOf(route.id));
		expect(new Set(titles).size, `two routes share a title: ${titles.join(' | ')}`).toBe(
			ROUTES.length
		);
	});
});

/** Every tab's box in page coordinates, plus the width the page really has.
 *
 * `window.innerWidth` is read inside the page and returned beside the boxes on
 * purpose: a viewport asked for and a viewport rendered are two numbers, and a
 * geometry figure quoted without the second one cannot be checked.
 */
async function stripBoxes(page: Page) {
	return page.locator('[data-console-nav] [data-console-tab]').evaluateAll((links) => ({
		innerWidth: window.innerWidth,
		clientWidth: document.documentElement.clientWidth,
		boxes: links.map((node) => {
			const box = node.getBoundingClientRect();
			return {
				id: node.getAttribute('data-console-tab') ?? '',
				top: Math.round(box.top + window.scrollY),
				left: Math.round(box.left),
				right: Math.round(box.right),
				bottom: Math.round(box.bottom + window.scrollY)
			};
		})
	}));
}

/** Widths and the rows six tabs may stand on at each.
 *
 * 1440 is where the console is read; 360 is the narrowest phone the rest of
 * this suite drives; 320 is the narrowest screen still in use and is here
 * because the basis that cleared 360 still stacked five deep there - the same
 * defect one screen narrower, found by measuring rather than by reading the
 * rule. Three rows on a phone, because the strip sits directly above the band
 * and the band is the first thing an operator reads: five rows of chrome would
 * push the verdict off a phone's first screen.
 *
 * **One row at 768.** From 731 to 871 px five 8rem tabs fit one row and a sixth
 * does not, so this is the width where the sixth tab, Data explorer, costs a row of
 * its own - and no strip test checked any width between a phone and 1440 until
 * that tab was foreseen.
 *
 * **One row at 1440, since 2026-09-27.** From `frame.breakpoints_px[1]` up the
 * strip is one row at any count of tabs - it sticks there, and a stuck strip
 * that wrapped would cover a second row of every screen - so a tab list too wide
 * for the row scrolls rather than wrapping. `console-shell.spec.ts` holds the
 * same rule with one tab more than the routes have.
 */
const STRIP_WIDTHS = [
	{ width: 1440, height: 1000, rows: 1 },
	{ width: 768, height: 1000, rows: 2 },
	{ width: 360, height: 780, rows: 3 },
	{ width: 320, height: 780, rows: 3 }
] as const;

for (const view of STRIP_WIDTHS) {
	test(`THE ORACLE: six tabs stand on at most ${view.rows} rows at ${view.width}`, async ({
		page
	}) => {
		await page.setViewportSize({ width: view.width, height: view.height });
		await page.goto(PIPELINES.href);

		const { innerWidth, clientWidth, boxes } = await stripBoxes(page);
		expect(boxes, `only ${boxes.length} tabs are drawn, so this proves nothing`).toHaveLength(6);

		// A row is a distinct top. Read off the built page rather than off the
		// rule, so a basis, a gap or a font change that breaks it fails here.
		const rows = new Set(boxes.map((box) => box.top));
		// Printed on every run, because a geometry figure without the width the
		// page really had is an assertion rather than a measurement (Guardrail #10),
		// and a passing oracle otherwise says nothing about the margin it passed by.
		console.log(
			`[strip] asked ${view.width} -> innerWidth ${innerWidth}, clientWidth ${clientWidth}, ` +
				`${rows.size} of ${view.rows} rows, boxes ` +
				boxes.map((box) => `${box.id} ${box.left}-${box.right} @${box.top}`).join(' | ')
		);
		expect(
			rows.size,
			`six tabs stand on ${rows.size} rows at innerWidth ${innerWidth} ` +
				`(clientWidth ${clientWidth}), over the ${view.rows} this width allows: ` +
				boxes.map((box) => `${box.id}@${box.left}-${box.right}x${box.top}`).join(' ')
		).toBeLessThanOrEqual(view.rows);

		// And no box sits on another. Flex cannot normally produce one, so this
		// catches the thing that can: a negative margin, an absolute position, or
		// a min-width that makes a slot wider than the row it is in.
		for (const [index, box] of boxes.entries()) {
			for (const other of boxes.slice(index + 1)) {
				const overlaps =
					box.left < other.right &&
					other.left < box.right &&
					box.top < other.bottom &&
					other.top < box.bottom;
				expect(
					overlaps,
					`${box.id} and ${other.id} overlap at innerWidth ${innerWidth}: ` +
						`${box.left}-${box.right}x${box.top}-${box.bottom} against ` +
						`${other.left}-${other.right}x${other.top}-${other.bottom}`
				).toBe(false);
			}
		}
	});
}

test.describe('the routes that name something they do not draw', () => {
	for (const route of NAMED_ABSENCES) {
		test(`${route.path} answers, names itself and says what is missing`, async ({
			page
		}) => {
			// A tab in a strip whose page does not exist is a strip that lies, and the
			// panels land later. So the absence is named rather than blank, and it is
			// named in words the reader can act on rather than in a pointer only the
			// repository can resolve.
			const errors: string[] = [];
			page.on('console', (message) => {
				if (message.type() === 'error') errors.push(message.text());
			});
			page.on('pageerror', (error) => errors.push(String(error)));

			const answered = await page.goto(route.href);
			expect(answered?.status(), `${route.path} did not answer`).toBe(200);

			// At least one, not exactly one: the route may have grown a panel, and a
			// panel heading is an h2 too. How many each route owes is in
			// `console-title.spec.ts`, which is the file that rules on headings.
			const heading = page.locator('[data-surface="operator"] h2');
			expect(
				await heading.count(),
				`${route.path} carries no heading of its own`
			).toBeGreaterThan(0);
			expect((await heading.first().innerText()).trim().length).toBeGreaterThan(10);

			const empty = page.locator(`[data-console-empty="${route.id}"]`);
			await expect(empty, `${route.path} prints no named absence`).toHaveCount(1);
			const said = (await empty.innerText()).replace(/\s+/g, ' ').trim();
			expect(said.length, `${route.path} left its absence empty`).toBeGreaterThan(80);
			expect(
				said,
				`${route.path} points at a plan instead of saying what is missing: ${said}`
			).not.toMatch(CITES_A_PLAN);

			// An absence a reader can do nothing with is half an answer, so the route
			// sends them somewhere that carries something today.
			const onward = page.locator(`[data-console-panels="${route.id}"] a[href]`);
			expect(
				await onward.count(),
				`${route.path} names no page a reader can open instead`
			).toBeGreaterThan(0);
			expect(errors, `${route.path} logged an error`).toEqual([]);
		});
	}
});

test.describe('with no script at all', () => {
	test('each route is its own complete document and every link resolves', async ({ browser }) => {
		const context = await browser.newContext({ javaScriptEnabled: false });
		const page = await context.newPage();

		for (const route of ROUTES.filter((entry) => entry.hasBand)) {
			const response = await page.goto(route.href);
			expect(response?.status(), `${route.path} did not answer`).toBe(200);

			// The band, the strip and the carry are all in the prerendered document.
			await expect(page.locator('[data-console-band]'), `${route.path} lost the band`).toHaveCount(
				1
			);
			await expect(
				page.locator('[data-console-nav]'),
				`${route.path} lost the strip`
			).toHaveCount(1);
			await expect(
				page.locator('[data-console-carry]'),
				`${route.path} points at no other route`
			).toHaveCount(1);
			await expect(
				page.locator(`[data-console-route="${route.id}"]`),
				`${route.path} rendered another route's page`
			).toHaveCount(1);

			// A real anchor with a real href, not a button waiting on a script.
			const drawn = await tabs(page);
			expect(drawn.map((tab) => tab.id)).toEqual(ROUTES.map((entry) => entry.id));
			for (const [index, entry] of ROUTES.entries()) {
				expect(drawn[index].href, `${entry.id} is not an anchor to its own route`).toContain(
					entry.path
				);
			}
		}

		// Every one of the twenty-five links, followed. A strip whose anchors 404 is
		// a strip that reads correctly and goes nowhere.
		for (const route of ROUTES.filter((entry) => entry.hasBand)) {
			await page.goto(route.href);
			for (const entry of ROUTES.filter((one) => one.hasBand)) {
				const href = await page
					.locator(`[data-console-tab="${entry.id}"]`)
					.getAttribute('href');
				const followed = await page.request.get(href as string);
				expect(followed.status(), `${route.path} -> ${entry.id} does not resolve`).toBe(200);
				expect(
					await followed.text(),
					`${route.path} -> ${entry.id} answered with another route`
				).toContain(`data-console-route="${entry.id}"`);
			}
		}

		await context.close();
	});
});

test.describe('the standing band', () => {
	// The per-route content/equality checks (same three facts, no control, and
	// agreement across every route) live in "the strip" above, on the same
	// page visits that already check the labels - not a second pass.

	test('the worst thing names the route it is on, and that route exists', async ({ page }) => {
		await page.goto(PIPELINES.href);
		const worst = page.locator('[data-band-worst]');
		const named = await worst.getAttribute('data-band-worst-route');
		if (named === null) {
			// The clear state is a sentence, never an empty slot.
			await expect(worst).toHaveAttribute('data-band-worst', 'clear');
			return;
		}
		expect(ROUTES.map((entry) => entry.id)).toContain(named);
		const href = await worst.locator('a').getAttribute('href');
		expect(href, 'the worst thing names a route it does not link to').toContain(
			ROUTES.find((entry) => entry.id === named)?.path ?? ''
		);
	});
});

test.describe('a route that draws what the server counted', () => {
	for (const MACHINE of MACHINE_ROUTES) {
		test('Machine renders its panels, and any panel with nothing to draw says so', async ({
			page
		}) => {
			// This route shipped empty on 2026-08-30 and gained its panels on
			// 2026-08-31. What is asserted is the shape that survives either state: the
			// panels exist, the span every figure reads is stated in words, and a panel
			// with no data says which reading is missing rather than drawing a zero.
			const errors: string[] = [];
			page.on('console', (message) => {
				if (message.type() === 'error') errors.push(message.text());
			});
			page.on('pageerror', (error) => errors.push(String(error)));

			await page.goto(MACHINE.href);
			const expected = MACHINE.machinePanels!;
			const intro = page.locator(expected.intro);
			await expect(intro).toBeVisible();
			expect((await intro.innerText()).trim().length).toBeGreaterThan(expected.minimumIntroLength);

			const panels = await page.locator('[data-console-panel]').count();
			expect(panels, 'the route draws no panels at all').toBeGreaterThan(expected.minimumPanelCount);

			// Absence prints as absence. Every panel that cannot draw names the reading
			// it is missing; none of them prints a zero in its place.
			const empties = await page
				.locator(expected.emptyPanels)
				.evaluateAll((nodes) =>
					nodes.map((node) => ({
						id: node.getAttribute('data-machine-panel-empty') ?? '',
						text: (node.textContent ?? '').trim()
					}))
				);
			for (const panel of empties) {
				expect(panel.text.length, `${panel.id} is empty without saying so`).toBeGreaterThan(
					expected.minimumEmptyLength
				);
			}
			expect(errors, 'the route logged an error').toEqual([]);
		});

		test('Hardware carries the same window control as the other two', async ({ page }) => {
			await page.goto(MACHINE.href);
			const expected = MACHINE.machinePanels!;
			// It was the one route without one until 2026-08-31, and it printed a
			// sentence pointing at the two routes that had it. An operator who
			// narrowed Pipelines to look at a bad afternoon lost the span the moment
			// he asked what the machine had been doing, and two charts on two spans
			// cannot be compared - which is the question he came to ask.
			const control = page.locator('[data-window-control]');
			await expect(control).toHaveCount(1);
			await expect(control).toHaveAttribute('data-window-days', /\d+/);
			await expect(page.locator('[data-band-window="none"]')).toHaveCount(0);
			// And the panels a span cannot narrow say so where the sentence used to be.
			// A window is a span; a snapshot of one run is not. Each says it in its own
			// subtitle since 2026-09-20, and the line above them carries the one fact no
			// panel can state for itself: which run the newest one is.
			await expect(page.locator(expected.newestRunExemption)).toContainText(expected.newestRunWords);
			await expect(
				page.locator(expected.twoClocksSubtitle)
			).toContainText(expected.twoClocksWords);
		});
	}
});

test.describe('the cross-boundary carries', () => {
	for (const route of ROUTES.filter((entry) => entry.carryTo !== null)) {
		test(`${route.path} carries one sentence pointing at another route`, async ({ page }) => {
			await page.goto(route.href);
			const carry = page.locator('[data-console-carry]');
			await expect(carry, `${route.path} carries none`).toHaveCount(1);
			const text = (await carry.innerText()).trim();
			// A sentence, not a chart, and not a number without a sentence around it.
			expect(text.length).toBeGreaterThan(20);
			const href = await carry.locator('a').getAttribute('href');
			const target = ROUTES.find((entry) => entry.id === route.carryTo)!;
			expect(href, `${route.path} points at the wrong route`).toContain(target.path);
		});
	}
});

/** A band written before Data explorer existed still reads, and the fallback fills the route. */
const OLD_BAND = resolve(process.cwd(), '..', 'tests', 'fixtures', 'contracts', 'console-band', 'newest-day.json');

test.describe('old bands still draw every route', () => {
	for (const DATA_EXPLORER of FALLBACK_ROUTES) {
		test('the strip draws Data explorer from the fallback words', () => {
			const payload = JSON.parse(readFileSync(OLD_BAND, 'utf8')) as { routes: { id: string }[] };
			expect(payload.routes.map((route) => route.id)).not.toContain('data-explorer');
			const band = readBand(payload);
			expect(band.read, 'an old band no longer reads').toBe(true);
			const drawn = stripRoutes(band.routes);
			expect(drawn.map((route) => route.id)).toEqual(ROUTES.map((entry) => entry.id));
			expect(drawn.at(-1)).toMatchObject({
				id: DATA_EXPLORER.id,
				label: DATA_EXPLORER.label,
				href: DATA_EXPLORER.path,
				description: DATA_EXPLORER.fallbackDescription,
				worst: null
			});
		});
	}
});
