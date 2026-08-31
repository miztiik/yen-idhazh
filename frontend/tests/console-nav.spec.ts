import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * The console is three routes, and this file is why it is routes and not tabs.
 *
 * A tab strip that switches with script fails every assertion here: with
 * JavaScript off it shows one panel set and no way to reach the others, and
 * every panel it hides still ships inside the one document. Three prerendered
 * routes with real anchors pass, and each one can be weighed on its own.
 *
 * Two things this file protects that a screenshot cannot. The three labels are
 * the owner's own words, taken verbatim on 2026-08-30, so a paraphrase fails.
 * And the strip may never take the health ramp: green, amber and red on a label
 * would say a route is failing, and a route is a noun.
 */

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
) as { page_weight: { ceilings_bytes: Record<string, number> } };

/** The owner's words, and the paths they sit on. Typed out on purpose: this is
 * the copy the file exists to protect, so reading it from the source it guards
 * would only prove the page agrees with itself. */
const ROUTES = [
	{ id: 'pipelines', label: 'Pipelines', path: '/console/' },
	{ id: 'model', label: 'Model', path: '/console/model/' },
	{ id: 'machine', label: 'Machine', path: '/console/machine/' }
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
		test(`${route.path} draws the same three labels and marks its own`, async ({ page }) => {
			await page.goto(route.path);

			const drawn = await tabs(page);
			expect(drawn.map((tab) => tab.id), 'the strip does not name the three routes in order').toEqual(
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

	test('every label carries a description, and the same words as its tooltip', async ({ page }) => {
		await page.goto('/console/');
		const drawn = await page.locator('[data-console-nav] [data-console-tab]').evaluateAll((links) =>
			links.map((node) => ({
				id: node.getAttribute('data-console-tab') ?? '',
				title: node.getAttribute('title') ?? '',
				line: (node.querySelector('.tab-line')?.textContent ?? '').trim()
			}))
		);
		expect(drawn).toHaveLength(3);
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

		// Every one of the nine links, followed. A strip whose anchors 404 is a
		// strip that reads correctly and goes nowhere.
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
		test(`${route.path} carries the same four things and no others`, async ({ page }) => {
			await page.goto(route.path);
			const facts = await page
				.locator('[data-console-band] [data-band-fact]')
				.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-band-fact') ?? ''));
			// Three facts plus the window slot. A band that grows becomes a fourth
			// page nobody chose to open.
			expect(facts).toEqual(['verdict', 'worst', 'size']);
			await expect(page.locator('[data-console-band] [data-band-window-slot]')).toHaveCount(1);

			for (const marker of ['[data-band-verdict]', '[data-band-worst]', '[data-band-size]']) {
				const text = (await page.locator(`[data-console-band] ${marker}`).innerText()).trim();
				expect(text.length, `${route.path} left ${marker} empty`).toBeGreaterThan(20);
			}
		});
	}

	test('the band says the same thing on all three routes', async ({ page }) => {
		const read = async (path: string) => {
			await page.goto(path);
			return {
				verdict: (await page.locator('[data-band-verdict]').innerText()).trim(),
				worst: (await page.locator('[data-band-worst]').innerText()).trim(),
				size: (await page.locator('[data-band-size]').innerText()).trim()
			};
		};
		// Derived once for all three, so they cannot disagree about which route is
		// worst - which is the failure a per-route band eventually produces.
		const pipelines = await read('/console/');
		expect(await read('/console/model/')).toEqual(pipelines);
		expect(await read('/console/machine/')).toEqual(pipelines);
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

test.describe('the ceilings follow the split', () => {
	test('config names a ceiling for each of the three routes', () => {
		const ceilings = CONFIG.page_weight.ceilings_bytes;
		// The gate already fails a ceiling that names no route in the build. This
		// is the reverse: a route that names no ceiling is only reported, so a new
		// surface would grow unwatched. One key over three surfaces cannot say
		// which of them blew a budget, and that is the argument for routes.
		for (const route of ROUTES) {
			expect(ceilings[route.path], `${route.path} has no ceiling in config`).toBeGreaterThan(0);
		}
		const named = Object.keys(ceilings).filter((key) => key.startsWith('/console/'));
		expect(named.sort()).toEqual(ROUTES.map((entry) => entry.path).sort());
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

	test('Machine draws no window control and says where the control is', async ({ page }) => {
		await page.goto('/console/machine/');
		// A control that governs nothing answers a click by changing nothing. The
		// sentence in its place points at the two routes it does govern, and the
		// choice is remembered across all three.
		await expect(page.locator('[data-console-band] [data-window-control]')).toHaveCount(0);
		await expect(page.locator('[data-band-window="none"]')).toBeVisible();
		const hrefs = await page
			.locator('[data-band-window="none"] a')
			.evaluateAll((links) => links.map((node) => (node as HTMLAnchorElement).getAttribute('href') ?? ''));
		expect(hrefs.some((href) => href.endsWith('/console/'))).toBe(true);
		expect(hrefs.some((href) => href.endsWith('/console/model/'))).toBe(true);
	});
});

test.describe('the cross-boundary carries', () => {
	const POINTS_AT: Record<string, string> = {
		pipelines: '/console/model/',
		model: '/console/machine/',
		machine: '/console/'
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
