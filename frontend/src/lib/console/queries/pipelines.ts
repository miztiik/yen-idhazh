/** What does each Pipelines panel ask the published ledgers? */
import type { PanelQuery } from './window';
export { failedRuleQuery } from './shared';

export const failureMixQuery = {
	name: 'failureMixQuery', ledger: 'item-health',
	columns: ['date', 'stage', 'outcome', 'code', 'failed_rule'],
	span: 'window'
} as const satisfies PanelQuery;

export const itemTimeSplitQuery = {
	name: 'itemTimeSplitQuery', ledger: 'item-health',
	columns: ['date', 'item_total_ms', 'fetch_ms', 'extract_ms', 'summarize_ms', 'label_ms', 'summary_ms', 'visual_plan_ms', 'faithfulness_ms', 'stage_gap_ms'],
	span: 'window'
} as const satisfies PanelQuery;

export const slowerOnSameWorkQuery = {
	name: 'slowerOnSameWorkQuery', ledger: 'item-health',
	columns: ['date', 'cpu_model', 'prefill_ms', 'input_tokens', 'cached_tokens', 'decode_ms', 'output_tokens'],
	span: 'window'
} as const satisfies PanelQuery;

export const stageTimingsQuery = {
	name: 'stageTimingsQuery', ledger: 'item-health',
	columns: ['date', 'fetch_ms', 'extract_ms', 'summarize_ms'],
	span: 'window'
} as const satisfies PanelQuery;

export const itemCostQuery = {
	name: 'itemCostQuery', ledger: 'item-health',
	columns: ['date', 'prefill_ms', 'decode_ms', 'input_tokens', 'output_tokens', 'cached_tokens', 'label_input_tokens', 'label_cached_tokens'],
	span: 'window'
} as const satisfies PanelQuery;

export const runTimelineQuery = {
	name: 'runTimelineQuery', ledger: 'item-health',
	columns: ['run_id', 'item_id', 'source_id', 'machine_shard', 'item_index', 'item_started_at', 'item_ended_at', 'queue_wait_ms', 'fetch_ms', 'robots_ms', 'extract_ms', 'label_ms', 'summary_ms', 'visual_plan_ms', 'faithfulness_ms', 'stage_gap_ms', 'item_total_ms'],
	span: 'newest-day'
} as const satisfies PanelQuery;

export const extractionQuery = {
	name: 'extractionQuery', ledger: 'item-health',
	columns: ['date', 'stage', 'outcome', 'code', 'url_key', 'element_class', 'span_integrity', 'elements_found'],
	span: 'window'
} as const satisfies PanelQuery;

export const extractionScoresQuery = {
	name: 'extractionScoresQuery', ledger: 'summary-quality-evals',
	columns: ['date', 'url_key', 'extraction_suspect'],
	span: 'window'
} as const satisfies PanelQuery;

export const articleAgeQuery = {
	name: 'articleAgeQuery', ledger: 'item-health',
	columns: ['published_at', 'time_source', 'item_started_at', 'outcome'],
	span: 'window'
} as const satisfies PanelQuery;
