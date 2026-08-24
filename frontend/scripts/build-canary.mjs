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
	const before = new Date(`${date}T00:00:00Z`);
	before.setUTCDate(before.getUTCDate() - 1);
	const earlier = before.toISOString().slice(0, 10);
	const dir = join(STATE, 'item-health');
	mkdirSync(dir, { recursive: true });

	// Every token and millisecond below is one real request from run
	// 32742672105 job work (0) - the cold first request and six that reused the
	// slot's prompt. Two dates and two runs on the newer one, so the chart has a
	// trend to draw, a previous day to compare against, and more than one run
	// behind a candle. Invented numbers would make the console's arithmetic
	// impossible for anyone to check.
	const HEADER =
		'version,date,run_id,item_id,url_key,canonical_url,vertical,source_id,stage,outcome,code,' +
		'http_status,source_chars,source_words,summary_words,detail,fetch_ms,extract_ms,summarize_ms,' +
		'prefill_ms,decode_ms,input_tokens,output_tokens,cached_tokens';
	// The newest day's fetch, extract and summarize values straddle 200, 30 and
	// 700 so its medians stay where the stage-timing test pins them.
	const row = (rowDate, run, id, stages, timings) =>
		`2026-08-24T18:30,${rowDate},${rowDate}-${run},${id},${id},https://canary.example/${id},ai,` +
		`canary,publish,ok,,,1200,180,45,,${stages},${timings}`;

	writeFileSync(
		join(dir, `${year}-${month}.csv`),
		[
			HEADER,
			// fetch_ms,extract_ms,summarize_ms | prefill_ms,decode_ms,input,output,cached
			row(earlier, 1, 'ai-01', '120,20,610', '53309,40210,1497,215,900'),
			row(earlier, 1, 'ai-02', '210,30,720', '77778,43436,1765,230,900'),
			row(earlier, 1, 'ai-03', '260,35,780', '63586,50753,1608,270,900'),
			row(date, 1, 'ai-01', '100,20,600', '79100,29062,942,170,0'),
			row(date, 1, 'ai-02', '150,25,650', '7120,28206,975,167,900'),
			row(date, 2, 'ai-03', '250,35,750', '8883,22537,999,129,900'),
			row(date, 2, 'ai-04', '300,40,800', '82146,33203,1337,189,383')
		].join('\n') + '\n'
	);
}

writeItemHealthCanary();
execFileSync(
	'python',
	['-m', 'idhazh.publish_telemetry', '--state', STATE, '--public', join(STATE, 'telemetry')],
	{
		stdio: 'inherit',
		shell: process.platform === 'win32',
		cwd: resolve(process.cwd(), '..'),
		env: { ...process.env, PYTHONPATH: resolve(process.cwd(), '..', 'backend') }
	}
);

console.log(`building the site from ${ROOT}`);
execFileSync('npm', ['run', 'build'], {
	stdio: 'inherit',
	shell: process.platform === 'win32',
	env: { ...process.env, DIGEST_ROOT: ROOT, STATE_ROOT: STATE, TELEMETRY_ROOT: join(STATE, 'telemetry') }
});
