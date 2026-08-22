import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { execSync } from 'node:child_process';
import { cpSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { defineConfig, type Plugin } from 'vite';

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

/**
 * Serve the visuals the pipeline rendered.
 *
 * `frontend/public/` is where `backend/` writes, and the page reads those
 * payloads through the filesystem at build time - so the JSON never needs
 * serving. A rendered chart is different: it is an `<img src>` the browser
 * fetches at runtime, and Vite only copies `static/` into the bundle. Without
 * this the payload would promise a picture at a path that returns 404, which is
 * worse than routing the item to no visual at all.
 *
 * Only image files are copied. The JSON payloads stay unserved on purpose:
 * publishing them would invite a runtime fetch, which is the thing the
 * prerendered design exists to avoid.
 */
const IMAGE_SUFFIXES = ['.svg', '.webp', '.png', '.jpg', '.jpeg'];

function copyRenderedVisuals(): Plugin {
	return {
		name: 'yen-idhazh:rendered-visuals',
		apply: 'build',
		closeBundle() {
			const source = 'public/digest';
			const target = 'build/digest';
			if (!existsSync(source)) return;
			let copied = 0;
			const walk = (relative: string) => {
				for (const name of readdirSync(join(source, relative))) {
					const next = join(relative, name);
					if (statSync(join(source, next)).isDirectory()) {
						walk(next);
					} else if (IMAGE_SUFFIXES.some((suffix) => name.toLowerCase().endsWith(suffix))) {
						cpSync(join(source, next), join(target, next), { recursive: false });
						copied += 1;
					}
				}
			};
			walk('');
			console.log(`rendered visuals: copied ${copied} file(s) into the bundle.`);
		}
	};
}

export default defineConfig({
	plugins: [tailwindcss(), sveltekit(), copyRenderedVisuals()],
	define: {
		__BUILD_COMMIT__: JSON.stringify(buildCommit()),
		__BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10))
	}
});
