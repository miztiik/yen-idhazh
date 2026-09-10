#!/usr/bin/env node
/**
 * Three checks over a finished build: no encoder on the first-load path, no
 * capped page over the weight ceiling config/idhazh.json sets for it, and no
 * fetched payload over its own.
 *
 * The encoder rule is that nothing downloads or executes before a reader
 * clicks. A dynamic `import()` is what keeps that true, and a dynamic import is
 * one careless edit away from becoming a static one. Nothing about that edit
 * looks wrong in review - the page still works, it just costs every reader of
 * every page a multi-megabyte library they never asked for.
 *
 * The document rule is a ceiling rather than a ratchet, because a page that got
 * lighter needs no permission. It bounds only the routes that render no day.
 *
 * The payload rule exists because the document rule stopped being able to see
 * the bytes. Moving the console's telemetry out of its HTML took 3.4 MB off a
 * page a ceiling watched and put it into files nothing watched; a reader still
 * waits for them. A ceiling on the document alone now reads as a bound on what
 * the console costs, and it is not one.
 *
 * **Every size here is gzip -5, because that is what the reader pays.** It was
 * gzip -9 until 2026-09-10, which is a level no origin serves. Measured that
 * day against the live Pages origin: it served /console/ in 46,917 bytes where
 * a local gzip -5 makes 46,787 and a gzip -9 makes 45,077, and /archive/ in
 * 5,760 against 5,755 at -5. So -5 lands within 0.3 pct of the wire and -9
 * understates it by 3.9 pct - on a page whose ceiling is meant to catch growth,
 * a level that flatters it by four percent is four percent of growth nobody
 * sees. On a large CSV -5 is 2.2 pct low rather than high (168,438 served
 * against 164,742 locally), which is the one place these numbers flatter the
 * payload rather than the page, and the payload ceilings carry that knowingly.
 *
 * There was a third check here until 2026-08-30: a per-route first-load
 * JavaScript ratchet against a hand-maintained record, failing at +/-64 B on
 * routes of about 80,000. It is gone, and what it cost is worth stating,
 * because the deletion is not "we stopped caring about bytes".
 *
 * Its own docstring said nobody had measured what first-load cost a reader, so
 * it did not invent a number - it failed on any difference instead. That makes
 * it a change-detector, and CLAUDE.md Rule #10 says an unmeasured number may
 * not justify a design. Two things followed. A local Windows build could not
 * reproduce a Linux CI build inside 64 B, so half of its failures were the
 * toolchain and every one of them needed a control build to tell apart. And the
 * record lived in one file every branch had to rewrite, so fifteen console rows
 * serialised behind it - a branch could not merge until it had rebuilt,
 * re-measured and re-recorded a number its own change had not moved.
 *
 * The ceilings below answer the question that survives - has this page, or this
 * file, grown past what somebody priced - and they are absolute, so nothing has
 * to re-record them to merge. `tests/payload-weight.spec.ts` covers the pages a
 * ceiling cannot bound, by counting a marker instead of bytes.
 *
 * So all three promises are checked mechanically rather than remembered.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, posix, relative, resolve, sep } from 'node:path';
import { gzipSync } from 'node:zlib';

const BUILD = 'build';
const ROOT = 'build/_app/immutable';

// Directories a browser loads before any reader gesture: the entry point and
// the route modules. Anything under chunks/ is only fetched when something
// imports it, which for the encoder means after a click.
const EAGER = ['entry', 'nodes'];

const FORBIDDEN = ['@huggingface/transformers', 'onnxruntime-web', 'ort-wasm'];

function filesUnder(directory) {
	let found = [];
	for (const name of readdirSync(directory)) {
		const path = join(directory, name);
		found = statSync(path).isDirectory()
			? found.concat(filesUnder(path))
			: found.concat(path.endsWith('.js') ? [path] : []);
	}
	return found;
}

const offenders = [];
for (const area of EAGER) {
	const directory = join(ROOT, area);
	let files;
	try {
		files = filesUnder(directory);
	} catch {
		console.error(`bundle gate: ${directory} is missing - was the site built?`);
		process.exit(1);
	}
	for (const file of files) {
		const source = readFileSync(file, 'utf8');
		for (const symbol of FORBIDDEN) {
			if (source.includes(symbol)) offenders.push(`${file} carries ${symbol}`);
		}
	}
}

if (offenders.length > 0) {
	console.error('bundle gate FAILED - the encoder is on the first-load path:');
	for (const line of offenders) console.error(`  ${line}`);
	console.error('\nThe assist library must only be reached through a dynamic import().');
	process.exit(1);
}

console.log('bundle gate: the first-load bundle carries no encoder.');

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** The route class a prerendered page belongs to, so a record survives a new day. */
function routeClass(route) {
	const parts = route.split('/').filter(Boolean);
	if (parts.length === 0) return '/';
	if (DATE.test(parts[0])) return parts.length === 1 ? '/<date>/' : '/<date>/<topic>/';
	return `/${parts.join('/')}/`;
}

function pagesUnder(directory) {
	let found = [];
	for (const name of readdirSync(directory)) {
		const path = join(directory, name);
		if (statSync(path).isDirectory()) {
			if (name === '_app') continue;
			found = found.concat(pagesUnder(path));
		} else if (name === 'index.html' || name === '404.html') {
			found.push(path);
		}
	}
	return found;
}

// Modules repeat heavily across the route classes, so each one is compressed
// once and its size reused. Level 5 and not 9: see the header - 9 is a level no
// origin serves, and the gate has to measure what the reader pays.
const compressed = new Map();
function gzipBytes(file) {
	let size = compressed.get(file);
	if (size === undefined) {
		size = gzipSync(readFileSync(file), { level: 5 }).length;
		compressed.set(file, size);
	}
	return size;
}

// The document is measured over one walk. A route class holds one page per
// published day, so the heaviest instance stands for the class.
const heaviestPage = new Map();
for (const page of pagesUnder(BUILD)) {
	const route = `/${relative(BUILD, page).split(sep).slice(0, -1).join(posix.sep)}`.replace(
		/\/$/,
		''
	);
	const name = page.endsWith('404.html') ? '/404' : routeClass(route);
	const html = gzipBytes(page);
	const worstPage = heaviestPage.get(name);
	if (!worstPage || html > worstPage.bytes) heaviestPage.set(name, { bytes: html, page });
}

const commas = (value) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');

let failed = false;

/**
 * The document, against the guardrails in `config/idhazh.json`.
 *
 * A guardrail is a limit somebody chose, so it is a knob and lives with the
 * other knobs (Rule #6), in config/idhazh.json and nowhere else - the model
 * default in app_config.py is empty so the numbers are not copied into a second
 * file.
 *
 * **A route is named here only if its weight does not move when a run
 * publishes** (owner, 2026-09-10). `/archive/` and the three `/console/` routes
 * were named until then and are not now: they grow when the pipeline appends a
 * day, so the gate fired on ordinary publishing and the only way past it was to
 * type a bigger number. `/404` and `/evals/` move only when a person edits
 * source, so they stay.
 *
 * config/idhazh.json decides what is guarded. A route it names is measured and
 * failed when it is over; a route it does not name is measured and printed
 * here, but never failed. **The regression this file used to be asked to catch
 * - a layout inlining a day payload, 313,300 gzipped bytes on 2026-08-26 - is
 * asserted directly by `tests/payload-weight.spec.ts`**, which looks for a
 * day-payload marker in every document that should not carry one. That check has
 * no number in it, so it returns the same verdict whatever the archive holds.
 */
const CONFIG = resolve(process.cwd(), '..', 'config', 'idhazh.json');

let config;
try {
	config = JSON.parse(readFileSync(CONFIG, 'utf8'));
} catch (error) {
	console.error(`bundle gate: ${CONFIG} could not be read - ${error.message}`);
	process.exit(1);
}
const ceilings = config.page_weight?.ceilings_bytes;
if (ceilings === null || typeof ceilings !== 'object' || Array.isArray(ceilings)) {
	console.error('bundle gate: config/idhazh.json needs a "page_weight.ceilings_bytes" object.');
	process.exit(1);
}

/** A page renders a day when it is the home page or a dated route. */
const rendersADay = (name) => name === '/' || name.startsWith('/<date>');

const kb = (value) => `${(value / 1000).toFixed(1)} KB`;
const uncapped = [];
const over = [];
const namesNothing = [];

for (const name of Object.keys(ceilings)) {
	if (!heaviestPage.has(name)) {
		namesNothing.push(
			`${name} is capped at ${kb(ceilings[name])}, and no page in the build is that route`
		);
	}
}

console.log('\nprerendered HTML, gzip -5, against page_weight.ceilings_bytes in config/idhazh.json:');
for (const [name, { bytes }] of [...heaviestPage].sort()) {
	const measured = `  ${name.padEnd(18)} ${commas(bytes).padStart(9)} B  ${kb(bytes).padStart(9)}`;
	if (rendersADay(name)) {
		console.log(`${measured}  (renders a day - counted, not guarded)`);
		continue;
	}
	const ceiling = ceilings[name];
	if (!Number.isInteger(ceiling) || ceiling <= 0) {
		uncapped.push(name);
		console.log(`${measured}  (no guardrail in config - reported, not guarded)`);
		continue;
	}
	const headroom = ceiling - bytes;
	const verdict = headroom < 0 ? `${commas(-headroom)} OVER` : `${commas(headroom)} spare`;
	console.log(`${measured}  (guardrail ${commas(ceiling)}, ${verdict})`);
	if (headroom < 0) over.push({ name, bytes, ceiling });
}

if (uncapped.length > 0) {
	console.log(
		`\nReported, not guarded: ${uncapped.join(', ')}. That is the normal state for\n` +
			'a route whose weight moves when the pipeline publishes, and it is deliberate:\n' +
			'a number on one of those has to be raised every time we publish, so it teaches\n' +
			'the operator to raise numbers and catches nothing. What a document must not do\n' +
			'is carry a payload it does not render, and tests/payload-weight.spec.ts asserts\n' +
			'that with no number in it. Add a key here only for a route that moves when a\n' +
			'person edits source and never when a run appends a day.'
	);
}

/**
 * The files a reader's browser fetches, against page_weight.payload_ceilings_bytes.
 *
 * A key is a build-relative POSIX path, and its shape says what it bounds. A
 * key naming a file bounds that file. A key ending in `/` bounds every file
 * under that directory, each on its own - a month series takes one number
 * rather than one a month, so a shard landing in October needs no config edit
 * and gets no free pass either.
 *
 * A key that matches nothing fails, for the same reason an unmatched route
 * ceiling does: a bound over nothing still reads as a bound somebody checked.
 *
 * The walk is over the named keys and not over the build, so what this costs is
 * set by how many ceilings are written rather than by how much the pipeline has
 * accumulated (Rule #12). A directory key does read every file under itself,
 * and that read grows - a month a run appends is a file this opens. It is
 * bounded where it matters by retention: observability.public_telemetry_keep_months
 * is 14, so the directory holds fourteen shards however long the project runs.
 */
const payloadCeilings = config.page_weight?.payload_ceilings_bytes ?? {};
if (payloadCeilings === null || typeof payloadCeilings !== 'object' || Array.isArray(payloadCeilings)) {
	console.error('bundle gate: "page_weight.payload_ceilings_bytes" must be an object.');
	process.exit(1);
}

/** Every build file a payload key covers, heaviest first. */
function payloadsFor(key) {
	const target = join(BUILD, ...key.split('/').filter(Boolean));
	let stat;
	try {
		stat = statSync(target);
	} catch {
		return [];
	}
	if (!stat.isDirectory()) return [{ path: key, bytes: gzipBytes(target) }];
	return readdirSync(target)
		.filter((name) => !statSync(join(target, name)).isDirectory())
		.map((name) => ({ path: `${key}${name}`, bytes: gzipBytes(join(target, name)) }))
		.sort((left, right) => right.bytes - left.bytes);
}

const payloadKeys = Object.keys(payloadCeilings).sort();
const heaviestPayload = new Map();
if (payloadKeys.length > 0) {
	console.log(
		'\nfetched payloads, gzip -5, against page_weight.payload_ceilings_bytes in config/idhazh.json:'
	);
}
for (const key of payloadKeys) {
	const ceiling = payloadCeilings[key];
	const found = payloadsFor(key);
	if (found.length === 0) {
		namesNothing.push(
			`${key} is capped at ${kb(ceiling)}, and no file in the build is at that path`
		);
		continue;
	}
	heaviestPayload.set(key, found[0].bytes);
	for (const { path, bytes } of found) {
		const headroom = ceiling - bytes;
		const verdict = headroom < 0 ? `${commas(-headroom)} OVER` : `${commas(headroom)} spare`;
		console.log(
			`  ${path.padEnd(26)} ${commas(bytes).padStart(9)} B  ${kb(bytes).padStart(9)}` +
				`  (guardrail ${commas(ceiling)}, ${verdict})`
		);
		if (headroom < 0) over.push({ name: path, bytes, ceiling });
	}
}

/**
 * What one cold opening of the console asks for over the network.
 *
 * This bounds the design and not the data. A per-file ceiling says how heavy
 * one shard may be; this says how many of them opening the page is allowed to
 * want, which is the thing a widened default window changes and no per-file
 * number can see. A key naming a file is fetched once. A key naming a directory
 * of month shards is fetched once per month the window reaches into, and the
 * page fetches those one after another, so this number and the four-hop chain
 * ceiling in `tests/console-cold-load.spec.ts` are two readings of one design.
 *
 * The worst case is arithmetic, not a date: a run of N consecutive days lands in
 * at most `1 + ceil((N - 1) / 28)` calendar months, because February is the
 * shortest month there is. At the default 30 days that is three - a window
 * opening on 31 January reaches 1 March - and not the two a reader sees for
 * three hundred and sixty-three days of the year.
 */
const coldCeiling = config.page_weight?.cold_console_load_bytes ?? 0;
if (Number.isInteger(coldCeiling) && coldCeiling > 0) {
	const windowDays = config.console?.default_window_days;
	if (!Number.isInteger(windowDays) || windowDays < 1) {
		console.error(
			'bundle gate: page_weight.cold_console_load_bytes needs console.default_window_days\n' +
				'to know how many month shards a cold load asks for.'
		);
		process.exit(1);
	}
	const monthsTouched = 1 + Math.ceil((windowDays - 1) / 28);
	let cold = 0;
	const parts = [];
	for (const key of payloadKeys) {
		const heaviest = heaviestPayload.get(key);
		if (heaviest === undefined) continue;
		const copies = key.endsWith('/') ? monthsTouched : 1;
		cold += heaviest * copies;
		parts.push(copies === 1 ? `${key} ${commas(heaviest)}` : `${copies} x ${key} ${commas(heaviest)}`);
	}
	const headroom = coldCeiling - cold;
	console.log(
		`\ncold console load at console.default_window_days=${windowDays} ` +
			`(${monthsTouched} month shards worst case):\n` +
			`  ${parts.join(' + ')} = ${commas(cold)} B  ${kb(cold)}\n` +
			`  (guardrail ${commas(coldCeiling)}, ` +
			`${headroom < 0 ? `${commas(-headroom)} OVER` : `${commas(headroom)} spare`})`
	);
	if (headroom < 0) {
		failed = true;
		console.error(
			`\nbundle gate FAILED - a cold console load asks for ${commas(cold)} B, ` +
				`${commas(-headroom)} B over its ${commas(coldCeiling)} B guardrail.`
		);
		console.error(
			'\nThe usual cause is not a heavier shard - it is a wider default window. Each\n' +
				'extra month is a whole shard AND one more serial round trip, so check\n' +
				'console.default_window_days before reaching for the guardrail. If the wider\n' +
				'window is what was wanted, raise this in the same commit and say what the\n' +
				'reader waits for in exchange.'
		);
	}
}

if (namesNothing.length > 0) {
	failed = true;
	console.error(
		'\nbundle gate FAILED - a guardrail in config/idhazh.json names nothing in the build:'
	);
	for (const line of namesNothing) console.error(`  ${line}`);
	console.error(
		'\nDelete the guardrail, or find out why the route or the payload stopped being\n' +
			'built. A guardrail over nothing still reads as a bound somebody checked.'
	);
}

if (over.length > 0) {
	failed = true;
	console.error(
		'\nbundle gate FAILED - a prerendered page or a fetched payload is over its guardrail:'
	);
	for (const { name, bytes, ceiling } of over) {
		console.error(
			`  ${name} weighs ${commas(bytes)} B (${kb(bytes)}), ` +
				`${commas(bytes - ceiling)} B over its ${commas(ceiling)} B guardrail`
		);
	}
	console.error(
		'\nA guardrail sits at twice the page, so an ordinary publish cannot reach it and\n' +
			'this is a change of a different order. Ask what took on the bytes first: a day\n' +
			'payload inlined by a layout is how it last happened to a page, and a column\n' +
			'added to a shard is how it happens to a payload. If the bytes are not read,\n' +
			'remove them. If they are genuinely earned, RE-DERIVE the number - five builds,\n' +
			'heaviest per route, never a mean, then twice it - and say in the same message\n' +
			'what the bytes bought. Nudging it up to just clear the new page turns a\n' +
			'guardrail back into a budget, which is what the 2026-09-10 ruling ended.'
	);
	if (over.some(({ name }) => name.startsWith('/console/'))) {
		console.error(
			'\nA console route is the third case, and re-deriving IS the answer. The owner\n' +
				'ruled on 2026-08-31 that no approved feature is cut, deferred or shrunk to\n' +
				'stay under a page-weight number. Windowing a seed the first paint does not\n' +
				'need is still the better first move, because a saving costs the operator\n' +
				'nothing; leaving a panel unbuilt is not.\n' +
				'See docs/architecture/publishing/frontend.md.'
		);
	}
}

if (failed) process.exit(1);

console.log('\nbundle gate: every guarded page and every guarded payload is inside its number.');
