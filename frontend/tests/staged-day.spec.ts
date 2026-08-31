import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	ITEM_FIELDS,
	VIEW_VERSION,
	VISUAL_FIELDS as PROJECTED_VISUAL_FIELDS
} from '../src/lib/payload/project';

/**
 * The staged day payload carries what a page renders, and no more.
 *
 * `frontend/public/digest/` is the committed day: every field the digest page
 * draws, plus the vector block. `scripts/copy-visuals.mjs` projects it into
 * `static/` through the allow-list in `src/lib/payload/project.ts`, and that
 * staged copy is what reaches a reader - fetched by `lib/assist/day.ts` when a
 * search result from that day is on screen, and by a reading route once row 26
 * of the reading-page plan lands.
 *
 * **The lists below are a second copy on purpose.** The module holds the
 * behaviour; this file holds the promise. Reading only the module's constants
 * here would make the test agree with any widening, which is the one failure it
 * exists to catch - a field added to the allow-list is paid for by every reader
 * who fetches a day, and nothing else in the build would say a word. So the
 * promise is written out longhand, and the first test below holds the module
 * against it: a widening now names the field it added, instead of surfacing as
 * a shape mismatch on every staged item at once.
 *
 * Runs in Node over the tree the build just staged, like the arithmetic tests
 * in `frame.spec.ts`. No page is loaded.
 */

const STAGED = resolve(process.cwd(), 'static', 'digest');
const COMMITTED = resolve(process.cwd(), 'public', 'digest');

/** Traced along the render path, not guessed: `DigestList` scopes, filters and
 * divides the list, and `DigestItem` with `ItemMeta`, `ItemVisual`,
 * `LensChips`, `ConfidenceChip`, `ReadAloud` and `SourceLink` draws one item. */
const RENDERED_FIELDS = [
	'band',
	'band_reason',
	'carried_by',
	'introduced_by_run',
	'item_id',
	'key_points',
	'lenses',
	'on_front_page',
	'published_at',
	'rank_score',
	'reader_note',
	'source_id',
	'source_kind',
	'source_name',
	'source_url',
	'summary',
	'time_source',
	'title',
	'truncated',
	'vertical',
	'visual',
	'watchlist_hit'
];

/** The three `ItemVisual` reads. `kind` is a build-time field of the committed
 * tree, for the console's chart count. */
const VISUAL_FIELDS = ['alt', 'path', 'state'];

interface Day {
	path: string;
	payload: Record<string, unknown>;
}

function daysUnder(root: string): Day[] {
	const found: Day[] = [];
	const walk = (at: string) => {
		for (const name of readdirSync(at)) {
			const path = join(at, name);
			if (statSync(path).isDirectory()) walk(path);
			else if (name === 'digest.json')
				found.push({ path, payload: JSON.parse(readFileSync(path, 'utf8')) });
		}
	};
	walk(root);
	return found;
}

function staged(): Day[] {
	const found = daysUnder(STAGED);
	expect(found.length, 'nothing is staged under static/digest - build first').toBeGreaterThan(0);
	return found;
}

function items(day: Day): Record<string, unknown>[] {
	return day.payload.items as Record<string, unknown>[];
}

test('the allow-list is the twenty-two fields this file promises', () => {
	// The staging step and the build-time reader share one module now, so a
	// widening is one edit in one place. This is the test that makes that edit
	// visible: it names the field that arrived, where the shape checks below
	// would only report that every staged item disagrees with the promise.
	expect(
		[...ITEM_FIELDS].sort(),
		'the projection allow-list moved. Every field on it is paid for by every\n' +
			'reader who fetches a day, so widening it is a decision, not a detail.'
	).toEqual(RENDERED_FIELDS);
	expect([...PROJECTED_VISUAL_FIELDS].sort(), 'the visual allow-list moved').toEqual(VISUAL_FIELDS);
});

test('a staged day carries its items and the stamp that says what shape they are', () => {
	// `assist/day.ts` refuses a payload whose `items` is not an array, and the
	// version is what an older shell branches on when this shape next moves -
	// `schemas/digest-view.schema.json` is the contract both answer to.
	for (const day of staged()) {
		expect(Object.keys(day.payload).sort(), `${day.path} is not the day projection`).toEqual([
			'items',
			'version'
		]);
		expect(Array.isArray(day.payload.items), `${day.path} has no items array`).toBe(true);
		expect(day.payload.version, `${day.path} carries the wrong contract stamp`).toBe(VIEW_VERSION);
	}
});

test('a staged item carries the twenty-two fields a page renders, and no twenty-third', () => {
	const wrong: string[] = [];
	let counted = 0;
	for (const day of staged()) {
		for (const item of items(day)) {
			counted += 1;
			const keys = Object.keys(item).sort();
			if (keys.join(',') !== RENDERED_FIELDS.join(',')) {
				const extra = keys.filter((key) => !RENDERED_FIELDS.includes(key));
				const missing = RENDERED_FIELDS.filter((key) => !keys.includes(key));
				wrong.push(
					`${day.path} ${String(item.item_id)}: extra [${extra}] missing [${missing}]`
				);
			}
		}
	}

	expect(counted, 'the staged days hold no items, so this proved nothing').toBeGreaterThan(0);
	expect(
		wrong.slice(0, 10),
		'the staged projection changed shape. Every field here is paid for by every\n' +
			'reader who fetches a day, so widening it is a decision, not a detail:\n' +
			wrong.join('\n')
	).toEqual([]);
});

test('a staged visual carries the three fields the image needs', () => {
	let withVisual = 0;
	for (const day of staged()) {
		for (const item of items(day)) {
			const visual = item.visual as Record<string, unknown> | null;
			if (visual === null) continue;
			withVisual += 1;
			expect(Object.keys(visual).sort(), `${day.path} ${String(item.item_id)}`).toEqual(
				VISUAL_FIELDS
			);
		}
	}
	// The canary corpus always renders at least one chart. Zero would mean the
	// nested projection was never exercised, which reads the same as a pass.
	expect(withVisual, 'no staged item carries a visual, so the nested projection is untested')
		.toBeGreaterThan(0);
});

/**
 * The block this projection exists to drop, and the tree that must keep it.
 *
 * The vectors have one store - the committed day payloads - and one production
 * reader, the backend's index rebuild. If a day loses them the rebuild does not
 * raise: it writes every entry and a zero-byte vector file, and search answers
 * nothing for every query with no log line saying why.
 */
test('the vectors are gone from the staged copy and still in the committed one', () => {
	for (const day of staged()) {
		expect(
			Object.keys(day.payload),
			`${day.path} is staging the vector block again - it is 40 percent of a day`
		).not.toContain('embeddings');
	}

	const committed = daysUnder(COMMITTED);
	expect(committed.length, 'no committed day, so the control below proves nothing').toBeGreaterThan(
		0
	);
	const carrying = committed.filter((day) => day.payload.embeddings !== null);
	expect(
		carrying.length,
		'no committed day carries a vector block - the index rebuild has no source left'
	).toBeGreaterThan(0);
});
