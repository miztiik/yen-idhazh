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
	test('nothing in the source touches notifications or push', () => {
		const offenders = sourceFiles().filter((path) =>
			/\bNotification\b|\bPushManager\b|\bserviceWorker\b/.test(readFileSync(path, 'utf8'))
		);
		expect(offenders, 'the reader decides when to read - CLAUDE.md section 0a').toEqual([]);
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

	test('the page ships a media-scoped tag for each theme, before any script runs', async ({
		page
	}) => {
		await page.goto('/');
		// These are what an installed window reads at launch, and a script has not
		// necessarily run by then. One per theme, or the chrome is wrong for
		// whichever one is not covered.
		const tags = await page.evaluate(() =>
			[...document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"][media]')].map(
				(t) => ({ media: t.media, content: t.content })
			)
		);
		expect(tags).toHaveLength(2);
		expect(tags.map((t) => t.content)).not.toContain('');
		expect(tags[0].content).not.toBe(tags[1].content);
	});

	test('a manual theme choice repaints the chrome', async ({ page }) => {
		await page.goto('/');
		const result = await page.evaluate(async () => {
			const read = () =>
				document
					.querySelector<HTMLMetaElement>('meta[name="theme-color"]:not([media])')
					?.content?.trim() ?? null;
			const buttons = [...document.querySelectorAll('[aria-label="Theme"] button')];
			const byLabel = (text: string) =>
				buttons.find((b) => (b.textContent ?? '').trim().startsWith(text)) as HTMLElement | undefined;
			byLabel('Dark')?.click();
			await new Promise((done) => setTimeout(done, 250));
			const dark = read();
			byLabel('Light')?.click();
			await new Promise((done) => setTimeout(done, 250));
			return { dark, light: read(), buttons: buttons.length };
		});
		expect(result.buttons).toBeGreaterThan(0);
		expect(result.dark).toBeTruthy();
		expect(result.light).toBeTruthy();
		expect(result.light).not.toBe(result.dark);
	});
});
