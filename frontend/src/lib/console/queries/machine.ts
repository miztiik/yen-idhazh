/** What does each Hardware panel ask the published ledgers? */
import type { PanelQuery } from './window';

export const runShardsQuery = {
	name: 'runShardsQuery', ledger: 'run-shards',
	columns: ['date', 'run_id', 'shards'],
	span: 'widest'
} as const satisfies PanelQuery;

export const twoClocksQuery = {
	name: 'twoClocksQuery', ledger: 'item-health',
	columns: ['date', 'run_id', 'machine_job', 'machine_shard', 'prefill_ms', 'input_tokens', 'cached_tokens'],
	span: 'newest-day'
} as const satisfies PanelQuery;

export const twoClocksHostsQuery = {
	name: 'twoClocksHostsQuery', ledger: 'host-fingerprint',
	columns: ['date', 'run_id', 'job', 'shard', 'server_prompt_tokens', 'server_prompt_seconds'],
	span: 'newest-day'
} as const satisfies PanelQuery;

export const processorLostQuery = {
	name: 'processorLostQuery', ledger: 'item-health',
	columns: ['date', 'run_id', 'machine_shard', 'cpu_steal_pct'],
	span: 'window'
} as const satisfies PanelQuery;

export const diskReadsQuery = {
	name: 'diskReadsQuery', ledger: 'item-health',
	columns: ['date', 'run_id', 'item_index', 'llama_major_faults', 'os_mem_cached_bytes', 'weights_pinned'],
	span: 'window'
} as const satisfies PanelQuery;

export const machineCardsQuery = {
	name: 'machineCardsQuery', ledger: 'host-fingerprint',
	columns: [
		'version', 'date', 'run_id', 'job', 'pipeline_name', 'task_name', 'shard', 'fingerprint', 'fingerprint_version',
		'cpu_model', 'cpu_vendor', 'cpu_family', 'cpu_model_number', 'cpu_stepping', 'microcode',
		'cpu_physical_cores', 'cpu_logical_processors', 'cpu_allowed_processors',
		'cpu_quota_cores', 'cpu_quota_state', 'cpu_target_measured_at', 'l3_cache_bytes',
		'cpu_observed_mhz', 'cpu_reported_max_mhz', 'flags', 'boot_seconds', 'memcpy_gib_s',
		'memcpy_probe_mib', 'vm_size', 'vm_location', 'vm_zone', 'vm_fault_domain',
		'cores', 'threads', 'mhz_max', 'mhz_at_probe'
	],
	span: 'newest-day'
} as const satisfies PanelQuery;

export const machineCardsItemsQuery = {
	name: 'machineCardsItemsQuery', ledger: 'item-health',
	columns: ['date', 'run_id', 'machine_job', 'machine_pipeline_name', 'machine_task_name', 'machine_shard', 'cpu_model'],
	span: 'newest-day'
} as const satisfies PanelQuery;

export const slowerMachinesQuery = {
	name: 'slowerMachinesQuery', ledger: 'item-health',
	columns: ['run_id', 'cpu_model', 'prefill_ms', 'input_tokens', 'cached_tokens', 'decode_ms', 'output_tokens'],
	span: 'window'
} as const satisfies PanelQuery;

export const platformMixQuery = {
	name: 'platformMixQuery', ledger: 'host-fingerprint',
	columns: [
		'version', 'date', 'run_id', 'job', 'pipeline_name', 'task_name', 'shard', 'fingerprint', 'fingerprint_version',
		'cpu_model', 'cpu_logical_processors', 'model_load_ms', 'job_seconds',
		'server_prompt_tokens', 'server_prompt_seconds',
		'cores', 'threads', 'mhz_max', 'mhz_at_probe'
	],
	span: 'widest'
} as const satisfies PanelQuery;

export const slowestArticlesQuery = {
	name: 'slowestArticlesQuery', ledger: 'item-health',
	columns: ['run_id', 'item_id', 'source_id', 'machine_shard', 'item_total_ms', 'fetch_ms', 'extract_ms', 'summarize_ms', 'faithfulness_ms', 'stage_gap_ms', 'queue_wait_ms'],
	span: 'newest-day'
} as const satisfies PanelQuery;

export const tailTrendQuery = {
	name: 'tailTrendQuery', ledger: 'item-health',
	columns: ['date', 'run_id', 'summarize_ms'],
	span: 'window'
} as const satisfies PanelQuery;

export const closestToMemoryQuery = {
	name: 'closestToMemoryQuery', ledger: 'item-health',
	columns: ['date', 'item_id', 'source_id', 'os_mem_total_bytes', 'os_mem_available_min_bytes', 'source_words'],
	span: 'window'
} as const satisfies PanelQuery;

export const memoryHeldQuery = {
	name: 'memoryHeldQuery', ledger: 'item-health',
	columns: ['date', 'item_id', 'os_mem_total_bytes', 'os_mem_available_bytes', 'llama_rss_bytes', 'python_rss_bytes', 'llama_rss_anon_bytes', 'python_rss_anon_bytes', 'os_swap_total_bytes', 'os_swap_free_bytes'],
	span: 'newest-day'
} as const satisfies PanelQuery;

export const contextHeadroomQuery = {
	name: 'contextHeadroomQuery', ledger: 'item-health',
	columns: ['label_input_tokens', 'summary_input_tokens', 'n_ctx_configured', 'n_parallel', 'truncation_cap_tokens'],
	span: 'window'
} as const satisfies PanelQuery;

export const articleCostQuery = {
	name: 'articleCostQuery', ledger: 'item-health',
	columns: ['date', 'run_id', 'machine_job', 'machine_pipeline_name', 'machine_task_name', 'machine_shard', 'item_index', 'item_total_ms', 'cpu_busy_pct', 'prefill_ms', 'decode_ms', 'llama_rss_bytes'],
	span: 'window'
} as const satisfies PanelQuery;

export const articleCostHostsQuery = {
	name: 'articleCostHostsQuery', ledger: 'host-fingerprint',
	columns: [
		'version', 'date', 'run_id', 'job', 'pipeline_name', 'task_name', 'shard', 'cpu_logical_processors',
		'cores', 'threads', 'mhz_max', 'mhz_at_probe'
	],
	span: 'window'
} as const satisfies PanelQuery;

export const promptReuseQuery = {
	name: 'promptReuseQuery', ledger: 'item-health',
	columns: ['date', 'label_input_tokens', 'label_cached_tokens', 'label_cache_pct', 'label_prefill_tokens_per_s', 'summary_input_tokens', 'summary_cached_tokens', 'summary_cache_pct', 'summary_prefill_tokens_per_s'],
	span: 'window'
} as const satisfies PanelQuery;

export const readAgainstWrittenQuery = {
	name: 'readAgainstWrittenQuery', ledger: 'item-health',
	columns: ['date', 'run_id', 'input_tokens', 'output_tokens', 'prefill_ms', 'decode_ms'],
	span: 'window'
} as const satisfies PanelQuery;
