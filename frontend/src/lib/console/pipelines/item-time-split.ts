/** Which complete item clocks reconcile, with calls shown only as non-additive detail? */
import type { Row } from '../../data/ledger';
import { readoutOf } from '../../charts/readout';
import { durationCohort } from '../duration-cohort';
import { SERIES_TOKENS } from '../series-tokens';

export function nativeTimeSplit(rows: readonly Row[], calendar?: readonly string[]) {
	return durationCohort(rows, calendar ?? [...new Set(rows.map((row) => String(row.date)))].sort());
}

export function timeSplitReadout(split: ReturnType<typeof nativeTimeSplit>) {
	const detailTokens = [SERIES_TOKENS['label-call'], SERIES_TOKENS['summary-call'], SERIES_TOKENS['visual-plan']];
	const seconds = (value: number) => `${(value / 1000).toFixed(2)} s`;
	return readoutOf({
		type: 'dateSeries', columns: split.days.map((day) => day.date),
		series: [
			...split.series.map((series) => ({
				label: series.label, swatch: series.token, values: series.points.map((point) => point.value), format: seconds
			})),
			...[split.reconciliation.elapsed, split.reconciliation.overlap].map((series) => ({
				label: series.label, swatch: series.token, values: series.points.map((point) => point.value), format: seconds
			})),
			...[0, 1, 2].map((index) => ({
				label: ['Label call', 'Summary call', 'Visual plan'][index], swatch: detailTokens[index],
				values: split.days.map((day) => day.details[index].value), format: seconds,
				note: 'detail, not added'
			})),
			{ label: 'Complete clocks', swatch: null, values: split.days.map((day) => day.count),
				format: (value: number, column: number) => `${value} of ${split.days[column].recorded}` }
		], notMeasured: 'Not measured for the complete cohort', resting: 'newest'
	});
}
