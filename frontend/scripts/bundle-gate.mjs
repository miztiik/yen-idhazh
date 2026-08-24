#!/usr/bin/env node
/**
 * Fail the build if the on-device encoder reaches the first-load bundle.
 *
 * The rule is that nothing downloads or executes before a reader clicks. A
 * dynamic `import()` is what keeps that true, and a dynamic import is one
 * careless edit away from becoming a static one. Nothing about that edit looks
 * wrong in review - the page still works, it just costs every reader of every
 * page a multi-megabyte library they never asked for.
 *
 * So the promise is checked mechanically rather than remembered.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

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
