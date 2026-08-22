import adapter from '@sveltejs/adapter-static';

// Every page is prerendered, so the reading path makes zero runtime requests
// (Holy Law #1) and there is no loading state to design.
export default {
	kit: {
		adapter: adapter({ fallback: '404.html', strict: false }),
		paths: { base: process.env.BASE_PATH ?? '' },
		prerender: { handleHttpError: 'warn' },
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
