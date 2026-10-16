import type { Row } from '../../data/ledger';
import type { SeriesInput } from '../../charts/d3/dateSeries';
import { SERIES_TOKENS } from '../series-tokens';

export function callEnding(rows: readonly Row[]): { series: SeriesInput[]; calls: number; length: number } {
	const totals = new Map<string, number>();
	const dates = new Map<string, Map<string, number>>();
	for (const row of rows) {
		if (typeof row.date !== 'string') throw new Error('A call ending needs its recorded date.');
		const day = dates.get(row.date) ?? new Map<string, number>();
		dates.set(row.date, day);
		for (const cell of [row.summary_finish_reason, row.label_finish_reason]) {
			if (cell === null || cell === undefined || cell === '') continue;
			if (typeof cell !== 'string') throw new Error('A call ending must be text.');
			day.set(cell, (day.get(cell) ?? 0) + 1);
			totals.set(cell, (totals.get(cell) ?? 0) + 1);
		}
	}
	const reasons = [...totals.keys()].sort((a, b) => a === 'length' ? -1 : b === 'length' ? 1 :
		(totals.get(b)! - totals.get(a)!) || a.localeCompare(b));
	return {
		calls: [...totals.values()].reduce((a, b) => a + b, 0),
		length: totals.get('length') ?? 0,
		series: reasons.map((reason) => ({
			label: reason === 'length' ? 'cut off at the length limit' : reason === 'stop' ? 'ended on its own' : reason,
			token: reason === 'length' ? SERIES_TOKENS['length-limit'] : reason === 'stop' ? '--chart-axis' : SERIES_TOKENS['other-ending'],
			points: [...dates].sort(([a], [b]) => a.localeCompare(b)).map(([date, counts]) =>
				({ date, value: counts.get(reason) ?? 0 }))
		}))
	};
}
