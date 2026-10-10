/** Which rule refused a reply, and how do the panels identify the same record? */
import type { Row } from '../../data/ledger';
import { isDay } from '../../data/slice-shapes';
import type { PanelQuery } from './window';

export const failedRuleQuery = {
	name: 'failedRuleQuery',
	ledger: 'item-health',
	columns: ['date', 'stage', 'outcome', 'code', 'failed_rule'],
	span: 'window'
} as const satisfies PanelQuery;

/** RunId is a UTC date followed by a decimal run number, not a lexical suffix. */
function runParts(run: Row[string] | undefined): { date: string; number: bigint } {
	if (typeof run !== 'string') throw new Error('run_id is not a dated run number');
	const match = /^(\d{4}-\d{2}-\d{2})-(\d+)$/.exec(run);
	if (match === null || !isDay(match[1])) throw new Error(`run_id is not a dated run number: ${run}`);
	return { date: match[1], number: BigInt(match[2]) };
}

export function compareRuns(left: Row[string] | undefined, right: Row[string] | undefined): number {
	const a = runParts(left);
	const b = runParts(right);
	return a.date < b.date ? -1 : a.date > b.date ? 1 : a.number < b.number ? -1 : a.number > b.number ? 1 : 0;
}

export function newestRunRows(rows: readonly Row[]): Row[] {
	let newest: Row[string] | undefined;
	for (const row of rows) {
		if (newest === undefined || compareRuns(row.run_id, newest) > 0) {
			runParts(row.run_id);
			newest = row.run_id;
		}
	}
	return rows.filter((row) => row.run_id === newest);
}

/** Host identity uses the machine cells, not the item ledger's writer envelope. */
export function hostKey(row: Row, item = false): string {
	const jobCell = item ? row.machine_job : row.job;
	const job = jobCell === null || jobCell === undefined || jobCell === '' ? 'work' : jobCell;
	const shard = item ? row.machine_shard : row.shard;
	if (typeof row.date !== 'string' || !isDay(row.date)) throw new Error('host key names no UTC date');
	runParts(row.run_id);
	if (typeof job !== 'string') throw new Error('host key names no job');
	if ((typeof shard !== 'number' && typeof shard !== 'string') || shard === '' ||
		!Number.isSafeInteger(Number(shard)) || Number(shard) < 0) {
		throw new Error('host key names no shard');
	}
	return JSON.stringify([row.date, row.run_id, job, Number(shard)]);
}

export function joinItemHosts(items: readonly Row[], hosts: readonly Row[]): {
	readonly rows: readonly { readonly item: Row; readonly host: Row | null }[];
	readonly unmatched: number;
} {
	const byKey = new Map(hosts.map((host) => [hostKey(host), host]));
	const rows = items.map((item) => ({
		item,
		// An unrecorded machine shard remains an unmatched item, not shard zero.
		host: item.machine_shard === null || item.machine_shard === undefined || item.machine_shard === ''
			? null : byKey.get(hostKey(item, true)) ?? null
	}));
	return { rows, unmatched: rows.filter((row) => row.host === null).length };
}
