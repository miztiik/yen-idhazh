#!/usr/bin/env node
/**
 * Stage the pipeline's rendered visuals, public telemetry and month indexes
 * into `static/` before the build.
 *
 * `frontend/public/` is where `backend/` writes, and the page reads those
 * payloads through the filesystem at build time - so the JSON never needs
 * serving. A rendered chart is different: it is fetched by the browser for any
 * story past the seed the document was built with, and only `static/` is copied
 * into the served bundle.
 *
 * **`visuals.asset_base_url` is the switch that stops this staging the images.**
 * It ships empty, which means this site, so the images are staged and the
 * bundle is what it always was. Naming a host there is the release valve for
 * the 1 GB published ceiling: `ItemVisual.svelte` asks that host for the
 * drawing, so staging a second copy here would leave the bytes in the bundle
 * and the valve would move nothing. The two are one switch for that reason -
 * where a drawing is asked for and whether it also ships cannot disagree.
 * Whoever opens it puts the same `digest/` tree at that prefix first; the day
 * payloads and the month index are staged either way, because they are read
 * from this origin and are not what the ceiling is about.
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
 * **A day payload is projected on the way across, not copied, and the shape it
 * is projected into is a contract.** The committed file is the whole day -
 * every field the digest page renders, plus the vector block the backend's
 * index rebuild reads. A page renders less than that, and a reader fetches one
 * of these per day they open. Staging it whole put a second full copy of every
 * day's text and vectors in the bundle. Measured 2026-08-31 on Intel Core
 * i7-1265U / Windows 11 / node 24.12.0, 11 committed days and 3,733 items,
 * `gzip -9`: the committed day is 792.65 bytes an item and the projection is
 * 468.58, which is 40.9 percent less. The floor is not zero because 2,259,497
 * bytes of the staged tree is 178 rendered images, which this step must not
 * touch.
 *
 * The shape is `schemas/digest-view.schema.json`, generated from
 * `backend/idhazh/contracts/digest_view.py`, and every staged file carries its
 * `version`. It is a contract because a reading route is about to fetch it, so
 * a browser we cannot upgrade will parse it (Rule #3).
 */

import {
	existsSync,
	mkdirSync,
	readdirSync,
	readFileSync,
	rmSync,
	statSync,
	writeFileSync
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { assetBaseUrl } from '../asset-base.js';
// The allow-list and the projector itself, shared with the build-time reader in
// `src/lib/server/payload.ts`. The `.ts` extension and the full relative path
// are both required: this script is run by plain `node`, which strips the types
// but resolves nothing else.
import { ITEM_FIELDS, VIEW_VERSION, projectDay } from '../src/lib/payload/project.ts';

const IMAGE_SUFFIXES = ['.svg', '.webp', '.png', '.jpg', '.jpeg'];

// Empty means this site, which is what ships, so the images are staged.
const servedElsewhere = assetBaseUrl() !== '';

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

// Generated, so a stale visual from a previous build would be served beside a
// payload that no longer names it. This used to be guaranteed by deleting all
// three trees and copying every file back, which rewrote every staged file on
// every build to replace it with the same bytes. The guarantee is now reached
// from both ends instead: `stage` writes a file only when its bytes differ, and
// `reconcile` removes a staged file the source no longer has.
//
// Measured 2026-09-08 on an Intel Core i7-1265U / Windows 11 / node 24.12.0
// over 453 staged files, five runs each: a build with no new day fell from
// 2.88 s to 1.38 s, spreads 2.77-3.32 and 1.32-1.94 - a little over half the
// step, on every build after the first. A fresh checkout got cheaper as well,
// three runs each, 2.65 s to 1.14 s, because `cpSync` on one file costs more
// than a read and a write. That second figure is the one CI sees: every job
// starts with `static/digest` absent, so its first stage is always a full one.
//
// Content, never a timestamp. A rebuilt projection can carry identical bytes
// and a new mtime, and a fresh checkout can carry a new mtime and identical
// bytes, so a timestamp answers wrongly in both directions.
const stage = (bytes, destination) => {
	if (existsSync(destination) && statSync(destination).size === bytes.length) {
		if (readFileSync(destination).equals(bytes)) return false;
	}
	mkdirSync(dirname(destination), { recursive: true });
	writeFileSync(destination, bytes);
	return true;
};

// The other half. A day, a telemetry shard or an index month that the source no
// longer has must leave the staged tree, or the site serves a file the producer
// deleted. `wanted` holds every relative path this run staged or found already
// current; everything else here goes, empty directories included, so the tree
// this leaves is the tree a full re-stage would have written.
//
// Rule #12, and it is the escape hatch taken in writing: this sweep opens a tree
// that gains a directory every published day, and it is unbounded on purpose.
// No bounded input answers "what is staged that the source no longer has" - a
// receipt tells you a file is current, never that a file is orphaned, and the
// only cheaper cover would be a manifest of the last run's output, which is a
// persisted contract that can silently disagree with the tree it describes. It
// also adds no order of cost: the source walk beside it is unbounded too and
// cannot be otherwise, because this step has to look at every day to know what
// to stage. Measured on the same machine and day over the same tree, five runs:
// the sweep is 27.3 ms median, 21.0 to 32.6 - two percent of the step it halved.
const reconcile = (root, wanted) => {
	if (!existsSync(root)) return 0;
	let removed = 0;
	const sweep = (relative) => {
		let kept = 0;
		for (const name of readdirSync(join(root, relative))) {
			const next = join(relative, name);
			if (statSync(join(root, next)).isDirectory()) {
				if (sweep(next) > 0) kept += 1;
				else rmSync(join(root, next), { recursive: true, force: true });
			} else if (wanted.has(next)) {
				kept += 1;
			} else {
				rmSync(join(root, next), { force: true });
				removed += 1;
			}
		}
		return kept;
	};
	if (sweep('') === 0) rmSync(root, { recursive: true, force: true });
	return removed;
};

function stageIndexes() {
	if (!existsSync(indexSource)) {
		console.log(`month index: no index tree at ${indexSource}, nothing to stage.`);
		rmSync(indexTarget, { recursive: true, force: true });
		return;
	}
	const wanted = new Set();
	let staged = 0;
	for (const name of readdirSync(indexSource)) {
		// Both halves. The browse list reads the JSON; a search reads the sibling
		// `.bin`, which is why it is staged at all - it was left out while nothing
		// fetched a vector, because it is megabytes a reader would download for
		// nothing.
		if (!/^\d{4}-\d{2}\.(json|bin)$/.test(name)) continue;
		wanted.add(name);
		if (stage(readFileSync(join(indexSource, name)), join(indexTarget, name))) staged += 1;
	}
	const stale = reconcile(indexTarget, wanted);
	console.log(
		`month index: staged ${staged} file(s) into static/index, ${wanted.size - staged} already ` +
			`current, ${stale} stale removed.`
	);
}

stageIndexes();

// The console's own payloads, staged the way the month index is: derived from
// the digest root so a canary build stages the canary's tree, written only on a
// byte difference, and swept by `reconcile` so a month the producer pruned
// leaves the bundle with it.
//
// Two of these are fetched by a browser since row 10 landed on 2026-09-09 -
// `console/band.json` by `console/+layout.ts` at build time, and
// `telemetry/<month>.csv` on mount - and both are capped by
// `page_weight.payload_ceilings_bytes`, which `bundle-gate.mjs` reads off this
// staged tree. The other five are staged and served and nothing asks for them
// yet: a payload written but never served is the half of the change that cannot
// be tested, and the staging rule is the same one the day payloads already take.
const CONSOLE_SERIES = [
	// The band is one file, not a month series, and it is named rather than
	// pattern-matched: it is the first thing the console asks for, so a typo in
	// a pattern would leave the page with no verdict and no error.
	{ dirname: 'console', keep: (name) => name === 'band.json' },
	{ dirname: 'scores', keep: (name) => /^\d{4}-\d{2}\.csv$/.test(name) },
	{ dirname: 'feed-health', keep: (name) => /^\d{4}-\d{2}\.csv$/.test(name) },
	{ dirname: 'run-days', keep: (name) => /^\d{4}-\d{2}\.json$/.test(name) },
	{ dirname: 'day-metrics', keep: (name) => /^\d{4}-\d{2}\.json$/.test(name) },
	{ dirname: 'machine', keep: (name) => /^\d{4}-\d{2}\.csv$/.test(name) },
	{ dirname: 'span-rollup', keep: (name) => /^\d{4}-\d{2}\.csv$/.test(name) }
];

function stageConsolePayloads() {
	for (const series of CONSOLE_SERIES) {
		const from = resolve(source, '..', series.dirname);
		const into = join('static', series.dirname);
		if (!existsSync(from)) {
			console.log(`${series.dirname}: no payload tree at ${from}, nothing to stage.`);
			rmSync(into, { recursive: true, force: true });
			continue;
		}
		const wanted = new Set();
		let staged = 0;
		for (const name of readdirSync(from)) {
			if (!series.keep(name)) continue;
			wanted.add(name);
			if (stage(readFileSync(join(from, name)), join(into, name))) staged += 1;
		}
		const stale = reconcile(into, wanted);
		console.log(
			`${series.dirname}: staged ${staged} file(s) into static/${series.dirname}, ` +
				`${wanted.size - staged} already current, ${stale} stale removed.`
		);
	}
}

stageConsolePayloads();

if (!existsSync(source)) {
	console.log(`rendered visuals: no payload tree at ${source}, nothing to stage.`);
	// Both trees, because this exit skips the telemetry pass at the foot of the
	// file and a staged tree with no source behind it is exactly what `reconcile`
	// exists to prevent.
	rmSync(target, { recursive: true, force: true });
	rmSync(telemetryTarget, { recursive: true, force: true });
	process.exit(0);
}

let copied = 0;
let payloads = 0;
let current = 0;
let skipped = 0;
let elsewhere = 0;
// Neither an unreadable day nor an image left out by `visuals.asset_base_url`
// joins this set, so `reconcile` clears a copy an earlier build staged - which
// is what deleting the tree first used to do for them.
const wanted = new Set();
const walk = (relative) => {
	for (const name of readdirSync(join(source, relative))) {
		const next = join(relative, name);
		if (statSync(join(source, next)).isDirectory()) {
			walk(next);
		} else if (name === 'digest.json') {
			// A page renders the day it names, fetched when it is needed. The archive
			// used to inline every one of these instead, which charged every browsing
			// visitor the whole corpus.
			//
			// A payload we cannot read is one day, and throwing here stops the whole
			// build - so one corrupt file stopped every OTHER day publishing too, and
			// the site went out unchanged with nobody told which day was wrong.
			// `$lib/server/payload.ts` takes the same view about the same file; this
			// is the second reader of it, and the one that runs first.
			let projected;
			try {
				projected = projectDay(readFileSync(join(source, next), 'utf8'));
			} catch (cause) {
				console.warn(`rendered visuals: ${next} is unreadable, day skipped - ${String(cause)}`);
				skipped += 1;
				continue;
			}
			wanted.add(next);
			if (stage(Buffer.from(projected), join(target, next))) payloads += 1;
			else current += 1;
		} else if (IMAGE_SUFFIXES.some((suffix) => name.toLowerCase().endsWith(suffix))) {
			if (servedElsewhere) {
				elsewhere += 1;
				continue;
			}
			wanted.add(next);
			if (stage(readFileSync(join(source, next)), join(target, next))) copied += 1;
			else current += 1;
		}
	}
};
walk('');
const stale = reconcile(target, wanted);
console.log(
	`rendered visuals: staged ${copied} image(s) and projected ${payloads} day payload(s) ` +
		`into static/digest at digest-view ${VIEW_VERSION}, ${ITEM_FIELDS.length} field(s) an item, ` +
		`${current} already current, ${stale} stale removed, ${skipped} unreadable.`
);
if (servedElsewhere) {
	console.log(
		`rendered visuals: ${elsewhere} image(s) left out of the bundle - visuals.asset_base_url ` +
			`says they are served from ${assetBaseUrl()}.`
	);
}

if (!existsSync(telemetrySource)) {
	console.log(`telemetry: no projection tree at ${telemetrySource}, nothing to stage.`);
	rmSync(telemetryTarget, { recursive: true, force: true });
	process.exit(0);
}

let telemetryCopied = 0;
const telemetryWanted = new Set();
for (const name of readdirSync(telemetrySource)) {
	if (!name.endsWith('.csv')) continue;
	telemetryWanted.add(name);
	if (stage(readFileSync(join(telemetrySource, name)), join(telemetryTarget, name))) {
		telemetryCopied += 1;
	}
}
const telemetryStale = reconcile(telemetryTarget, telemetryWanted);
console.log(
	`telemetry: staged ${telemetryCopied} shard(s) into static/telemetry, ` +
		`${telemetryWanted.size - telemetryCopied} already current, ${telemetryStale} stale removed.`
);
