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

// Every page is prerendered, so the reading path makes zero runtime requests
// (Rule #1) and there is no loading state to design.
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
