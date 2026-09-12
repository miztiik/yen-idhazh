/** The one payload loader. Lives under `$lib/server/` so SvelteKit refuses to
 * bundle it into anything a browser receives.
 *
 * Prerendering removes the wait for the first frame: by the time a reader has
 * the page, the head of the day is already in the HTML. It stopped removing the
 * runtime request on 2026-09-01, when the reading routes began carrying a seed
 * and letting the browser fetch the rest - `$lib/assist/day.ts` is that half,
 * and `PayloadState.svelte` is the state a reader meets when it fails.
 *
 * It stopped proving something else at the same time, and that is the larger
 * change: a story past the seed is never read here, so it is never checked
 * here. `idhazh validate-days` opens every story of every committed day, in CI
 * and before every publish.
 */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
// Relative, not `$lib`: the browser suite imports this module in plain Node,
// where no Vite alias exists to resolve one.
import { dayKey, toDay } from '../charts/viewport';
import { deskOf, orderByTime } from '../day-shape';
import { settled } from '../feed-health';
import { publishedVisual, refusedDrawing } from '../payload/drawing';
import { dropVectors } from '../payload/project';
import type { DigestDay, DigestItem, SeededVisual } from '$lib/payload/types';

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

/** Where the source-health view is read from.
 *
 * Derived from the digest root rather than given a switch of its own, the way
 * `INDEX_ROOT` is: a canary build has to read the canary's own view or the
 * console would draw fixture runs beside the real source census.
 *
 * Read at build time and never fetched. The view is small, the console needs it
 * on first paint, and every other console panel is already prerendered - so it
 * is not staged into `static/` and no page asks for it over the network.
 */
export const SOURCE_HEALTH_PATH = process.env.DIGEST_ROOT
	? resolve(process.env.DIGEST_ROOT, '..', 'source-health.json')
	: join(process.cwd(), 'public', 'source-health.json');

const DATE_PART = /^\d{2,4}$/;

const DAY_MS = 86_400_000;

/** The cover every read over the archive takes when its caller names none.
 *
 * 90 is the widest span the window control offers - `console.window_presets`
 * ends there in `config/appearance.json` - so a panel cannot draw a day older
 * than this whatever the operator does. Reading further back buys a number
 * nothing can display (`CLAUDE.md` Rule #12).
 *
 * It is a constant here and not a config read because `config.ts` imports
 * `REPO_ROOT` from this module, so importing the config reader back would close
 * a cycle. A surface that has already worked out its own widest preset passes
 * it - the console routes all do - and this is what a caller with no window of
 * its own inherits.
 */
export const ARCHIVE_WINDOW_DAYS = 90;

/** The month shards a span of days can touch, rounded up so it cannot starve.
 *
 * A month is at least 28 days, so a span of `windowDays` crosses at most
 * `windowDays / 28` boundaries, and it starts inside a month it may only touch
 * one day of. The estimate is deliberately generous: at 90 days it says five
 * where the calendar allows four, because the three shortest consecutive months
 * run to 89 days. One shard too many costs a file; one too few costs a panel a
 * day it should have drawn.
 *
 * `-1` in, `-1` out - a cover of everything in days is a cover of everything in
 * months.
 */
export function shardMonths(windowDays: number): number {
	return unbounded(windowDays) ? -1 : Math.ceil(windowDays / 28) + 1;
}

/** The month shards that cover `ARCHIVE_WINDOW_DAYS`.
 *
 * Derived rather than written down, so the two covers cannot drift apart: a
 * surface that widens its day window widens its ledger window by the same rule.
 */
export const LEDGER_WINDOW_MONTHS = shardMonths(ARCHIVE_WINDOW_DAYS);

/** `-1` and nothing else means "every one of them" (`docs/concepts/growing-reads.md`).
 *
 * Not `0`, not `null`, and not a very large number - a large number is a cover
 * that silently turns finite the day the archive outgrows it.
 */
function unbounded(cover: number): boolean {
	return cover < 1;
}

/** Published dates newest first, back as far as `windowDays` from the newest one.
 *
 * The walk descends newest first and stops at the cutoff, so it opens the year,
 * month and day directories the window reaches and no others. Adding another
 * published day adds another directory this call never lists once the window has
 * been filled (`CLAUDE.md` Rule #12). Pass `-1` to read the whole tree, and say
 * beside the call why (`docs/concepts/growing-reads.md`).
 *
 * **The window is anchored on the newest day found, never on today.** Anchored
 * on the clock, a corpus that stopped publishing three months ago would answer
 * with nothing at all, and `latestDate` - which is this function's first entry -
 * would take the whole site down with it. This is the same anchoring `seedCutoff`
 * takes below and for the same reason.
 *
 * One listing of the root is unavoidable and it is the honest residue: it names
 * one directory a year, and finding the newest year is what the anchor needs.
 */
export function publishedDates(
	root: string = DIGEST_ROOT,
	windowDays: number = ARCHIVE_WINDOW_DAYS
): string[] {
	if (!existsSync(root)) return [];
	const found: string[] = [];
	let cutoff: string | null = null;
	for (const year of dirsIn(root).reverse()) {
		if (cutoff !== null && year < cutoff.slice(0, 4)) break;
		for (const month of dirsIn(join(root, year)).reverse()) {
			if (cutoff !== null && `${year}-${month}` < cutoff.slice(0, 7)) break;
			for (const day of dirsIn(join(root, year, month)).reverse()) {
				const date = `${year}-${month}-${day}`;
				if (cutoff !== null && date < cutoff) break;
				if (!existsSync(join(root, year, month, day, 'digest.json'))) continue;
				found.push(date);
				if (cutoff === null && !unbounded(windowDays)) {
					cutoff = dayKey(new Date(toDay(date).getTime() - (windowDays - 1) * DAY_MS));
				}
			}
		}
	}
	return found;
}

function dirsIn(path: string): string[] {
	if (!existsSync(path)) return [];
	return readdirSync(path, { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && DATE_PART.test(entry.name))
		.map((entry) => entry.name)
		.sort();
}

/** A day, or null when that date was never published or its payload cannot be
 * read. Null is a designed state, not an error.
 *
 * **The vectors are dropped here, and this is the only place they can be.**
 * What a caller keeps of this is inlined into the document that renders the
 * day - the whole of it on `/`, the seed alone on a reading route.
 * `$lib/payload/project` owns that drop, alongside the allow-list the staging
 * step projects with, so both copies that leave `frontend/public/` are ruled by
 * one module.
 */
export function loadDay(date: string, root: string = DIGEST_ROOT): DigestDay | null {
	const [year, month, day] = date.split('-');
	if (!year || !month || !day) return null;
	const path = join(root, year, month, day, 'digest.json');
	if (!existsSync(path)) return null;
	try {
		const parsed: unknown = JSON.parse(readFileSync(path, 'utf8'));
		// A parser is not a contract. `null`, a list, and an object with no item
		// list all parse cleanly and all three reach the page as a white screen,
		// which `CLAUDE.md` section 12 calls a failure. One condition turns each
		// of them into the same designed screen a missing payload gets.
		if (!parsed || typeof parsed !== 'object' || !Array.isArray((parsed as DigestDay).items)) {
			throw new TypeError('the payload holds no item list');
		}
		return dropVectors(parsed as DigestDay);
	} catch (cause) {
		// Degrade, do not fail (`CLAUDE.md` section 1a). A payload we cannot read
		// is one day; throwing here takes the build down for every other day too,
		// so one corrupt file stops the whole site publishing rather than one
		// date. The day drops out and the reader meets a designed screen instead.
		// The build log is where this is answered, not the page: nothing a reader
		// could do would fix it.
		console.warn(`[digest] ${date}: payload unreadable, day dropped - ${String(cause)}`);
		return null;
	}
}

export function latestDate(
	root: string = DIGEST_ROOT,
	windowDays: number = ARCHIVE_WINDOW_DAYS
): string | null {
	return publishedDates(root, windowDays)[0] ?? null;
}

/** A day split at the seam a reading route loads across.
 *
 * `facts` is everything the day says that does not grow with the number of
 * stories - the date, the run list, the topic counts, the retention window.
 * `seed` is what the prerendered document carries and `rest` is what a browser
 * fetches.
 *
 * `facts.items` is empty and keeps its slot on purpose. A prerendered document
 * serialises an object in its own key order and the committed payload writes
 * its keys sorted, so a day rebuilt with the stories appended is a different
 * document holding the same day.
 */
export interface DayShell {
	facts: DigestDay;
	seed: DigestItem[];
	rest: DigestItem[];
}

/** Which stories a reading route splits, and which of them the document keeps. */
export interface DayShellSplit {
	/** One topic's stories only, in the day's own published order.
	 *
	 * A topic page's seed has to be the head of the list that page renders. The
	 * published order is desk-blocked rather than globally ranked, so the head of
	 * the whole day is one desk - and every other topic route would open on a
	 * screen holding none of its own stories.
	 */
	vertical?: string | null;
	/** Item ids the seed keeps whatever their position in the order.
	 *
	 * The head is a prefix and a leading story is not inside one. Row 15 of the
	 * reading-page plan measured its five leads at positions 249, 285, 337, 344
	 * and 493 of 601, so a seed built as a plain head ships lead links that land
	 * on nothing until the fetch arrives, and on nothing at all when it fails.
	 * The seed is therefore the head UNION whatever the page must be able to
	 * anchor before the rest of the day is in hand.
	 *
	 * A shell built with this is not one to put back together: a kept story moves
	 * forward into the seed, so `[...seed, ...rest]` is the same set in a
	 * different order. `wholeDay` is for the routes that still inline everything,
	 * and none of them keeps anything.
	 */
	keep?: Iterable<string>;
	/** Where the committed days are read from. */
	root?: string;
}

/** The drawing itself, or null when there is nothing safe to inline.
 *
 * Null is a designed state and not an error: the story keeps its `path`, so the
 * browser asks for the same file and runs the same refusal from
 * [../payload/drawing.ts](../payload/drawing.ts) over the answer. A file this
 * build refuses is a file that build refuses too, so the reader gets a shorter
 * story rather than a drawing nobody checked. Degrade, do not fail
 * (`CLAUDE.md` section 1a).
 */
function inlineSvg(root: string, path: string): string | null {
	if (!publishedVisual(path)) {
		console.warn(`[digest] ${path}: not a published visual path, so it is not drawn`);
		return null;
	}
	// `..` off the digest root rather than a switch of its own, the way
	// `INDEX_ROOT` is derived: a canary build then reads the canary's own
	// drawings and can never reach the published tree.
	const file = join(root, '..', path);
	if (!existsSync(file)) return null;
	const markup = readFileSync(file, 'utf8');
	const refused = refusedDrawing(markup);
	if (refused !== null) {
		console.warn(`[digest] ${path}: ${refused}, so it is not drawn`);
		return null;
	}
	return markup;
}

/** One story with its drawing in hand, for the stories the document carries. */
function withDrawing(item: DigestItem, root: string): DigestItem {
	if (item.visual?.state !== 'rendered' || !item.visual.path) return item;
	const markup = inlineSvg(root, item.visual.path);
	if (markup === null) return item;
	const visual: SeededVisual = { ...item.visual, markup };
	return { ...item, visual };
}

/** The day, in the two halves a reading route loads.
 *
 * Null for the same reason `loadDay` is null: the date was never published, or
 * its payload cannot be read. Both are designed states, not errors.
 *
 * **The seed carries its drawings and the rest does not**, which is the whole
 * reason the split is the right place to read them. A day has published 621
 * stories and the drawings average 12.7 KB each, so a document holding every
 * one of them would be about a megabyte of markup on the surface a phone loads
 * first. Measured 2026-09-05 over the 15 committed days: a seed holds 0.87
 * drawings on average and 3 at most, which is 11.8 KB of markup a day.
 */
export function dayShell(
	date: string,
	seedItems: number,
	split: DayShellSplit = {}
): DayShell | null {
	const root = split.root ?? DIGEST_ROOT;
	const day = loadDay(date, root);
	if (!day) return null;
	// The head has to be the head of the order the PAGE draws, not of the
	// published one. The stream runs newest first, so a seed taken off the
	// desk-blocked payload would put one desk's stories in the document and then
	// shuffle them the moment the rest of the day arrived - a first screen that
	// rewrites itself while the reader is on it.
	const ordered = orderByTime(day.items);
	// `deskOf` and not `item.vertical`: the route is a topic, and the topic a
	// story is read under is where the day published it. Filtering on the feed's
	// own word here would seed the document with a different set from the one the
	// browser draws when the served day lands.
	const items = split.vertical
		? ordered.filter((item) => deskOf(item) === split.vertical)
		: ordered;
	const kept = new Set(split.keep ?? []);
	const head = new Set(items.slice(0, seedItems).map((item) => item.item_id));
	const seeded = (item: DigestItem): boolean => head.has(item.item_id) || kept.has(item.item_id);
	return {
		facts: { ...day, items: [] },
		seed: items.filter(seeded).map((item) => withDrawing(item, root)),
		rest: items.filter((item) => !seeded(item))
	};
}

/** The day the home page carries: a seed with the day's leads anchored in it.
 *
 * A route `load` can only read the committed tree, so a seed decision made
 * inside one is reachable by a test only through the archive - which Rule #12
 * forbids and the canary cannot stand in for, because its biggest day holds 8
 * stories against a 15-story seed and no leads at all. So the decision is here,
 * with a root a fixture can point at.
 *
 * The leads are the whole reason this is not a plain `dayShell` call. A lead is
 * chosen across the whole day rather than off its head - measured 2026-09-01 on
 * the 601-story day of 2026-08-31, the five sat at positions 249, 285, 337, 344
 * and 493 - so a seed built as a prefix ships a leading block whose links land
 * on nothing until the fetch arrives, and on nothing at all when it fails.
 */
export function homeShell(
	date: string,
	seedItems: number,
	root: string = DIGEST_ROOT
): DayShell | null {
	const day = loadDay(date, root);
	if (!day) return null;
	return dayShell(date, seedItems, { keep: (day.leads ?? []).map((lead) => lead.item_id), root });
}

/** The two halves back together.
 *
 * The home page still renders the whole day inline, so this is what its `load`
 * returns. The dated routes stopped calling it: they keep a seed and let the
 * browser fetch the remainder.
 *
 * Only for a shell split with nothing kept out of order (see `DayShellSplit`).
 */
export function wholeDay(shell: DayShell): DigestDay {
	return { ...shell.facts, items: [...shell.seed, ...shell.rest] };
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

/** One row per scored item, read from the committed ledger and never recomputed.
 *
 * The ledger is a directory of month shards, so this reads the newest `months`
 * of them oldest first and hands back one table. Pass `-1` to read every month,
 * and say beside the call why (`docs/concepts/growing-reads.md`).
 */
export function evalRows(months: number = LEDGER_WINDOW_MONTHS): CsvTable {
	return readShards(join(STATE_ROOT, 'scores'), months);
}

/** The newest `months` `<YYYY-MM>.csv` shards of a ledger, oldest first, as one table.
 *
 * Three ledgers shard by month and all three wanted this loop. The columns come
 * from the first shard that has any, so an empty month cannot blank the header.
 *
 * **This is where the bound has to sit.** It is exported, so bounding only
 * `evalRows` and `itemHealthRows` would leave the next caller reading every
 * month a run ever wrote. Adding another month adds a file this call does not
 * open once the cover is filled (`CLAUDE.md` Rule #12); pass `-1` to open all of
 * them.
 *
 * The listing itself still names every shard, and that is the honest residue:
 * one directory entry a month, read to find which the newest are. Deriving the
 * newest stem from today's date instead would answer nothing at all for a
 * ledger whose last run was two months ago.
 */
export function readShards(dir: string, months: number = LEDGER_WINDOW_MONTHS): CsvTable {
	if (!existsSync(dir)) return { rows: [], columns: [] };
	const shards = readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.sort();
	const kept = unbounded(months) ? shards : shards.slice(Math.max(0, shards.length - months));
	const rows: Record<string, string>[] = [];
	let columns: string[] = [];
	for (const shard of kept) {
		const table = readCsv(join(dir, shard));
		if (columns.length === 0 && table.columns.length > 0) columns = table.columns;
		rows.push(...table.rows);
	}
	return { rows, columns };
}

/** One row per planned item per run, read from the newest `months` shards. */
export function itemHealthRows(months: number = LEDGER_WINDOW_MONTHS): CsvTable {
	return readShards(join(STATE_ROOT, 'item-health'), months);
}

/** One published day's item-health rows, from that month's shard alone.
 *
 * Opens only `state/item-health/<YYYY-MM>.csv` for the one date handed in -
 * never a listing of the directory, never an older month - so the cost is one
 * file whatever the archive holds behind it (`CLAUDE.md` Rule #12). The console
 * band reads the newest published day this way instead of walking every month
 * shard through `readShards` to keep only that one day. A month with no shard
 * yet returns no rows, and the caller shows the day no health fact rather than
 * reaching for the whole tree (section 1a).
 *
 * `root` is overridable for the same reason `dayMetrics`' is: the canary suite
 * points it at a fixture state that must never reach the real ledger.
 */
export function itemHealthForDay(
	date: string,
	root: string = STATE_ROOT
): Record<string, string>[] {
	const month = date.slice(0, 7);
	if (!/^\d{4}-\d{2}$/.test(month)) return [];
	const path = join(root, 'item-health', `${month}.csv`);
	if (!existsSync(path)) return [];
	return readCsv(path).rows.filter((row) => (row.date ?? '') === date);
}

/** The published-set counts a run settled about one day.
 *
 * Read back from the committed day-metrics record so the console does not
 * re-count them by walking the whole score ledger. All three count the day's
 * *distinct published* items, never score-ledger rows: the ledger dedupes by
 * measurement, so one item re-scored under a new stamp keeps both rows, and a
 * run may score an item it then drops (`backend/idhazh/publish_day_metrics.py`).
 * The measurement distributions the console draws still read every row - only
 * these per-item counts join the published set, so only these are read here. The
 * whole record shape is `schemas/day-metrics.schema.json`; this is the slice the
 * console reduces from.
 */
export interface DayMetrics {
	date: string;
	/** Distinct published items the checker gave a faithfulness score. */
	summariesScored: number;
	/** Of those, the ones whose identical inputs produced different words. */
	determinismViolations: number;
	/** Of those, the ones whose source read like page furniture. */
	extractionSuspect: number;
	/** Published items the checker put in the lowest confidence band, from the
	 * record's `bands.low`. Null only where a record predates the field; every
	 * record the producer writes carries it, so real data never reads null. */
	notSure: number | null;
	/** Published items whose source extract the cap cut short, from the record's
	 * `items_truncated`. Null on the same terms as `notSure`. */
	itemsTruncated: number | null;
	/** What the candidate pass found on the day and what the page drew from it,
	 * or null on a record written before 2026-09-08. */
	extraction: DayExtraction | null;
}

/** One day's extraction block, exactly as `schemas/day-metrics.schema.json`
 * holds it. Every count is additive across days, so a window is a sum.
 *
 * The two rates are not stored and are not read: a rate is not additive, so the
 * page derives both from these counts over whichever window is open. */
export interface DayExtraction {
	items: number;
	spanIntegrityPass: number;
	elementsFound: number;
	chartable: number;
	narrative: number;
	unclassified: number;
	chartablePublished: number;
	chartableCharted: number;
}

const EXTRACTION_CELLS = [
	['items', 'items'],
	['spanIntegrityPass', 'span_integrity_pass'],
	['elementsFound', 'elements_found'],
	['chartable', 'chartable'],
	['narrative', 'narrative'],
	['unclassified', 'unclassified'],
	['chartablePublished', 'chartable_published'],
	['chartableCharted', 'chartable_charted']
] as const;

/** The extraction block, or null where the record predates it or is short a cell.
 *
 * Lenient in one direction only. A record with no block is a day that measured
 * nothing and reads null, which the page prints as such; a block missing a cell
 * is a record this build cannot reduce, and a zero substituted for it would say
 * the extractor found nothing. Both read null and neither takes the day down. */
function extractionOf(parsed: Record<string, unknown>): DayExtraction | null {
	const block = parsed.extraction as Record<string, unknown> | null | undefined;
	if (block === null || block === undefined) return null;
	const cells: Record<string, number> = {};
	for (const [name, cell] of EXTRACTION_CELLS) {
		const value = block[cell];
		if (typeof value !== 'number') return null;
		cells[name] = value;
	}
	return cells as unknown as DayExtraction;
}

/** The day-metrics record for each named date, read one file at a time.
 *
 * Opens only `state/day-metrics/<YYYY>/<MM>/<DD>.json` for the dates handed in -
 * never a listing of the tree - so the cost is the window the caller asked for
 * and not the archive it sits in (`CLAUDE.md` Rule #12). Adding another
 * published day writes another file this call never opens unless the window
 * reaches it. A date with no record, or a record that cannot be read, is left
 * out of the map: the caller falls back to the raw ledger for that day, which is
 * what it read before.
 *
 * `root` is overridable for the same reason the other ledger readers' roots are:
 * the canary suite points it at a fixture state that must never reach the real
 * records.
 */
export function dayMetrics(
	dates: readonly string[],
	root: string = STATE_ROOT
): Map<string, DayMetrics> {
	const found = new Map<string, DayMetrics>();
	for (const date of dates) {
		if (found.has(date)) continue;
		const [year, month, day] = date.split('-');
		if (!year || !month || !day) continue;
		const path = join(root, 'day-metrics', year, month, `${day}.json`);
		if (!existsSync(path)) continue;
		try {
			const parsed = JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
			const scored = parsed.summaries_scored;
			const drift = parsed.determinism_violations;
			const suspect = parsed.extraction_suspect;
			if (
				typeof scored !== 'number' ||
				typeof drift !== 'number' ||
				typeof suspect !== 'number'
			) {
				throw new TypeError('a day-metrics count is missing or not a number');
			}
			// The band's two counts are read leniently: a record predating either
			// field drops to null for that count rather than dropping the whole day,
			// which would take the model route's strict triple down with it. Every
			// record the producer writes carries both, so real data never reads null.
			const bands = parsed.bands as Record<string, unknown> | undefined;
			const low = bands?.low;
			const truncated = parsed.items_truncated;
			found.set(date, {
				date,
				summariesScored: scored,
				determinismViolations: drift,
				extractionSuspect: suspect,
				notSure: typeof low === 'number' ? low : null,
				itemsTruncated: typeof truncated === 'number' ? truncated : null,
				extraction: extractionOf(parsed)
			});
		} catch (cause) {
			// Degrade, do not fail (`CLAUDE.md` section 1a): one unreadable record
			// drops that day back to the ledger count, it does not take the build
			// down for every other day.
			console.warn(
				`[day-metrics] ${date}: record unreadable, day falls back to the ledger - ${String(cause)}`
			);
		}
	}
	return found;
}

/** Public monthly telemetry shards, the newest `months` of them, oldest first.
 *
 * These are safe for a browser to fetch, and the console hands the whole list
 * to the browser so a reader can pan. A cover here therefore bounds two things
 * at once: what this build reads, and how far back a pan can reach. Pass `-1`
 * where the pan has to reach every month on record.
 */
export function telemetryMonths(
	root: string = TELEMETRY_ROOT,
	months: number = LEDGER_WINDOW_MONTHS
): string[] {
	if (!existsSync(root)) return [];
	const found = readdirSync(root)
		.filter((name) => /^\d{4}-\d{2}\.csv$/.test(name))
		.map((name) => name.slice(0, 7))
		.sort();
	return unbounded(months) ? found : found.slice(Math.max(0, found.length - months));
}

/** The newest `months` months with an index on disk, newest first.
 *
 * The names only. The stories inside them are fetched by the browser, which is
 * what keeps the archive page a fixed size while the corpus grows.
 *
 * The archive page passes `-1`, because this list is every month a reader may
 * ask for and a cover would delete the older ones from the page.
 */
export function indexMonths(
	root: string = INDEX_ROOT,
	months: number = LEDGER_WINDOW_MONTHS
): string[] {
	if (!existsSync(root)) return [];
	const found = readdirSync(root)
		.filter((name) => /^\d{4}-\d{2}\.json$/.test(name))
		.map((name) => name.slice(0, 7))
		.sort()
		.reverse();
	return unbounded(months) ? found : found.slice(0, months);
}

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
 *
 * The month list follows the same rule. A bounded seed needs `LEDGER_WINDOW_MONTHS`
 * shards at most, so it asks for those; an unbounded seed asks for every month,
 * which is what "no window" means.
 */
export function telemetryRows(root: string = TELEMETRY_ROOT, windowDays?: number): CsvTable {
	const bounded = windowDays !== undefined && windowDays > 0;
	const months = telemetryMonths(root, bounded ? LEDGER_WINDOW_MONTHS : -1);
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
		bounded && windowDays !== undefined ? seedCutoff(months, read, windowDays) : null;
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
	checkedAt: string;
	outcome: string;
	status: number | null;
	items: number;
	detail: string;
}

/** Feed results from the newest `months` shards, one per feed per run, oldest first.
 *
 * Sharded by month under `state/feed-health/`, so this reads a directory rather
 * than a file - through `readShards`, so the cover is the one every month-sharded
 * ledger takes. Absent is the ordinary state of a fresh clone: no run has
 * written a record yet, and no record is exactly what an empty list says.
 *
 * Settled here, at the one read every console panel shares, rather than in each
 * panel. A repeat is a second attempt at one run writing a second account of
 * one event, and a panel that counted both would count that run twice. Doing it
 * once is also what stops two panels disagreeing about the same feed.
 */
export function feedResults(months: number = LEDGER_WINDOW_MONTHS): FeedResult[] {
	const found: FeedResult[] = readShards(join(STATE_ROOT, 'feed-health'), months).rows.map(
		(row) => ({
			runId: row.run_id ?? '',
			date: row.date ?? '',
			feedId: row.feed_id ?? '',
			checkedAt: row.checked_at ?? '',
			outcome: row.outcome ?? '',
			status: row.status ? Number(row.status) : null,
			items: Number(row.items ?? 0) || 0,
			detail: row.detail ?? ''
		})
	);
	return settled(found);
}

/** What the pipeline published about one source. Mirrors `SourceHealthRow` in
 * `backend/idhazh/contracts/source_health_view.py`, which is the shape that
 * decides what may cross - there is no field here that could hold an address,
 * a key or a diagnostic, because there is none there. */
export interface SourceHealthRow {
	source_id: string;
	title: string;
	vertical: string;
	permission: 'allowed' | 'denied' | 'unreachable' | 'unrecorded';
	availability: 'answering' | 'failing' | 'resting' | 'never_asked';
	retired: boolean;
	retired_on: string | null;
	opportunities: number;
	publications: number;
	source_failures: number;
}

/** The published source-health view, as the console reads it. */
export interface SourceHealthView {
	generated_at: string;
	run_id: string;
	min_complete_days: number;
	complete_dates: number;
	yield_readable: boolean;
	first_date: string | null;
	last_date: string | null;
	sources: SourceHealthRow[];
}

/** The view, or null when the pipeline has not written one or it cannot be read.
 *
 * Null is a designed state, exactly as it is for a day payload: a console
 * section drops out and the page renders. The alternative is a build that dies
 * because one projection is malformed, which costs every other panel too.
 *
 * The guard is the same one `loadDay` uses and for the same reason - `null`, a
 * list and an object with no source list all parse cleanly and all three reach
 * the page as a section rendering nothing.
 */
export function sourceHealthView(path: string = SOURCE_HEALTH_PATH): SourceHealthView | null {
	if (!existsSync(path)) return null;
	try {
		const parsed: unknown = JSON.parse(readFileSync(path, 'utf8'));
		if (
			!parsed ||
			typeof parsed !== 'object' ||
			!Array.isArray((parsed as SourceHealthView).sources)
		) {
			throw new TypeError('the view holds no source list');
		}
		return parsed as SourceHealthView;
	} catch (cause) {
		console.warn(`[source-health] view unreadable, section dropped - ${String(cause)}`);
		return null;
	}
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
	/** Items the visual planner posted to the model. */
	decided: number;
	/** Items the planner decided without posting, because no enabled kind could survive its checks. */
	prefiltered: number;
	/** Items whose planner reply asked for a chart, whatever the decision became. */
	chartsDrafted: number;
	/** What the planner spent, or null where the run wrote no time down at all.
	 *
	 * Null and zero are different facts: a visuals job that never ran spent no
	 * measured time, and printing that as zero minutes reads as a stage that was
	 * free rather than one that is missing. */
	decisionMs: number | null;
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
 *
 * One manifest open a day inside `windowDays`, and none outside it - so another
 * published day costs this call nothing (`CLAUDE.md` Rule #12).
 */
export function loadManifests(
	root: string = DIGEST_ROOT,
	windowDays: number = ARCHIVE_WINDOW_DAYS
): RunSummary[] {
	const found: RunSummary[] = [];
	for (const date of publishedDates(root, windowDays)) {
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
							decided: Number(run.items_routed ?? 0) || 0,
							prefiltered: Number(run.items_prefiltered ?? 0) || 0,
							chartsDrafted: Number(run.charts_drafted ?? 0) || 0,
							// The manifest writes an integer or a literal null. `Number(null)` is 0,
							// so coercing here would turn "never measured" into "measured zero".
							decisionMs: typeof run.route_ms === 'number' ? run.route_ms : null
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
 *
 * One day payload open a day inside `windowDays`, and none outside it. This is
 * the most expensive of the archive reads - a day payload is hundreds of
 * kilobytes where a manifest is two - so it is the one the cover buys the most
 * on (`CLAUDE.md` Rule #12).
 */
export function publishedItems(
	root: string = DIGEST_ROOT,
	windowDays: number = ARCHIVE_WINDOW_DAYS
): Map<string, number> {
	const found = new Map<string, number>();
	for (const date of publishedDates(root, windowDays)) {
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
 * manifest records what the planner decided and this records what survived to
 * the page. A chart whose render failed is a visual and is not a published
 * chart.
 *
 * The item count rides along rather than costing a second pass: the arm's
 * second threshold is a share of what the day published, and the day payload is
 * already open here.
 *
 * Bounded the same way `publishedItems` is, and for the same reason: no console
 * panel can draw a day older than the widest preset (`CLAUDE.md` Rule #12).
 */
export function publishedCharts(
	root: string = DIGEST_ROOT,
	windowDays: number = ARCHIVE_WINDOW_DAYS
): Map<string, DayVisuals> {
	const found = new Map<string, DayVisuals>();
	for (const date of publishedDates(root, windowDays)) {
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
