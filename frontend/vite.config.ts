import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import { assetBaseUrl } from './asset-base.js';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	define: {
		// Where a drawing is asked for. A build-time constant and not a fetch,
		// because it cannot change between builds and a reader should not spend a
		// round trip learning it (docs/concepts/config.md, "Build-time config
		// versus shipped config"). At the shipped default it is the empty string,
		// so `__ASSET_BASE_URL__ || base` folds away and the bundle is unchanged.
		__ASSET_BASE_URL__: JSON.stringify(assetBaseUrl())
	}
});
