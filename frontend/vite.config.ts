import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import { assetBaseUrl, encoderSource } from './asset-base.js';
import { assistConfig, consoleConfig, engineExtensionRepository, explorerConfig, frameConfig, iconsConfig, ledgerArchiveBaseUrl, uiConfig } from './src/lib/server/config';
import { queryEngineAssetModule } from './scripts/query-engine-assets';
import { rawListedThrough } from './scripts/raw-listed-through.mjs';
import { publishedLedgers } from './scripts/published-ledgers.mjs';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit(), queryEngineAssetModule()],
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
		// in the one module that owns them (Guardrail #6).
		__UI_CONFIG__: JSON.stringify(uiConfig()),
		// What on-device search reads, keeps and shows.
		//
		// The archive gets these through its own `load`, which is a server load
		// because that route is prerendered. A reading route is not: one shell
		// answers every dated URL and its load is universal, so there is no server
		// reader on it at all. Putting them on the root layout instead would inline
		// four numbers into every prerendered document on the site, `/404` among
		// them, for two surfaces that use them - so they ride as a define and land
		// only in the chunk that opens them.
		//
		// `assistConfig()` itself rather than a second merge written here, so the
		// keep-list that decides what a browser may see stays in the one module that
		// owns it (Guardrail #6).
		__ASSIST_CONFIG__: JSON.stringify(assistConfig()),
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
		__ENCODER_SOURCE__: JSON.stringify(encoderSource()),
		// Where the query engine downloads its add-ons; `connect-src` admits the same origin.
		__ENGINE_EXTENSION_REPOSITORY__: JSON.stringify(engineExtensionRepository()),
		// Where Records reads older packed ledgers; the page fetches whole files and hands buffers to the engine.
		__ARCHIVE_BASE_URL__: JSON.stringify(ledgerArchiveBaseUrl()),
		__CONSOLE_CONFIG__: JSON.stringify(consoleConfig()),
		__EXPLORER_CONFIG__: JSON.stringify(explorerConfig()),
		__FRAME_CONFIG__: JSON.stringify(frameConfig()),
		__PUBLISHED_LEDGERS__: JSON.stringify(publishedLedgers()),
		__RAW_LISTED_THROUGH__: JSON.stringify(rawListedThrough()),
		// The icon line width in screen pixels. Icon.svelte converts it to Lucide's 24-unit grid.
		__ICON_STROKE_PX__: JSON.stringify(iconsConfig().stroke_px)
	}
});
