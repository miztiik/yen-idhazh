/** Which measured runs differ from their earlier matching token readings? */
import { isDay, SliceRequestError } from './slice-shapes';
import type { Bound } from './slice-query';

export interface TokenDeviationRules {
	historyRuns: number;
	minimumRuns: number;
	multiplier: number;
}

export interface TokenDeviationOptions extends TokenDeviationRules {
	settingsFrom: string | null;
	settingsThrough: string | null;
	changeDays: readonly string[];
}

export const TOKEN_HISTORY_COLUMNS = [
	'date', 'run_id', 'input_tokens', 'output_tokens', 'model_id', 'model_quantisation',
	'n_ctx_configured', 'n_parallel', 'n_threads', 'n_batch',
	'temperature', 'label_budget_tokens', 'summary_budget_tokens', 'run_visual_decision'
] as const;

/** Sample variance is undefined below two readings, regardless of configuration. */
const MIN_SAMPLE_READINGS = 2;

export function checkedTokenDeviationRules(rules: TokenDeviationRules): TokenDeviationRules {
	if (!Number.isSafeInteger(rules.historyRuns) || rules.historyRuns < MIN_SAMPLE_READINGS ||
		!Number.isSafeInteger(rules.minimumRuns) || rules.minimumRuns < MIN_SAMPLE_READINGS ||
		rules.minimumRuns > rules.historyRuns ||
		!Number.isFinite(rules.multiplier) || rules.multiplier <= 0) {
		throw new SliceRequestError('token history needs whole run counts >= 2, minimum <= history, and a positive finite standard-deviation multiplier');
	}
	return rules;
}

export function checkedTokenDeviationOptions(options: TokenDeviationOptions): TokenDeviationOptions {
	checkedTokenDeviationRules(options);
	if ([options.settingsFrom, options.settingsThrough].some((day) => day !== null && !isDay(day)) ||
		options.changeDays.some((day) => !isDay(day)) ||
		new Set(options.changeDays).size !== options.changeDays.length) {
		throw new SliceRequestError('token settings history needs distinct UTC change days and valid comparison bounds');
	}
	return options;
}

/** Only this authored computation can extend a slice; it accepts no caller SQL. */
export function tokenDeviationStatement(
	source: { sql: string; params: Bound[] },
	options: TokenDeviationOptions,
	historyComplete: boolean
): { sql: string; params: Bound[] } {
	checkedTokenDeviationOptions(options);
	const changes = options.changeDays.length
		? `VALUES ${options.changeDays.map(() => '(?::VARCHAR)').join(', ')}`
		: 'SELECT NULL::VARCHAR WHERE FALSE';
	return {
		params: [...source.params, ...options.changeDays, options.historyRuns, options.minimumRuns, options.multiplier,
			options.settingsFrom ?? '', options.settingsThrough ?? '', historyComplete ? 1 : 0],
		sql: `WITH raw AS (${source.sql}),
		changes(date) AS (${changes}),
		controls AS MATERIALIZED (
			SELECT ?::BIGINT AS history_runs, ?::BIGINT AS minimum_runs, ?::DOUBLE AS multiplier,
				?::VARCHAR AS settings_from, ?::VARCHAR AS settings_through, ?::BOOLEAN AS history_complete
		),
		articles AS (
			SELECT date, run_id, TRY_CAST(input_tokens AS DOUBLE) AS input,
				TRY_CAST(output_tokens AS DOUBLE) AS output,
				model_id IS NOT NULL AND model_id <> '' AND model_quantisation IS NOT NULL AND model_quantisation <> ''
				AND n_ctx_configured > 0 AND n_parallel > 0
				AND n_threads > 0 AND n_batch > 0 AND temperature >= 0 AND isfinite(temperature)
				AND label_budget_tokens > 0 AND summary_budget_tokens > 0 AND run_visual_decision IS NOT NULL AS known_setup,
				struct_pack(model_id := model_id, quantisation := model_quantisation,
					context := n_ctx_configured, slots := n_parallel,
					threads := n_threads, batch := n_batch, temperature := temperature,
					label_budget := label_budget_tokens, summary_budget := summary_budget_tokens,
					visual := run_visual_decision) AS setup
			FROM raw
		),
		paired AS (
			SELECT date, run_id, input, output, known_setup, setup,
				input >= 0 AND output >= 0 AND isfinite(input) AND isfinite(output) AS measured
			FROM articles
		),
		runs AS (
			SELECT date, run_id, count(*) AS recorded, count(*) FILTER (WHERE measured) AS measured,
				sum(input) FILTER (WHERE measured) AS total_read,
				sum(output) FILTER (WHERE measured) AS total_written,
				median(input) FILTER (WHERE measured) AS median_read,
				median(output) FILTER (WHERE measured) AS median_written,
				CASE WHEN bool_and(coalesce(known_setup, FALSE)) FILTER (WHERE measured)
					AND count(DISTINCT setup) FILTER (WHERE measured) = 1
					THEN any_value(setup) FILTER (WHERE measured) END AS setup
			FROM paired GROUP BY date, run_id
		),
		tagged AS (
			SELECT runs.*,
				row_number() OVER (ORDER BY date, left(run_id, 10),
					length(ltrim(substr(run_id, 12), '0')), ltrim(substr(run_id, 12), '0'), run_id) AS sequence,
				coalesce((SELECT max(changes.date) FROM changes WHERE changes.date <= runs.date), settings_from) AS epoch,
				CASE WHEN NOT history_complete THEN 'incomplete-history'
					WHEN measured = 0 THEN 'no-reading'
					WHEN settings_from = '' OR settings_through = '' OR runs.date < settings_from OR runs.date > settings_through
						THEN 'settings-unavailable'
					WHEN runs.date IN (SELECT date FROM changes) THEN 'change-day'
					WHEN setup IS NULL THEN 'unknown-setup' END AS reason
			FROM runs CROSS JOIN controls
		),
		previous AS (
			SELECT tagged.*, lag(setup) OVER ordered AS previous_setup,
				lag(epoch) OVER ordered AS previous_epoch, lag(reason) OVER ordered AS previous_reason
			FROM tagged WINDOW ordered AS (ORDER BY sequence)
		),
		segments AS (
			SELECT previous.*, sum(CASE WHEN setup IS DISTINCT FROM previous_setup OR epoch IS DISTINCT FROM previous_epoch
				OR reason IS NOT NULL OR previous_reason IS NOT NULL THEN 1 ELSE 0 END)
				OVER (ORDER BY sequence ROWS UNBOUNDED PRECEDING) AS segment
			FROM previous
		),
		readings AS (
			SELECT date, run_id, sequence, measured, recorded, segment, reason, metric, trace, value
			FROM segments CROSS JOIN LATERAL (VALUES
				('total', 'read', total_read), ('total', 'written', total_written),
				('median', 'read', median_read), ('median', 'written', median_written)
			) AS values(metric, trace, value)
		),
		baselines AS (
			SELECT date, run_id, metric, trace,
				count(*) OVER prior AS prior_count, avg(value) OVER prior AS prior_mean,
				stddev_samp(value) OVER prior AS prior_stddev,
				CAST(sum(measured) OVER prior AS BIGINT) AS prior_measured,
				CAST(sum(recorded) OVER prior AS BIGINT) AS prior_recorded,
				first_value(run_id) OVER prior AS prior_first, last_value(run_id) OVER prior AS prior_last
			FROM readings WHERE reason IS NULL AND isfinite(value)
			WINDOW prior AS (PARTITION BY segment, metric, trace ORDER BY sequence
				ROWS BETWEEN (SELECT history_runs FROM controls) PRECEDING AND 1 PRECEDING)
		),
		assessed AS (
			SELECT readings.date, readings.run_id, readings.sequence, readings.metric, readings.trace,
				readings.value, readings.measured, readings.recorded, prior_count, prior_mean, prior_stddev,
				prior_measured, prior_recorded, prior_first, prior_last, multiplier * prior_stddev AS threshold,
				abs(value - prior_mean) AS distance,
				coalesce(reason, CASE WHEN value IS NULL OR NOT isfinite(value) THEN 'no-reading'
					WHEN coalesce(prior_count, 0) < minimum_runs THEN 'insufficient-history'
					WHEN prior_mean IS NULL OR prior_stddev IS NULL OR NOT isfinite(prior_mean) OR NOT isfinite(prior_stddev)
						THEN 'baseline-unavailable' END) AS reason
			FROM readings LEFT JOIN baselines USING (date, run_id, metric, trace) CROSS JOIN controls
		)
		SELECT date, run_id, metric, trace, value, measured, recorded,
			prior_count, prior_mean, prior_stddev, prior_measured, prior_recorded, prior_first, prior_last,
			distance, threshold, reason,
			CASE WHEN reason IS NULL THEN distance > threshold END AS warning
		FROM assessed ORDER BY sequence, metric, trace`
	};
}
