/** Which packed judge readings belong to the window and to its selected digest? */
import type { PanelQuery } from './window';

export const judgeHistoryQuery = {
	name: 'judgeHistoryQuery',
	ledger: 'threshold-history',
	columns: [
		'date', 'run_id', 'attempt', 'pairs_drawn', 'pairs_returned',
		'sample_tp', 'sample_fp', 'sample_fn', 'sample_tn', 'score_psi'
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
		'judge_probability_baseline_brier_score', 'judge_probability_ece',
		'canary_answers', 'canary_expectations', 'canary_kappa', 'canary_kappa_pairs'
	],
	span: 'window'
} as const satisfies PanelQuery;
