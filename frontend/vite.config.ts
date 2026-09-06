import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { execSync } from 'node:child_process';
import { defineConfig } from 'vite';
import { assetBaseUrl } from './asset-base.js';

// The commit the reader is looking at. Injected at build time, never fetched
// and never read from a committed pointer file that could go stale.
function buildCommit(): string {
	if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA;
	try {
		return execSync('git rev-parse HEAD', { encoding: 'utf8' }).trim();
	} catch {
		return 'dev';
	}
}

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	define: {
		__BUILD_COMMIT__: JSON.stringify(buildCommit()),
		__BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10)),
		// Where a drawing is asked for. A build-time constant and not a fetch,
		// because it cannot change between builds and a reader should not spend a
		// round trip learning it (docs/concepts/config.md, "Build-time config
		// versus shipped config"). At the shipped default it is the empty string,
		// so `__ASSET_BASE_URL__ || base` folds away and the bundle is unchanged.
		__ASSET_BASE_URL__: JSON.stringify(assetBaseUrl())
	}
});
