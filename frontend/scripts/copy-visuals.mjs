#!/usr/bin/env node
/**
 * Stage the pipeline's rendered visuals, public telemetry and month indexes
 * into `static/` before the build.
 *
 * `frontend/public/` is where `backend/` writes, and the page reads those
 * payloads through the filesystem at build time - so the JSON never needs
 * serving. A rendered chart is different: it is an `<img src>` the browser
 * fetches at runtime, and only `static/` is copied into the served bundle.
 *
 * Two earlier placements were wrong, both silently:
 *
 * - As a Vite plugin in `closeBundle`, the copy ran before adapter-static wrote
 *   `build/`, so the files were written and then wiped.
 * - As a post-build step into `build/`, the files existed on disk but
 *   `vite preview` never served them - it serves SvelteKit's own output dirs,
 *   not the adapter's directory.
 *
 * Staging into `static/` before the build is the placement where dev, preview
 * and the deployed bundle all agree.
 *
 * Three kinds of file are staged from the digest tree: rendered images, the day
 * payloads a search result renders from, and the month index with its sibling
 * vector file. `run.json` is not staged - nothing fetches it. Telemetry is
 * different again: the console fetches a projected CSV that has already dropped
 * URL keys, canonical URLs and free text.
 *
 * **A day payload is projected on the way across, not copied.** The committed
 * file is the whole day - every field the digest page renders, plus the vector
 * block the backend's index rebuild reads. A search result renders far less
 * than that, and a reader who searches downloads one of these per day a result
 * of theirs sits on. Staging it whole put a second full copy of every day's
 * text and vectors in the bundle. Measured 2026-08-27 on Intel Core i7-1265U /
 * Windows 11 / node 24.12.0, six committed days, 2,237 items: the tree went
 * 6,966,247 -> 3,883,127 bytes, a 44.3 percent cut. The floor is not zero
 * because 1,055,600 bytes of it is 87 rendered images, which this step must not
 * touch.
 */

import {
	cpSync,
	existsSync,
	mkdirSync,
	readdirSync,
	readFileSync,
	rmSync,
	statSync,
	writeFileSync
} from 'node:fs';
import { join, resolve } from 'node:path';

const IMAGE_SUFFIXES = ['.svg', '.webp', '.png', '.jpg', '.jpeg'];

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
const ITEM_FIELDS = [
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
const VISUAL_FIELDS = ['state', 'path', 'alt'];

// One key. `assist/day.ts` refuses a payload whose `items` is not an array, so
// this is the entire contract the fetched file answers to.
const DAY_FIELDS = ['items'];

// Names that may never reach a staged copy, whoever widens the lists above.
// `embeddings` is why this projection exists: it is the vector block, its only
// production reader is the backend's index rebuild, and it was 40.0 percent of
// a day page. The other four are bulk the digest page renders and a search
// result does not.
const FORBIDDEN_FIELDS = ['embeddings', 'key_points', 'lenses', 'events', 'entities'];

// The build fails here rather than shipping a widened payload, because a
// projection that has quietly grown looks exactly like one that has not.
const staged = new Set([...DAY_FIELDS, ...ITEM_FIELDS, ...VISUAL_FIELDS]);
const leaked = FORBIDDEN_FIELDS.filter((name) => staged.has(name));
if (leaked.length > 0) {
	throw new Error(`copy-visuals: a staged day may never carry ${leaked.join(', ')}`);
}

/** Keep only the named fields, in one fixed order. */
const project = (source, fields) =>
	Object.fromEntries(fields.map((name) => [name, source[name] ?? null]));

/** One item, as a search result renders it. */
function projectItem(item) {
	const kept = project(item, ITEM_FIELDS);
	kept.visual = item.visual ? project(item.visual, VISUAL_FIELDS) : null;
	return kept;
}

/** The day, narrowed to its items.
 *
 * Compact, where the committed payload is pretty-printed. That indent is worth
 * paying for a file whose diff a person reviews by eye, and not for one a
 * reader downloads.
 */
function projectDay(text) {
	const day = JSON.parse(text);
	return JSON.stringify({ items: (day.items ?? []).map(projectItem) });
}

// The same root the payload loader reads, so a canary build stages its own
// visuals rather than the real day's.
const source = process.env.DIGEST_ROOT
	? resolve(process.env.DIGEST_ROOT)
	: join('public', 'digest');
const target = join('static', 'digest');
const telemetrySource = process.env.TELEMETRY_ROOT
	? resolve(process.env.TELEMETRY_ROOT)
	: join('public', 'telemetry');
const telemetryTarget = join('static', 'telemetry');
// Derived from the digest root rather than given its own switch, because the
// index is a projection of exactly those days. One switch cannot leave a
// canary build serving the real archive's stories.
const indexSource = resolve(source, '..', 'assist', 'index');
// Its own top-level tree, beside `static/digest/` and `static/telemetry/`, and
// deliberately not under `static/assist/`. That directory is the on-device
// encoder, which is secondary by contract: the bundle must render complete with
// it deleted (`CLAUDE.md` section 0a), and CI proves that by parking it and
// asserting the build carries no `assist/` at all. The archive's story list is
// not a model feature - it is how the page lists anything - so it has to
// survive that parking, and a staged tree inside the parked one cannot.
const indexTarget = join('static', 'index');

// Generated, so it is rebuilt rather than accumulated. A stale visual from a
// previous build would be served beside a payload that no longer names it.
rmSync(target, { recursive: true, force: true });
rmSync(telemetryTarget, { recursive: true, force: true });
rmSync(indexTarget, { recursive: true, force: true });

function stageIndexes() {
	if (!existsSync(indexSource)) {
		console.log(`month index: no index tree at ${indexSource}, nothing to stage.`);
		return;
	}
	let staged = 0;
	for (const name of readdirSync(indexSource)) {
		// Both halves. The browse list reads the JSON; a search reads the sibling
		// `.bin`, which is why it is staged at all - it was left out while nothing
		// fetched a vector, because it is megabytes a reader would download for
		// nothing.
		if (!/^\d{4}-\d{2}\.(json|bin)$/.test(name)) continue;
		mkdirSync(indexTarget, { recursive: true });
		cpSync(join(indexSource, name), join(indexTarget, name));
		staged += 1;
	}
	console.log(`month index: staged ${staged} file(s) into static/index.`);
}

stageIndexes();

if (!existsSync(source)) {
	console.log(`rendered visuals: no payload tree at ${source}, nothing to stage.`);
	process.exit(0);
}

let copied = 0;
let payloads = 0;
const walk = (relative) => {
	for (const name of readdirSync(join(source, relative))) {
		const next = join(relative, name);
		if (statSync(join(source, next)).isDirectory()) {
			walk(next);
		} else if (name === 'digest.json') {
			// A search result is rendered from the day it names, fetched when it is
			// on screen. The archive used to inline every one of these instead, which
			// charged every browsing visitor the whole corpus.
			mkdirSync(join(target, relative), { recursive: true });
			writeFileSync(join(target, next), projectDay(readFileSync(join(source, next), 'utf8')));
			payloads += 1;
		} else if (IMAGE_SUFFIXES.some((suffix) => name.toLowerCase().endsWith(suffix))) {
			mkdirSync(join(target, relative), { recursive: true });
			cpSync(join(source, next), join(target, next));
			copied += 1;
		}
	}
};
walk('');
console.log(
	`rendered visuals: staged ${copied} image(s) and projected ${payloads} day payload(s) ` +
		`into static/digest, ${ITEM_FIELDS.length} field(s) an item.`
);

if (!existsSync(telemetrySource)) {
	console.log(`telemetry: no projection tree at ${telemetrySource}, nothing to stage.`);
	process.exit(0);
}

let telemetryCopied = 0;
for (const name of readdirSync(telemetrySource)) {
	if (!name.endsWith('.csv')) continue;
	mkdirSync(telemetryTarget, { recursive: true });
	cpSync(join(telemetrySource, name), join(telemetryTarget, name));
	telemetryCopied += 1;
}
console.log(`telemetry: staged ${telemetryCopied} shard(s) into static/telemetry.`);
