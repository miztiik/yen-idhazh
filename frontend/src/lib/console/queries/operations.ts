/** Read packed work records before placing them on their UTC event days. */
import type { PanelQuery } from './window';

export const councilRunsQuery = {
	name: 'councilRunsQuery', ledger: 'council-run-records',
	columns: ['date', 'run_id', 'attempt', 'job', 'judge_id', 'started_at', 'evaluation_step', 'work_part_index', 'work_part_count', 'outcome'],
	span: 'widest'
} as const satisfies PanelQuery;

export const gardenerWakeQuery = {
	name: 'gardenerWakeQuery', ledger: 'gardener',
	columns: ['date', 'run_id', 'attempt', 'job', 'shard', 'task', 'work_ended_at', 'dry_run', 'selected', 'deleted',
		'bytes_freed', 'stopped_because', 'fault', 'resume_from', 'candidates_seen', 'handled_through', 'recovered'],
	span: 'widest'
} as const satisfies PanelQuery;
