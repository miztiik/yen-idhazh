/** The one payload loader. Lives under `$lib/server/` so SvelteKit refuses to
 * bundle it into anything a browser receives.
 *
 * Prerendering is what removes the loading state, the spinner and the runtime
 * request all at once: by the time a reader has the page, the items are already
 * in the HTML.
 */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { DigestDay } from '$lib/payload/types';

/** The build runs from `frontend/`, so the repo root is one level up. */
export const REPO_ROOT = resolve(process.cwd(), '..');
export const DIGEST_ROOT = join(process.cwd(), 'public', 'digest');

const DATE_PART = /^\d{2,4}$/;

/** Every published date, newest first. Read from the committed tree, not an index file. */
export function publishedDates(root: string = DIGEST_ROOT): string[] {
	if (!existsSync(root)) return [];
	const found: string[] = [];
	for (const year of dirsIn(root)) {
		for (const month of dirsIn(join(root, year))) {
			for (const day of dirsIn(join(root, year, month))) {
				if (existsSync(join(root, year, month, day, 'digest.json'))) {
					found.push(`${year}-${month}-${day}`);
				}
			}
		}
	}
	return found.sort().reverse();
}

function dirsIn(path: string): string[] {
	if (!existsSync(path)) return [];
	return readdirSync(path, { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && DATE_PART.test(entry.name))
		.map((entry) => entry.name)
		.sort();
}

/** A day, or null when that date was never published. Null is a designed state, not an error. */
export function loadDay(date: string, root: string = DIGEST_ROOT): DigestDay | null {
	const [year, month, day] = date.split('-');
	if (!year || !month || !day) return null;
	const path = join(root, year, month, day, 'digest.json');
	if (!existsSync(path)) return null;
	return JSON.parse(readFileSync(path, 'utf8')) as DigestDay;
}

export function latestDate(root: string = DIGEST_ROOT): string | null {
	return publishedDates(root)[0] ?? null;
}

/** One row per scored item, read from the committed ledger and never recomputed. */
export function evalRows(): { rows: Record<string, string>[]; columns: string[] } {
	const path = join(REPO_ROOT, 'evals', 'scores.csv');
	if (!existsSync(path)) return { rows: [], columns: [] };
	const lines = readFileSync(path, 'utf8').trim().split('\n');
	const columns = lines[0]?.split(',') ?? [];
	const rows = lines.slice(1).map((line) => {
		const cells = line.split(',');
		return Object.fromEntries(columns.map((name, index) => [name, cells[index] ?? '']));
	});
	return { rows, columns };
}
