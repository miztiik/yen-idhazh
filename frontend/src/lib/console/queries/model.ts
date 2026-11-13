/** What does each Summaries panel ask the published ledgers? */
import type { PanelQuery } from './window';

export const modelThroughputQuery = {
	name: 'modelThroughputQuery', ledger: 'item-health',
	columns: ['date', 'run_id', 'model_id', 'prefill_ms', 'decode_ms', 'input_tokens', 'cached_tokens', 'output_tokens'],
	span: 'window'
} as const satisfies PanelQuery;

export const itemCostQuery = {
	name: 'itemCostQuery', ledger: 'item-health',
	columns: ['date', 'prefill_ms', 'decode_ms', 'input_tokens', 'output_tokens', 'cached_tokens', 'label_input_tokens', 'label_cached_tokens'],
	span: 'window'
} as const satisfies PanelQuery;

export const callEndingQuery = {
	name: 'callEndingQuery', ledger: 'item-health',
	columns: ['date', 'summary_finish_reason', 'label_finish_reason'],
	span: 'window'
} as const satisfies PanelQuery;

export const faithfulnessQuery = {
	name: 'faithfulnessQuery', ledger: 'summary-quality-evals',
	columns: ['date', 'hhem', 'hhem_delta'],
	span: 'window'
} as const satisfies PanelQuery;

export const sourceDoubtsQuery = {
	name: 'sourceDoubtsQuery', ledger: 'summary-quality-evals',
	columns: ['date', 'url_key', 'band', 'unsupported_numbers', 'hedge_dropped', 'evidential_density', 'speculative_density'],
	span: 'window'
} as const satisfies PanelQuery;

export const sourceDoubtsItemsQuery = {
	name: 'sourceDoubtsItemsQuery', ledger: 'item-health',
	columns: ['url_key', 'source_id'],
	span: 'window'
} as const satisfies PanelQuery;

export const scoreCostQuery = {
	name: 'scoreCostQuery', ledger: 'summary-quality-evals',
	columns: ['date', 'score_ms'],
	span: 'window'
} as const satisfies PanelQuery;

export const summaryLengthQuery = {
	name: 'summaryLengthQuery', ledger: 'summary-quality-evals',
	columns: ['date', 'run_id', 'model_id', 'summary_words', 'source_words_before_cap', 'source_words', 'compression'],
	span: 'window'
} as const satisfies PanelQuery;
