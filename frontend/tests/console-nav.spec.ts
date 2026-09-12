import { expect, test, type Page } from '@playwright/test';

/**
 * The console is five routes, and this file is why it is routes and not tabs.
 *
 * A tab strip that switches with script fails every assertion here: with
 * JavaScript off it shows one panel set and no way to reach the others, and
 * every panel it hides still ships inside the one document. Five prerendered
 * routes with real anchors pass.
 *
 * Four things this file protects that a screenshot cannot. The labels are the
 * words the owner chose, so a paraphrase fails. The ids and the paths under
 * them did NOT move when two of the labels changed on 2026-08-31, which is what
 * makes that a rename and not a route change. The strip may never take the
 * health ramp: green, amber and red on a label would say a route is failing,
 * and a route is a noun. And since 2026-09-12 the strip has to FIT - five tabs
 * on no more than two rows at 1440 and three at 360 and 320, with no box
 * overlapping another.
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
 * added them. `Judgement` is singular because the other three name a place and
 * this one names an act; `Voices` is the owner's word over Susan's `Sources`.
 */
const ROUTES = [
	{ id: 'pipelines', label: 'Pipelines', path: '/console/' },
	{ id: 'model', label: 'Summaries', path: '/console/model/' },
	{ id: 'machine', label: 'Hardware', path: '/console/machine/' },
	{ id: 'judgement', label: 'Judgement', path: '/console/judgement/' },
	{ id: 'voices', label: 'Voices', path: '/console/voices/' }
] as const;

/** The two routes opened with no panel of their own, and the row that fills
 * each. A strip that names a page nobody can reach is a strip that lies. */
const EMPTY_ROUTES = [
	{ id: 'judgement', path: '/console/judgement/', rows: ['row #12', 'row #15'] },
	{ id: 'voices', path: '/console/voices/', rows: ['row #13'] }
] as const;

/** The three verdict colours, as the tokens a stylesheet would have to name. */
const HEALTH_RAMP = ['--fill-high', '--fill-medium', '--fill-low', '--band-high', '--band-medium', '--band-low'];

async function tabs(page: Page) {
	return page.locator('[data-console-nav] [data-console-tab]').evaluateAll((links) =>
		links.map((node) => ({
			id: node.getAttribute('data-console-tab') ?? '',
			href: (node as HTMLAnchorElement).getAttribute('href') ?? '',
			current: node.getAttribute('aria-current'),
			text: (node.textContent ?? '').trim()
		}))
	);
}

test.describe('the strip', () => {
	for (const route of ROUTES) {
		test(`${route.path} draws the same five labels and marks its own`, async ({ page }) => {
			await page.goto(route.path);

			const drawn = await tabs(page);
			expect(drawn.map((tab) => tab.id), 'the strip does not name the five routes in order').toEqual(
				ROUTES.map((entry) => entry.id)
			);
			// Verbatim. A label that paraphrases the owner's word fails here.
			for (const [index, entry] of ROUTES.entries()) {
				expect(drawn[index].text, `${entry.id} lost its label`).toContain(entry.label);
			}
			expect(
				drawn.filter((tab) => tab.current === 'page').map((tab) => tab.id),
				'exactly one label says which route this is'
			).toEqual([route.id]);
		});
	}

	test('THE ORACLE: a label changed and no address moved with it', async ({ page }) => {
		// Two of the three labels were rewritten on 2026-08-31. The whole risk of a
		// rename row is that a word an operator reads and a word a browser resolves
		// are the same string somewhere, so this asserts the second set did not
		// move: the tab ids, the hrefs, and the route markers each page prints.
		await page.goto('/console/');
		const drawn = await tabs(page);
		expect(
			drawn.map((tab) => tab.id),
			'a tab id moved, which is an address and not a label'
		).toEqual(['pipelines', 'model', 'machine', 'judgement', 'voices']);

		for (const [index, entry] of ROUTES.entries()) {
			expect(drawn[index].href, `${entry.id} no longer points at its own route`).toContain(
				entry.path
			);
		}

		for (const entry of ROUTES) {
			const answered = await page.request.get(entry.path);
			expect(answered.status(), `${entry.path} stopped answering`).toBe(200);
			expect(
				await answered.text(),
				`${entry.path} no longer prints its own route marker`
			).toContain(`data-console-route="${entry.id}"`);
		}
	});

	test('every label carries a description, and the same words as its tooltip', async ({ page }) => {
		await page.goto('/console/');
		const drawn = await page.locator('[data-console-nav] [data-console-tab]').evaluateAll((links) =>
			links.map((node) => ({
				id: node.getAttribute('data-console-tab') ?? '',
				title: node.getAttribute('title') ?? '',
				line: (node.querySelector('.tab-line')?.textContent ?? '').trim()
			}))
		);
		expect(drawn).toHaveLength(5);
		for (const tab of drawn) {
			expect(tab.line.length, `${tab.id} has no description under its label`).toBeGreaterThan(20);
			expect(tab.title, `${tab.id}'s tooltip is not its description`).toBe(tab.line);
		}
	});

	test('every label carries its own worst state', async ({ page }) => {
		await page.goto('/console/');
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

	test('the health ramp never touches the strip', async ({ page }) => {
		await page.goto('/console/');
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

/** Widths and the rows five tabs may stand on at each.
 *
 * 1440 is where the console is read; 360 is the narrowest phone the rest of
 * this suite drives; 320 is the narrowest screen still in use and is here
 * because the basis that cleared 360 still stacked five deep there - the same
 * defect one screen narrower, found by measuring rather than by reading the
 * rule. Two rows and three rows, because the strip sits directly above the band
 * and the band is the first thing an operator reads: five rows of chrome would
 * push the verdict off a phone's first screen.
 */
const STRIP_WIDTHS = [
	{ width: 1440, height: 1000, rows: 2 },
	{ width: 360, height: 780, rows: 3 },
	{ width: 320, height: 780, rows: 3 }
] as const;

for (const view of STRIP_WIDTHS) {
	test(`THE ORACLE: five tabs stand on at most ${view.rows} rows at ${view.width}`, async ({
		page
	}) => {
		await page.setViewportSize({ width: view.width, height: view.height });
		await page.goto('/console/');

		const { innerWidth, clientWidth, boxes } = await stripBoxes(page);
		expect(boxes, `only ${boxes.length} tabs are drawn, so this proves nothing`).toHaveLength(5);

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
			`five tabs stand on ${rows.size} rows at innerWidth ${innerWidth} ` +
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

test.describe('the two routes opened empty', () => {
	for (const route of EMPTY_ROUTES) {
		test(`${route.path} answers, names itself and names the row that fills it`, async ({
			page
		}) => {
			// A tab in a strip whose page does not exist is a strip that lies, and
			// rows #12 and #13 land later. So the absence is named rather than
			// blank, and it names where the specification is - which is the only
			// part of it that stays true as those rows are written.
			const errors: string[] = [];
			page.on('console', (message) => {
				if (message.type() === 'error') errors.push(message.text());
			});
			page.on('pageerror', (error) => errors.push(String(error)));

			const answered = await page.goto(route.path);
			expect(answered?.status(), `${route.path} did not answer`).toBe(200);

			const heading = page.locator('[data-surface="operator"] h2');
			await expect(heading, `${route.path} carries no heading of its own`).toHaveCount(1);
			expect((await heading.innerText()).trim().length).toBeGreaterThan(10);

			const empty = page.locator(`[data-console-empty="${route.id}"]`);
			await expect(empty, `${route.path} prints no named absence`).toHaveCount(1);
			const said = (await empty.innerText()).replace(/\s+/g, ' ').trim();
			expect(said.length, `${route.path} left its absence empty`).toBeGreaterThan(80);
			for (const row of route.rows) {
				expect(said, `${route.path} does not say which row fills it`).toContain(row);
			}

			// It fetches nothing, so it has no window control to govern nothing.
			await expect(page.locator('[data-window-control]')).toHaveCount(0);
			expect(errors, `${route.path} logged an error`).toEqual([]);
		});
	}
});

test.describe('with no script at all', () => {
	test('each route is its own complete document and every link resolves', async ({ browser }) => {
		const context = await browser.newContext({ javaScriptEnabled: false });
		const page = await context.newPage();

		for (const route of ROUTES) {
			const response = await page.goto(route.path);
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
		for (const route of ROUTES) {
			await page.goto(route.path);
			for (const entry of ROUTES) {
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
	for (const route of ROUTES) {
		test(`${route.path} carries the same three things and no others`, async ({ page }) => {
			await page.goto(route.path);
			const facts = await page
				.locator('[data-console-band] [data-band-fact]')
				.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-band-fact') ?? ''));
			// Three facts and no control. A band that grows becomes a fourth page
			// nobody chose to open, and the control governs nothing inside it.
			expect(facts).toEqual(['verdict', 'worst', 'size']);
			await expect(page.locator('[data-console-band] [data-window-control]')).toHaveCount(0);

			for (const marker of ['[data-band-verdict]', '[data-band-worst]', '[data-band-size]']) {
				const text = (await page.locator(`[data-console-band] ${marker}`).innerText()).trim();
				expect(text.length, `${route.path} left ${marker} empty`).toBeGreaterThan(20);
			}
		});
	}

	test('the band says the same thing on every route', async ({ page }) => {
		const read = async (path: string) => {
			await page.goto(path);
			return {
				verdict: (await page.locator('[data-band-verdict]').innerText()).trim(),
				worst: (await page.locator('[data-band-worst]').innerText()).trim(),
				size: (await page.locator('[data-band-size]').innerText()).trim()
			};
		};
		// Derived once for all five, so they cannot disagree about which route is
		// worst - which is the failure a per-route band eventually produces.
		const pipelines = await read('/console/');
		for (const route of ROUTES.slice(1)) {
			expect(await read(route.path), `the band differs on ${route.path}`).toEqual(pipelines);
		}
	});

	test('the worst thing names the route it is on, and that route exists', async ({ page }) => {
		await page.goto('/console/');
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

		await page.goto('/console/machine/');
		const intro = page.locator('[data-machine="intro"]');
		await expect(intro).toBeVisible();
		expect((await intro.innerText()).trim().length).toBeGreaterThan(40);

		const panels = await page.locator('[data-console-panel]').count();
		expect(panels, 'the route draws no panels at all').toBeGreaterThan(5);

		// Absence prints as absence. Every panel that cannot draw names the reading
		// it is missing; none of them prints a zero in its place.
		const empties = await page
			.locator('[data-machine-panel-empty]')
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					id: node.getAttribute('data-machine-panel-empty') ?? '',
					text: (node.textContent ?? '').trim()
				}))
			);
		for (const panel of empties) {
			expect(panel.text.length, `${panel.id} is empty without saying so`).toBeGreaterThan(20);
		}
		expect(errors, 'the route logged an error').toEqual([]);
	});

	test('Hardware carries the same window control as the other two', async ({ page }) => {
		await page.goto('/console/machine/');
		// It was the one route without one until 2026-08-31, and it printed a
		// sentence pointing at the two routes that had it. An operator who
		// narrowed Pipelines to look at a bad afternoon lost the span the moment
		// he asked what the machine had been doing, and two charts on two spans
		// cannot be compared - which is the question he came to ask.
		const control = page.locator('[data-window-control]');
		await expect(control).toHaveCount(1);
		await expect(control).toHaveAttribute('data-window-days', /\d+/);
		await expect(page.locator('[data-band-window="none"]')).toHaveCount(0);
		// And the four panels a span cannot narrow say so where the sentence used
		// to be. A window is a span; a snapshot of one run is not.
		await expect(page.locator('[data-window-exempt="newest-run"]')).toContainText(
			'do not follow the window'
		);
	});
});

test.describe('the cross-boundary carries', () => {
	const POINTS_AT: Record<string, string> = {
		pipelines: '/console/model/',
		model: '/console/machine/',
		machine: '/console/',
		// The two empty routes point at the route that holds the nearest figure
		// they have none of: what the checker doubted is on Summaries, and which
		// feeds broke is on Pipelines.
		judgement: '/console/model/',
		voices: '/console/'
	};

	for (const route of ROUTES) {
		test(`${route.path} carries one sentence pointing at another route`, async ({ page }) => {
			await page.goto(route.path);
			const carry = page.locator('[data-console-carry]');
			await expect(carry, `${route.path} carries none`).toHaveCount(1);
			const text = (await carry.innerText()).trim();
			// A sentence, not a chart, and not a number without a sentence around it.
			expect(text.length).toBeGreaterThan(20);
			const href = await carry.locator('a').getAttribute('href');
			expect(href, `${route.path} points at the wrong route`).toContain(POINTS_AT[route.id]);
		});
	}
});
