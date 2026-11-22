import type { Row } from '../../data/ledger';

interface Endings {
	reported: number;
	cutoffs: number;
	stops: number;
	other: number;
}

/** A finish reason comes from a reply, not from a ledger of all attempts. */
export function callEnding(rows: readonly Row[], dates: readonly string[]) {
	const byDate = new Map<string, Endings>();
	const total: Endings = { reported: 0, cutoffs: 0, stops: 0, other: 0 };
	for (const row of rows) {
		if (typeof row.date !== 'string') throw new Error('A call ending needs its recorded date.');
		const day = byDate.get(row.date) ?? { reported: 0, cutoffs: 0, stops: 0, other: 0 };
		for (const cell of [row.summary_finish_reason, row.label_finish_reason]) {
			if (cell === null || cell === undefined || cell === '') continue;
			if (typeof cell !== 'string') throw new Error('A call ending must be text.');
			const key = cell === 'length' ? 'cutoffs' : cell === 'stop' ? 'stops' : 'other';
			day[key]++;
			day.reported++;
		}
		if (day.reported > 0) byDate.set(row.date, day);
	}
	const days = dates.map((date) => {
		const endings = byDate.get(date) ?? null;
		if (endings !== null) {
			for (const key of ['reported', 'cutoffs', 'stops', 'other'] as const) total[key] += endings[key];
		}
		return { date, endings };
	});
	return { total, days };
}
