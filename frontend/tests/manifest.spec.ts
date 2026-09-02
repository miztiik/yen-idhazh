import { expect, test } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/**
 * Installable, and nothing more than that.
 *
 * A manifest is a static JSON file. It adds no request, no account, no code
 * running off the reader's device, and - the part worth a test rather than a
 * promise - no notification. Installability is what makes that temptation
 * concrete, so the ban is asserted instead of implied.
 *
 * The way this actually breaks is the base path. The site is served from a
 * GitHub Pages project path, a manifest that validates at the root 404s every
 * icon one directory up, and nothing on the page reports it. Every path here is
 * relative for that reason, and the test resolves them the way a browser would.
 */

const BUILD = resolve(process.cwd(), 'build');

interface Manifest {
	name: string;
	start_url: string;
	scope: string;
	theme_color: string;
	background_color: string;
	icons: { src: string; sizes: string; type: string; purpose: string }[];
}

function manifest(): Manifest {
	return JSON.parse(readFileSync(join(BUILD, 'manifest.webmanifest'), 'utf8'));
}

function sourceFiles(): string[] {
	const out: string[] = [];
	const walk = (at: string) => {
		for (const entry of readdirSync(at, { withFileTypes: true })) {
			const path = join(at, entry.name);
			if (entry.isDirectory()) walk(path);
			else if (/\.(svelte|ts|js|html)$/.test(entry.name)) out.push(path);
		}
	};
	walk(resolve(process.cwd(), 'src'));
	return out;
}

test.describe('the web app manifest', () => {
	test('it is in the built site and it parses', () => {
		expect(existsSync(join(BUILD, 'manifest.webmanifest'))).toBe(true);
		const m = manifest();
		expect(m.name).toBeTruthy();
		expect(m.icons.length).toBeGreaterThanOrEqual(2);
	});

	test('every icon it declares exists in the built tree', () => {
		// Resolved the way a browser resolves a relative src against the
		// manifest's own URL, which is what makes the project path a non-issue.
		for (const icon of manifest().icons) {
			expect(icon.src.startsWith('./'), `${icon.src} is not relative`).toBe(true);
			const path = join(BUILD, icon.src.replace(/^\.\//, ''));
			expect(existsSync(path), `${icon.src} is declared and missing`).toBe(true);
		}
	});

	test('it carries a maskable icon as well as a plain one', () => {
		const purposes = manifest().icons.map((i) => i.purpose);
		expect(purposes).toContain('any');
		// Without one, a platform crops the square icon and takes the ends off the
		// mark. A maskable icon is a different drawing, not a crop.
		expect(purposes).toContain('maskable');
	});

	test('start_url and scope survive a project path', () => {
		const m = manifest();
		for (const field of [m.start_url, m.scope]) {
			expect(field.startsWith('/'), 'an absolute path breaks under a project path').toBe(false);
		}
	});

	test('the apple-touch icon is served, because Safari ignores the manifest for it', () => {
		expect(existsSync(join(BUILD, 'icons', 'apple-touch-icon.png'))).toBe(true);
	});
});

test.describe('what installability may not become', () => {
	test('nothing in the source touches notifications, push or background sync', () => {
		// The site ships a service worker since 2026-09-02, so this grep widened
		// rather than relaxed. A worker is the context in which every one of these
		// names becomes available and every one of them starts to sound
		// reasonable, and the ban is asserted rather than promised for exactly
		// that reason. `sourceFiles()` walks `src/`, so `src/service-worker.ts` is
		// inside it.
		const banned =
			/\bNotification\b|\bshowNotification\b|\bPushManager\b|\bpushManager\b|\bPushSubscription\b|\bperiodicSync\b|\bPeriodicSyncManager\b|\bSyncManager\b|registration\.sync\b/;
		const offenders = sourceFiles().filter((path) => banned.test(readFileSync(path, 'utf8')));
		expect(offenders, 'the reader decides when to read - CLAUDE.md section 0a').toEqual([]);
	});

	test('exactly one file registers the worker, and it is not the worker', () => {
		// `serviceWorker` used to be banned outright, which was the right rule
		// while there was no worker. What replaced it is narrower and says more:
		// the registration lives in one module a reviewer can read in full, so
		// "nothing else in this site reaches for the worker API" is a fact rather
		// than a hope.
		const naming = sourceFiles()
			.filter((path) => /\bnavigator\.serviceWorker\b/.test(readFileSync(path, 'utf8')))
			.map((path) => path.split(/[\\/]/).slice(-2).join('/'));
		expect(naming, 'the worker API is reached for in more than one place').toEqual([
			'lib/offline.ts'
		]);
	});

	test('the worker fetches nothing that is not our own origin', () => {
		const source = readFileSync(resolve(process.cwd(), 'src', 'service-worker.ts'), 'utf8');
		// Rule #1: a worker runs on the reader's device over files we already
		// serve. An absolute URL in it would be the one way that stops being true,
		// and the guard that keeps it true is read back here rather than trusted.
		expect(source.match(/https?:\/\/[^\s'"`]+/g) ?? [], 'the worker names an origin').toEqual([]);
		expect(source, 'the worker does not check the origin it is answering for').toContain(
			'url.origin !== sw.location.origin'
		);
	});

	test('the manifest asks for no messaging identity', () => {
		const raw = readFileSync(join(BUILD, 'manifest.webmanifest'), 'utf8');
		expect(raw).not.toContain('gcm_sender_id');
	});
});

test.describe('the browser chrome follows the page', () => {
	test('the manifest and its icons resolve from a deep route, not just the root', async ({
		page
	}) => {
		// The root page proves nothing: SvelteKit rewrites the asset prefix per
		// page depth, so the root emits './manifest.webmanifest' and a dated page
		// emits '../manifest.webmanifest'. What matters is that the URL a browser
		// actually resolves returns the file, from the deepest page there is.
		await page.goto('/');
		const deep = await page.evaluate(() => {
			const link = [...document.querySelectorAll<HTMLAnchorElement>('a[href]')]
				.map((a) => a.getAttribute('href') ?? '')
				.find((href) => /\/\d{4}-\d{2}-\d{2}\//.test(href) || /\/\d{4}\/\d{2}\/\d{2}\//.test(href));
			return link ?? null;
		});

		for (const route of [null, deep].filter((r) => r !== undefined)) {
			if (route) await page.goto(route);
			const resolved = await page.evaluate(() => {
				const href = document.querySelector('link[rel="manifest"]')?.getAttribute('href');
				const icon = document.querySelector('link[rel="apple-touch-icon"]')?.getAttribute('href');
				return {
					manifest: href ? new URL(href, location.href).href : null,
					icon: icon ? new URL(icon, location.href).href : null
				};
			});
			expect(resolved.manifest, `no manifest link on ${page.url()}`).toBeTruthy();

			const asManifest = await page.request.get(resolved.manifest as string);
			expect(asManifest.status(), `manifest 404s from ${page.url()}`).toBe(200);

			const body = await asManifest.json();
			for (const icon of body.icons) {
				const iconUrl = new URL(icon.src, resolved.manifest as string).href;
				const got = await page.request.get(iconUrl);
				expect(got.status(), `${icon.src} 404s from ${page.url()}`).toBe(200);
			}

			const apple = await page.request.get(resolved.icon as string);
			expect(apple.status(), `apple-touch-icon 404s from ${page.url()}`).toBe(200);
		}
	});

	test('the page ships one unconditional theme-color tag, before any script runs', async ({
		page
	}) => {
		// Read off the served bytes rather than the live DOM: an installed window
		// reads this at launch, and by the time a script has run the question has
		// already been answered. One tag and no media query, because the page is
		// dark whatever the system prefers - a tag scoped to the system
		// preference would be wrong for every reader whose system says light and
		// who has chosen nothing.
		const html = await (await page.request.get('/')).text();
		const tags = [...html.matchAll(/<meta[^>]*name="theme-color"[^>]*>/g)].map((m) => m[0]);
		expect(tags).toHaveLength(1);
		expect(tags[0], 'the chrome asks the system again').not.toContain('media=');
		expect(tags[0].toLowerCase()).toContain('#0b0e14');
	});

	test('a manual theme choice repaints the chrome', async ({ page }) => {
		await page.goto('/');

		// `paintBrowserChrome` in lib/theme.ts rewrites this tag, and only a click
		// reaches it: mount reads the stored choice and paints nothing. So the page
		// offers no DOM change that means "hydrated", and any fixed wait before the
		// click is a guess.
		const chrome = page.locator('meta[name="theme-color"]');
		const button = page.getByRole('button', { name: /Switch to the .* theme/ });

		// Clicking is what proves hydration, so poll on the label flipping rather
		// than on a timer. Before hydration the click lands on a button with no
		// handler and the label stays where it was.
		const flip = async (): Promise<string> => {
			const before = await button.getAttribute('aria-label');
			await expect
				.poll(async () => {
					await button.click();
					return await button.getAttribute('aria-label');
				})
				.not.toBe(before);
			return (await chrome.getAttribute('content'))?.trim() ?? '';
		};

		const light = await flip();
		expect(light, 'light left the chrome unpainted').toBeTruthy();

		const dark = await flip();
		expect(dark, 'dark left the chrome unpainted').toBeTruthy();
		expect(light).not.toBe(dark);
	});
});
