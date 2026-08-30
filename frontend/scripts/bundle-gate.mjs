#!/usr/bin/env node
/**
 * Two checks over a finished build: no encoder on the first-load path, and no
 * capped page over the weight ceiling config/idhazh.json sets for it.
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
 * The page ceilings below answer the question that survives - has this page
 * grown past what somebody priced - and they are absolute, so nothing has to
 * re-record them to merge. `tests/payload-weight.spec.ts` covers the pages a
 * ceiling cannot bound, by counting a marker instead of bytes.
 *
 * So both remaining promises are checked mechanically rather than remembered.
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
// once and its size reused.
const compressed = new Map();
function gzipBytes(file) {
	let size = compressed.get(file);
	if (size === undefined) {
		size = gzipSync(readFileSync(file), { level: 9 }).length;
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
 * The document, against the ceilings in `config/idhazh.json`.
 *
 * A ceiling is a limit somebody chose, so it is a knob and lives with the other
 * knobs (Rule #6), in config/idhazh.json and nowhere else - the model default
 * in app_config.py is empty so the numbers are not copied into a second file.
 *
 * config/idhazh.json decides what is capped. A route it names is measured and
 * failed when it is over; a route it does not name is measured and printed
 * here, but never failed. A route earns a ceiling when somebody priced its
 * growth: /404 and /evals/ move only when the source moves, /archive/ grows by
 * one day link a published day so its number carries a measured year of that,
 * and each of the three /console/ routes grows with the ledger its own panels
 * read so each carries a measured few days and is meant to expire. One surface
 * split across several routes takes one key per route, or a blown budget cannot
 * name which route blew it. A page that renders a day is never capped, because
 * the only way under such a ceiling is to publish fewer items -
 * `tests/payload-weight.spec.ts` covers that class by counting a marker instead.
 */
const CONFIG = resolve(process.cwd(), '..', 'config', 'idhazh.json');

let ceilings;
try {
	ceilings = JSON.parse(readFileSync(CONFIG, 'utf8')).page_weight?.ceilings_bytes;
} catch (error) {
	console.error(`bundle gate: ${CONFIG} could not be read - ${error.message}`);
	process.exit(1);
}
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

console.log('\nprerendered HTML, gzip -9, against page_weight.ceilings_bytes in config/idhazh.json:');
for (const [name, { bytes }] of [...heaviestPage].sort()) {
	const measured = `  ${name.padEnd(18)} ${commas(bytes).padStart(9)} B  ${kb(bytes).padStart(9)}`;
	if (rendersADay(name)) {
		console.log(`${measured}  (renders a day - counted, not capped)`);
		continue;
	}
	const ceiling = ceilings[name];
	if (!Number.isInteger(ceiling) || ceiling <= 0) {
		uncapped.push(name);
		console.log(`${measured}  (no ceiling in config - reported, not capped)`);
		continue;
	}
	const headroom = ceiling - bytes;
	const verdict = headroom < 0 ? `${commas(-headroom)} OVER` : `${commas(headroom)} spare`;
	console.log(`${measured}  (ceiling ${commas(ceiling)}, ${verdict})`);
	if (headroom < 0) over.push({ name, bytes, ceiling });
}

if (uncapped.length > 0) {
	console.log(
		`\nReported, not capped: ${uncapped.join(', ')}. config/idhazh.json names what\n` +
			'is capped, and a route it leaves out is one whose growth nobody has priced\n' +
			'yet - a fixed ceiling before that measurement fires on an ordinary publish\n' +
			'rather than catching a regression. Measure what a published day costs the\n' +
			'page, then add it under "page_weight": { "ceilings_bytes": { ... } } in\n' +
			'config/idhazh.json with that many days of headroom.'
	);
}

if (namesNothing.length > 0) {
	failed = true;
	console.error('\nbundle gate FAILED - a ceiling in config/idhazh.json names no route in the build:');
	for (const line of namesNothing) console.error(`  ${line}`);
	console.error(
		'\nDelete the ceiling, or find out why the route stopped building. A ceiling over\n' +
			'nothing still reads as a bound somebody checked.'
	);
}

if (over.length > 0) {
	failed = true;
	console.error('\nbundle gate FAILED - a prerendered page is over its ceiling:');
	for (const { name, bytes, ceiling } of over) {
		console.error(
			`  ${name} weighs ${commas(bytes)} B (${kb(bytes)}), ` +
				`${commas(bytes - ceiling)} B over the ${commas(ceiling)} B ceiling`
		);
	}
	console.error(
		'\nTwo answers are legitimate and they are not interchangeable. If the page took on\n' +
			'bytes it does not render - a day payload inlined by a layout is how this last\n' +
			'happened - remove them. If the page genuinely carries more, raise the ceiling in\n' +
			'config/idhazh.json, in the commit that earned the bytes, and say in the message\n' +
			'what they buy.'
	);
	if (over.some(({ name }) => name.startsWith('/console/'))) {
		console.error(
			'\nA console route is the third case, and raising it IS the answer. The owner\n' +
				'ruled on 2026-08-31 that no approved feature is cut, deferred or shrunk to\n' +
				'stay under a page-weight number: a ceiling here is a ratchet, not a budget.\n' +
				'Re-measure it - five builds, heaviest per route, never a mean - raise it, and\n' +
				'say in the same commit what the bytes bought. Windowing a seed the first paint\n' +
				'does not need is still the better first move, because a saving costs the\n' +
				'operator nothing; leaving a panel unbuilt is not.\n' +
				'See docs/architecture/publishing/frontend.md.'
		);
	}
}

if (failed) process.exit(1);

console.log('\nbundle gate: every capped page is under its ceiling.');
