import type { TelemetryRow } from '../../src/lib/charts/series';

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
		summarize_ms: null,
		prefill_ms: null,
		decode_ms: null,
		input_tokens: null,
		output_tokens: null,
		cached_tokens: null,
		model_calls: null,
		call_1_kind: '',
		call_1_prefill_ms: null,
		call_1_decode_ms: null,
		call_1_input_tokens: null,
		call_1_output_tokens: null,
		call_1_cached_tokens: null,
		...over
	};
}
