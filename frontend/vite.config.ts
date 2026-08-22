import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { execSync } from 'node:child_process';
import { defineConfig } from 'vite';

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
		__BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10))
	}
});
