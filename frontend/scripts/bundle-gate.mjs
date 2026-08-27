#!/usr/bin/env node
/**
 * Three checks over a finished build: no encoder on the first-load path, no
 * route whose first-load JavaScript has left its recorded weight, and no
 * capped page over the weight ceiling config/idhazh.json sets for it.
 *
 * The encoder rule is that nothing downloads or executes before a reader
 * clicks. A dynamic `import()` is what keeps that true, and a dynamic import is
 * one careless edit away from becoming a static one. Nothing about that edit
 * looks wrong in review - the page still works, it just costs every reader of
 * every page a multi-megabyte library they never asked for.
 *
 * The weight rule is a regression detector and not a performance budget. Every
 * route is prerendered, so the page is complete HTML before a script runs and
 * the reading path works with JavaScript off: first-load JS is hydration cost,
 * not time-to-read. Nobody has measured what that cost may be, so the gate does
 * not invent a number for it. It compares each route against the last
 * measurement somebody recorded and fails when the two disagree by more than
 * the noise floor - in either direction, because an unclaimed saving left in
 * the record is slack the next regression lands inside.
 *
 * The document rule is a ceiling rather than a ratchet, because a page that got
 * lighter needs no permission. It bounds only the routes that render no day.
 *
 * So all three promises are checked mechanically rather than remembered.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, posix, relative, resolve, sep } from 'node:path';
import { gzipSync } from 'node:zlib';

const BUILD = 'build';
const ROOT = 'build/_app/immutable';
const BASELINE = 'bundle-baseline.json';

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

/**
 * The recorded weight of every route class lives in `bundle-baseline.json`,
 * hand-edited, with a sentence beside each number saying what those bytes buy.
 *
 * Not `config/`: that holds knobs a person tunes to change behaviour, and
 * filing a measurement under preferences invites editing it as one. Not
 * generated either - a file the build rewrites is a log, and a gate whose own
 * tooling updates its baseline cannot fail. And not inline here, because that
 * mixes a logic diff and a measurement diff in one review and pollutes the
 * history of the numbers.
 *
 * The document's ceilings are the mirror-image case and do live in `config/`:
 * a ceiling is a limit somebody chose, not a number the bundler moves. They are
 * read further down.
 */
let baseline;
try {
	baseline = JSON.parse(readFileSync(BASELINE, 'utf8'));
} catch (error) {
	console.error(`bundle gate: ${BASELINE} could not be read - ${error.message}`);
	process.exit(1);
}

const TOLERANCE = baseline.tolerance_bytes;
if (!Number.isInteger(TOLERANCE) || TOLERANCE <= 0) {
	console.error(`bundle gate: ${BASELINE} needs a positive integer "tolerance_bytes".`);
	process.exit(1);
}

const RECORDED = baseline.routes;
if (RECORDED === null || typeof RECORDED !== 'object' || Array.isArray(RECORDED)) {
	console.error(`bundle gate: ${BASELINE} needs a "routes" object.`);
	process.exit(1);
}

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

/** What a browser fetches before a reader does anything: the preloaded modules.
 *
 * Each one is gzipped on its own because that is how it arrives - one response,
 * one encoding. Gzipping the concatenation instead is order-sensitive, so the
 * number moves when the bundler reorders the preloads, which is noise nobody
 * caused, and it under-reports what the wire costs.
 */
function firstLoadBytes(page) {
	const html = readFileSync(page, 'utf8');
	const hrefs = new Set(
		[...html.matchAll(/<link\s+href="([^"]+)"\s+rel="modulepreload">/g)].map((match) => match[1])
	);
	let bytes = 0;
	for (const href of hrefs) {
		// 404.html is served from any depth, so it addresses its modules from the root.
		const absolute = href.startsWith('/');
		const from = absolute ? resolve(BUILD) : dirname(page);
		bytes += gzipBytes(resolve(from, absolute ? href.slice(1) : href));
	}
	return { bytes, modules: hrefs.size };
}

// Every date route preloads the same module set, so one instance stands for the
// whole class: take the heaviest and compare that.
const heaviest = new Map();
// The document is measured over the same walk. A route class holds one page per
// published day, so again the heaviest instance stands for the class.
const heaviestPage = new Map();
for (const page of pagesUnder(BUILD)) {
	const route = `/${relative(BUILD, page).split(sep).slice(0, -1).join(posix.sep)}`.replace(
		/\/$/,
		''
	);
	const name = page.endsWith('404.html') ? '/404' : routeClass(route);
	const { bytes, modules } = firstLoadBytes(page);
	const worst = heaviest.get(name);
	if (!worst || bytes > worst.bytes) heaviest.set(name, { bytes, modules, page });

	const html = gzipSync(readFileSync(page), { level: 9 }).length;
	const worstPage = heaviestPage.get(name);
	if (!worstPage || html > worstPage.bytes) heaviestPage.set(name, { bytes: html, page });
}

const commas = (value) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const signed = (value) => `${value < 0 ? '-' : '+'}${commas(Math.abs(value))}`;
const TODAY = new Date().toISOString().slice(0, 10);

/** One route's record, ready to paste. Only the sentence is left to write. */
const record = (name, bytes, why) =>
	`    ${JSON.stringify(name)}: { "bytes": ${bytes}, "measured": "${TODAY}", ` +
	`"why": ${JSON.stringify(why)} },`;

const pinned = typeof baseline.toolchain === 'string' ? baseline.toolchain : '';
const running = `node ${process.versions.node.split('.')[0]}`;
if (pinned && pinned !== running) {
	console.log(
		`\nbundle gate: recorded on ${pinned}, running on ${running}. gzip -9 is deterministic for ` +
			'given bytes, so a difference here may be the toolchain rather than the change.'
	);
}

const unrecorded = [];
const stale = [];
const malformed = [];
const moved = [];
const silent = [];

// A record is checked whether or not its route still builds. One that names
// nothing, or carries no reason, is how the file rots quietly.
for (const [name, entry] of Object.entries(RECORDED)) {
	if (entry === null || typeof entry !== 'object' || Array.isArray(entry)) {
		malformed.push(`${name} is not an object`);
		continue;
	}
	if (!Number.isInteger(entry.bytes) || entry.bytes <= 0) {
		malformed.push(`${name} needs a positive integer "bytes"`);
	}
	if (typeof entry.why !== 'string' || entry.why.trim() === '') {
		malformed.push(`${name} has an empty "why" - say what those bytes buy`);
	}
	if (typeof entry.measured !== 'string' || !DATE.test(entry.measured)) {
		malformed.push(
			`${name} has "measured": ${JSON.stringify(entry.measured)}, which is not a YYYY-MM-DD date`
		);
	}
	if (!heaviest.has(name)) {
		stale.push(`${name} is recorded at ${commas(entry.bytes)} B, and no page in the build is that route`);
	}
}

console.log('\nfirst-load JS, gzip -9 summed per module, against bundle-baseline.json:');
for (const [name, { bytes, modules, page }] of [...heaviest].sort()) {
	if (modules === 0) {
		silent.push(`${name} preloads no module at all (${page})`);
		continue;
	}
	const entry = RECORDED[name];
	const measured = `  ${name.padEnd(18)} ${commas(bytes).padStart(7)} B  ${String(modules).padStart(2)} modules`;
	if (entry === undefined || !Number.isInteger(entry.bytes)) {
		if (entry === undefined) unrecorded.push({ name, bytes, page });
		console.log(`${measured}  (no recorded weight)`);
		continue;
	}
	const delta = bytes - entry.bytes;
	const verdict = Math.abs(delta) <= TOLERANCE ? 'within' : 'OUTSIDE';
	console.log(
		`${measured}  (recorded ${commas(entry.bytes)}, ${signed(delta)}, ${verdict} +/-${TOLERANCE})`
	);
	if (Math.abs(delta) > TOLERANCE) moved.push({ name, bytes, entry, delta });
}

let failed = false;

if (silent.length > 0) {
	failed = true;
	console.error('\nbundle gate FAILED - a route declared no modules:');
	for (const line of silent) console.error(`  ${line}`);
	console.error(
		'\nA gate that measures 0 B and passes is worse than no gate. Either the build\n' +
			'changed how it declares its modules, or that page did not build.'
	);
}

if (malformed.length > 0) {
	failed = true;
	console.error(`\nbundle gate FAILED - a record in ${BASELINE} is incomplete:`);
	for (const line of malformed) console.error(`  ${line}`);
	console.error(
		'\nThe number is the measurement; the sentence beside it is what the bytes buy.\n' +
			'A record without both is a number nobody has to defend.'
	);
}

if (unrecorded.length > 0) {
	failed = true;
	console.error('\nbundle gate FAILED - a route in the build has no recorded weight:');
	for (const { name, bytes, page } of unrecorded) {
		console.error(`  ${name} measured ${commas(bytes)} B, first seen at ${page}`);
	}
	console.error(`\nAdd it under "routes" in ${BASELINE}:`);
	for (const { name, bytes } of unrecorded) console.error(record(name, bytes, ''));
	console.error(
		'\nThe gate keeps failing until the "why" names what those bytes buy. A route\n' +
			'nobody recorded is a route nobody measured.'
	);
}

if (stale.length > 0) {
	failed = true;
	console.error(`\nbundle gate FAILED - a record in ${BASELINE} names no route in the build:`);
	for (const line of stale) console.error(`  ${line}`);
	console.error(
		'\nDelete the record, or find out why the route stopped building. A record that\n' +
			'measures nothing still reads as a measurement.'
	);
}

if (moved.length > 0) {
	failed = true;
	console.error('\nbundle gate FAILED - a route left its recorded weight:');
	for (const { name, bytes, entry, delta } of moved) {
		console.error(
			`  ${name} ${delta > 0 ? 'grew to' : 'fell to'} ${commas(bytes)} B, ` +
				`${commas(Math.abs(delta))} B ${delta > 0 ? 'over' : 'under'} the recorded ` +
				`${commas(entry.bytes)} (tolerance +/-${TOLERANCE} B)`
		);
	}
	console.error(
		'\nThe ratchet is two-sided on purpose. A route that got lighter leaves slack in\n' +
			'the record, and the next regression lands inside it without a word.'
	);
	console.error(`\nRecord what you measured, in ${BASELINE}:`);
	for (const { name, bytes, entry } of moved) console.error(record(name, bytes, entry.why));
	console.error('\nThe "why" above is the old one. Replace it when the cause changed.');
}

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
 * growth: /404 and /evals/ move only when the source moves, and /archive/ grows
 * by one day link a published day, so its number carries a measured year of
 * that. /console/ grows with the ledger its charts read and nobody has priced
 * it, so a fixed byte ceiling there would fail on an ordinary publish rather
 * than catch a regression - `tests/payload-weight.spec.ts` covers that class by
 * counting a marker instead.
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
			'is capped, and a route it leaves out grows with the published corpus or the\n' +
			'ledger, where a fixed ceiling would fail on an ordinary publish rather than\n' +
			'catch a regression. To cap one, add it under "page_weight": { "ceilings_bytes":\n' +
			'{ ... } } in config/idhazh.json.'
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
}

if (failed) process.exit(1);

console.log('\nbundle gate: every route matches its recorded weight.');
console.log('bundle gate: every capped page is under its ceiling.');
