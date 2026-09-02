import adapter from '@sveltejs/adapter-static';
import { handleUnseenRoutes } from './prerender-guard.js';

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
		csp: {
			mode: 'auto',
			directives: {
				'default-src': ['self'],
				'connect-src': ['self'],
				// The encoder is WebAssembly, which needs its own compile permission.
				// It does NOT need 'unsafe-eval'.
				'script-src': ['self', 'wasm-unsafe-eval'],
				'style-src': ['self', 'unsafe-inline'],
				'img-src': ['self', 'data:'],
				'worker-src': ['self', 'blob:'],
				'object-src': ['none'],
				'base-uri': ['self']
			}
		}
	}
};
