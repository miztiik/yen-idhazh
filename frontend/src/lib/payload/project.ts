/** The one allow-list: what a day payload keeps when it leaves
 * `frontend/public/`, and what it may never carry out.
 *
 * Two callers used to hold a copy each. `scripts/copy-visuals.mjs` writes the
 * staged file a search result fetches, and `lib/server/payload.ts` reads the
 * committed day at build time. Both drop the vector block; only one of them
 * said so, and the list of kept names lived where TypeScript could not see it.
 *
 * **This module imports nothing at run time, and that is a constraint rather
 * than an accident.** `copy-visuals.mjs` is run by plain `node` before Vite
 * starts, so it reaches this file through node's own type stripping - on by
 * default since node 22.18, and CI installs the newest 22.x. Stripping erases
 * annotations. It does not resolve a `$lib` alias and it does not supply a
 * missing file extension. So every type below arrives through `import type`,
 * which is erased with the annotations, and no value is imported at all.
 */

import type { DigestDay } from './types';

/** Parsed JSON, before anything has been proved about it. */
type Json = Record<string, unknown>;

// The fields a search result renders, and no others. Traced along the render
// path rather than guessed: `assist/day.ts` fetches the file,
// `routes/archive/+page.svelte` hands one item to `DigestItem`, and that
// component with `ItemMeta`, `ItemVisual`, `ConfidenceChip`, `ReadAloud` and
// `SourceLink` reads exactly this list. `source_url` is on it because it is the
// reader's way out to the source, which is the most important thing on a result
// after the summary itself.
//
// `published_at` is not, and that is the one entry worth explaining.
// `ItemMeta` reads it only in the branch where no day was passed, and a search
// result always passes one. It stays in the committed payload; it never had a
// reader here.
//
// The order is the order the staged file writes its keys in, so a name moved
// here rewrites every staged day.
export const ITEM_FIELDS: readonly string[] = [
	'item_id',
	'vertical',
	'title',
	'summary',
	'reader_note',
	'band',
	'band_reason',
	'truncated',
	'visual',
	'source_name',
	'source_id',
	'source_kind',
	'source_url'
];

// The three `ItemVisual` reads. `kind` is read at build time off the committed
// tree, for the console's chart count, and never from a staged copy.
export const VISUAL_FIELDS: readonly string[] = ['state', 'path', 'alt'];

// One key. `assist/day.ts` refuses a payload whose `items` is not an array, so
// this is the entire contract the fetched file answers to.
export const DAY_FIELDS: readonly string[] = ['items'];

// Names that may never reach a staged copy, whoever widens the lists above.
// `embeddings` is why this projection exists: it is the vector block, its only
// production reader is the backend's index rebuild, and it was 40.0 percent of
// a day page. The other four are bulk the digest page renders and a search
// result does not.
export const FORBIDDEN_FIELDS: readonly string[] = [
	'embeddings',
	'key_points',
	'lenses',
	'events',
	'entities'
];

// The build fails on import rather than shipping a widened payload, because a
// projection that has quietly grown looks exactly like one that has not.
const kept = new Set([...DAY_FIELDS, ...ITEM_FIELDS, ...VISUAL_FIELDS]);
const leaked = FORBIDDEN_FIELDS.filter((name) => kept.has(name));
if (leaked.length > 0) {
	throw new Error(`payload projection: a staged day may never carry ${leaked.join(', ')}`);
}

/** Keep only the named fields, in one fixed order. */
const pick = (source: Json, fields: readonly string[]): Json =>
	Object.fromEntries(fields.map((name) => [name, source[name] ?? null]));

/** One item, as a search result renders it. */
export function projectItem(item: Json): Json {
	const projected = pick(item, ITEM_FIELDS);
	projected.visual = item.visual ? pick(item.visual as Json, VISUAL_FIELDS) : null;
	return projected;
}

/** The day, narrowed to its items.
 *
 * Compact, where the committed payload is pretty-printed. That indent is worth
 * paying for a file whose diff a person reviews by eye, and not for one a
 * reader downloads.
 */
export function projectDay(text: string): string {
	const day = JSON.parse(text) as Json;
	const items = (day.items ?? []) as Json[];
	return JSON.stringify({ items: items.map((item) => projectItem(item)) });
}

/** The committed day with its vector block removed.
 *
 * The other half of the same rule, for the caller that keeps the whole day
 * rather than thirteen fields of it. Whatever the build-time reader returns is
 * inlined into every prerendered document that renders the day, and nothing in
 * a browser opens the block: its one production reader is the backend's index
 * rebuild, which reads `frontend/public/` from disk. The committed payload
 * keeps it - that tree is the only store the vectors have.
 *
 * Measured 2026-08-27 on Intel Core i7-1265U / Windows 11 / node 24.12.0, six
 * committed days, 2,237 items, `gzip -9`, heaviest of five builds: the block
 * was 232,462 of the 581,553 gzipped bytes of `/<date>/`, which is 40.0 percent
 * of a page nobody could read it on, and it rode in twelve documents per day.
 */
export function dropVectors(day: DigestDay): DigestDay {
	return { ...day, embeddings: null };
}
