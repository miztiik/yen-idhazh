/** Read the run's exact displayed-figure counts, preserving unmeasured history. */

export interface ChartEvidence {
	displayed_values: number;
	derived_values: number;
	trusted_values: number;
	derived_value_rate: number | null;
	trusted_data_ratio: number | null;
}

export function readChartEvidence(value: unknown): ChartEvidence | null {
	if (value === undefined || value === null) return null;
	if (typeof value !== 'object') throw new Error('chart_evidence must be an object or null');
	const { displayed_values, derived_values, trusted_values, derived_value_rate, trusted_data_ratio } =
		value as Record<string, unknown>;
	if (
		typeof displayed_values !== 'number' ||
		typeof derived_values !== 'number' ||
		typeof trusted_values !== 'number' ||
		!Number.isSafeInteger(displayed_values) ||
		!Number.isSafeInteger(derived_values) ||
		!Number.isSafeInteger(trusted_values) ||
		displayed_values < 0 ||
		derived_values < 0 ||
		trusted_values < 0 ||
		derived_values > displayed_values ||
		trusted_values > displayed_values
	) throw new Error('chart_evidence has invalid figure counts');
	if (
		(typeof derived_value_rate !== 'number' && derived_value_rate !== null) ||
		(typeof trusted_data_ratio !== 'number' && trusted_data_ratio !== null) ||
		derived_value_rate !== (displayed_values ? derived_values / displayed_values : null) ||
		trusted_data_ratio !== (displayed_values ? trusted_values / displayed_values : null)
	) throw new Error('chart_evidence rates do not match its figure counts');
	return { displayed_values, derived_values, trusted_values, derived_value_rate, trusted_data_ratio };
}
