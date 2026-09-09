import adapter from '@sveltejs/adapter-static';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { assetBaseUrl, connectSources } from './asset-base.js';
import { handleUnseenRoutes } from './prerender-guard.js';

/** The CSP hash of every inline script `src/app.html` carries.
 *
 * **`mode: 'auto'` covers our inline script on a prerendered page and not on the
 * fallback.** SvelteKit hashes the scripts of a page it prerenders and nonces
 * the scripts of one it renders dynamically, and `404.html` is the second kind -
 * so from 2026-09-09, when that document started answering every dated address,
 * the theme script in `app.html` was blocked on every one of them. What a reader
 * lost was small and only visible to some of them: the stored light choice is
 * applied by that script before the first frame, so a light-theme reader met a
 * dark flash on a dated URL and nowhere else.
 *
 * A hash source and a nonce source coexist in one directive - a script matching
 * either is allowed - so this adds the hash and changes nothing about the nonce.
 *
 * Derived rather than written down, because a hash somebody pasted goes stale
 * the next time the script is edited and takes the theme with it, silently
 * (Rule #6).
 */
function inlineScriptHashes() {
	const shell = readFileSync(
		join(dirname(fileURLToPath(import.meta.url)), 'src', 'app.html'),
		'utf8'
	);
	return [...shell.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(
		(found) => `sha256-${createHash('sha256').update(found[1], 'utf8').digest('base64')}`
	);
}

// SvelteKit's own default for `kit.version.name` is one `Date.now()` taken when
// its options module loads, so it is the same string for every pass of a build.
// A `Date.now()` written HERE is not: this file is evaluated once per pass, so
// the client chunk and the prerendered documents end up naming two different
// `__sveltekit_<id>` globals and every page throws on hydration. So the key is
// present only when `BUILD_VERSION` is, which is how a byte measurement pins the
// id without editing this file - see docs/reference/agent-notes.md.
const version = process.env.BUILD_VERSION ? { name: process.env.BUILD_VERSION } : undefined;

// Every page is prerendered, and since 2026-09-01 that is a statement about the
// DOCUMENT rather than about the item list inside it. A reading route ships the
// head of its day and the browser fetches the rest from a file this same site
// publishes, so the reading path makes at most one same-origin request and the
// first frame is readable without it (Rule #1). `/`, `/archive/`, `/404` and
// `/evals/` still make none at all.
export default {
	kit: {
		adapter: adapter({ fallback: '404.html', strict: false }),
		paths: { base: process.env.BASE_PATH ?? '' },
		...(version ? { version } : {}),
		// `src/service-worker.ts` is built and shipped; registering it is ours.
		// The framework's own snippet registers on load with no `catch`, so a
		// browser that refuses - a private window, a policy, a test that blocks
		// them - turns into an unhandled rejection on every page. Ours is one
		// call in one module, which is also the one place `serviceWorker` is
		// named and therefore the one place a test has to read.
		//
		// `files` decides what `$service-worker` hands the worker, and the default
		// is everything under `static/`. That is the wrong default here:
		// `static/digest/` is staged from the pipeline's own output, so the
		// default baked the path of every published day and every rendered visual
		// into the worker - 16,888 bytes of strings on 2026-09-02, growing with
		// the archive. What is left is the shell's own assets, which is what the
		// worker keeps for offline reading.
		serviceWorker: {
			register: false,
			/** @param {string} path */
			files: (path) =>
				path === 'favicon.svg' ||
				path === 'manifest.webmanifest' ||
				// The font itself, not the licence and the provenance note beside it.
				(path.startsWith('fonts/') && path.endsWith('.woff2')) ||
				path.startsWith('icons/')
		},
		// A dated route has no page until a day is published, and a clone has to
		// build before its first run. The guard tells that apart from a page that
		// went missing - see `prerender-guard.js`.
		prerender: { handleHttpError: 'warn', handleUnseenRoutes },
		// GitHub Pages serves no headers we control, so this ships as a meta tag
		// in every prerendered page. `connect-src 'self'` is the one that matters:
		// it makes exfiltration from a planted instruction a browser-level
		// impossibility rather than a property of our own code being careful.
		//
		// **The migration made it MORE load-bearing, not less.** The header is
		// emitted per rendered document, a shell is a rendered document, and a
		// reading shell now fetches. So the one directive bounds every request the
		// page can make, wherever in our source the URL was built - which is a
		// stronger guarantee than a rule about how carefully `assist/day.ts`
		// assembles a path.
		//
		// Which is why `connect-src` is derived rather than written: when
		// `visuals.asset_base_url` names a host, the drawings are asked for there,
		// and this directive is the thing that would otherwise refuse them. Both
		// halves read the one config value, so the valve opens on a config edit and
		// not on a second source edit nobody documented. At the shipped default the
		// list is `['self']` and this meta tag is byte-identical to what it was.
		csp: {
			mode: 'auto',
			directives: {
				'default-src': ['self'],
				'connect-src': connectSources(assetBaseUrl()),
				// The encoder is WebAssembly, which needs its own compile permission.
				// It does NOT need 'unsafe-eval'.
				'script-src': ['self', 'wasm-unsafe-eval', ...inlineScriptHashes()],
				'style-src': ['self', 'unsafe-inline'],
				'img-src': ['self', 'data:'],
				'worker-src': ['self', 'blob:'],
				'object-src': ['none'],
				'base-uri': ['self']
			}
		}
	}
};
