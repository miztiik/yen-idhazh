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
	const back = (days) => {
		const at = new Date(`${date}T00:00:00Z`);
		at.setUTCDate(at.getUTCDate() - days);
		return at.toISOString().slice(0, 10);
	};
	const earlier = back(1);
	const earliest = back(2);
	const dir = join(STATE, 'item-health');
	mkdirSync(dir, { recursive: true });

	// Every token and millisecond on a published row below is one real request
	// from run 32742672105 job work (0) - the cold first request and six that
	// reused the slot's prompt. Two dates carry them, and two runs carry the
	// newer one, so the chart has a trend to draw, a previous day to compare
	// against, and more than one run behind a candle. Invented numbers would
	// make the console's arithmetic impossible for anyone to check.
	//
	// Three days, because the chart has to tell three facts apart and each one
	// needs a day of its own to sit on: a stage nothing timed, a stage timed at
	// zero, and a day timed in part.
	const COLUMNS = [
		'version', 'date', 'run_id', 'item_id', 'url_key', 'canonical_url', 'vertical',
		'source_id', 'stage', 'outcome', 'code', 'http_status', 'source_chars', 'source_words',
		'summary_words', 'detail', 'fetch_ms', 'extract_ms', 'summarize_ms', 'prefill_ms',
		'decode_ms', 'input_tokens', 'output_tokens', 'cached_tokens'
	];
	// Named cells, so a column added to the row cannot silently shift every
	// number one place to the left.
	const line = (cells) => COLUMNS.map((name) => cells[name] ?? '').join(',');
	const item = (rowDate, run, id) => ({
		version: '2026-08-24T18:30',
		date: rowDate,
		run_id: `${rowDate}-${run}`,
		item_id: id,
		url_key: id,
		canonical_url: `https://canary.example/${id}`,
		vertical: 'ai',
		source_id: 'canary'
	});

	/** An item that reached the digest, so every stage timed itself. */
	const published = (rowDate, run, id, [fetchMs, extractMs, summarizeMs], model) =>
		line({
			...item(rowDate, run, id),
			stage: 'publish',
			outcome: 'ok',
			source_chars: 1200,
			source_words: 180,
			summary_words: 45,
			fetch_ms: fetchMs,
			extract_ms: extractMs,
			summarize_ms: summarizeMs,
			prefill_ms: model[0],
			decode_ms: model[1],
			input_tokens: model[2],
			output_tokens: model[3],
			cached_tokens: model[4]
		});

	/** An item the extractor threw away. Not a failure: dropping a page that is
	 * not an article is the job, so the row is `ok` and the failed-item list
	 * stays empty. It fetched and it parsed, so those two stages have a number.
	 * The model never saw it, so summarize has none. */
	const dropped = (rowDate, run, id, code, chars, words, fetchMs, extractMs) =>
		line({
			...item(rowDate, run, id),
			stage: 'extract',
			outcome: 'ok',
			code,
			source_chars: chars,
			source_words: words,
			fetch_ms: fetchMs,
			extract_ms: extractMs
		});

	writeFileSync(
		join(dir, `${year}-${month}.csv`),
		[
			COLUMNS.join(','),
			// The oldest day found three pages too short to be articles and
			// summarised none of them. Parsing 200 characters finished inside the
			// millisecond clock, so extract reads 0 on all three: a measurement,
			// not a gap. The score ledger recorded exactly that on 2026-08-22, on
			// all ten of that day's rows. Summarize has no number at all here,
			// which is the other fact - and the chart must not draw them alike.
			dropped(earliest, 1, 'ai-06', 'too_short', 214, 32, 130, 0),
			dropped(earliest, 1, 'ai-07', 'too_short', 186, 27, 220, 0),
			dropped(earliest, 1, 'ai-08', 'too_short', 241, 35, 270, 0),
			// fetch,extract,summarize | prefill,decode,input,output,cached
			published(earlier, 1, 'ai-01', [120, 20, 610], [53309, 40210, 1497, 215, 900]),
			published(earlier, 1, 'ai-02', [210, 30, 720], [77778, 43436, 1765, 230, 900]),
			published(earlier, 1, 'ai-03', [260, 35, 780], [63586, 50753, 1608, 270, 900]),
			// The newest day's fetch, extract and summarize values straddle 200, 30
			// and 700 so its medians stay where the stage-timing test pins them.
			published(date, 1, 'ai-01', [100, 20, 600], [79100, 29062, 942, 170, 0]),
			published(date, 1, 'ai-02', [150, 25, 650], [7120, 28206, 975, 167, 900]),
			published(date, 2, 'ai-03', [250, 35, 750], [8883, 22537, 999, 129, 900]),
			published(date, 2, 'ai-04', [300, 40, 800], [82146, 33203, 1337, 189, 383]),
			// A whole page parsed, then thrown away for boilerplate. It makes the
			// newest day a partly timed one for summarize: four items of five. Its
			// fetch and extract are that day's own medians, so neither median moves
			// and the fifth item only widens the denominator.
			dropped(date, 2, 'ai-05', 'boilerplate', 1180, 174, 200, 30)
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
