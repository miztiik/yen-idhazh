#!/usr/bin/env node
/**
 * Build the site out of the injection canaries instead of the real digest.
 *
 * `DIGEST_ROOT` and `STATE_ROOT` are the only switches. The canary day never
 * enters `frontend/public/`, so an attack fixture can never be published by
 * accident - which matters, because these payloads carry raw hostile markup on
 * purpose. The state root is switched with it so the console draws the fixture
 * run manifest and the fixture feed results, never the real ledger.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary');
const ROOT = resolve(CANARY, 'digest');
const STATE = resolve(CANARY, 'state');

if (!existsSync(ROOT)) {
	console.error(
		'canary day is missing. Build it first:\n' +
			'  python backend/utilities/build_canary_day.py'
	);
	process.exit(1);
}

function newestDirectory(at) {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort()
		.at(-1);
}

function writeItemHealthCanary() {
	const year = newestDirectory(ROOT);
	const month = newestDirectory(join(ROOT, year));
	const day = newestDirectory(join(ROOT, year, month));
	const date = `${year}-${month}-${day}`;
	const dir = join(STATE, 'item-health');
	mkdirSync(dir, { recursive: true });
	writeFileSync(
		join(dir, `${year}-${month}.csv`),
		[
			'version,date,run_id,item_id,url_key,canonical_url,vertical,source_id,stage,outcome,code,http_status,source_chars,source_words,summary_words,detail,fetch_ms,extract_ms,summarize_ms',
			`2026-08-23T18:40,${date},${date}-1,ai-01,one,https://canary.example/one,ai,canary,publish,ok,,,1200,180,45,,100,20,600`,
			`2026-08-23T18:40,${date},${date}-1,ai-02,two,https://canary.example/two,ai,canary,publish,ok,,,1200,180,45,,200,30,700`,
			`2026-08-23T18:40,${date},${date}-1,ai-03,three,https://canary.example/three,ai,canary,publish,ok,,,1200,180,45,,300,40,800`
		].join('\n') + '\n'
	);
}

writeItemHealthCanary();

console.log(`building the site from ${ROOT}`);
execFileSync('npm', ['run', 'build'], {
	stdio: 'inherit',
	shell: process.platform === 'win32',
	env: { ...process.env, DIGEST_ROOT: ROOT, STATE_ROOT: STATE }
});
