/** The one allow-list: what a day payload keeps when it leaves
 * `frontend/public/`, and what it may never carry out.
 *
 * Two callers used to hold a copy each. `scripts/copy-visuals.mjs` writes the
 * staged file a browser fetches, and `lib/server/payload.ts` reads the
 * committed day at build time. Both drop the vector block; only one of them
 * said so, and the list of kept names lived where TypeScript could not see it.
 *
 * **Since 2026-08-31 the shape this module writes is a contract**, generated
 * from `backend/idhazh/contracts/digest_view.py` into
 * `schemas/digest-view.schema.json`. The reason is a consumer we cannot
 * upgrade: a reading route is about to fetch this file, so a reader's cached
 * shell can be older than the payload it reads. `VIEW_VERSION` below is that
 * contract's stamp, and a backend contract test fails if the two drift.
 *
 * **The read-side rule: absent and null both mean unknown.** A reader may never
 * fill either with a default - `0` for `carried_by` says no feed carried the
 * story, `false` for `on_front_page` denies a vote nobody counted. The
 * projector writes an explicit null for a key the committed day does not hold,
 * so an older payload and a newer one read the same way.
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

/** The stamp `DigestView` carries, and the same string
 * `DigestView.schema_version()` returns.
 *
 * It is written into every staged day so a shell can branch on the shape it
 * received. `backend/tests/test_contracts.py` reads this literal out of this
 * file and fails if it and the contract disagree, which is what stops the two
 * halves of one payload drifting across two languages.
 */
export const VIEW_VERSION = '2026-08-31T12:00';

// The fields a page renders, and no others. Traced along the render path rather
// than guessed: `DigestList` scopes, filters and divides the list, and
// `DigestItem` with `ItemMeta`, `ItemVisual`, `LensChips`, `ConfidenceChip`,
// `ReadAloud` and `SourceLink` draws one item. `source_url` is on it because it
// is the reader's way out to the source, which is the most important thing on
// an item after the summary itself.
//
// Nine names joined the original thirteen on 2026-08-31, each with a named
// renderer and each priced. Measured over 11 committed days and 3,596 items,
// `gzip -9` on the compact projection, against the thirteen-field arm:
//
//   carried_by, watchlist_hit, on_front_page, rank_score    +3.21 B an item
//   published_at, time_source                               +9.04 B an item
//   introduced_by_run                                       +1.16 B an item
//   lenses                                                  +1.07 B an item
//   key_points                                             +92.91 B an item
//
// `key_points` is nine tenths of that and it is the one worth defending.
// `DigestList` filters on it today, so once a reading route fetches this file
// instead of inlining the day, an absent `key_points` is a thrown TypeError
// rather than a narrower filter. The six prerendered documents it replaces
// carried the same words six times over, so on the wire it is cheaper here than
// it was there.
//
// Three names were refused. `events` and `entities` have no renderer and the
// reading-page plan forbids publishing them as reader-facing chips (+1.57 and
// +1.71 B an item). `source_form` has no reader at all (+1.20).
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
	'source_url',
	'published_at',
	'time_source',
	'carried_by',
	'watchlist_hit',
	'on_front_page',
	'rank_score',
	'introduced_by_run',
	'lenses',
	'key_points'
];

// The three `ItemVisual` reads. `kind` is read at build time off the committed
// tree, for the console's chart count, and never from a staged copy.
export const VISUAL_FIELDS: readonly string[] = ['state', 'path', 'alt'];

// The day-level keys carried over from the committed payload. `version` is the
// other key on a staged day and it is minted rather than copied - the committed
// file's own `version` stamps `DigestDay`, which is a different contract with a
// different changelog.
export const DAY_FIELDS: readonly string[] = ['items'];

// Names that may never reach a staged copy, whoever widens the lists above.
// `embeddings` is why this projection exists: it is the vector block, its only
// production reader is the backend's index rebuild, and it was 40.0 percent of
// a day page. `events` and `entities` are bulk no component draws, and the
// reading-page plan puts them out of scope as reader-facing chips.
export const FORBIDDEN_FIELDS: readonly string[] = ['embeddings', 'events', 'entities'];

// The build fails on import rather than shipping a widened payload, because a
// projection that has quietly grown looks exactly like one that has not.
const kept = new Set([...DAY_FIELDS, ...ITEM_FIELDS, ...VISUAL_FIELDS]);
const leaked = FORBIDDEN_FIELDS.filter((name) => kept.has(name));
if (leaked.length > 0) {
	throw new Error(`payload projection: a staged day may never carry ${leaked.join(', ')}`);
}

/** Keep only the named fields, in one fixed order.
 *
 * An absent key becomes an explicit null rather than being left out, so every
 * staged item has the same shape whichever day it was published on - and a
 * reader that must not invent a default sees the same thing either way.
 */
const pick = (source: Json, fields: readonly string[]): Json =>
	Object.fromEntries(fields.map((name) => [name, source[name] ?? null]));

/** One item, as a page renders it. */
export function projectItem(item: Json): Json {
	const projected = pick(item, ITEM_FIELDS);
	projected.visual = item.visual ? pick(item.visual as Json, VISUAL_FIELDS) : null;
	return projected;
}

/** The day, narrowed to its items and stamped with the shape it is.
 *
 * Compact, where the committed payload is pretty-printed. That indent is worth
 * paying for a file whose diff a person reviews by eye, and not for one a
 * reader downloads.
 *
 * `version` is written first so a file truncated in transit still says what it
 * was meant to be.
 */
export function projectDay(text: string): string {
	const day = JSON.parse(text) as Json;
	const items = (day.items ?? []) as Json[];
	return JSON.stringify({ version: VIEW_VERSION, items: items.map((item) => projectItem(item)) });
}

/** The committed day with its vector block removed.
 *
 * The other half of the same rule, for the caller that keeps the whole day
 * rather than twenty-two fields of it. Whatever the build-time reader returns
 * is inlined into every prerendered document that renders the day, and nothing
 * in a browser opens the block: its one production reader is the backend's
 * index rebuild, which reads `frontend/public/` from disk. The committed
 * payload keeps it - that tree is the only store the vectors have.
 *
 * Measured 2026-08-27 on Intel Core i7-1265U / Windows 11 / node 24.12.0, six
 * committed days, 2,237 items, `gzip -9`, heaviest of five builds: the block
 * was 232,462 of the 581,553 gzipped bytes of `/<date>/`, which is 40.0 percent
 * of a page nobody could read it on, and it rode in twelve documents per day.
 */
export function dropVectors(day: DigestDay): DigestDay {
	return { ...day, embeddings: null };
}
