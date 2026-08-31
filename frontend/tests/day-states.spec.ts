import { expect, test, type Page } from '@playwright/test';
import {
	existsSync,
	mkdirSync,
	mkdtempSync,
	readdirSync,
	readFileSync,
	rmSync,
	writeFileSync
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { loadDay, publishedDates } from '../src/lib/server/payload';

/**
 * Row #14's oracle: the three screens a reader meets on a bad day.
 *
 * A quiet day, a day whose payload is not there, and a day whose payload is
 * there and cannot be read. All three are normal, all three are frequent, and
 * on this site all three used to be the plainest thing on it - which reads as a
 * page that broke rather than as a day with nothing on it.
 *
 * What is asserted is that each state reaches a designed screen, that each one
 * wears the card an item wears, and that a quiet day is never painted like a
 * fault. The card is checked by resolving the tokens in the live document
 * rather than by pinning a colour, because the claim is "the same tokens the
 * item uses", not "this hex".
 *
 * The third input has no browser arm here and cannot have one: the canary tree
 * is written by `build_canary_day.py` through the contract, so it cannot hold a
 * corrupt file. That input is driven against the loader itself, which is where
 * the difference between a designed screen and a dead build is decided.
 */

const THEMES = ['light', 'dark'] as const;
type Theme = (typeof THEMES)[number];

/** A phone, the side-rail breakpoint, and a wide desktop. `frame.breakpoints_px`
 * in `config/appearance.json` is [640, 1024, 1400]; 801 sits between two of
 * them, which is where a layout tested only at a breakpoint breaks. */
const WIDTHS = [360, 801, 1536];

const ROOT = resolve(process.cwd(), '..');
const CANARY = resolve(ROOT, 'backend', 'var', 'canary', 'digest');

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** Every date the canary tree published, with the item count it published. */
function canaryDays(): Array<{ date: string; items: number }> {
	const found: Array<{ date: string; items: number }> = [];
	for (const year of dirs(CANARY)) {
		for (const month of dirs(join(CANARY, year))) {
			for (const day of dirs(join(CANARY, year, month))) {
				const raw = readFileSync(join(CANARY, year, month, day, 'digest.json'), 'utf8');
				const parsed = JSON.parse(raw) as { date: string; items: unknown[] };
				found.push({ date: parsed.date, items: parsed.items.length });
			}
		}
	}
	return found.sort((a, b) => a.date.localeCompare(b.date));
}

/** A day the canary published with nothing on it.
 *
 * `build_canary_day.py` writes nineteen of these before the attack day, which
 * is what makes the quiet state reachable in a real browser instead of only in
 * a unit test.
 */
function quietDay(): string {
	const quiet = canaryDays().filter((day) => day.items === 0);
	expect(quiet.length, 'the canary tree publishes no day with zero items').toBeGreaterThan(0);
	return quiet[quiet.length - 1].date;
}

/** A date the canary never published, so its payload file is absent. */
const NEVER_PUBLISHED = '2001-09-11';
const MISSING_ROUTE = `/${NEVER_PUBLISHED}/`;

/** What a static host serves for an address it does not have.
 *
 * GitHub Pages answers any unknown path with `404.html`, which is why
 * `svelte.config.js` names that file as the adapter's fallback. `vite preview`
 * has no such rule - it answers its own bare page - so the screen is reached
 * here by asking for the file itself. That is the same document, the same
 * hydration and the same rendered error; only the address bar differs.
 */
const HOST_FALLBACK = '/404.html';

/** What a static host serves for an address it does not have.
 *
 * GitHub Pages answers any unknown path with `404.html` - which is why
 * `svelte.config.js` names that file as the adapter's fallback - and it keeps
 * the requested address in the bar. `vite preview` has no such rule: measured
 * 2026-08-31, it answers `/2001-09-11/` and `/404.html` alike with a bare 404
 * and a zero-byte body, so the screen is simply unreachable under it.
 *
 * So the host is stood in for, and only the host: the real built `404.html` is
 * served, with status 404, at the real address. Everything after that is the
 * shipped bundle doing what it does on Pages - the router resolves the dated
 * route, its data file is not there, and the error page renders.
 */
function asStaticHost(page: Page, route: string): Promise<void> {
	const shell = readFileSync(join(process.cwd(), 'build', '404.html'), 'utf8');
	return page.route(`**${route}`, (intercepted) =>
		intercepted.fulfill({ status: 404, contentType: 'text/html', body: shell })
	);
}

async function open(page: Page, theme: Theme, route: string, width: number) {
	await page.setViewportSize({ width, height: 900 });
	await page.addInitScript(`localStorage.setItem('idhazh:theme', '${theme}')`);
	const response = await page.goto(route);
	await expect
		.poll(() => page.evaluate(() => document.documentElement.getAttribute('data-theme')))
		.toBe(theme);
	return response;
}

/** What the browser computes for a property set from a token.
 *
 * `getPropertyValue('--item-edge')` hands back the literal `var(--color-rule)`,
 * because a custom property resolves where it is used. A probe element resolves
 * it the same way the component does, so a token and the thing painted from it
 * arrive in one format and compare exactly.
 */
function resolved(page: Page, property: string, value: string): Promise<string> {
	return page.evaluate(
		([prop, token]) => {
			const probe = document.createElement('div');
			probe.style.setProperty(prop, token);
			document.body.appendChild(probe);
			const computed = getComputedStyle(probe).getPropertyValue(prop);
			probe.remove();
			return computed;
		},
		[property, value]
	);
}

/** The card a block is painted as: its surface, its edge and its corner. */
async function card(page: Page, selector: string) {
	const box = page.locator(selector).first();
	await expect(box, `nothing matched ${selector}`).toBeVisible();
	return box.evaluate((el) => {
		const style = getComputedStyle(el);
		return {
			background: style.backgroundColor,
			border: style.borderTopColor,
			borderWidth: style.borderTopWidth,
			radius: style.borderTopLeftRadius
		};
	});
}

/** Every console error and page error the visit produced.
 *
 * A 404 the browser reports itself is the request failing, not our code. The
 * missing-day arm asks for a data file that is deliberately not there, so that
 * line is expected and everything else on the list would be ours.
 */
function watchErrors(page: Page): string[] {
	const seen: string[] = [];
	page.on('console', (message) => {
		if (message.type() !== 'error') return;
		if (message.text().includes('Failed to load resource')) return;
		seen.push(`console: ${message.text()}`);
	});
	page.on('pageerror', (error) => seen.push(`pageerror: ${error.message}`));
	return seen;
}

test.describe('a day with nothing on it', () => {
	for (const theme of THEMES) {
		for (const width of WIDTHS) {
			test(`the quiet-day panel is the item's card in ${theme} at ${width}`, async ({ page }) => {
				const errors = watchErrors(page);
				await open(page, theme, `/${quietDay()}/`, width);

				const surface = await resolved(page, 'background-color', 'var(--color-surface)');
				const edge = await resolved(page, 'border-top-color', 'var(--item-edge)');
				const radius = await resolved(page, 'border-top-left-radius', 'var(--radius-lg)');

				for (const selector of ['[data-empty-day]', 'section[aria-label="About today"]']) {
					const painted = await card(page, selector);
					// The neutral tint stays neutral, and it is the same neutral the
					// item sits on. A wash here would be one panel a different colour
					// from every other panel on the site.
					expect(painted.background, `${selector} is not on the item's surface`).toBe(surface);
					expect(painted.border, `${selector} does not carry the item's hairline`).toBe(edge);
					expect(painted.borderWidth, `${selector} hairline is not 1px`).toBe('1px');
					expect(painted.radius, `${selector} does not carry the item's corner`).toBe(radius);
				}

				expect(errors, `console errors on a quiet day:\n${errors.join('\n')}`).toEqual([]);
			});
		}
	}

	test('the quiet day says what happened and offers two ways on', async ({ page }) => {
		const date = quietDay();
		await open(page, 'dark', `/${date}/`, 1536);

		const panel = page.locator('[data-empty-day]');
		await expect(panel).toContainText('Nothing was published for');
		await expect(panel).toContainText('That can mean there was no news, or the run did not finish.');

		// A screen with nothing to do on it is a dead end, and a dead end reads as
		// a dead site. Both links are followed rather than counted.
		const targets = await panel
			.locator('a[href]')
			.evaluateAll((links) => links.map((link) => (link as HTMLAnchorElement).href));
		expect(targets.length, 'the quiet day offers no way on').toBeGreaterThanOrEqual(2);
		for (const href of targets) {
			const response = await page.goto(href);
			expect(response?.status(), `${href} from the quiet day`).toBeLessThan(400);
		}
	});

	test('the day notice leads with what the day held and puts the run last', async ({ page }) => {
		await open(page, 'dark', `/${quietDay()}/`, 1536);

		const notice = page.locator('section[aria-label="About today"]');
		// The order is the hierarchy. One paragraph holding all four facts gave
		// the block no order to be read in.
		const paragraphs = await notice.locator('p').allInnerTexts();
		expect(paragraphs[0], 'the notice does not lead with the count').toContain('No stories today.');
		expect(paragraphs.at(-1), 'the run stamp is not last').toMatch(
			/This page came from run \d+, at \d\d:\d\d UTC\./
		);
	});
});

test.describe('a day whose payload is not there', () => {
	test('a day with no payload is built into no document at all', () => {
		// Which is why the screen below is the one a reader meets: there is no
		// page of ours to serve, so the host's fallback answers instead.
		expect(publishedDates(CANARY)).not.toContain(NEVER_PUBLISHED);
		expect(loadDay(NEVER_PUBLISHED, CANARY), 'a day with no payload loaded anyway').toBeNull();
		expect(
			existsSync(join(process.cwd(), 'build', NEVER_PUBLISHED, 'index.html')),
			'the build holds a document for a day that was never published'
		).toBe(false);
	});

	for (const theme of THEMES) {
		for (const width of WIDTHS) {
			test(`the missing-day screen is designed in ${theme} at ${width}`, async ({ page }) => {
				const errors = watchErrors(page);
				await asStaticHost(page, MISSING_ROUTE);
				await open(page, theme, MISSING_ROUTE, width);

				const screen = page.locator('[data-error-screen]');
				await expect(screen, 'no designed screen for a day that is not there').toBeVisible();
				await expect(screen.locator('h1')).toHaveText('Not here');
				// A day that went wrong must not look like a site that is gone.
				await expect(screen.locator('a[href]')).toHaveCount(2);

				const surface = await resolved(page, 'background-color', 'var(--color-surface)');
				const edge = await resolved(page, 'border-top-color', 'var(--item-edge)');
				const painted = await card(page, '[data-error-screen]');
				expect(painted.background, 'the failed screen is not on the item surface').toBe(surface);
				expect(painted.border, 'the failed screen has no hairline').toBe(edge);

				expect(errors, `console errors on a missing day:\n${errors.join('\n')}`).toEqual([]);
			});
		}
	}

	test('the screen is a page, not a blank document', async ({ page }) => {
		await asStaticHost(page, MISSING_ROUTE);
		await open(page, 'dark', MISSING_ROUTE, 1536);

		// This is the white-screen check. Before the layout was guarded, a wrong
		// address rendered nothing at all: the shell asked for a data file that is
		// not there, the root layout read `data.ui.site_title` off `undefined`,
		// and the body kept only its own boot script.
		await expect(page.locator('[data-error-screen]')).toContainText(
			'The address may be wrong, or the day it names was never published.'
		);
		const text = await page.evaluate(() => document.body.innerText.trim().length);
		expect(text, 'the document rendered no words at all').toBeGreaterThan(40);

		// And a way back that goes somewhere.
		const targets = await page
			.locator('[data-error-screen] a[href]')
			.evaluateAll((links) => links.map((link) => (link as HTMLAnchorElement).href));
		expect(targets.length, 'the screen offers no way on').toBe(2);
		for (const href of targets) {
			const response = await page.goto(href);
			expect(response?.status(), `${href} from the missing-day screen`).toBeLessThan(400);
		}
	});
});

test.describe('a day whose payload cannot be read', () => {
	/**
	 * The build used to die here, and a build that dies publishes nothing.
	 *
	 * One unreadable file took down the whole site, including every other day in
	 * the tree, so no reader ever reached a screen for it - which is the same as
	 * not having designed one. The day now drops out and the reader meets the
	 * quiet-day panel or the missing-day screen instead.
	 *
	 * The readable payload in the same tree is the control: without it this
	 * passes on a loader that returns null for everything.
	 */
	test('an unreadable payload drops its day instead of taking the build down', () => {
		const root = mkdtempSync(join(tmpdir(), 'r14-day-'));
		try {
			const readable = join(root, '2026', '01', '02');
			const corrupt = join(root, '2026', '01', '03');
			mkdirSync(readable, { recursive: true });
			mkdirSync(corrupt, { recursive: true });
			writeFileSync(
				join(readable, 'digest.json'),
				JSON.stringify({ date: '2026-01-02', items: [], verticals: [], runs: [] })
			);
			// Truncated mid-object, which is what an interrupted write leaves.
			writeFileSync(join(corrupt, 'digest.json'), '{"date": "2026-01-03", "items": [');

			expect(loadDay('2026-01-02', root)?.date, 'the control day did not load').toBe('2026-01-02');
			expect(loadDay('2026-01-03', root), 'an unreadable payload still throws').toBeNull();
			// It is still a published date, because the file is there. That is what
			// makes the day reachable and the screen necessary.
			expect(publishedDates(root)).toContain('2026-01-03');
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});

	test('a payload that parses into something that is not a day drops too', () => {
		const root = mkdtempSync(join(tmpdir(), 'r14-shape-'));
		try {
			const day = join(root, '2026', '01', '04');
			mkdirSync(day, { recursive: true });
			// Valid JSON, no day in it. A parser is not a contract, and this one
			// used to arrive at the page as an object with no items on it - which
			// is a white screen rather than a designed one.
			writeFileSync(join(day, 'digest.json'), 'null');

			expect(loadDay('2026-01-04', root), 'a payload with no day in it still loads').toBeNull();
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});
});
