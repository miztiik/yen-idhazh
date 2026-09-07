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
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
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

/** The article key the score ledger gave each published canary item.
 *
 * The two canary ledgers are written by two programs - the day and its scores
 * by `build_canary_day.py`, the item-health rows here - and `url_key` is the
 * key that joins them. It is a digest of the canonical address, so it is READ
 * off the ledger the Python step already wrote rather than derived a second
 * time in JavaScript: two derivations of one key is how the fixture would come
 * to disagree with the contract it stands in for.
 *
 * An item the scores do not name keeps its own id, which is what every row
 * here carried before. Those rows are the cut fixtures, which nothing scored.
 */
function scoredKeys() {
	const dir = join(STATE, 'scores');
	const found = new Map();
	if (!existsSync(dir)) return found;
	for (const name of readdirSync(dir).filter((entry) => entry.endsWith('.csv'))) {
		const lines = readFileSync(join(dir, name), 'utf8').split('\n').filter(Boolean);
		const header = lines[0].split(',');
		const itemAt = header.indexOf('item_id');
		const keyAt = header.indexOf('url_key');
		if (itemAt < 0 || keyAt < 0) continue;
		for (const row of lines.slice(1)) {
			const cells = row.split(',');
			if (cells[itemAt] && cells[keyAt]) found.set(cells[itemAt], cells[keyAt]);
		}
	}
	return found;
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
	const sourceDay = back(3);
	const outsideWindow = back(10);
	/** The same day the counters fixture puts its widest-preset run on.
	 *
	 * Outside 7, 14 and 30 days, inside 90. Two runs sit here and each times six
	 * items, which is the only place on this fixture that clears
	 * `console.min_attempts_for_rate` - so the latency plots draw a line at the
	 * widest preset and nowhere else. Without it every run here times two or
	 * three items, a p99 over three items is the third item, and the panel is a
	 * state no test could reach.
	 */
	const longAgo = back(40);
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
		'decode_ms', 'input_tokens', 'output_tokens', 'cached_tokens', 'source_words_before_cap',
		'shard'
	];
	// Named cells, so a column added to the row cannot silently shift every
	// number one place to the left.
	const line = (cells) => COLUMNS.map((name) => cells[name] ?? '').join(',');
	const keyOf = scoredKeys();
	const item = (rowDate, run, id) => ({
		version: '2026-08-24T18:30',
		date: rowDate,
		run_id: `${rowDate}-${run}`,
		item_id: id,
		url_key: keyOf.get(id) ?? id,
		canonical_url: `https://canary.example/${id}`,
		vertical: 'ai',
		source_id: 'canary'
	});

	/** An item that reached the digest, so every stage timed itself.
	 *
	 * `cut` is `[source_chars, source_words, source_words_before_cap]` and those
	 * three numbers are fixture values, not measurements - unlike every token and
	 * millisecond above. The truncation cap never fired in the run this canary was
	 * taken from, so the one state the new column exists for, a body trimmed before
	 * the model read it, is unreachable without them. 1923 is
	 * `int(extract.truncation_cap_tokens / 1.3)` at the committed cap of 2500, so
	 * the post-cap count sits on the ceiling a real cut leaves it on. A row without
	 * `cut` leaves the cell empty, which is what every run before 2026-08-28 wrote.
	 */
	const published = (rowDate, run, id, [fetchMs, extractMs, summarizeMs], model, cut) =>
		line({
			...item(rowDate, run, id),
			stage: 'publish',
			outcome: 'ok',
			source_chars: cut?.[0] ?? 1200,
			source_words: cut?.[1] ?? 180,
			summary_words: 45,
			fetch_ms: fetchMs,
			extract_ms: extractMs,
			summarize_ms: summarizeMs,
			prefill_ms: model[0],
			decode_ms: model[1],
			input_tokens: model[2],
			output_tokens: model[3],
			cached_tokens: model[4],
			source_words_before_cap: cut?.[2]
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

	/** What the cap cost each source, so the source table has a table to draw.
	 *
	 * `[source, articles, cuts]`. The whole block is fixture, not measurement:
	 * the cap has never fired in a real run this canary was taken from, so every
	 * state the table exists for - several sources, a share too thin to divide,
	 * more sources than the list prints - is unreachable without inventing them.
	 * They carry no timing at all, so the day they sit on draws no candle, no
	 * stage median and no model row, and nothing already pinned to this fixture
	 * moves.
	 *
	 * `cut-c` has four articles, under `console.min_attempts_for_rate`, so its
	 * share prints as a dash. Twelve sources are cut once `canary` below is
	 * counted, which is two more than the table prints.
	 */
	const CUT_SOURCES = [
		['cut-a', 7, 6],
		['cut-b', 6, 5],
		['cut-c', 4, 4],
		['cut-d', 5, 3],
		['cut-e', 5, 3],
		['cut-f', 5, 2],
		['cut-g', 5, 2],
		['cut-h', 5, 2],
		['cut-i', 5, 1],
		['cut-j', 5, 1],
		['cut-k', 5, 1]
	];

	/** One article of one source on the source-cut day.
	 *
	 * `before` is the length the extractor read and `after` is what survived the
	 * cap, exactly as `extract` writes them. An empty `before` is what every run
	 * before 2026-08-28 wrote, and it is the cell that must never be read as a
	 * zero: a source whose lengths are all empty publishes articles nobody
	 * measured, not articles of no length.
	 */
	const article = (rowDate, run, source, index, before, after, summaryWords = 60) =>
		line({
			version: '2026-08-29T09:00',
			date: rowDate,
			run_id: `${rowDate}-${run}`,
			item_id: `${source}-${index}`,
			url_key: `${source}-${index}`,
			canonical_url: `https://canary.example/${source}-${index}`,
			vertical: 'ai',
			source_id: source,
			stage: 'publish',
			outcome: 'ok',
			source_chars: after * 6,
			source_words: after,
			summary_words: summaryWords,
			source_words_before_cap: before
		});

	/** Every row of the source-cut day, plus the two rows that must be excluded.
	 *
	 * Three things here are what stop the table's oracle passing on an
	 * implementation that only counts: a source whose longest article was never
	 * cut, a source whose longest surviving body sits on a row that recorded no
	 * length before the cut, and one article written by two runs.
	 */
	function sourceCutRows() {
		const rows = [];
		for (const [source, articles, cuts] of CUT_SOURCES) {
			for (let index = 0; index < articles; index += 1) {
				if (index < cuts) {
					// A body the cap trimmed to 1,923 words. Each one loses a different
					// amount, so the middle article and the worst are two numbers.
					rows.push(article(sourceDay, 1, source, index, 1923 + 700 * (index + 1), 1923));
					continue;
				}
				if (source === 'cut-a') {
					// The longest article this source published was never cut. A column
					// that read the longest *cut* article would print 6,123 here.
					rows.push(article(sourceDay, 1, source, index, 9000, 9000));
					continue;
				}
				if (source === 'cut-b') {
					// A migrated row: no length before the cut, and a surviving body
					// longer than anything the source was cut at. A column that took the
					// largest `source_words` would print 30,000 and mean nothing by it.
					rows.push(article(sourceDay, 1, source, index, '', 30000));
					continue;
				}
				if (source === 'cut-k' && index === articles - 1) {
					// The one summary that ran PAST its band. Every other row this fixture
					// writes lands inside its band or short of it, so without this the
					// third state of the day's split is a state the suite cannot reach and
					// an implementation that never says "too long" passes every assertion.
					// 404 words asks for 50 to 90, so 260 is 170 words past - the widest
					// miss in the fixture either way, which is what puts it top of the
					// outlier list.
					rows.push(article(sourceDay, 1, source, index, 400 + index, 400 + index, 260));
					continue;
				}
				rows.push(article(sourceDay, 1, source, index, 400 + index, 400 + index));
			}
		}
		// The same article on a second run. A count of rows says this source
		// published eight; it published seven.
		rows.push(article(sourceDay, 2, 'cut-a', 0, 1923 + 700, 1923));
		// Articles nobody measured. The table must leave this source out rather
		// than list it with a zero.
		for (let index = 0; index < 5; index += 1) {
			rows.push(article(sourceDay, 1, 'no-length', index, '', 800 + index));
		}
		// Cut, and older than the window. A table that read the whole ledger would
		// name it.
		rows.push(article(outsideWindow, 1, 'old-cut', 0, 4000, 1923));
		return rows;
	}

	/** One run's worth of timed items, for the latency plots.
	 *
	 * Six of them, because `console.min_attempts_for_rate` is the floor below
	 * which a p99 is just the slowest item. The stage clock is all these rows
	 * carry: no `prefill_ms`, no `decode_ms` and no token count, which is the
	 * state every run before token capture is in and is also what keeps these
	 * rows out of the throughput candles, the token totals and the cost figures.
	 * A row that carries a stage clock and no model clock is evidence about the
	 * stage and about nothing else.
	 */
	function tailRows(rowDate, run, model) {
		return model.map((summarizeMs, index) =>
			published(rowDate, run, `tail-${run}-${index}`, [120, 20, summarizeMs], ['', '', '', '', ''])
		);
	}

	const currentRows = [
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
		// The one cut row, so both shapes of the cell are on the day: a body the
		// cap trimmed from 2612 words to 1923, beside four rows that carry nothing.
		// Its 4200 ms is a fixture value like the three word counts beside it: at
		// 800 the day's split by cut printed the same second as the day itself, so
		// a table that never split at all read the same. It sits either side of
		// this day's summarize median, so the median does not move.
		published(date, 2, 'ai-04', [300, 40, 4200], [82146, 33203, 1337, 189, 383], [12800, 1923, 2612]),
		// A whole page parsed, then thrown away for boilerplate. It makes the
		// newest day a partly timed one for summarize: four items of five. Its
		// fetch and extract are that day's own medians, so neither median moves
		// and the fifth item only widens the denominator.
		dropped(date, 2, 'ai-05', 'boilerplate', 1180, 174, 200, 30),
		...sourceCutRows()
	];
	// Forty days back, on the day the counters fixture already uses for its
	// widest-preset run. Two runs of six timed items each - the only rows
	// here that clear `console.min_attempts_for_rate`, so the latency plots
	// have a line to draw at 90 days and an empty state at every narrower
	// preset. The six values a run climb steeply on purpose: the p99 is
	// about eight times the p50, which is what the shared scale across the
	// five plots exists to show, and two plots on two scales would draw the
	// same shape twice.
	//
	// These rows are dated a month before the rest, so they are a telemetry
	// shard of their own - the file a run in that month would have written,
	// which is how the real ledger shards item-health. A browser that widens the
	// window fetches this file, and `console-telemetry-heal.spec.ts` fails that
	// fetch to prove a retry heals it.
	const longAgoRows = [
		...tailRows(longAgo, 1, [520, 640, 700, 810, 1100, 4300]),
		...tailRows(longAgo, 2, [560, 690, 760, 880, 1250, 4900])
	];
	const currentMonth = `${year}-${month}`;
	const longAgoMonth = longAgo.slice(0, 7);
	const shards = new Map([[currentMonth, currentRows]]);
	// The back-dated run stands alone in its month on this fixture. The guard is
	// only there so a fixture edit that moved it into the current month could not
	// write one file twice and lose the rows above.
	shards.set(
		longAgoMonth,
		longAgoMonth === currentMonth ? [...currentRows, ...longAgoRows] : longAgoRows
	);
	for (const [shardMonth, shardRows] of shards) {
		writeFileSync(
			join(dir, `${shardMonth}.csv`),
			[COLUMNS.join(','), ...shardRows].join('\n') + '\n'
		);
	}
}

/** What llama-server counted, for the two canary runs the item ledger already has.
 *
 * Without this file the Machine route draws nothing at all in the browser
 * suite, so every panel on it would be asserted only in its empty state - a
 * canary column nothing exercises is a chart state no test can reach.
 *
 * The numbers are chosen so three states are on the page at once and each one
 * can be checked with a pencil:
 *
 *  - **A real read spread.** Shard 0 of the newest run reads 800 prompt tokens
 *    in 40 seconds and shard 1 reads 253 in 52, which is 20.00 against 4.87 -
 *    4.11x apart inside one run, which is the whole reason the route exists.
 *  - **The two clocks agreeing without agreeing exactly.** The item rows above
 *    give run `<date>-2` 1,053 read tokens over 91.029 seconds, or 11.57 a
 *    second. This file gives the server 1,053 over 92, or 11.45 - 1.1 percent
 *    apart, inside the 5 percent `reconcile_prefill.py` gates on. Equal figures
 *    would pass a check that had never run.
 *  - **Absence drawn as absence.** Shard 1 of that run carries no `job_seconds`,
 *    no `cpu_model` and none of the three host cells, exactly as 24 of the 54
 *    committed rows do, because each of those columns landed after the ledger
 *    started. The board prints a dash and ranks that shard last rather than
 *    treating a blank clock as a fast one.
 *  - **A run only the widest span can reach.** One run sits 40 days back, so it
 *    is drawn at 90 days and at no other preset. Without it every preset draws
 *    the same runs on this fixture, and a route that wired the day count onto
 *    its surfaces while ignoring the window entirely would pass the window
 *    oracle - which is the one bug that oracle exists to catch.
 */
function writeRuntimeCountersCanary() {
	const year = newestDirectory(ROOT);
	const month = newestDirectory(join(ROOT, year));
	const day = newestDirectory(join(ROOT, year, month));
	const date = `${year}-${month}-${day}`;
	const back = (days) => {
		const at = new Date(`${date}T00:00:00Z`);
		at.setUTCDate(at.getUTCDate() - days);
		return at.toISOString().slice(0, 10);
	};
	const before = back(1);
	// Outside 7, 14 and 30 days, inside 90. The default window is 30, so nothing
	// already pinned to this fixture moves.
	const longAgo = back(40);

	// Named cells for the same reason the item-health canary uses them: a column
	// added to the row must not shift every number one place to the left.
	const COUNTER_COLUMNS = [
		'version', 'date', 'run_id', 'shard', 'shards', 'scraped_at',
		'prompt_tokens_total', 'prompt_tokens_cached_total', 'prompt_seconds_total',
		'tokens_predicted_total', 'tokens_predicted_seconds_total', 'n_decode_total',
		'n_tokens_max', 'n_busy_slots_per_decode', 'job_seconds', 'cpu_model',
		'cpu_busy_pct', 'peak_rss_bytes', 'model_load_ms'
	];
	const row = (cells) => COUNTER_COLUMNS.map((name) => cells[name] ?? '').join(',');
	const shard = (rowDate, run, index, cells) => ({
		version: '2026-08-30',
		date: rowDate,
		run_id: `${rowDate}-${run}`,
		shard: index,
		shards: 2,
		scraped_at: `${rowDate}T2${run}:0${index}:00Z`,
		n_busy_slots_per_decode: '1.0',
		...cells
	});

	writeFileSync(join(STATE, 'runtime-counters.csv'), [
		COUNTER_COLUMNS.join(','),
		// The newest run. Shard 0 is fully instrumented; shard 1 is a shard that
		// ran before the host cells existed.
		row(shard(date, 2, 0, {
			prompt_tokens_total: 800, prompt_tokens_cached_total: 700, prompt_seconds_total: 40,
			tokens_predicted_total: 296, tokens_predicted_seconds_total: 60, n_decode_total: 299,
			n_tokens_max: 4096, job_seconds: 900,
			cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C',
			cpu_busy_pct: 94.5, peak_rss_bytes: 12990730240, model_load_ms: 2470.828
		})),
		row(shard(date, 2, 1, {
			prompt_tokens_total: 253, prompt_tokens_cached_total: 583, prompt_seconds_total: 52,
			tokens_predicted_total: 22, tokens_predicted_seconds_total: 4, n_decode_total: 23,
			n_tokens_max: 2048
		})),
		// A second run on the same day, so the cache chart has a column to sum and
		// the context panel has more than one bar to compare.
		row(shard(date, 1, 0, {
			prompt_tokens_total: 942, prompt_tokens_cached_total: 0, prompt_seconds_total: 79.1,
			tokens_predicted_total: 170, tokens_predicted_seconds_total: 29.062, n_decode_total: 172,
			n_tokens_max: 1112, job_seconds: 640,
			cpu_model: 'AMD EPYC 7763 64-Core Processor',
			cpu_busy_pct: 88.4, peak_rss_bytes: 10804060160, model_load_ms: 3881.795
		})),
		row(shard(date, 1, 1, {
			prompt_tokens_total: 975, prompt_tokens_cached_total: 900, prompt_seconds_total: 7.12,
			tokens_predicted_total: 167, tokens_predicted_seconds_total: 28.206, n_decode_total: 169,
			n_tokens_max: 1875, job_seconds: 610,
			cpu_model: 'AMD EPYC 7763 64-Core Processor',
			cpu_busy_pct: 91.2, peak_rss_bytes: 11779497984, model_load_ms: 3769.648
		})),
		// The day before, so the cache chart draws a second column and a trend
		// rather than one bar with nothing to be a trend against.
		row(shard(before, 1, 0, {
			prompt_tokens_total: 1497, prompt_tokens_cached_total: 900, prompt_seconds_total: 53.309,
			tokens_predicted_total: 215, tokens_predicted_seconds_total: 40.21, n_decode_total: 218,
			n_tokens_max: 1712, job_seconds: 720,
			cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C',
			cpu_busy_pct: 93.1, peak_rss_bytes: 13072498688, model_load_ms: 2418.609
		})),
		row(shard(before, 1, 1, {
			prompt_tokens_total: 1765, prompt_tokens_cached_total: 900, prompt_seconds_total: 77.778,
			tokens_predicted_total: 230, tokens_predicted_seconds_total: 43.436, n_decode_total: 233,
			n_tokens_max: 1995, job_seconds: 780,
			cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C',
			cpu_busy_pct: 92.8, peak_rss_bytes: 12990730240, model_load_ms: 2470.828
		})),
		// Forty days back, so only the widest preset reaches it. Its readings sit
		// outside the span of every other run - the lowest processor share, the
		// highest memory and the slowest load - so widening the window moves the
		// three host spans as well as adding a bar and a cache column.
		row(shard(longAgo, 1, 0, {
			prompt_tokens_total: 1210, prompt_tokens_cached_total: 300, prompt_seconds_total: 96.4,
			tokens_predicted_total: 188, tokens_predicted_seconds_total: 35.5, n_decode_total: 190,
			n_tokens_max: 3210, job_seconds: 1020,
			cpu_model: 'AMD EPYC 7763 64-Core Processor',
			cpu_busy_pct: 61.7, peak_rss_bytes: 14495514624, model_load_ms: 6120.5
		})),
		row(shard(longAgo, 1, 1, {
			prompt_tokens_total: 640, prompt_tokens_cached_total: 120, prompt_seconds_total: 51.2,
			tokens_predicted_total: 96, tokens_predicted_seconds_total: 18.9, n_decode_total: 98,
			n_tokens_max: 2740, job_seconds: 940,
			cpu_model: 'AMD EPYC 7763 64-Core Processor',
			cpu_busy_pct: 64.3, peak_rss_bytes: 13958643712, model_load_ms: 5880.25
		}))
	].join('\n') + '\n');
}

/** One traced run's span rollup, so the console's span breakdown has a run to
 * draw. `build_canary_day.py` fabricates a day rather than running the traced
 * pipeline, so it writes no spans; without this the panel only ever shows its
 * empty state, and the residual it exists to draw would never be tested.
 *
 * The one run sits on the day the span record begins, 2026-09-06, because a run
 * before then could not have committed spans. Two shards, so the panel draws
 * more than one bar and the overhead differs between them - the whole point of
 * the residual is that it is not the same on every shard. Every number
 * reconciles the way the fold requires: `total_ms` on the item row plus
 * `unattributed_ms` is the shard's wall clock, and the four sub-steps sit inside
 * the item time and never beyond it.
 */
function writeSpanRollupCanary() {
	const COLUMNS = [
		'version', 'date', 'run_id', 'shard', 'span_name', 'count', 'total_ms', 'unattributed_ms'
	];
	const line = (cells) => COLUMNS.map((name) => cells[name] ?? '').join(',');
	// The residual is a cell on the item row alone; empty on the four sub-steps,
	// the way the contract writes it.
	const row = (shard, span_name, count, total_ms, unattributed_ms) =>
		line({
			version: '2026-09-06T15:00',
			date: '2026-09-06',
			run_id: '2026-09-06-1',
			shard,
			span_name,
			count,
			total_ms,
			unattributed_ms: unattributed_ms ?? ''
		});
	const dir = join(STATE, 'span-rollup');
	mkdirSync(dir, { recursive: true });
	writeFileSync(
		join(dir, '2026-09.csv'),
		[
			COLUMNS.join(','),
			// Shard 0: 6 items, 46.0 s inside them and 6.0 s of overhead - a 52.0 s
			// clock. The four sub-steps sum to 6.6 s, well inside the item time.
			row(0, 'item', 6, 46000, 6000),
			row(0, 'robots', 6, 1800),
			row(0, 'tag', 6, 2400),
			row(0, 'render_prompt', 6, 900),
			row(0, 'parse_reply', 6, 1500),
			// Shard 1: 5 items, 39.0 s inside them and 12.0 s of overhead - a 51.0 s
			// clock, so nearly a quarter of it fell outside every item. That gap
			// between the two shards is what the panel exists to show.
			row(1, 'item', 5, 39000, 12000),
			row(1, 'robots', 5, 1500),
			row(1, 'tag', 5, 2000),
			row(1, 'render_prompt', 5, 800),
			row(1, 'parse_reply', 5, 1300)
		].join('\n') + '\n'
	);
}

writeItemHealthCanary();
writeRuntimeCountersCanary();
writeSpanRollupCanary();
execFileSync(
	process.env.IDHAZH_PYTHON || 'python',
	['-m', 'idhazh.publish_telemetry', '--state', STATE, '--public', join(STATE, 'telemetry')],
	{
		stdio: 'inherit',
		shell: false,
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
