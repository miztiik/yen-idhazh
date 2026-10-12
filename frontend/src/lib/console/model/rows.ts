import type { Row } from '../../data/ledger';
import { nearestRank } from '../rates';

/** Keep the declared cells only; the native door uses numbers and booleans. */
export function textRows(rows: readonly Row[]): Record<string, string>[] {
	return rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) =>
		[key, value === null || value === undefined ? '' : String(value)])));
}

export function number(value: Row[string] | undefined): number | null {
	if (value === null || value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

export function median(values: readonly number[]): number | null {
	return nearestRank(values, 0.5);
}
