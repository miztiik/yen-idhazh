#!/usr/bin/env node
/** Stage only files named by the producer's publication inventory and ledger indexes. */

import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { assetBaseUrl } from '../asset-base.js';
import { projectDay } from '../src/lib/payload/project.ts';
import { publicFiles } from '../src/lib/server/publication.ts';
import { ledgerCopy, publishedLedgers } from './published-ledgers.mjs';
import { stagedPath } from './staged-publication.mjs';

const digestRoot = process.env.DIGEST_ROOT
	? resolve(process.env.DIGEST_ROOT)
	: resolve('public', 'digest');
const publicRoot = resolve(digestRoot, '..');
const telemetryRoot = process.env.TELEMETRY_ROOT
	? resolve(process.env.TELEMETRY_ROOT)
	: resolve('public', 'telemetry');
const stateRoot = process.env.STATE_ROOT
	? resolve(process.env.STATE_ROOT)
	: resolve('..', 'state');
const servedElsewhere = assetBaseUrl() !== '';
const stagedTrees = ['digest', 'index', 'telemetry', 'console', 'run-days', 'day-metrics', 'machine', 'state'];

// These are this build's generated output directories, not the committed input.
// Replacing them also removes files the producer no longer names, with no
// discovery of either the archive or the previous build's files.
for (const tree of stagedTrees) rmSync(join('static', tree), { recursive: true, force: true });

function stage(bytes, destination) {
	mkdirSync(dirname(destination), { recursive: true });
	writeFileSync(destination, bytes);
}

let copied = 0;
let projected = 0;
let skipped = 0;
for (const file of publicFiles(publicRoot)) {
	const named = stagedPath(file, servedElsewhere);
	if (named === null) continue;
	const destination = join('static', ...named.split('/'));
	const dayPayload = /^digest\/\d{4}\/\d{2}\/\d{2}\/digest\.json$/.test(file);
	const source = file.startsWith('telemetry/')
		? join(telemetryRoot, file.slice('telemetry/'.length))
		: join(publicRoot, ...file.split('/'));
	if (!existsSync(source)) {
		console.warn(`published visuals: inventory file ${file} is missing, skipped.`);
		skipped += 1;
		continue;
	}
	if (dayPayload) {
		let bytes;
		try {
			bytes = Buffer.from(projectDay(readFileSync(source, 'utf8')));
		} catch (cause) {
			console.warn(`published visuals: ${file} is unreadable, day skipped - ${String(cause)}`);
			skipped += 1;
			continue;
		}
		stage(bytes, destination);
		projected += 1;
	} else {
		stage(readFileSync(source), destination);
		copied += 1;
	}
}

const ledgers = publishedLedgers();
const stateLabel = relative(resolve('..'), stateRoot).split(sep).join('/');
const copy = ledgerCopy(stateRoot, ledgers, stateLabel);
if (copy.refused.length > 0) {
	throw new Error(`Published ledger is incomplete:\n${copy.refused.join('\n')}`);
}
for (const file of copy.missing) {
	const [, ledger] = file.split('/');
	console.log(
		`::warning title=A published ledger file is missing::file-missing ${ledger} ${stateLabel}/${file}: ` +
			'an index names it and it is not in the tree. The site is built without it, and the ' +
			'console shows the days it covers as unreachable. Re-pack that day.'
	);
}
for (const line of copy.logs ?? []) console.log(line);
if (!servedElsewhere) {
	for (const file of copy.files) {
		const bytes = copy.indexes[file] === undefined
			? readFileSync(join(stateRoot, ...file.split('/')))
			: Buffer.from(copy.indexes[file], 'utf8');
		stage(bytes, join('static', 'state', ...file.split('/')));
	}
}

const registrySource = resolve('..', 'config', 'ledgers.json');
const registryTarget = join('static', 'config', 'ledgers.json');
if (existsSync(registrySource)) stage(readFileSync(registrySource), registryTarget);
else rmSync(registryTarget, { force: true });

console.log(
	`published visuals: staged ${copied} named file(s), projected ${projected} day payload(s), ` +
		`${skipped} missing or unreadable; published ledgers: ${servedElsewhere ? 0 : copy.files.length} file(s).`
);
