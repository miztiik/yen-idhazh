import adapter from '@sveltejs/adapter-static';

// Every page is prerendered, so the reading path makes zero runtime requests
// (Holy Law #1) and there is no loading state to design.
export default {
	kit: {
		adapter: adapter({ fallback: '404.html', strict: false }),
		paths: { base: process.env.BASE_PATH ?? '' },
		prerender: { handleHttpError: 'warn' }
	}
};
