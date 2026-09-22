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
 *
 * The ledger files `<YYYY>/<MM>/<DD>.csv` since 2026-09-13, so this walks the
 * tree. A `readdir` of `*.csv` over the root now finds nothing, and finding
 * nothing here is silent: every row would keep its own id and the join the
 * console draws would quietly stop matching.
 */
function scoredKeys() {
	const dir = join(STATE, 'scores');
	const found = new Map();
	if (!existsSync(dir)) return found;
	for (const path of dayFiles(dir)) {
		const lines = readFileSync(path, 'utf8').split('\n').filter(Boolean);
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

/** Every `<YYYY>/<MM>/<DD>.csv` under a day-filed store, oldest first. */
function dayFiles(root) {
	const found = [];
	for (const year of readdirSync(root, { withFileTypes: true })) {
		if (!year.isDirectory()) continue;
		for (const month of readdirSync(join(root, year.name), { withFileTypes: true })) {
			if (!month.isDirectory()) continue;
			for (const day of readdirSync(join(root, year.name, month.name))) {
				if (day.endsWith('.csv')) found.push(join(root, year.name, month.name, day));
			}
		}
	}
	return found.sort();
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
	//
	// The machine cells that no committed run has written yet are named and left
	// empty - the stolen share. A plausible figure nobody measured is worse here
	// than a dash: this file is what the console's arithmetic is checked against.
	// The six `os_` ones and the two anonymous-memory readings are filled on four
	// of the days, from the committed readings and from a model that says it is
	// one (`READINGS`).
	//
	// The newest day is not one of those four. It carries the kernel's own
	// account - what the machine has, what was left at the item's worst moment
	// and what was left when it ended - written row by row instead. That is the
	// shape the committed archive has: the three columns landed late, so most
	// days carry none of them. The memory board leads with that account, so a
	// fixture without it could only ever reach the board's empty state.
	//
	// The fault count, the pinning setting and the disk copies are filled on three
	// named days as well, and `memory` below says exactly which and why. They are
	// fixture, like the stage clock: the states the disk-read panel exists to tell
	// apart have never been produced by a committed run, and a panel drawing a
	// state nothing can reach is a panel nobody can tell from a broken one.
	const COLUMNS = [
		'version', 'date', 'run_id', 'item_id', 'url_key', 'canonical_url', 'vertical',
		'source_id', 'stage', 'outcome', 'code', 'http_status', 'source_chars', 'source_words',
		'summary_words', 'detail', 'fetch_ms', 'extract_ms', 'summarize_ms', 'prefill_ms',
		'decode_ms', 'input_tokens', 'output_tokens', 'cached_tokens', 'source_words_before_cap',
		'shard', 'job', 'span_integrity', 'elements_found', 'element_class', 'model_calls',
		'label_kind', 'label_prefill_ms', 'label_decode_ms', 'label_input_tokens',
		'label_output_tokens', 'label_cached_tokens', 'summary_kind', 'summary_prefill_ms',
		'summary_decode_ms', 'summary_input_tokens', 'summary_output_tokens', 'summary_cached_tokens',
		'truncation_cap_tokens', 'selection_score', 'authority_score', 'tier_score', 'feed_weight',
		'feed_reliability', 'lens_bonus', 'recency_bonus', 'carriage_step', 'watchlist_bonus',
		'carried_by', 'watchlist_hit', 'on_front_page', 'tier', 'source_form', 'published_at',
		'time_source', 'item_started_at', 'item_ended_at', 'item_index', 'shard_item_count',
		'queue_wait_ms', 'fetch_connect_ms', 'fetch_ttfb_ms', 'robots_ms', 'retry_count',
		'retry_total_ms', 'label_ms', 'summary_ms', 'visual_plan_ms', 'visual_plan_ms_is_estimate',
		'faithfulness_ms', 'model_wait_ms', 'item_total_ms', 'stage_gap_ms',
		'visual_plan_tokens_written', 'label_cache_pct', 'summary_cache_pct', 'slot_id',
		'kv_tokens_at_start', 'prefix_shared_with_previous', 'label_prefill_tokens_per_s',
		'label_decode_tokens_per_s', 'summary_prefill_tokens_per_s', 'summary_decode_tokens_per_s',
		'label_finish_reason', 'summary_finish_reason', 'recovered', 'cpu_model',
		'cpu_busy_pct', 'cpu_busy_max', 'cpu_busy_min', 'cpu_steal_pct', 'load_1m',
		'llama_rss_bytes', 'llama_rss_anon_bytes', 'llama_rss_peak_bytes', 'llama_major_faults',
		'python_rss_bytes', 'python_rss_anon_bytes', 'model_id',
		'model_quantisation', 'n_ctx_configured', 'n_parallel', 'n_threads', 'n_batch',
		'weights_pinned', 'label_budget_tokens', 'summary_budget_tokens',
		'run_visual_decision',
		'temperature', 'failed_field', 'failed_rule', 'os_mem_available_bytes',
		'os_mem_total_bytes', 'os_mem_cached_bytes', 'os_swap_free_bytes', 'os_swap_total_bytes',
		'os_mem_available_min_bytes'
	];
	/** What the machine itself had, on the days this fixture gives one.
	 *
	 * **The six `os_` cells and the two process readings are real**, taken from
	 * the tightest committed row of 2026-09-19 and of 2026-09-20 - the two days
	 * `state/item-health/` carries a machine reading on, measured 2026-09-21.
	 * Nothing here invents a memory figure the pipeline has never produced.
	 *
	 * **The two anonymous cells are modelled, and that is the honest word for
	 * them.** No committed row carries either: they landed with row #5 and no run
	 * has written a day since, so a four-segment bar is unreachable without a
	 * fixture. The server's is its resident set less the measured weight file,
	 * 5,680,522,464 bytes - the same model the plan's own arithmetic used. The
	 * worker's is 0.92 of its resident set, and that fraction is a fixture:
	 * nothing has measured how much of our python is file-backed. Neither is a
	 * claim about the runner.
	 *
	 * **One day is constructed to disagree.** The modelled remainder is positive
	 * on all 378 committed rows, 0.26 GiB at its smallest, so the one state the
	 * panel must never clamp - the two own-memory readings exceeding what the
	 * kernel says is held - has no real row to render on.
	 *
	 * The newest day is left blank on purpose. The memory ceiling board reads the
	 * newest run's rows, and a fixture that filled them would move that panel
	 * while answering a different question.
	 */
	const READINGS = {
		// Four segments that close, off 2026-09-19.
		[earlier]: {
			os_mem_total_bytes: 16766414848,
			os_mem_available_bytes: 5455843328,
			os_mem_available_min_bytes: 5455843328,
			os_mem_cached_bytes: 5035253760,
			os_swap_total_bytes: 3221221376,
			os_swap_free_bytes: 3179167744,
			llama_rss_bytes: 13723394048,
			llama_rss_anon_bytes: 8042871584,
			python_rss_bytes: 1188237312,
			python_rss_anon_bytes: 1093178327
		},
		// The same machine, with the two own-memory readings put past what the
		// kernel says is held. Its swap is the worst committed row, 657.9 MiB.
		[earliest]: {
			os_mem_total_bytes: 16766414848,
			os_mem_available_bytes: 8000000000,
			os_mem_available_min_bytes: 7900000000,
			os_mem_cached_bytes: 5035253760,
			os_swap_total_bytes: 3221221376,
			os_swap_free_bytes: 2531356672,
			llama_rss_bytes: 13723394048,
			llama_rss_anon_bytes: 8500000000,
			python_rss_bytes: 1188237312,
			python_rss_anon_bytes: 1100000000
		},
		// Two segments and two brackets, off 2026-09-20 - the shape every
		// committed row is in.
		[sourceDay]: {
			os_mem_total_bytes: 16765374464,
			os_mem_available_bytes: 2982404096,
			os_mem_available_min_bytes: 2963472384,
			os_mem_cached_bytes: 2699153408,
			os_swap_total_bytes: 3221221376,
			os_swap_free_bytes: 2816811008,
			llama_rss_bytes: 13546360832,
			python_rss_bytes: 1085865984
		},
		// Ten days back, so the narrowest preset cannot reach it and the widest
		// can. Nothing had been pushed out to disk here, which 32 of the 378
		// committed rows also read.
		[outsideWindow]: {
			os_mem_total_bytes: 16766414848,
			os_mem_available_bytes: 6800000000,
			os_mem_available_min_bytes: 6800000000,
			os_mem_cached_bytes: 5035253760,
			os_swap_total_bytes: 3221221376,
			os_swap_free_bytes: 3221221376,
			llama_rss_bytes: 13723394048,
			python_rss_bytes: 1188237312
		}
	};

	/** One row's reading, with the day's spare memory nudged by item id.
	 *
	 * A panel that draws one bar a day has to pick a row, and a day where every
	 * row reads the same leaves the pick untested. The nudge is in hundreds of
	 * megabytes, always upward, so the item with no nudge keeps the day's real
	 * committed figures and is the one the panel draws.
	 */
	const memoryReading = (rowDate, id) => {
		const reading = READINGS[rowDate];
		if (reading === undefined || id === undefined) return {};
		const nudge = ([...id].reduce((total, letter) => total + letter.charCodeAt(0), 0) % 5) * 1e8;
		return {
			...reading,
			os_mem_available_bytes: reading.os_mem_available_bytes + nudge,
			os_mem_available_min_bytes: reading.os_mem_available_min_bytes + nudge
		};
	};

	// Named cells, so a column added to the row cannot silently shift every
	// number one place to the left.
	//
	// The memory reading is spread in first rather than written on each row, so
	// every builder on this day - published, dropped, refused, article - carries
	// it, and an explicit cell still wins.
	const line = (cells) => {
		const row = { ...memoryReading(cells.date, cells.item_id), ...cells };
		return COLUMNS.map((name) => row[name] ?? '').join(',');
	};
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
	const published = (rowDate, run, id, [fetchMs, extractMs, summarizeMs], model, cut, calls) =>
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
			source_words_before_cap: cut?.[2],
			...extraction(id),
			...perCall(model, calls, cut),
			...clock(rowDate, run, id, [fetchMs, extractMs, summarizeMs], model, calls)
		});

	/** Where each shard is up to, in whole seconds from its run's own start.
	 *
	 * A shard works its items one after another, so an item begins when the item
	 * before it on that shard ended. Keying the seat by run AND shard is what makes
	 * two bars legitimately overlap on the clock - the state the timeline's `shard`
	 * column exists to tell apart from a contradiction - and it is what gives the
	 * chart a staircase to draw instead of a column of bars all starting at zero.
	 */
	const seats = new Map();

	/** One item's place on its run's clock: which shard, which seat, and when.
	 *
	 * Fixture, like every other millisecond of the stage clock here. The run this
	 * canary was taken from predates the item clock, so there is no start time to
	 * read off it - and a chart that places items on a clock is a chart no test can
	 * reach without one.
	 *
	 * The two shards start three seconds apart, and each one leaves a two-second
	 * gap between items: that gap is the overhead between items the span rollup
	 * calls `unattributed_ms`, so the two panels on this page tell the same story
	 * about the same kind of time.
	 */
	const place = (rowDate, run, id, totalMs, waitMs) => {
		const spread = [...id].reduce((total, letter) => total + letter.charCodeAt(0), 0);
		const shard = spread % 2;
		const key = `${rowDate}-${run}-${shard}`;
		const seat = seats.get(key) ?? { at: shard * 3, index: 0 };
		// Second precision, because the census records a timestamp to the second and
		// a fixture that carried more would be inventing a clock the pipeline has not
		// got.
		const spent = Math.ceil((waitMs + totalMs) / 1000);
		seats.set(key, { at: seat.at + spent + 2, index: seat.index + 1 });
		const stamp = (seconds) =>
			new Date(Date.parse(`${rowDate}T06:00:00Z`) + seconds * 1000).toISOString().slice(0, 19) + 'Z';
		return {
			shard,
			item_index: seat.index,
			item_started_at: stamp(seat.at),
			item_ended_at: stamp(seat.at + spent)
		};
	};

	/** Whether the machine took the model's memory back, on three named days.
	 *
	 * **Fixture, and a set of states no committed run has produced.** No row of
	 * the committed item ledger carries `llama_major_faults` or
	 * `weights_pinned` at all, and the rows carrying `os_mem_cached_bytes` sit
	 * on two days - measured 2026-09-21 over 13,946 rows across 28 days, and it
	 * is the property rather than the count that matters, because the ledger
	 * grows every run. So every state the disk-read panel exists to tell apart
	 * is unreachable from the archive, and three of them have to sit on a
	 * fixture or no test can see them.
	 *
	 * One day a state, because a day is one tile:
	 *
	 * - The newest day waited on the disk AND its disk copies collapsed by about
	 *   a third over the day. That is the machine reclaiming, and it is the one
	 *   the panel exists to catch.
	 * - The day before waited on the disk while its disk copies never moved.
	 *   Same tile on the upper strip, a different one underneath, and the two
	 *   have different fixes - which is the whole reason the second strip is
	 *   drawn beside the first rather than instead of it.
	 * - The day forty days back counted and found nothing, and it is the one day
	 *   here whose memory was held down. A quiet strip on a run that pinned its
	 *   weights is the expected reading; a quiet strip on a run that did not is
	 *   luck, and the panel must be able to say which it is looking at.
	 *
	 * Every other day leaves all three cells empty, which is what every run
	 * before the columns wrote and which must never draw as a quiet day.
	 *
	 * The count climbs with the seat so that the day's own arithmetic is
	 * checkable from this file. The FIRST article of a shard carries a far larger
	 * one - `starting` - because a server that has just started really does read
	 * its whole weight file in, and that is the read the panel leaves out. Left
	 * at zero it would make the exclusion untestable: a fold that quietly counted
	 * the first article would get the same total as one that did not.
	 *
	 * Both pinning settings are real: `config/models/qwen3.5-9b-q4km.json` sets
	 * `-lm` and the other four leave it out, so neither value
	 * here is a setting the repository cannot produce.
	 */
	const MEMORY_DAYS = new Map([
		[
			date,
			{ waits: 4100, starting: 148000, copies: 10_400_000_000, step: 1_900_000_000, pinned: 'False' }
		],
		[earlier, { waits: 1700, starting: 148000, copies: 10_200_000_000, step: 0, pinned: 'False' }],
		[longAgo, { waits: 0, starting: 148000, copies: 11_000_000_000, step: 0, pinned: 'True' }]
	]);

	const memory = (rowDate, seat) => {
		const day = MEMORY_DAYS.get(rowDate);
		if (!day) return {};
		return {
			llama_major_faults: seat === 0 ? day.starting : day.waits * seat,
			os_mem_cached_bytes: day.copies - day.step * seat,
			weights_pinned: day.pinned
		};
	};

	/** The item's own clock, the per-call rates, and what it ran on.
	 *
	 * **Fixture, and derived from the milliseconds already on the row.** The run
	 * this canary was taken from predates the item clock, so `item_total_ms` and
	 * `stage_gap_ms` cannot be read off it - but a panel that draws where an
	 * item's time went is a panel no test can reach without them.
	 *
	 * The contract refuses a row whose gap is not what the named stages left
	 * over, so the total is built from the stages rather than the other way
	 * round: fetch, extract, summarize and faithfulness, plus a remainder that
	 * varies by item id so the top band is not a flat ribbon across the chart.
	 *
	 * The six derived cells are `CallCost`'s arithmetic in JavaScript, to two
	 * decimals: a share of the prompt that was cached, and two rates. A prefill
	 * rate is over the tokens the server really evaluated - `input_tokens` minus
	 * `cached_tokens` - because over the whole prompt a warm slot reads as a fast
	 * server and the cell says the same thing as `cache_pct`. Those milliseconds
	 * are the server's real numbers, so they are used for the rates and NOT for the bands: this
	 * canary's stage clock is a fixture and its model clock is a measurement, so
	 * `prefill_ms + decode_ms` is far larger than `summarize_ms` on the rows that
	 * carry both. The bands split `summarize_ms` in the calls' own proportion
	 * instead, which keeps the stack adding up to the item rather than drawing a
	 * band tens of seconds below the axis.
	 *
	 * `cpu_model` is the machine record's fallback and not its instrument: the
	 * Hardware page reads the processor off `state/host-fingerprint/` and only
	 * reaches for this cell on a shard that record never reached, so a row here
	 * may name a different machine than the record without the page saying two
	 * things at once.
	 *
	 * The three memory cells and `n_ctx_configured` are fixture as well, and they
	 * are what the Hardware page folds per shard: a high-water for the server,
	 * one for the Python process, one for the whole cgroup, and the window the
	 * prompt had to fit. Each one ends in the item id's own spread, so a reader
	 * checking the page against this file can see which row a figure came from.
	 * `n_ctx_configured` is the committed `--ctx-size`, because a fixture
	 * that disagreed with the config would draw a context share no run had.
	 *
	 * `kernelRecorded` is what puts the newest day's kernel account on the row
	 * and leaves the refused row without one. See the comment beside it.
	 *
	 * `gapMs` overrides the unclaimed remainder. Only the refused row below sets
	 * it, and only to a negative value - see that row for why. The total is built
	 * from the stages plus the gap either way, so the contract's rule that the
	 * gap is what the named stages left over holds whichever branch runs.
	 */
	const clock = (rowDate, run, id, [fetchMs, extractMs, summarizeMs], model, calls, gapMs) => {
		const spread = [...id].reduce((total, letter) => total + letter.charCodeAt(0), 0);
		const faithfulness = 20 + (spread % 40);
		const gap = gapMs ?? 60 + (spread % 120);
		const rate = (tokens, ms) => (ms > 0 ? Math.round(((1000 * tokens) / ms) * 100) / 100 : '');
		const share = (cached, prompt) =>
			prompt > 0 ? Math.round(((100 * cached) / prompt) * 100) / 100 : '';
		const [label, summary] = calls ?? [];
		const wire = (calls ?? []).reduce((total, call) => total + call[1] + call[2], 0);
		const labelMs = label && wire > 0 ? Math.round((summarizeMs * (label[1] + label[2])) / wire) : '';
		const summaryMs = summary ? summarizeMs - labelMs : '';
		const planMs = summary ? Math.round(summaryMs * 0.18) : '';
		const totalMs = fetchMs + extractMs + summarizeMs + faithfulness + gap;
		if (totalMs < 0) {
			throw new Error(
				`canary item ${id} would cost ${totalMs} ms, and an item cannot cost less than nothing`
			);
		}
		const waitMs = spread % 900;
		const seat = place(rowDate, run, id, totalMs, waitMs);
		// The one shard the machine record reached with no processor on it. Its item
		// rows name none either, so the fallback cannot quietly fill the cell in and
		// the board has a row that says "Not recorded".
		const unrecorded = `${rowDate}-${run}-${seat.shard}` === `${date}-2-1`;
		// The kernel's own account, on the newest day and on every row of it but
		// the refused one. `gapMs` is set by the refused builder and by nothing
		// else, so it is what marks the row this fixture uses to carry states no
		// committed day holds - here, an item drawn with no kernel reading, which
		// is the memory board's hatched mark and its printed skip count.
		const kernelRecorded = rowDate === date && gapMs === undefined;
		// A day `READINGS` already answers is left alone below. An empty cell beats
		// the reading spread in by `line`, so writing one here would draw a day that
		// has a reading as a day that has none.
		const dayHasReading = READINGS[rowDate] !== undefined;
		// Inside the range 378 committed rows carrying the floor actually span,
		// measured 2026-09-21: 2.96 to 9.48 GB left, on a machine reporting
		// 16,766,410,752 B. The server's end-of-item figure sits 50 to 70 MB under
		// its own high-water mark, which is the gap those rows show.
		//
		// The item ids on a day are consecutive, so `spread` is too - and a floor
		// stepping one unit an item would draw four marks a reader cannot tell
		// apart. 173 is coprime with 1000, so it scatters those consecutive ids
		// across the whole range in steps of about a gigabyte.
		const scatter = (spread * 173) % 1000;
		const floor = 3200000000 + scatter * 6000000;
		const peak = 12000000000 + (spread % 1000) * 1000000;
		return {
			...seat,
			queue_wait_ms: waitMs,
			faithfulness_ms: faithfulness,
			model_wait_ms: Math.round(summarizeMs * 0.02),
			item_total_ms: totalMs,
			stage_gap_ms: gap,
			label_ms: labelMs,
			summary_ms: summaryMs,
			visual_plan_ms: planMs,
			visual_plan_ms_is_estimate: summary ? 'True' : '',
			visual_plan_tokens_written: summary ? Math.round(summary[4] * 0.2) : '',
			label_cache_pct: label ? share(label[5], label[3]) : '',
			summary_cache_pct: summary ? share(summary[5], summary[3]) : '',
			label_prefill_tokens_per_s: label ? rate(label[3] - label[5], label[1]) : '',
			label_decode_tokens_per_s: label ? rate(label[4], label[2]) : '',
			summary_prefill_tokens_per_s: summary ? rate(summary[3] - summary[5], summary[1]) : '',
			summary_decode_tokens_per_s: summary ? rate(summary[4], summary[2]) : '',
			cpu_model: unrecorded ? '' : 'AMD EPYC 7763 64-Core Processor',
			cpu_busy_pct: Math.round((60 + (spread % 3500) / 100) * 100) / 100,
			load_1m: Math.round((2 + (spread % 600) / 100) * 100) / 100,
			llama_rss_peak_bytes: peak,
			python_rss_bytes: 1700000000 + (spread % 1000) * 100000,
			...(dayHasReading
				? {}
				: {
						llama_rss_bytes: peak - 50000000 - (spread % 200) * 100000,
						os_mem_total_bytes: kernelRecorded ? 16766410752 : '',
						os_mem_available_min_bytes: kernelRecorded ? floor : '',
						os_mem_available_bytes: kernelRecorded ? floor + (scatter % 300) * 1000000 : ''
					}),
			n_ctx_configured: 65536,
			// Last, so the three disk-read cells beat `READINGS` on the one day both
			// name. `READINGS` sets the copies flat across that day, and this day is
			// here to say the copies did not move - the same fact, written by the
			// side whose panel reads it.
			...memory(rowDate, seat.item_index)
		};
	};

	/** The two calls one item took, as the ledger's flat cells.
	 *
	 * **A fixture split of a real total, and the only fixture part of a published
	 * row's cost.** The run this canary was taken from made one call an item, so
	 * the state the split exists for - a first call that reads the article cold
	 * and a second that replays it and is answered from the cache - has never been
	 * produced and cannot be read off a run. The two calls are written to add up
	 * to the total beside them, cell by cell, because the contract refuses a row
	 * whose total is not the sum of its calls and a canary that broke that rule
	 * would fail at publish rather than say anything.
	 */
	const perCall = (model, calls, cut) => {
		if (!calls) return {};
		const cells = { model_calls: calls.length };
		const slots = ['label', 'summary'];
		const names = ['prefill_ms', 'decode_ms', 'input_tokens', 'output_tokens', 'cached_tokens'];
		calls.forEach(([kind, ...numbers], index) => {
			cells[`${slots[index]}_kind`] = kind;
			names.forEach((name, at) => {
				cells[`${slots[index]}_${name}`] = numbers[at];
			});
			cells[`${slots[index]}_finish_reason`] = stoppedBecause(index, cut);
		});
		names.forEach((name, at) => {
			const summed = calls.reduce((total, call) => total + call[1 + at], 0);
			if (summed !== model[at]) {
				throw new Error(`canary calls sum to ${summed} ${name}, beside a total of ${model[at]}`);
			}
		});
		return cells;
	};

	/** Why one call's decode stopped.
	 *
	 * **Fixture, and the one state no committed day has ever produced.** Every
	 * finish reason in the archive says the model finished on its own - measured
	 * 2026-09-21, 2,624 of 2,624 calls. So the state the Hardware page's context
	 * panel exists to catch, a reply that stopped because it ran out of room, is
	 * unreachable from any real ledger, and a panel drawing a state nothing can
	 * reach is a panel nobody can tell from a broken one.
	 *
	 * It lands on the LAST call of the one article the truncation cap already
	 * trimmed, which is the only coherent place for it: an article too long to
	 * send whole is the article whose reply runs out of room first.
	 */
	const stoppedBecause = (index, cut) => (index === 1 && cut ? 'length' : 'stop');

	/** What the candidate pass got out of one article, as a published row holds it.
	 *
	 * Fixture, not measurement: this canary never runs the extractor, and the
	 * article text a span was cut from is not in the ledger to re-read. The split
	 * is by item id so it is stable across builds and so each of the three classes
	 * is on the day - a fixture that only ever wrote one class is a panel two
	 * thirds of which no test can reach.
	 */
	const extraction = (id) => {
		const bucket = [...id].reduce((total, letter) => total + letter.charCodeAt(0), 0) % 4;
		if (bucket === 0) return { span_integrity: 'True', elements_found: 0, element_class: 'narrative' };
		if (bucket === 1)
			return { span_integrity: 'True', elements_found: 2, element_class: 'unclassified' };
		return { span_integrity: 'True', elements_found: 5, element_class: 'chartable' };
	};

	/** An item the extractor threw away. Not a failure: dropping a page that is
	 * not an article is the job, so the row is `ok` and it is not on the
	 * failed-item list. It fetched and it parsed, so those two stages have a
	 * number. The model never saw it, so summarize has none.
	 *
	 * It carries an item clock all the same, because it really did occupy a shard
	 * for as long as it took. That is the state the run timeline draws as a short
	 * bar with two steps on it and the rest unaccounted - the case the contract
	 * names when it says an absent step is not a zero. */
	const dropped = (rowDate, run, id, code, chars, words, fetchMs, extractMs) =>
		line({
			...item(rowDate, run, id),
			stage: 'extract',
			outcome: 'ok',
			code,
			source_chars: chars,
			source_words: words,
			fetch_ms: fetchMs,
			extract_ms: extractMs,
			...place(rowDate, run, id, fetchMs + extractMs + 40, 0),
			queue_wait_ms: 0,
			item_total_ms: fetchMs + extractMs + 40,
			stage_gap_ms: 40
		});

	/** An item the model read whole and then refused to answer for.
	 *
	 * **The five cost cells on a failed row are the state this row exists for.**
	 * A refused reply costs the server the whole prompt, and until 2026-09-13 the
	 * failure path threw that cost away - so the item ledger under-counted a
	 * shard's reading while llama-server counted it. That is the one defect two
	 * independent clocks catch and one clock cannot, and a fixture where every
	 * row reads at the same rate could never put the panel in its red state.
	 *
	 * So this row reads deliberately fast: 1,600 tokens in 64 seconds, or 25.00 a
	 * second, against about 11 on every other row of the day. That is inside the
	 * 9.80 to 42.58 a second one recorded run measured across its own shards, so
	 * it is a rate the fleet really runs at, and it is near enough the rest that
	 * the throughput axis still ticks without falling back to zero. Its shard
	 * sits 1.1 percent from the server WITH it and 52 percent out without it,
	 * which is what lets a test blank five cells and watch the panel turn.
	 *
	 * Its three stage numbers are this day's own medians, so adding it moves
	 * none of them.
	 *
	 * **Its unclaimed time is below zero, and no committed day holds that.** The
	 * ledger's `stage_gap_ms` is signed on purpose: under zero says the named
	 * steps claim more time than the item took, which is two clocks disagreeing
	 * rather than an item that cost nothing. Nothing could draw that state until
	 * a fixture carried it, and the failure path is where it would really come
	 * from - a refused reply costs the server the whole prompt, and the item
	 * ledger and the server have disagreed about that cost before. 852 ms is a
	 * fixture value chosen to stay inside this row's 982 ms of named stages, so
	 * the item still costs more than nothing, and to be large enough that the
	 * shard total it lands in stays under zero rather than being cancelled by the
	 * two positive rows beside it.
	 */
	const UNCLAIMED_BELOW_ZERO_MS = -852;

	const refused = (rowDate, run, id, [fetchMs, extractMs, summarizeMs], model) =>
		line({
			...item(rowDate, run, id),
			stage: 'summarize',
			outcome: 'failed',
			code: 'model_refused',
			source_chars: 9400,
			source_words: 1410,
			fetch_ms: fetchMs,
			extract_ms: extractMs,
			summarize_ms: summarizeMs,
			prefill_ms: model[0],
			decode_ms: model[1],
			input_tokens: model[2],
			output_tokens: model[3],
			cached_tokens: model[4],
			...extraction(id),
			...clock(
				rowDate,
				run,
				id,
				[fetchMs, extractMs, summarizeMs],
				model,
				undefined,
				UNCLAIMED_BELOW_ZERO_MS
			)
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
			published(
				rowDate,
				run,
				// Two digits, because an item id ends in a number the pipeline minted
				// and `ItemId` refuses a single digit. The run timeline validates every
				// row it publishes through that contract, so a loose fixture id is a
				// publish failure rather than a cosmetic one.
				`tail-${run}-${String(index).padStart(2, '0')}`,
				[120, 20, summarizeMs],
				['', '', '', '', '']
			)
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
		// An earlier day's item whose cost is split by call, so the projection's
		// per-call cells reach a page at all. Its totals are the same measured numbers
		// the other rows carry; only the split beside them is a fixture. The two
		// cached_tokens are 0 and 900 - a first call that read its prompt cold and a
		// second that was answered from the cache, which one folded cell cannot say.
		published(earlier, 1, 'ai-03', [260, 35, 780], [63586, 50753, 1608, 270, 900], undefined, [
			['label', 45000, 8000, 708, 60, 0],
			['summarize_and_plan', 18586, 42753, 900, 210, 900]
		]),
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
		//
		// It carries the newest run's per-call split as well, and that is what puts
		// a fully accounted bar on the run timeline: without a split, a row's whole
		// model call falls into the residual, and a panel demonstrated on nothing but
		// hollow bars is a panel nobody can tell from a broken one. The two calls add
		// up to the folded totals beside them cell by cell, which the contract
		// requires and `perCall` re-checks.
		published(
			date,
			2,
			'ai-04',
			[300, 40, 4200],
			[82146, 33203, 1337, 189, 383],
			[12800, 1923, 2612],
			[
				['label', 20000, 8000, 437, 40, 0],
				['summarize_and_plan', 62146, 25203, 900, 149, 383]
			]
		),
		// A whole page parsed, then thrown away for boilerplate. It makes the
		// newest day a partly timed one for summarize: five items of six. Its
		// fetch and extract are that day's own medians, so neither median moves
		// and the sixth item only widens the denominator.
		dropped(date, 2, 'ai-05', 'boilerplate', 1180, 174, 200, 30),
		// The model read this one whole and refused to answer. It shares shard 0 of
		// the newest run with ai-03, which is what gives the two clocks panel a
		// shard whose answer changes when one row's cost goes missing. It is also
		// the only failed row this fixture writes, so the failed-item list, the
		// failure code column and one stage's failure count draw something rather
		// than their empty states.
		refused(date, 2, 'ai-09', [200, 30, 700], [64000, 10300, 1700, 60, 100]),
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
	// These rows are dated a month before the rest, so their own day files sit a
	// month behind the others - and the month mirror the publisher folds from them
	// is a file only the widest preset reaches. A browser that widens the window
	// fetches it, and `console-telemetry-heal.spec.ts` fails that fetch to prove a
	// retry heals it.
	const longAgoRows = [
		...tailRows(longAgo, 1, [520, 640, 700, 810, 1100, 4300]),
		...tailRows(longAgo, 2, [560, 690, 760, 880, 1250, 4900])
	];
	// The ledger files one CSV a day (`docs/concepts/partitions.md`), so each row
	// goes where its own date cell sends it. The index is read off `COLUMNS` rather
	// than written down, and only `version` precedes it - a schema date, which
	// carries no comma.
	const dateAt = COLUMNS.indexOf('date');
	const byDay = new Map();
	for (const row of [...currentRows, ...longAgoRows]) {
		const day = row.split(',')[dateAt];
		const held = byDay.get(day);
		if (held === undefined) byDay.set(day, [row]);
		else held.push(row);
	}
	for (const [day, dayRows] of byDay) {
		const target = join(dir, day.slice(0, 4), day.slice(5, 7), `${day.slice(8, 10)}.csv`);
		mkdirSync(join(dir, day.slice(0, 4), day.slice(5, 7)), { recursive: true });
		writeFileSync(target, [COLUMNS.join(','), ...dayRows].join('\n') + '\n');
	}
}

/** One traced run's span rollup, so the console's sub-step readout has a run to
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

/** The machines the canary's jobs drew, so the machine panels have cards to draw.
 *
 * `build_canary_day.py` fabricates a day rather than running the pipeline, so
 * nothing probes a processor and the panels would only ever show their empty
 * state - which is the state that needs the least proving.
 *
 * **The rows are chosen for the two things a browser cannot check any other
 * way.** One machine reports none of the watched AVX-512 entries and one
 * reports every watched flag, so the absent chips have to be drawn rather than
 * omitted; and one probe used a buffer smaller than that machine's L3, so the
 * reading has to say it measured cache rather than memory.
 *
 * **This file is also the machine half of the Hardware page**, and the four
 * cells after `measured_at` are the only place the server's own counters and
 * the job clock reach a screen. Every `work` row's `server_prompt_tokens` over
 * its `server_prompt_seconds` lands 1.0 to 1.1 percent from the same shard's
 * rate in the item ledger, inside the 5 percent the two clocks panel allows.
 * Equal figures would pass a check that had never run, so the gap is put there
 * on purpose and every shard carries one.
 *
 * Three states nothing else can reach are written here as well. Shard 1 of the
 * newest run carries the server's counters and neither clock, so the board has
 * a dash to rank last. The two runs forty days back carry both clocks and no
 * server counters, so the two clocks panel has a run it compared nothing on.
 * And the day two days back keeps an empty file, so a quiet day is not an
 * incident.
 */
function writeHostFingerprintCanary() {
	const COLUMNS = [
		'version', 'date', 'run_id', 'job', 'shard', 'fingerprint', 'cpu_model', 'cpu_vendor',
		'cpu_family', 'cpu_model_number', 'cpu_stepping', 'microcode', 'cores', 'threads',
		'l3_cache_bytes', 'mhz_max', 'mhz_at_probe', 'flags', 'boot_seconds', 'memcpy_gib_s',
		'memcpy_probe_mib', 'vm_size', 'vm_location', 'vm_zone', 'vm_fault_domain', 'runner_name',
		'measured_at', 'model_load_ms', 'job_seconds', 'server_prompt_tokens',
		'server_prompt_seconds'
	];
	const year = newestDirectory(ROOT);
	const month = newestDirectory(join(ROOT, year));
	const day = newestDirectory(join(ROOT, year, month));
	const date = `${year}-${month}-${day}`;
	const back = (days) => {
		const at = new Date(`${date}T00:00:00Z`);
		at.setUTCDate(at.getUTCDate() - days);
		return at.toISOString().slice(0, 10);
	};
	// Outside 7, 14 and 30 days, inside 90 - the same day the item ledger puts
	// its two tail runs on.
	const longAgo = back(40);

	// The EPYC reports none of the watched AVX-512 entries, which is what the
	// fleet's most common machine really does.
	const EPYC = {
		fingerprint: '3a7f0b1c2d4e5f60',
		cpu_model: 'AMD EPYC 7763 64-Core Processor',
		cpu_vendor: 'AuthenticAMD',
		cpu_family: 25, cpu_model_number: 1, cpu_stepping: 1, microcode: '0xa0011d3',
		cores: 2, threads: 4, l3_cache_bytes: 33554432,
		flags: 'avx2 f16c fma sse4_2',
		memcpy_gib_s: 12.4, memcpy_probe_mib: 512,
		vm_size: 'Standard_D4ads_v5', vm_location: 'eastus', vm_zone: '1', vm_fault_domain: '0'
	};
	// Every watched flag, and a probe buffer only 1.97 times its own L3 - the
	// shape nine of the committed rows carry, and under the margin that proves
	// the copy left the cache. So this card has to withhold its copy speed.
	const XEON = {
		fingerprint: 'c81d9e0a1b2c3d4e',
		cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C',
		cpu_vendor: 'GenuineIntel',
		cpu_family: 6, cpu_model_number: 207, cpu_stepping: 2, microcode: '0x21000283',
		cores: 2, threads: 4, l3_cache_bytes: 272629760,
		flags: [
			'amx_bf16', 'amx_int8', 'amx_tile', 'avx2', 'avx512_bf16', 'avx512_fp16',
			'avx512_vnni', 'avx512f', 'avx_vnni', 'f16c', 'fma', 'sse4_2'
		].join(' '),
		memcpy_gib_s: 9.8, memcpy_probe_mib: 512,
		vm_size: 'Standard_D4ls_v5', vm_location: 'westus2', vm_zone: '2', vm_fault_domain: '1'
	};

	const line = (cells) => COLUMNS.map((name) => cells[name] ?? '').join(',');
	const probe = (rowDate, run, job, index, machine, clocks) =>
		line({
			version: '2026-09-17',
			date: rowDate,
			run_id: `${rowDate}-${run}`,
			job,
			shard: index,
			mhz_max: 2450, mhz_at_probe: 2445,
			boot_seconds: 410.5,
			runner_name: `runner-${job}-${index}`,
			measured_at: `${rowDate}T2${run}:0${index}:00Z`,
			...machine,
			...clocks
		});

	/** The half a job files after the work, with no probe behind it.
	 *
	 * A job writes its record in two halves at one key - the probe before the
	 * work, the clocks and the server's counters after it - so a shard whose
	 * probe never landed carries the clocks and no machine at all.
	 */
	const clocksOnly = (rowDate, run, job, index, clocks) =>
		line({
			version: '2026-09-17',
			date: rowDate,
			run_id: `${rowDate}-${run}`,
			job,
			shard: index,
			...clocks
		});

	const rows = [
		// The newest run: three jobs and two machines.
		probe(date, 2, 'plan', 0, EPYC),
		probe(date, 2, 'work', 0, XEON, {
			model_load_ms: 2470.828, job_seconds: 900,
			server_prompt_tokens: 1700, server_prompt_seconds: 73.72
		}),
		// Absence drawn as absence. This shard carries the server's two counters and
		// nothing else - no clock, no weights load, no processor - exactly as every
		// row written before those columns landed. The board prints a dash for its
		// job, says "Not recorded" for its machine and ranks it last, rather than
		// reading a blank clock as a fast one.
		clocksOnly(date, 2, 'work', 1, {
			server_prompt_tokens: 962, server_prompt_seconds: 83.73
		}),
		probe(date, 2, 'assemble', 0, EPYC),
		// Older runs inside the window, so the fleet count has more than one kind
		// and a denominator. Far below the drawing threshold on purpose: that is
		// the state the list-and-a-sentence exists for.
		probe(date, 1, 'plan', 0, EPYC),
		probe(date, 1, 'work', 0, EPYC, {
			model_load_ms: 2309.44, job_seconds: 812,
			server_prompt_tokens: 950, server_prompt_seconds: 80.65
		}),
		probe(date, 1, 'work', 1, EPYC, {
			model_load_ms: 2298.17, job_seconds: 795,
			server_prompt_tokens: 76, server_prompt_seconds: 7.29
		}),
		probe(back(1), 1, 'plan', 0, XEON),
		probe(back(1), 1, 'work', 0, XEON, {
			model_load_ms: 2512.06, job_seconds: 868,
			server_prompt_tokens: 1300, server_prompt_seconds: 117.74
		}),
		probe(back(1), 1, 'work', 1, XEON, {
			model_load_ms: 2498.33, job_seconds: 851,
			server_prompt_tokens: 860, server_prompt_seconds: 78.18
		}),
		probe(back(1), 1, 'assemble', 0, EPYC),
		// Forty days back, on the day the item ledger puts its widest-preset runs.
		// They carry a job clock and a weights load and no server counters at all,
		// which is the state every run before the server counters landed is in: the
		// board draws them and the two clocks panel says it compared nothing.
		probe(longAgo, 1, 'work', 0, EPYC, { model_load_ms: 2290.5, job_seconds: 780 }),
		probe(longAgo, 1, 'work', 1, EPYC, { model_load_ms: 2284.9, job_seconds: 774 }),
		probe(longAgo, 2, 'work', 0, XEON, { model_load_ms: 2602.7, job_seconds: 836 }),
		probe(longAgo, 2, 'work', 1, XEON, { model_load_ms: 2588.1, job_seconds: 829 })
	];

	// A day tree, the shape a bounded window reads.
	const byDay = new Map();
	for (const row of rows) {
		const rowDate = row.split(',')[1];
		const held = byDay.get(rowDate);
		if (held === undefined) byDay.set(rowDate, [row]);
		else held.push(row);
	}
	// A day the record opened a file for and kept no row of, on a day that
	// published nothing. It is the control for the loss state: the page may say
	// a day lost its machine record only where that day published articles, and
	// a quiet day with an empty file must not read as an incident.
	if (!byDay.has(back(2))) byDay.set(back(2), []);
	for (const [rowDate, dayRows] of byDay) {
		const at = join(STATE, 'host-fingerprint', rowDate.slice(0, 4), rowDate.slice(5, 7));
		mkdirSync(at, { recursive: true });
		writeFileSync(
			join(at, `${rowDate.slice(8, 10)}.csv`),
			[COLUMNS.join(','), ...dayRows].join('\n') + '\n'
		);
	}
}

writeItemHealthCanary();
writeSpanRollupCanary();
writeHostFingerprintCanary();
execFileSync(
	process.env.IDHAZH_PYTHON || 'python',
	['-m', 'idhazh.telemetry.publish.public_telemetry', '--state', STATE, '--public', join(STATE, 'telemetry')],
	{
		stdio: 'inherit',
		shell: false,
		cwd: resolve(process.cwd(), '..'),
		env: { ...process.env, PYTHONPATH: resolve(process.cwd(), '..', 'backend') }
	}
);

// The payloads the console fetches, written here and not in `build_canary_day.py`
// because every source they read is written above: the item-health rows, the
// counters, the span rollup and the telemetry projection all land in this file.
// A band derived before them names one month where the telemetry holds two, and
// the console would then never ask for the older shard the widest-window spec
// fetches.
execFileSync(
	process.env.IDHAZH_PYTHON || 'python',
	[
		'backend/utilities/build_canary_day.py',
		'--console-payloads-only',
		'--out',
		ROOT,
		'--state',
		STATE
	],
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
