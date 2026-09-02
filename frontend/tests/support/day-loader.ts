/** The shipped day loader, bundled the way the site bundles it, for a spec that
 * needs it live in a page.
 *
 * Two specs drive `$lib/assist/day.ts` in a real browser rather than in Node,
 * because the thing under test is a fetch and a fetch needs a network layer to
 * intercept. Neither can `import` the module directly: it takes `base` from
 * `$app/paths` as a VALUE, which only SvelteKit's own build resolves. So Vite
 * bundles it here with that one import aliased to a file holding the base a
 * GitHub Pages project path would give it, and the result is injected into a
 * page of the real built site.
 *
 * **The base is a project path on purpose.** It is not the empty string the
 * preview server serves from, so a URL the loader built without `base` cannot
 * match the pattern a spec routes on, and the intercept count would be zero -
 * which every arm here fails on.
 *
 * UMD rather than a bare IIFE, because a UMD wrapper assigns the global itself
 * instead of relying on how an injected script scopes a `var`. `write: false`
 * keeps the bundle in memory; the one file it does write is the alias stub,
 * under `test-results/`, which is gitignored scratch and never ships.
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build, type Rollup } from 'vite';

const here = path.dirname(fileURLToPath(import.meta.url));
export const FRONTEND = path.resolve(here, '..', '..');

/** A project path, the way GitHub Pages serves this site. */
export const BASE = '/yen-idhazh';

/** What the bundled module hands the page. */
export interface Loader {
	watchDay: (
		date: string,
		watch: {
			onStatus: (status: string, day: { items: unknown[] } | null) => void;
			slowMs: number;
			again?: boolean;
		}
	) => Promise<{ items: unknown[] } | null>;
	dayUrl: (date: string, root?: string) => string | null;
	restoreAnchor: (hash?: string) => boolean;
}

/** The address the loader must ask for, spelled out rather than rebuilt from
 * `dayUrl` - a helper that agreed with the code under test would prove nothing. */
export function servedDayUrl(date: string): string {
	const [year, month, day] = date.split('-');
	return `${BASE}/digest/${year}/${month}/${day}/digest.json`;
}

/** Every interception, counted and named, so a zero cannot read as a pass. */
export class Intercepted {
	readonly urls: string[] = [];

	get count(): number {
		return this.urls.length;
	}

	take(url: string): void {
		this.urls.push(new URL(url).pathname);
	}
}

export async function loaderSource(scratchName: string): Promise<string> {
	const scratch = path.join(FRONTEND, 'test-results', scratchName);
	mkdirSync(scratch, { recursive: true });
	const paths = path.join(scratch, 'app-paths.js');
	writeFileSync(paths, `export const base = ${JSON.stringify(BASE)};\nexport const assets = '';\n`);
	const built = await build({
		configFile: false,
		logLevel: 'silent',
		resolve: { alias: { '$app/paths': paths, $lib: path.join(FRONTEND, 'src', 'lib') } },
		build: {
			write: false,
			minify: false,
			lib: {
				entry: path.join(FRONTEND, 'src', 'lib', 'assist', 'day.ts'),
				formats: ['umd'],
				name: 'dayLoader',
				fileName: () => 'day.js'
			}
		}
	});
	const bundles = (Array.isArray(built) ? built : [built]) as Rollup.RollupOutput[];
	const chunk = bundles[0]?.output.find((part) => part.type === 'chunk');
	if (!chunk || chunk.type !== 'chunk') throw new Error('the day loader did not bundle');
	return chunk.code;
}
