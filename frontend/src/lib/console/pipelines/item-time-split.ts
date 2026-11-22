/** Which complete item clocks reconcile, with calls shown only as non-additive detail? */
import type { Row } from '../../data/ledger';
import { readoutOf } from '../../charts/readout';
import { durationCohort, DURATION_DETAILS } from '../duration-cohort';
import { formatNumber, type NumberFormatConfig } from '../../number-format';

export function nativeTimeSplit(rows: readonly Row[], calendar?: readonly string[]) {
	return durationCohort(rows, calendar ?? [...new Set(rows.map((row) => String(row.date)))].sort());
}

export function timeSplitReadout(split: ReturnType<typeof nativeTimeSplit>, numberFormat: NumberFormatConfig) {
	const seconds = (value: number) => `${formatNumber(value / 1000, numberFormat, { si: false })} s`;
	return readoutOf({
		type: 'dateSeries', columns: split.days.map((day) => day.date),
		series: [
			...[...split.series, split.reconciliation.elapsed, split.reconciliation.overlap].map((series) => ({
				label: series.label, swatch: `var(${series.token})`, values: series.points.map((point) => point.value), format: seconds
			})),
			...DURATION_DETAILS.map(([, label], index) => ({
				label, swatch: null,
				values: split.days.map((day) => day.details[index].value), format: seconds,
				note: 'detail, not added'
			})),
			{ label: 'Complete clocks', swatch: null, values: split.days.map((day) => day.count),
				format: (value: number, column: number) => `${formatNumber(value, numberFormat, { exact: true })} of ${formatNumber(split.days[column].recorded, numberFormat, { exact: true })}` }
		], notMeasured: 'Not measured for the complete cohort', resting: 'newest'
	});
}
