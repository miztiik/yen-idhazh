/** The theme's oracle: the first painted frame is already the right theme.
 *
 * A theme that is right after hydration and wrong on the first frame has
 * failed. That frame is what a slow connection shows longest, and a white
 * flash on the way to a dark page is the defect this row exists to remove.
 *
 * So nothing here reads the settled state and calls it a pass. Two things are
 * asserted instead:
 *
 * 1. Every change to `data-theme` happened while `document.body` was still
 *    null. The body is what carries the background, so a change recorded
 *    before it existed cannot have repainted anything - and a change recorded
 *    after it existed is the flash, whatever the final colour is.
 * 2. With JavaScript switched off the page is dark. There is exactly one frame
 *    in that arm, so it is the first one by construction, and it proves the
 *    default lives in `:root` rather than in the inline script.
 *
 * Three storage arms, because the reader has three states and only one of them
 * is the interesting case: no key at all, `light`, and `dark`.
 */

import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = dirname(dirname(fileURLToPath(import.meta.url)));
const TOKENS = readFileSync(join(FRONTEND, 'src', 'styles', 'tokens.css'), 'utf8');
const CANARY = resolve(FRONTEND, '..', 'backend', 'var', 'canary', 'digest');

/** `#rrggbb` as the browser serialises it, so the comparison needs no parser. */
function rgb(hex: string): string {
	const n = Number.parseInt(hex.slice(1), 16);
	return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}

/** The page background each theme declares, read from the token file.
 *
 * Read rather than repeated: a literal here is a second place a theme colour
 * is decided, and the day somebody retunes the ground this test would keep
 * asserting the old one and still pass.
 */
function backgroundHex(selector: string): string {
	const start = TOKENS.indexOf(selector);
	expect(start, `tokens.css no longer has a ${selector} block`).toBeGreaterThan(-1);
	const value = /--color-bg:\s*(#[0-9a-f]{6})/.exec(TOKENS.slice(start));
	expect(value, `${selector} declares no --color-bg`).not.toBeNull();
	return (value as RegExpExecArray)[1];
}

const DARK_HEX = backgroundHex(":root,\n[data-theme='dark']");
const LIGHT_HEX = backgroundHex("[data-theme='light']");
const DARK = rgb(DARK_HEX);
const LIGHT = rgb(LIGHT_HEX);

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** Every reading route the canary day publishes, plus the console.
 *
 * Discovered rather than listed: a route added later is covered without
 * anybody remembering to add it here, and a list that went stale would report
 * a pass over routes nobody loaded.
 *
 * `/evals/` is deliberately absent. It navigates to `/console/` rather than
 * rendering, so there is no settled document to read a background off - and
 * the page it lands on is in the list.
 */
function routes(): string[] {
	const year = dirs(CANARY).at(-1) as string;
	const month = dirs(join(CANARY, year)).at(-1) as string;
	const day = dirs(join(CANARY, year, month)).at(-1) as string;
	// The payload tree is `YYYY/MM/DD`; the route is one dashed segment.
	const date = `${year}-${month}-${day}`;
	const payload = JSON.parse(
		readFileSync(join(CANARY, year, month, day, 'digest.json'), 'utf8')
	) as { verticals: { id: string }[] };
	const topic = payload.verticals[0]?.id;
	return ['/', `/${date}/`, ...(topic ? [`/${date}/${topic}/`] : []), '/archive/', '/console/'];
}

interface Step {
	theme: string | null;
	bodyExisted: boolean;
}

/** Record every `data-theme` the document ever holds, and whether a body
 * existed at the time. Installed before any script the page carries. */
async function trail(page: Page): Promise<void> {
	await page.addInitScript(() => {
		const seen: { theme: string | null; bodyExisted: boolean }[] = [];
		(window as unknown as { __themeTrail: typeof seen }).__themeTrail = seen;
		const record = () =>
			seen.push({
				theme: document.documentElement?.getAttribute('data-theme') ?? null,
				bodyExisted: document.body !== null
			});
		const attach = (): boolean => {
			if (!document.documentElement) return false;
			record();
			new MutationObserver(record).observe(document.documentElement, {
				attributes: true,
				attributeFilter: ['data-theme']
			});
			return true;
		};
		if (!attach()) {
			// `documentElement` arrives with the first parsed bytes; watch the
			// document itself until it does.
			const boot = new MutationObserver(() => {
				if (attach()) boot.disconnect();
			});
			boot.observe(document, { childList: true });
		}
	});
}

/** The colour the page actually paints.
 *
 * `app.css` puts the background on `html`, and the browser propagates that to
 * the canvas - so `body` reads back transparent and says nothing.
 */
async function painted(page: Page): Promise<string> {
	return page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor);
}

async function assertPainted(page: Page, route: string, expected: string, theme: string) {
	const steps = (await page.evaluate(
		() => (window as unknown as { __themeTrail: Step[] }).__themeTrail
	)) as Step[];

	expect(steps.length, `${route}: nothing recorded, so the observer never attached`).toBeGreaterThan(
		0
	);
	const late = steps.filter((step) => step.bodyExisted);
	expect(
		late,
		`${route}: data-theme moved to ${late.map((s) => s.theme).join(', ')} after the body existed, which is a repaint a reader can see`
	).toEqual([]);

	const wrong = steps.filter((step) => step.theme !== null && step.theme !== theme);
	expect(wrong, `${route}: the document held ${wrong.map((s) => s.theme).join(', ')} on the way`).toEqual(
		[]
	);

	expect(await painted(page), `${route}: the painted background is not the ${theme} theme`).toBe(
		expected
	);
}

test.describe('the first painted frame', () => {
	for (const route of routes()) {
		test(`is dark with no stored choice: ${route}`, async ({ page }) => {
			await trail(page);
			await page.goto(route);
			await assertPainted(page, route, DARK, 'dark');
		});

		test(`is light with light stored: ${route}`, async ({ page }) => {
			await trail(page);
			await page.addInitScript(() => localStorage.setItem('idhazh:theme', 'light'));
			await page.goto(route);
			await assertPainted(page, route, LIGHT, 'light');
		});

		test(`is dark with dark stored: ${route}`, async ({ page }) => {
			await trail(page);
			await page.addInitScript(() => localStorage.setItem('idhazh:theme', 'dark'));
			await page.goto(route);
			await assertPainted(page, route, DARK, 'dark');
		});
	}
});

test.describe('with no script at all', () => {
	test.use({ javaScriptEnabled: false });

	for (const route of routes()) {
		test(`the page is still dark: ${route}`, async ({ page }) => {
			await page.goto(route);
			// No attribute is set, so `:root` is the only thing that can have
			// painted this. That is the whole of "the default lives in the CSS".
			expect(
				await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
			).toBeNull();
			expect(await painted(page)).toBe(DARK);
		});
	}

	test('the document tells the browser dark comes first', async ({ page }) => {
		await page.goto('/');
		expect(
			await page.evaluate(
				() => document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]')?.content
			)
		).toBe('dark light');
	});
});

test.describe('the theme control', () => {
	test('is one button whose glyph does not change', async ({ page }) => {
		await page.goto('/');
		const button = page.locator('[data-theme-toggle]');
		await expect(button).toHaveCount(1);
		await expect(button).toHaveAttribute('aria-label', 'Switch to the light theme');
		// No `aria-pressed`: this switches between two states, it is not a thing
		// that is on or off.
		expect(await button.getAttribute('aria-pressed')).toBeNull();

		const glyph = () => button.locator('svg.icon').innerHTML();
		const before = await glyph();

		await expect
			.poll(async () => {
				await button.click();
				return await button.getAttribute('aria-label');
			})
			.toBe('Switch to the dark theme');

		expect(await page.evaluate(() => document.documentElement.getAttribute('data-theme'))).toBe(
			'light'
		);
		expect(await painted(page)).toBe(LIGHT);
		// The page is the state indicator. A glyph that flipped would be a second
		// and weaker copy of it.
		expect(await glyph(), 'the glyph flipped with the theme').toBe(before);
	});

	test('a choice is stored as a theme, never as the absence of one', async ({ page }) => {
		await page.goto('/');
		const button = page.locator('[data-theme-toggle]');
		await expect
			.poll(async () => {
				await button.click();
				return await page.evaluate(() => localStorage.getItem('idhazh:theme'));
			})
			.toBe('light');
		await button.click();
		expect(await page.evaluate(() => localStorage.getItem('idhazh:theme'))).toBe('dark');
	});

	test('a returning reader who stored light gets light chrome without clicking', async ({
		page
	}) => {
		// The tag `app.html` ships holds the base theme, so without a sync on
		// mount a light page sits under dark chrome on every visit - which is the
		// exact mismatch the one unconditional tag was chosen to avoid.
		await page.addInitScript(() => localStorage.setItem('idhazh:theme', 'light'));
		await page.goto('/');
		const chrome = page.locator('meta[name="theme-color"]');
		await expect
			.poll(async () => ((await chrome.getAttribute('content')) ?? '').trim().toLowerCase())
			.toBe(LIGHT_HEX);
	});
});
