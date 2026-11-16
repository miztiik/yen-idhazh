/** Which articles in the newest recorded run exceeded its median work time? */
import { median } from 'd3-array';
import type { Row } from '../../data/ledger';
import type { RankedInput } from '../../charts/d3/rankedList';
import { formatNumber, type NumberFormatConfig } from '../../number-format';
import { newestRunRows } from '../queries/shared';
import { finiteCell } from '../rates';

export function slowestArticles(
	rows: readonly Row[],
	numberFormat: NumberFormatConfig
): { run: string | null; rows: RankedInput[]; medianSeconds: number | null; measured: number; unmeasured: number } {
	const selected = newestRunRows(rows);
	const run = selected.length ? String(selected[0].run_id) : null;
	const ready = selected.flatMap((row): RankedInput[] => {
		const workMs = finiteCell(row.item_total_ms);
		if (workMs === null || workMs < 0) return [];
		const gap = finiteCell(row.stage_gap_ms);
		const wait = finiteCell(row.queue_wait_ms);
		const clocks = [
			['Fetch', 'fetch_ms', '--chart-1'], ['Extract', 'extract_ms', '--chart-2'],
			['Summarize', 'summarize_ms', '--chart-3'], ['Checking', 'faithfulness_ms', '--chart-7']
		] as const;
		const complete = clocks.every(([, key]) => {
			const value = finiteCell(row[key]); return value !== null && value >= 0;
		});
		return [{
			label: `${row.item_id ?? 'unnamed article'} - ${row.source_id ?? 'source not recorded'}`,
			value: workMs / 1000,
			context: [wait === null ? 'queue wait not recorded' : `queue wait ${formatNumber(wait / 1000, numberFormat, { si: false })} s`,
				gap === null ? 'stage gap not recorded' : gap < 0 ? `stages overlapped by ${formatNumber(-gap / 1000, numberFormat, { si: false })} s` : ''].filter(Boolean).join('; '),
			...(complete && gap !== null && gap >= 0 ? { segments: [
				...clocks.map(([label, key, token]) => ({ label, value: finiteCell(row[key])! / 1000, token })),
				...(gap > 0 ? [{ label: 'Other', value: gap / 1000, token: '--chart-8' }] : [])
			] } : {})
		}];
	});
	const medianSeconds = median(ready, (row) => row.value) ?? null;
	return {
		run,
		rows: medianSeconds === null ? [] : ready.filter((row) => row.value > medianSeconds),
		medianSeconds,
		measured: ready.length,
		unmeasured: selected.length - ready.length
	};
}
