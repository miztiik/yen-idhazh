/** Which articles in the newest recorded run exceeded its median work time? */
import { median } from 'd3-array';
import type { Row } from '../../data/ledger';
import type { RankedInput } from '../../charts/d3/rankedList';
import { formatNumber, type NumberFormatConfig } from '../../number-format';
import { newestRunRows } from '../queries/shared';
import { finiteCell } from '../rates';
import { DURATION_STAGES, stageClock } from '../duration-cohort';

export function slowestArticles(
	rows: readonly Row[],
	numberFormat: NumberFormatConfig
): { run: string | null; rows: RankedInput[]; medianSeconds: number | null; measured: number; unmeasured: number } {
	const selected = newestRunRows(rows);
	const run = selected.length ? String(selected[0].run_id) : null;
	const measured = selected.flatMap((row) => {
		const workMs = finiteCell(row.item_total_ms);
		return workMs === null || workMs < 0 ? [] : [{ row, workMs }];
	});
	const medianMs = median(measured, ({ workMs }) => workMs) ?? null;
	const ready = measured.filter(({ workMs }) => medianMs !== null && workMs > medianMs).map(({ row, workMs }): RankedInput => {
		const gap = finiteCell(row.stage_gap_ms);
		const wait = finiteCell(row.queue_wait_ms);
		const clocks = DURATION_STAGES.map(([cell, label, token]) => ({ label, token, ms: stageClock(row, cell) }));
		const complete = clocks.every(({ ms }) => ms !== null && ms >= 0);
		return {
			label: `${row.item_id ?? 'unnamed article'} - ${row.source_id ?? 'source not recorded'}`,
			value: workMs / 1000,
			context: [wait === null ? 'queue wait not recorded' : `queue wait ${formatNumber(wait / 1000, numberFormat, { si: false })} s`,
				gap === null ? 'stage gap not recorded' : gap < 0 ? `stages overlapped by ${formatNumber(-gap / 1000, numberFormat, { si: false })} s` : ''].filter(Boolean).join('; '),
			...(complete && gap !== null && gap >= 0 ? { segments: [
				...clocks.map(({ label, token, ms }) => ({ label, value: (ms ?? 0) / 1000, token })),
				...(gap > 0 ? [{ label: 'Other', value: gap / 1000, token: '--chart-8' }] : [])
			] } : {})
		};
	});
	return {
		run,
		rows: ready,
		medianSeconds: medianMs === null ? null : medianMs / 1000,
		measured: measured.length,
		unmeasured: selected.length - measured.length
	};
}
