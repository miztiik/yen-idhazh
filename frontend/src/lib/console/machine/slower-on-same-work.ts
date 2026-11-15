/** Is one fixed typical article becoming slower on the same reference machine? */
import type { Row } from '../../data/ledger';
import type { SeriesInput } from '../../charts/d3/dateSeries';
import { nearestRank, referenceWork, typicalSeconds } from '../rates';
import { SERIES_TOKENS } from '../series-tokens';

export function slowerOnSameWork(rows: readonly Row[], calendar?: readonly string[]) {
	const reference = referenceWork(rows);
	const dates = calendar ?? [...new Set(rows.map((row) => String(row.date)))].sort();
	const days = dates.map((date) => {
		const timed = typicalSeconds(rows.filter((row) => row.date === date), reference);
		return { date, ...timed, seconds: timed.read === null || timed.write === null ? null : timed.read + timed.write };
	});
	const measured = days.flatMap((day) => day.seconds === null ? [] : [day.seconds]);
	const series: SeriesInput[] = [{
		label: 'Seconds for the typical article', token: SERIES_TOKENS['model-time'],
		points: days.map((day) => ({ date: day.date, value: day.seconds }))
	}];
	return { reference, days, series, median: nearestRank(measured, 0.5), newest: days.at(-1)?.seconds ?? null };
}
