/** What is each recorded day's median time, and how many articles actually carried it? */
import type { Row } from '../../data/ledger';
import type { StageTimingDay } from '../../charts/series';
import { finiteCell, nearestRank } from '../rates';

export function nativeStageTimings(rows: readonly Row[]): StageTimingDay[] {
	const dates = [...new Set(rows.map((row) => String(row.date)))].sort();
	return dates.map((date) => {
		const own = rows.filter((row) => row.date === date);
		const stage = (cell: string) => {
			const values = own.flatMap((row) => {
				const value = finiteCell(row[cell]);
				return value === null ? [] : [value];
			});
			return { ms: nearestRank(values, 0.5), timed: values.length, total: own.length };
		};
		return { date, items: own.length, fetch: stage('fetch_ms'), extract: stage('extract_ms'), summarize: stage('summarize_ms') };
	});
}
