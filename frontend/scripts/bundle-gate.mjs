#!/usr/bin/env node
/**
 * Two checks over a finished build: no encoder on the first-load path, and no
 * route heavier than its declared ceiling.
 *
 * The encoder rule is that nothing downloads or executes before a reader
 * clicks. A dynamic `import()` is what keeps that true, and a dynamic import is
 * one careless edit away from becoming a static one. Nothing about that edit
 * looks wrong in review - the page still works, it just costs every reader of
 * every page a multi-megabyte library they never asked for.
 *
 * The weight rule prices the next dependency before it ships. A library that
 * computes rather than draws is cheap enough to be worth it and cheap enough to
 * be invisible, so the only thing that stops the second and the third one is a
 * number that fails a build.
 *
 * So both promises are checked mechanically rather than remembered.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, posix, relative, resolve, sep } from 'node:path';
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

/**
 * Ceilings on gzipped first-load JavaScript, in bytes, one per route class.
 *
 * They live here rather than in `config/` because they are not a knob: an
 * operator has no reason to raise the weight a reader pays, and a budget that
 * can be edited to fit the build is not a budget (Rule #2). Raising one is a
 * reviewed diff with a measurement beside it in
 * `docs/reference/measurements.md`.
 *
 * Each is a measured baseline plus a stated headroom. The baselines were taken
 * by this script on 2026-08-25.
 *
 * HTML weight is deliberately not gated here. The document is owned by the
 * payload work, and one gate spanning both would make two workstreams fail each
 * other's builds.
 */

/** Room for framework noise, not for a dependency. A reader route may not buy one. */
const READER_HEADROOM = 1024;

/** What the console chart work was authorised to spend on `d3-scale` and `d3-array`. */
const CONSOLE_HEADROOM = 10 * 1024;

const CEILINGS = {
	'/': 49_201 + READER_HEADROOM,
	'/<date>/': 49_071 + READER_HEADROOM,
	'/<date>/<topic>/': 49_164 + READER_HEADROOM,
	'/archive/': 44_476 + READER_HEADROOM,
	'/evals/': 41_883 + READER_HEADROOM,
	'/404': 40_925 + READER_HEADROOM,
	'/console/': 54_180 + CONSOLE_HEADROOM
};

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** The route class a prerendered page belongs to, so a ceiling survives a new day. */
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

/** What a browser fetches before a reader does anything: the preloaded modules.
 *
 * Each one is gzipped on its own because that is how it arrives - one response,
 * one encoding. Summing separately compressed files is the honest total.
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
		bytes += gzipSync(readFileSync(resolve(from, absolute ? href.slice(1) : href)), {
			level: 9
		}).length;
	}
	return { bytes, modules: hrefs.size };
}

const heaviest = new Map();
for (const page of pagesUnder(BUILD)) {
	const route = `/${relative(BUILD, page).split(sep).slice(0, -1).join(posix.sep)}`.replace(
		/\/$/,
		''
	);
	const name = page.endsWith('404.html') ? '/404' : routeClass(route);
	const { bytes, modules } = firstLoadBytes(page);
	const worst = heaviest.get(name);
	if (!worst || bytes > worst.bytes) heaviest.set(name, { bytes, modules, page });
}

const kb = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;
console.log('\nfirst-load JS, gzip -9, heaviest page of each route class:');
const overweight = [];
for (const [name, { bytes, modules, page }] of [...heaviest].sort()) {
	const ceiling = CEILINGS[name];
	if (ceiling === undefined) {
		overweight.push(`${name} has no ceiling (first seen at ${page})`);
		continue;
	}
	console.log(
		`  ${name.padEnd(20)} ${kb(bytes).padStart(9)} ${String(bytes).padStart(7)} B  ` +
			`${String(modules).padStart(2)} modules  (ceiling ${kb(ceiling)})`
	);
	if (bytes > ceiling) overweight.push(`${name} is ${kb(bytes)} against a ${kb(ceiling)} ceiling`);
}

if (overweight.length > 0) {
	console.error('\nbundle gate FAILED - a route outgrew its first-load budget:');
	for (const line of overweight) console.error(`  ${line}`);
	console.error(
		'\nPrice the change: measure it, record it in docs/reference/measurements.md,'
	);
	console.error('and raise the ceiling in the same diff - or do not ship the bytes.');
	process.exit(1);
}

console.log('bundle gate: every route is inside its first-load budget.');
