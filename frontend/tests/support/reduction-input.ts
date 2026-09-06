/** One deterministic ledger the one-pass build reductions are measured over.
 *
 * Row 2 of `TODO/20260906-constant-cost-reads-plan.md` replaces six repeated
 * reductions with single passes and must move no number on any page. That is
 * two claims and they share one input. The parity half compares what the
 * reductions return against `../fixtures/one-pass-golden.json`, captured from
 * the implementation this row replaced. The counted half doubles the input and
 * reads how the visits grow.
 *
 * Every cell here comes from one seeded sequence, so the same ledger is built
 * on every machine and the golden stays comparable. Nothing reads a committed
 * ledger: a test that walks the archive costs more every published day
 * (Rule #12), and the shapes this row is about are reachable from a fixture.
 */

import type { SummaryBand, TelemetryRow } from '../../src/lib/charts/series';

/** The sizes one arm of the counted-visit oracle is built at.
 *
 * `runs` and `items` double together, which is what turns a run-by-row join
 * into four times the work rather than two.
 */
export interface Sizes {
	runs: number;
	shards: number;
	/** Item-health rows the whole ledger holds, spread evenly across the runs. */
	items: number;
}

/** A seeded sequence, so a value looks varied and reproduces exactly.
 *
 * A plain linear congruential generator: the numbers only have to differ from
 * each other and be the same on the next run.
 */
export function sequence(seed: number): () => number {
	let state = seed >>> 0;
	return () => {
		state = (state * 1_664_525 + 1_013_904_223) >>> 0;
		return state / 4_294_967_296;
	};
}

/** `YYYY-MM-DD`, counting forward from a fixed first day. */
export function dayOf(index: number): string {
	const at = new Date(Date.UTC(2026, 4, 1));
	at.setUTCDate(at.getUTCDate() + index);
	return at.toISOString().slice(0, 10);
}

/** Run ids are `<date>-<n>`, which is the shape `machineCounters` sorts on. */
export function runIdOf(index: number): string {
	return `${dayOf(Math.floor(index / 2))}-${(index % 2) + 1}`;
}

/** One row per shard per run, the shape `state/runtime-counters.csv` holds. */
export function counterRows(sizes: Sizes): Record<string, string>[] {
	const next = sequence(11);
	const rows: Record<string, string>[] = [];
	for (let run = 0; run < sizes.runs; run += 1) {
		for (let shard = 0; shard < sizes.shards; shard += 1) {
			const promptTokens = 40_000 + Math.round(next() * 20_000);
			const readSeconds = 900 + Math.round(next() * 600);
			rows.push({
				date: dayOf(Math.floor(run / 2)),
				run_id: runIdOf(run),
				shard: String(shard),
				shards: String(sizes.shards),
				scraped_at: `${dayOf(Math.floor(run / 2))}T0${shard % 8}:00:00Z`,
				prompt_tokens_total: String(promptTokens),
				prompt_tokens_cached_total: String(Math.round(promptTokens / 8)),
				prompt_seconds_total: String(readSeconds),
				tokens_predicted_total: String(6_000 + Math.round(next() * 2_000)),
				tokens_predicted_seconds_total: String(700 + Math.round(next() * 300)),
				n_decode_total: String(5_000 + Math.round(next() * 1_000)),
				n_tokens_max: String(4_000 + Math.round(next() * 2_000)),
				n_busy_slots_per_decode: '1.0',
				job_seconds: String(2_400 + Math.round(next() * 1_200)),
				cpu_model: shard % 2 === 0 ? 'AMD EPYC 9V45' : 'AMD EPYC 9V74',
				cpu_busy_pct: String(85 + Math.round(next() * 10)),
				peak_rss_bytes: String(12_000_000_000 + Math.round(next() * 1_000_000_000)),
				model_load_ms: String(3_500 + Math.round(next() * 800))
			});
		}
	}
	return rows;
}

/** One row per item, the shape `state/item-health/<YYYY-MM>.csv` holds.
 *
 * Spread evenly over the runs, because the join this row is about is every
 * accepted run against every one of these.
 */
export function healthRows(sizes: Sizes): Record<string, string>[] {
	const next = sequence(29);
	const rows: Record<string, string>[] = [];
	for (let index = 0; index < sizes.items; index += 1) {
		const run = index % sizes.runs;
		const seen = 400 + Math.round(next() * 1_500);
		// Every fourth article is cut, so `sourceCuts` has both kinds to rank.
		const cut = index % 4 === 0;
		rows.push({
			date: dayOf(Math.floor(run / 2)),
			run_id: runIdOf(run),
			shard: String(index % sizes.shards),
			item_id: `item-${index}`,
			url_key: `key-${index}`,
			source_id: `source-${index % 7}`,
			stage: 'summarize',
			outcome: index % 11 === 0 ? 'failed' : 'ok',
			code: index % 11 === 0 ? 'context_exceeded' : '',
			source_words: String(seen),
			source_words_before_cap: cut ? String(seen + 200 + Math.round(next() * 800)) : String(seen),
			summarize_ms: String(60_000 + Math.round(next() * 240_000)),
			prefill_ms: String(30_000 + Math.round(next() * 60_000)),
			decode_ms: String(20_000 + Math.round(next() * 40_000)),
			input_tokens: String(2_000 + Math.round(next() * 3_000)),
			cached_tokens: String(Math.round(next() * 400)),
			output_tokens: String(150 + Math.round(next() * 120))
		});
	}
	return rows;
}

/** One row per scored summary, the shape `state/scores/<YYYY-MM>.csv` holds. */
export function scoreRows(sizes: Sizes): Record<string, string>[] {
	const next = sequence(43);
	const rows: Record<string, string>[] = [];
	for (let index = 0; index < sizes.items; index += 1) {
		const run = index % sizes.runs;
		const words = 300 + Math.round(next() * 3_000);
		rows.push({
			version: '2026-08-29',
			date: dayOf(Math.floor(run / 2)),
			run_id: runIdOf(run),
			url_key: `key-${index}`,
			item_id: `item-${index}`,
			// Two models over the window, so `modelByDate` and the swap divider
			// have a boundary to find.
			model_id: run < sizes.runs / 2 ? 'older-9b' : 'newer-9b',
			pipeline_fingerprint: run < sizes.runs / 2 ? 'aaaa1111' : 'bbbb2222',
			band: index % 9 === 0 ? 'low' : 'high',
			unsupported_numbers: index % 13 === 0 ? '1' : '0',
			hedge_dropped: index % 17 === 0 ? 'True' : 'False',
			truncation_flagged: index % 4 === 0 ? 'True' : 'False',
			extractiveness: String(Math.round(next() * 100) / 100),
			verbatim_run: String(Math.round(next() * 100) / 100),
			summary_word_count: String(40 + Math.round(next() * 160)),
			source_word_count: String(words),
			source_seen_word_count: String(words),
			score_ms: String(1_000 + Math.round(next() * 20_000))
		});
	}
	return rows;
}

/** The published telemetry projection, one row per item per stage. */
export function telemetryRows(days: number, perDay: number): TelemetryRow[] {
	const next = sequence(67);
	const rows: TelemetryRow[] = [];
	for (let day = 0; day < days; day += 1) {
		for (let item = 0; item < perDay; item += 1) {
			const index = day * perDay + item;
			// One row in six never leaves `plan`, so the denominator that excludes
			// them is exercised; one in five fails, at a stage that rotates.
			const stage = index % 6 === 0 ? 'plan' : ['fetch', 'extract', 'summarize'][index % 3];
			const failed = index % 5 === 0 && stage !== 'plan';
			rows.push({
				date: dayOf(day),
				run_id: runIdOf(day * 2),
				item_id: `item-${index}`,
				vertical: `desk-${index % 5}`,
				source_id: `source-${index % 7}`,
				stage,
				outcome: failed ? 'failed' : 'ok',
				code: failed ? ['paywalled', 'http_client_error', ''][index % 3] : '',
				source_words: 400 + Math.round(next() * 1_200),
				summary_words: 60 + Math.round(next() * 90),
				source_words_before_cap: null,
				fetch_ms: 400 + Math.round(next() * 900),
				extract_ms: 200 + Math.round(next() * 500),
				summarize_ms: 60_000 + Math.round(next() * 200_000),
				prefill_ms: 30_000 + Math.round(next() * 40_000),
				decode_ms: 20_000 + Math.round(next() * 30_000),
				input_tokens: 2_000 + Math.round(next() * 2_000),
				output_tokens: 150 + Math.round(next() * 100),
				cached_tokens: Math.round(next() * 300)
			});
		}
	}
	return rows;
}

/** Timings for the histogram, spread over enough doublings to need many bins. */
export function timings(count: number): number[] {
	const next = sequence(83);
	const found: number[] = [];
	for (let index = 0; index < count; index += 1) {
		// A third of a second to about twenty minutes, which is the span the
		// committed summarize clock covers.
		found.push(Math.round(300 * Math.pow(2, next() * 12)));
	}
	return found;
}

/** The band ladder, deliberately NOT in ascending order.
 *
 * The reduction sorts it once instead of once per article, so a ladder already
 * sorted would let a reduction that dropped the sort pass anyway.
 */
export const BANDS: SummaryBand[] = [
	{ min_source_words: 2_000, target_words_min: 110, target_words_max: 200 },
	{ min_source_words: 0, target_words_min: 30, target_words_max: 45 },
	{ min_source_words: 700, target_words_min: 70, target_words_max: 150 },
	{ min_source_words: 3_000, target_words_min: 150, target_words_max: 230 },
	{ min_source_words: 60, target_words_min: 50, target_words_max: 90 }
];
