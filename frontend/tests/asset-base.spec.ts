/** The release valve for the published site's 1 GB ceiling, driven both ways.
 *
 * `visuals.asset_base_url` decides where a browser asks for a drawing and
 * whether that drawing also ships in the bundle. It is committed empty, and
 * this file's first job is to keep it that way: a valve that changes the
 * default output is not a valve, it is a change.
 *
 * The other arms drive it OPEN. A bound tested in one direction only is not a
 * bound - a `connectSources` that ignored its argument and always answered
 * `['self']` would pass the shut arm and ship a site that fetches nothing.
 *
 * This is a `logic` spec and not a browser one on purpose. The canary day the
 * browser suite builds is 8 stories against a seed of 15, so every drawing is
 * already in the document and nothing in a browser can reach the fetch this
 * valve moves. `item-visual.spec.ts` says the same thing about the same code.
 * So the fetch expression is asserted against the source, which is where the
 * fold that keeps the default byte-identical is visible anyway.
 */

import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { assetBaseUrl, connectSources } from '../asset-base.js';

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..');

/** A real host with a real `Access-Control-Allow-Origin`, not a placeholder. */
const OPEN = 'https://raw.githubusercontent.com/miztiik/yen-idhazh/refs/heads/main/frontend/public';

test.describe('the asset base URL ships shut', () => {
	test('the committed config names no host', () => {
		expect(assetBaseUrl()).toBe('');
	});

	test('the committed CSP admits this origin and nothing else', () => {
		// Read as source rather than through an import, because the config the
		// module would read is the same one the test above just pinned - so an
		// import would only prove the two agree, not that what is COMMITTED is
		// `['self']`. A deploy ships the file, not the call.
		const config = readFileSync(join(FRONTEND, 'svelte.config.js'), 'utf8');
		expect(config).toContain("'connect-src': connectSources(assetBaseUrl())");
		expect(connectSources(assetBaseUrl())).toEqual(['self']);
	});
});

test.describe('the asset base URL opens', () => {
	test('a named host is added to connect-src, and self stays', () => {
		expect(connectSources(OPEN)).toEqual(['self', 'https://raw.githubusercontent.com']);
	});

	test('the path in the value is a directory, not a permission', () => {
		// CSP has no business knowing which folder the drawings sit in, and a
		// directory in a source list is a directive that does not do what it looks
		// like it does.
		expect(connectSources(OPEN)[1]).not.toContain('/miztiik');
	});

	test('an empty value is the only thing that means this site', () => {
		expect(connectSources('')).toEqual(['self']);
		expect(connectSources(OPEN)).not.toEqual(['self']);
	});
});

test.describe('the valve moves the URL and not the carrier', () => {
	test('the drawing is still fetched as text and inlined', () => {
		const component = readFileSync(
			join(FRONTEND, 'src', 'lib', 'components', 'ItemVisual.svelte'),
			'utf8'
		);
		// `|| base` and not a ternary or a helper: at the shipped default the
		// constant is `''`, so the minifier folds the whole expression to `base`
		// and the built tree is byte-identical to one built without this valve.
		// Measured 2026-09-06 on Intel Core i7-1265U / Windows 11 / node 24.12.0,
		// two builds at a pinned `BUILD_VERSION`: 685 files, 111,255,143 bytes,
		// zero differing hashes.
		//
		// The address and not the whole call. What follows it is the caller's own
		// business - a story that leaves the page aborts its request - and a test
		// that pins the argument list goes red on a change that never touched the
		// valve, which is how a valve test stops being one.
		expect(component).toContain('fetch(`${__ASSET_BASE_URL__ || base}/${file}`');
		// The response is read as text and inlined. An `img` cannot be repainted
		// from the page's tokens, which is why it was removed and why moving the
		// bytes must not bring it back.
		expect(component).toContain('await response.text()');
		expect(component).not.toContain('<img');
		// And the path is still refused before either half is joined onto it.
		expect(component).toContain('if (!publishedVisual(file))');
	});

	test('the staging step and the fetch read the one value', () => {
		// Two switches would let the bundle keep a copy of every drawing the page
		// is asking a host for, and the valve would move nothing.
		const staging = readFileSync(join(FRONTEND, 'scripts', 'copy-visuals.mjs'), 'utf8');
		expect(staging).toContain("import { assetBaseUrl } from '../asset-base.js'");
		expect(staging).toContain("const servedElsewhere = assetBaseUrl() !== ''");
	});
});
