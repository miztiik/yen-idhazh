import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import { assetBaseUrl, encoderSource } from './asset-base.js';
import { uiConfig } from './src/lib/server/config';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	define: {
		// Where a drawing is asked for. A build-time constant and not a fetch,
		// because it cannot change between builds and a reader should not spend a
		// round trip learning it (docs/concepts/config.md, "Build-time config
		// versus shipped config"). At the shipped default it is the empty string,
		// so `__ASSET_BASE_URL__ || base` folds away and the bundle is unchanged.
		__ASSET_BASE_URL__: JSON.stringify(assetBaseUrl()),
		// The knobs the published surface draws itself from.
		//
		// **The root layout hands these to every page and it is a universal load,
		// so it cannot open `config/` itself.** A universal module may not import
		// `$lib/server/`, and the reason the layout is one is written beside its own
		// `load`. The same doc that owns the config names the answer: a knob a
		// surface genuinely needs is imported into the bundle at build time, never
		// fetched at read time, because it cannot change between builds and a round
		// trip on the first paint buys nothing. Copying `config/` into the published
		// tree was weighed there and refused - two copies of one file, free to drift.
		//
		// This is `uiConfig()` itself rather than a second merge written here, so
		// the three layers, the defaults and the build-only keys it strips all stay
		// in the one module that owns them (Rule #6).
		__UI_CONFIG__: JSON.stringify(uiConfig()),
		// Where the encoder comes from when our own origin cannot serve it, and the
		// SHA-256 of every file the browser will accept.
		//
		// A build-time constant for the same reason as the two above, and for one
		// more that is specific to this value: a manifest a page FETCHED could be
		// answered by whoever answered the fetch, which is the thing it exists to
		// guard against. Baked into the bundle, it is as trustworthy as the bundle.
		//
		// It rides in the `/archive/` route's chunk rather than the prerendered
		// document, because only `assist/loader.ts` reads it. That keeps roughly 600
		// bytes of hex out of the page-weight ceiling the archive document is
		// measured against, and out of its `__data.json` twin.
		__ENCODER_SOURCE__: JSON.stringify(encoderSource())
	}
});
