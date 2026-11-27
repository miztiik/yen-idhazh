/** Which packed judge readings belong to the window and to its selected digest? */
import type { PanelQuery } from './window';

export const judgeHistoryQuery = {
	name: 'judgeHistoryQuery',
	ledger: 'threshold-history',
	columns: [
		'date', 'run_id', 'attempt', 'pairs_drawn', 'pairs_returned',
		'judge_model',
		'sample_tp', 'sample_fp', 'sample_fn', 'sample_tn', 'score_psi',
		'canary_answers', 'canary_expectations', 'canary_kappa', 'canary_kappa_pairs', 'config_versions'
	],
	span: 'window'
} as const satisfies PanelQuery;

export const judgeDayQuery = {
	name: 'judgeDayQuery',
	ledger: 'threshold-history',
	columns: [
		'date', 'run_id', 'attempt', 'pairs_drawn', 'pairs_returned',
		'runners_reported', 'runners_expected', 'pairs_dealt', 'pairs_valid', 'pairs_agreed',
		'disagreement_rate', 'pairs_refused', 'pairs_unreadable', 'pairs_abandoned', 'unclear_rate',
		'slice_outcomes', 'sample_status', 'evaluated_cutoff',
		'sample_tp', 'sample_fp', 'sample_fn', 'sample_tn', 'sample_precision', 'sample_recall',
		'upper_threshold_before', 'upper_cutoff_false_match_share', 'upper_cutoff_sample_size',
		'upper_cutoff_brier_score', 'cutoff_brier_score',
		'score_drift_baseline', 'score_drift_status', 'score_psi', 'score_wasserstein_distance', 'score_ks_distance',
		'judge_probability_evidence', 'judge_probability_status', 'judge_probability_brier_score',
		'judge_probability_baseline_brier_score', 'judge_probability_ece'
	],
	span: 'window'
} as const satisfies PanelQuery;

export const judgeDrawTrialQuery = {
	name: 'judgeDrawTrialQuery',
	ledger: 'threshold-history',
	columns: [
		'date', 'run_id', 'attempt', 'pairs_drawn', 'pairs_returned', 'sample_status', 'slice_outcomes',
		'lower_threshold_before', 'upper_threshold_before', 'lower_threshold_after', 'upper_threshold_after'
	],
	span: 'window'
} as const satisfies PanelQuery;

export const judgePairTrialQuery = {
	name: 'judgePairTrialQuery',
	ledger: 'pair-verdicts',
	columns: [
		'date', 'run_id', 'attempt', 'pair_key', 'similarity_score', 'verdict', 'verdict_swapped',
		'lower_threshold_in_force', 'upper_threshold_in_force', 'scorer_model', 'cosine_weight',
		'judge_model', 'prompt_digest', 'grammar_digest', 'judge_policy_version', 'judge_temperature'
	],
	span: 'window'
} as const satisfies PanelQuery;

export const judgeCutoffTrialQuery = {
	name: 'judgeCutoffTrialQuery',
	ledger: 'threshold-history',
	columns: [
		'date', 'run_id', 'attempt', 'sample_f0_5', 'sample_average_precision',
		'sample_precision_at_recall_90', 'sample_recall_90_cutoff', 'sample_recall_at_recall_90_cutoff',
		'lower_estimate', 'lower_nights_used', 'lower_usable_pairs_used', 'lower_held_because', 'lower_move_limited_by',
		'upper_estimate', 'upper_nights_used', 'upper_usable_pairs_used', 'upper_held_because', 'upper_move_limited_by'
	],
	span: 'window'
} as const satisfies PanelQuery;

export const judgePoolTrialQuery = {
	name: 'judgePoolTrialQuery',
	ledger: 'threshold-history',
	columns: ['date', 'run_id', 'attempt', 'score_pool_histogram'],
	span: 'window'
} as const satisfies PanelQuery;
