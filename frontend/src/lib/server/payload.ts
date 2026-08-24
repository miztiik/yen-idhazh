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

/** Where the published payloads are read from.
 *
 * Overridable so the canary suite can build a site out of planted attacks
 * without those attacks ever entering the real published tree. There is no
 * other caller, and nothing at runtime reads this - the value is baked into the
 * prerender.
 */
export const DIGEST_ROOT = process.env.DIGEST_ROOT
	? resolve(process.env.DIGEST_ROOT)
	: join(process.cwd(), 'public', 'digest');

/** Where the committed ledgers are read from.
 *
 * Overridable for the same reason `DIGEST_ROOT` is: the canary suite builds a
 * site out of fixture runs, and a fixture must never be able to reach the real
 * ledger. Read at build time only. Nothing under `state/` is ever served - the
 * page carries the numbers, never the file.
 */
export const STATE_ROOT = process.env.STATE_ROOT
	? resolve(process.env.STATE_ROOT)
	: join(REPO_ROOT, 'state');

export const TELEMETRY_ROOT = process.env.TELEMETRY_ROOT
	? resolve(process.env.TELEMETRY_ROOT)
	: join(process.cwd(), 'public', 'telemetry');

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

/** The cells of a CSV, quoting and all.
 *
 * The backend writes these with `csv.DictWriter`, which quotes any field that
 * carries a comma, a quote or a newline - and the health ledger's `detail` is
 * free text from a host that just failed. Splitting on commas is right until it
 * is not, and a mangled cell reads like a real value, which is worse than an
 * empty one. Twenty lines beat a dependency for two build-time readers.
 */
function parseCsv(text: string): string[][] {
	const rows: string[][] = [];
	let row: string[] = [];
	let cell = '';
	let quoted = false;
	for (let i = 0; i < text.length; i += 1) {
		const ch = text[i];
		if (quoted) {
			// Two quotes inside a quoted field are one literal quote.
			if (ch === '"' && text[i + 1] === '"') {
				cell += '"';
				i += 1;
			} else if (ch === '"') {
				quoted = false;
			} else {
				cell += ch;
			}
		} else if (ch === '"') {
			quoted = true;
		} else if (ch === ',') {
			row.push(cell);
			cell = '';
		} else if (ch === '\n' || (ch === '\r' && text[i + 1] === '\n')) {
			if (ch === '\r') i += 1;
			row.push(cell);
			rows.push(row);
			row = [];
			cell = '';
		} else {
			cell += ch;
		}
	}
	// A file with no trailing newline still ends on a real row.
	if (cell !== '' || row.length > 0) {
		row.push(cell);
		rows.push(row);
	}
	return rows;
}

/** A CSV read into named cells, with the column order it was written in. */
export interface CsvTable {
	rows: Record<string, string>[];
	columns: string[];
}

/** A CSV as named cells. A missing file is empty, never an error. */
export function readCsv(path: string): CsvTable {
	if (!existsSync(path)) return { rows: [], columns: [] };
	const parsed = parseCsv(readFileSync(path, 'utf8')).filter((row) => row.some((cell) => cell !== ''));
	const columns = parsed[0] ?? [];
	const rows = parsed
		.slice(1)
		.map((cells) => Object.fromEntries(columns.map((name, index) => [name, cells[index] ?? ''])));
	return { rows, columns };
}

/** One row per scored item, read from the committed ledger and never recomputed. */
export function evalRows(): CsvTable {
	return readCsv(join(STATE_ROOT, 'scores.csv'));
}

/** One row per planned item per run, read from month shards. */
export function itemHealthRows(): CsvTable {
	const dir = join(STATE_ROOT, 'item-health');
	if (!existsSync(dir)) return { rows: [], columns: [] };
	const rows: Record<string, string>[] = [];
	let columns: string[] = [];
	for (const shard of readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.sort()) {
		const table = readCsv(join(dir, shard));
		if (columns.length === 0 && table.columns.length > 0) columns = table.columns;
		rows.push(...table.rows);
	}
	return { rows, columns };
}

/** Public monthly telemetry shards. These are safe for a browser to fetch. */
export function telemetryMonths(root: string = TELEMETRY_ROOT): string[] {
	if (!existsSync(root)) return [];
	return readdirSync(root)
		.filter((name) => /^\d{4}-\d{2}\.csv$/.test(name))
		.map((name) => name.slice(0, 7))
		.sort();
}

/** Initial telemetry for the SSR fallback. Runtime panning fetches the same files. */
export function telemetryRows(root: string = TELEMETRY_ROOT): CsvTable {
	const rows: Record<string, string>[] = [];
	let columns: string[] = [];
	for (const month of telemetryMonths(root)) {
		const table = readCsv(join(root, `${month}.csv`));
		if (columns.length === 0 && table.columns.length > 0) columns = table.columns;
		rows.push(...table.rows);
	}
	return { rows, columns };
}

export interface FeedResult {
	runId: string;
	date: string;
	feedId: string;
	outcome: string;
	status: number | null;
	items: number;
	detail: string;
}

/** Every feed result on record, oldest shard first.
 *
 * Sharded by month under `state/feed-health/`, so this reads a directory rather
 * than a file. Absent is the ordinary state of a fresh clone: no run has
 * written a record yet, and no record is exactly what an empty list says.
 */
export function feedResults(): FeedResult[] {
	const dir = join(STATE_ROOT, 'feed-health');
	if (!existsSync(dir)) return [];
	const found: FeedResult[] = [];
	for (const shard of readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.sort()) {
		for (const row of readCsv(join(dir, shard)).rows) {
			found.push({
				runId: row.run_id ?? '',
				date: row.date ?? '',
				feedId: row.feed_id ?? '',
				outcome: row.outcome ?? '',
				status: row.status ? Number(row.status) : null,
				items: Number(row.items ?? 0) || 0,
				detail: row.detail ?? ''
			});
		}
	}
	return found;
}

/** One run of one day, as the manifest recorded it. */
export interface RunRecord {
	runId: string;
	n: number;
	status: string;
	planned: number;
	succeeded: number;
	failed: number;
	skipped: number;
	startedAt: string;
	sourceListStale: boolean;
}

export interface RunSummary {
	date: string;
	runs: number;
	planned: number;
	failed: number;
	siteBytes: number;
	siteFiles: number;
	models: string[];
	records: RunRecord[];
}

/** What each run manifest recorded about itself, newest first.
 *
 * The manifest is the only place run-level facts live. Widening a per-item row
 * to carry them would leave every item row with columns that are blank for it.
 *
 * Every figure here belongs to a run, not to the day: the manifest holds no
 * top-level counts at all. The day's totals are summed across its runs, and the
 * site size is taken from the last run rather than added up - the site is one
 * thing measured once per run, not a new thing each run.
 */
export function loadManifests(root: string = DIGEST_ROOT): RunSummary[] {
	const found: RunSummary[] = [];
	for (const date of publishedDates(root)) {
		const [year, month, day] = date.split('-');
		const path = join(root, year, month, day, 'run.json');
		if (!existsSync(path)) continue;
		try {
			const manifest = JSON.parse(readFileSync(path, 'utf8'));
			const runs: Record<string, unknown>[] = manifest.runs ?? [];
			const records: RunRecord[] = runs.map((run) => ({
				runId: String(run.run_id ?? ''),
				n: Number(run.n ?? 0) || 0,
				status: String(run.status ?? ''),
				planned: Number(run.items_planned ?? 0) || 0,
				succeeded: Number(run.items_succeeded ?? 0) || 0,
				failed: Number(run.items_failed ?? 0) || 0,
				skipped: Number(run.items_skipped ?? 0) || 0,
				startedAt: String(run.started_at ?? ''),
				sourceListStale: run.source_list_stale === true
			}));
			const last = runs.at(-1) ?? {};
			const models = runs.flatMap((run) =>
				((run.models ?? []) as { model_ref?: { id?: string } }[]).map((use) => use.model_ref?.id ?? '?')
			);
			found.push({
				date,
				runs: records.length,
				planned: records.reduce((total, run) => total + run.planned, 0),
				failed: records.reduce((total, run) => total + run.failed, 0),
				siteBytes: Number(last.site_bytes ?? 0) || 0,
				siteFiles: Number(last.site_files ?? 0) || 0,
				models: [...new Set(models)],
				records
			});
		} catch {
			// A manifest that will not parse costs the console one row, never the page.
		}
	}
	return found;
}
