import { expect, test } from '@playwright/test';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	DAY_FIELDS,
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
 *
 * **Nothing here reads the committed archive** (2026-09-14). The last test
 * needs one day on the source side of the projection, and it used to take the
 * newest one under `frontend/public/digest` - a walk over a collection every
 * run appends to, banned by `CLAUDE.md` section 13 and Guardrail #12. It also
 * inherited whatever the pipeline last wrote: on 2026-09-14 that was an empty
 * day, which carries no vector block because it carries no stories, and the
 * control failed over a day that was never its subject. It reads the canary day
 * now, which the production embedder writes and which is fixed in size.
 */

const STAGED = resolve(process.cwd(), 'static', 'digest');
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'digest');

/** Traced along the render path, not guessed: `DigestList` scopes and filters
 * the list, and `DigestItem` with `ItemMeta`, `ItemVisual`, `LensChips`,
 * `ConfidenceChip`, `ReadAloud` and `SourceLink` draws one item.
 *
 * `introduced_by_run` is the exception and it is deliberate. Nothing has drawn
 * it since the run divider was deleted on 2026-09-01, and it stays because
 * taking a name off the allow-list is a change to `DigestView` rather than a
 * detail. Removing it here would make this promise agree with a contract change
 * nobody had decided.
 *
 * `desk` joined on 2026-09-12. The reading page groups by the topic a story is
 * read under, so a desk this projection dropped would be a grouping the browser
 * cannot make.
 *
 * `same_story_as` and `covered_by` joined on 2026-09-16 and joined together.
 * The page folds a group into one card now: the first is what it folds on, the
 * second is the other newsrooms by name, and the names are what make the fold
 * recoverable. Either one alone ships a card with no way out of it. */
const RENDERED_FIELDS = [
	'also_covered_by',
	'band',
	'band_reason',
	'carried_by',
	'covered_by',
	'desk',
	'introduced_by_run',
	'item_id',
	'key_points',
	'lenses',
	'on_front_page',
	'published_at',
	'rank_score',
	'reader_note',
	'same_story_as',
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
const VISUAL_FIELDS = ['alt', 'data_path', 'state'];

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

/** The canary day that carries stories - the source the projection reads from.
 *
 * It used to be the newest day under `frontend/public/digest`, and that was a
 * walk over a collection every run appends to: banned by `CLAUDE.md` section 13
 * and Guardrail #12, and it cost more than a rule. On 2026-09-14 the pipeline
 * published an empty day, an empty day carries no vector block because it
 * carries no stories, and this control failed over a day that was never its
 * subject. A committed day is frozen; the day that can still be wrong is the
 * one a producer is writing.
 *
 * The canary is that day. `backend/utilities/build_canary_day.py` runs the
 * production `build_embeddings` over the production `Embedder`, so the block it
 * writes is the one the pipeline writes - not a fixture somebody typed - and
 * the tree is a fixed nineteen quiet days plus one that publishes. Exactly one
 * may carry stories; if that stops being true the builder changed shape, and
 * this says so instead of picking one.
 */
function canaryDayWithStories(): Day {
	if (!existsSync(CANARY)) {
		throw new Error(
			`no canary tree at ${CANARY}. Run \`python backend/utilities/build_canary_day.py\`, ` +
				'which `npm run build:canary` does for the browser suite'
		);
	}
	const carrying = daysUnder(CANARY).filter((day) => items(day).length > 0);
	if (carrying.length !== 1) {
		throw new Error(
			`the canary tree holds ${carrying.length} days with stories, not 1. ` +
				'The builder changed shape and this control no longer knows which day to read'
		);
	}
	return carrying[0]!;
}

function items(day: Day): Record<string, unknown>[] {
	return day.payload.items as Record<string, unknown>[];
}

test('the allow-list is the twenty-six fields this file promises', () => {
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

test('a staged day carries its items, its own facts, and the stamp that says what shape they are', () => {
	// `assist/day.ts` refuses a payload whose `items` is not an array, and the
	// version is what an older shell branches on when this shape next moves -
	// `schemas/digest-view.schema.json` is the contract both answer to. The day's
	// own facts joined it on 2026-09-09: a dated URL is served by one shell that
	// no build writes a day into, so this file is the only source a browser has
	// for the date, the desks, the leading block and the day notice.
	for (const day of staged()) {
		expect(Object.keys(day.payload).sort(), `${day.path} is not the day projection`).toEqual(
			[...DAY_FIELDS, 'version'].sort()
		);
		expect(Array.isArray(day.payload.items), `${day.path} has no items array`).toBe(true);
		expect(day.payload.version, `${day.path} carries the wrong contract stamp`).toBe(VIEW_VERSION);
	}
});

test('a staged item carries the twenty-six fields a page renders, and no twenty-seventh', () => {
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
 * The block this projection exists to drop, and the day that must keep it.
 *
 * The vectors have one store - the day payload the producer writes - and one
 * production reader, the backend's index rebuild. If a day loses them the
 * rebuild does not raise: it writes every entry and a zero-byte vector file,
 * and search answers nothing for every query with no log line saying why. So
 * the drop and the keep are asserted together, in one test: proving only that
 * staging drops the block would pass just as happily over a source that had
 * already lost it.
 */
test('the vectors are gone from the staged copy and still in the day it came from', () => {
	for (const day of staged()) {
		expect(
			Object.keys(day.payload),
			`${day.path} is staging the vector block again - it is 40 percent of a day`
		).not.toContain('embeddings');
	}

	const source = canaryDayWithStories();
	const block = source.payload.embeddings as { vectors?: Record<string, unknown> } | null;
	expect(
		block,
		`${source.path} carries no vector block - the index rebuild has no source left`
	).not.toBeNull();
	// An empty block is the same outage as a missing one, and it is the shape
	// the rebuild cannot tell apart: every entry written, nothing to search.
	expect(
		Object.keys(block?.vectors ?? {}).length,
		`${source.path} carries an empty vector block - the rebuild would write a zero-byte file`
	).toBeGreaterThan(0);
});
