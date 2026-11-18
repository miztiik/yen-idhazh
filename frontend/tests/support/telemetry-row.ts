/** The published telemetry row as the console specs spell it.
 *
 * Each column and what it means is `ItemHealthRow`'s
 * (`backend/idhazh/contracts/item_health.py`); this is the typed copy the specs
 * share. An absent measurement is `null`, and a text cell is empty when nothing
 * was recorded.
 */
export interface TelemetryRow {
	date: string;
	run_id: string;
	item_id: string;
	vertical: string;
	source_id: string;
	stage: string;
	outcome: string;
	code: string;
	source_words: number | null;
	summary_words: number | null;
	source_words_before_cap: number | null;
	fetch_ms: number | null;
	extract_ms: number | null;
	analyze_ms: number | null;
	summarize_ms: number | null;
	prefill_ms: number | null;
	decode_ms: number | null;
	input_tokens: number | null;
	output_tokens: number | null;
	cached_tokens: number | null;
	model_calls: number | null;
	label_kind: string;
	label_prefill_ms: number | null;
	label_decode_ms: number | null;
	label_input_tokens: number | null;
	label_output_tokens: number | null;
	label_cached_tokens: number | null;
	summary_kind: string;
	summary_prefill_ms: number | null;
	summary_decode_ms: number | null;
	summary_input_tokens: number | null;
	summary_output_tokens: number | null;
	summary_cached_tokens: number | null;
	queue_wait_ms: number | null;
	label_ms: number | null;
	summary_ms: number | null;
	visual_plan_ms: number | null;
	visual_plan_ms_is_estimate: string;
	faithfulness_ms: number | null;
	model_wait_ms: number | null;
	item_total_ms: number | null;
	stage_gap_ms: number | null;
	visual_plan_tokens_written: number | null;
	label_prefill_tokens_per_s: number | null;
	label_decode_tokens_per_s: number | null;
	summary_prefill_tokens_per_s: number | null;
	summary_decode_tokens_per_s: number | null;
	cpu_model: string;
	cpu_busy_pct: number | null;
	load_1m: number | null;
}

/** One published telemetry row, spelled in full once.
 *
 * Five specs used to write the whole row out by hand, so every column appended
 * to the projection broke all five at type-check time - on the commit that
 * added the column, in files that change had no reason to open. The default
 * below is the row a reader with no split and no instrument gets: every
 * measurement absent, because an absent cell is what the projection writes when
 * nothing measured (`docs/architecture/publishing/telemetry-series.md`).
 *
 * Override only the cells a test is about. A spread of `Partial<TelemetryRow>`
 * on its own cannot do this job - it widens every field to optional and the
 * target type then refuses the result - so the override is spread over a
 * complete row rather than used as one.
 */
export function telemetryRow(over: Partial<TelemetryRow> = {}): TelemetryRow {
	return {
		date: '2026-08-20',
		run_id: '2026-08-20-1',
		item_id: 'ai-01',
		vertical: 'ai',
		source_id: 'canary',
		stage: 'publish',
		outcome: 'ok',
		code: '',
		source_words: null,
		summary_words: null,
		source_words_before_cap: null,
		fetch_ms: null,
		extract_ms: null,
		analyze_ms: null,
		summarize_ms: null,
		prefill_ms: null,
		decode_ms: null,
		input_tokens: null,
		output_tokens: null,
		cached_tokens: null,
		model_calls: null,
		label_kind: '',
		label_prefill_ms: null,
		label_decode_ms: null,
		label_input_tokens: null,
		label_output_tokens: null,
		label_cached_tokens: null,
		summary_kind: '',
		summary_prefill_ms: null,
		summary_decode_ms: null,
		summary_input_tokens: null,
		summary_output_tokens: null,
		summary_cached_tokens: null,
		queue_wait_ms: null,
		label_ms: null,
		summary_ms: null,
		visual_plan_ms: null,
		visual_plan_ms_is_estimate: '',
		faithfulness_ms: null,
		model_wait_ms: null,
		item_total_ms: null,
		stage_gap_ms: null,
		visual_plan_tokens_written: null,
		label_prefill_tokens_per_s: null,
		label_decode_tokens_per_s: null,
		summary_prefill_tokens_per_s: null,
		summary_decode_tokens_per_s: null,
		cpu_model: '',
		cpu_busy_pct: null,
		load_1m: null,
		...over
	};
}
