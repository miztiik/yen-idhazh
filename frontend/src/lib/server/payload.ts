/** The one payload loader. Lives under `$lib/server/` so SvelteKit refuses to
 * bundle it into anything a browser receives.
 *
 * Prerendering is what removes the loading state, the spinner and the runtime
 * request all at once: by the time a reader has the page, the items are already
 * in the HTML.
 */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
// Relative, not `$lib`: the browser suite imports this module in plain Node,
// where no Vite alias exists to resolve one.
import { dayKey, toDay } from '../charts/viewport';
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

/** Where the month indexes are read from.
 *
 * Derived from the digest root rather than given a switch of its own, because
 * an index is a projection of exactly those days. `scripts/copy-visuals.mjs`
 * derives the staging source the same way, so a canary build cannot end up
 * listing the real archive's stories.
 */
export const INDEX_ROOT = process.env.DIGEST_ROOT
	? resolve(process.env.DIGEST_ROOT, '..', 'assist', 'index')
	: join(process.cwd(), 'public', 'assist', 'index');

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

/** A day, or null when that date was never published. Null is a designed state, not an error.
 *
 * **The vectors are dropped here, and this is the only place they can be.**
 * Whatever this returns is inlined into every prerendered document that renders
 * the day, and nothing in a browser opens the block: its one production reader
 * is the backend's index rebuild, which reads `frontend/public/` from disk. The
 * committed payload keeps it - that tree is the only store the vectors have.
 *
 * Measured 2026-08-27 on Intel Core i7-1265U / Windows 11 / node 24.12.0, six
 * committed days, 2,237 items, `gzip -9`, heaviest of five builds: the block
 * was 232,462 of the 581,553 gzipped bytes of `/<date>/`, which is 40.0 percent
 * of a page nobody could read it on, and it rode in twelve documents per day.
 */
export function loadDay(date: string, root: string = DIGEST_ROOT): DigestDay | null {
	const [year, month, day] = date.split('-');
	if (!year || !month || !day) return null;
	const path = join(root, year, month, day, 'digest.json');
	if (!existsSync(path)) return null;
	const payload = JSON.parse(readFileSync(path, 'utf8')) as DigestDay;
	return { ...payload, embeddings: null };
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

/** Every month with an index on disk, newest first.
 *
 * The names only. The stories inside them are fetched by the browser, which is
 * what keeps the archive page a fixed size while the corpus grows.
 */
export function indexMonths(root: string = INDEX_ROOT): string[] {
	if (!existsSync(root)) return [];
	return readdirSync(root)
		.filter((name) => /^\d{4}-\d{2}\.json$/.test(name))
		.map((name) => name.slice(0, 7))
		.sort()
		.reverse();
}

const DAY_MS = 86_400_000;

/** The oldest day the seed keeps, or null when no month holds a dated row.
 *
 * Anchored on the newest day on record rather than on today, because that is
 * what the viewport anchors its opening window on. Anchored on today instead,
 * a corpus that stopped last month would seed an empty page.
 */
function seedCutoff(
	months: string[],
	read: (month: string) => CsvTable,
	windowDays: number
): string | null {
	for (const month of [...months].reverse()) {
		const dates = read(month)
			.rows.map((row) => row.date ?? '')
			.filter((date) => date !== '');
		if (dates.length === 0) continue;
		const newest = dates.reduce((later, date) => (date > later ? date : later));
		return dayKey(new Date(toDay(newest).getTime() - (windowDays - 1) * DAY_MS));
	}
	return null;
}

/** Initial telemetry for the SSR fallback. Runtime panning fetches the same files.
 *
 * `windowDays` bounds the seed to the window the viewport opens on. Without it
 * every committed month is concatenated and inlined into the prerendered HTML,
 * so the page a reader downloads grows for as long as the pipeline runs. The
 * month shards are untouched, so panning back still reaches the dropped days -
 * the browser fetches the same files it always did.
 *
 * A window is a count of days, so it can straddle a month boundary. Reading is
 * still bounded: the shards are monthly, so the worst case is two of them.
 */
export function telemetryRows(root: string = TELEMETRY_ROOT, windowDays?: number): CsvTable {
	const months = telemetryMonths(root);
	const shards = new Map<string, CsvTable>();
	const read = (month: string): CsvTable => {
		let table = shards.get(month);
		if (!table) {
			table = readCsv(join(root, `${month}.csv`));
			shards.set(month, table);
		}
		return table;
	};

	const cutoff =
		windowDays !== undefined && windowDays > 0 ? seedCutoff(months, read, windowDays) : null;
	const rows: Record<string, string>[] = [];
	let columns: string[] = [];
	for (const month of months) {
		if (cutoff !== null && month < cutoff.slice(0, 7)) continue;
		const table = read(month);
		if (columns.length === 0 && table.columns.length > 0) columns = table.columns;
		rows.push(...table.rows.filter((row) => cutoff === null || (row.date ?? '') >= cutoff));
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
	/** Items the router posted to the model. */
	routed: number;
	/** Items the router decided without posting, because no enabled kind could survive its checks. */
	prefiltered: number;
	/** Items whose routing reply asked for a chart, whatever the decision became. */
	chartsDrafted: number;
	/** What the router spent, or null where the run wrote no time down at all.
	 *
	 * Null and zero are different facts: a route job that never ran spent no
	 * measured time, and printing that as zero minutes reads as a stage that was
	 * free rather than one that is missing. */
	routeMs: number | null;
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
				sourceListStale: run.source_list_stale === true,
				routed: Number(run.items_routed ?? 0) || 0,
				prefiltered: Number(run.items_prefiltered ?? 0) || 0,
				chartsDrafted: Number(run.charts_drafted ?? 0) || 0,
				// The manifest writes an integer or a literal null. `Number(null)` is 0,
				// so coercing here would turn "never measured" into "measured zero".
				routeMs: typeof run.route_ms === 'number' ? run.route_ms : null
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

/** Articles each published day carries, from the day payload itself.
 *
 * The denominator of the site's per-article cost, and it is read from the same
 * tree the numerator is: `site_bytes` measures `frontend/public/digest/`, and
 * so does this. Taking the count off a run manifest instead would divide the
 * bytes of one tree by somebody else's articles the first time a run planned
 * items it did not publish - which is the lesson
 * `backend/idhazh/retention.py` already wrote down about its own pairing.
 */
export function publishedItems(root: string = DIGEST_ROOT): Map<string, number> {
	const found = new Map<string, number>();
	for (const date of publishedDates(root)) {
		const day = loadDay(date, root);
		if (day === null) continue;
		found.set(date, day.items.length);
	}
	return found;
}

/** What one published day put on a page: its items, and the charts among them. */
export interface DayVisuals {
	/** Every item the day published. The denominator of the arm's coverage rule. */
	items: number;
	/** Charts a reader can actually see. */
	charts: number;
}

/** Charts a reader can actually see on each published day, and what they are of.
 *
 * Counted from the day payload rather than from the manifest, because the
 * manifest records what the router decided and this records what survived to
 * the page. A chart whose render failed, and a diagram, are both visuals and
 * neither is a published chart.
 *
 * The item count rides along rather than costing a second pass: the arm's
 * second threshold is a share of what the day published, and the day payload is
 * already open here.
 */
export function publishedCharts(root: string = DIGEST_ROOT): Map<string, DayVisuals> {
	const found = new Map<string, DayVisuals>();
	for (const date of publishedDates(root)) {
		const day = loadDay(date, root);
		if (day === null) continue;
		found.set(date, {
			items: day.items.length,
			charts: day.items.filter(
				(item) => item.visual?.kind === 'chart' && item.visual.state === 'rendered'
			).length
		});
	}
	return found;
}
