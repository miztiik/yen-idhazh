/** Lay out a labelled matrix whose color and exact readout describe the same cells. */
import type { ReadoutFacts } from '../readout';

export interface GridHeading {
	readonly label: string;
	readonly title?: string;
	readonly change?: boolean;
	readonly chosen?: boolean;
	readonly tone?: string;
}

export interface GridDiagnostic {
	readonly paint: string | null;
	readonly facts: ReadoutFacts;
	readonly text?: string;
	readonly diagonal?: boolean;
}

export function diagnosticGrid(
	rows: readonly GridHeading[], columns: readonly GridHeading[],
	cells: readonly (readonly GridDiagnostic[])[], restingColumn = 0
) {
	if (!rows.length || !columns.length) return null;
	if (cells.length !== rows.length || cells.some((line) => line.length !== columns.length)) {
		throw new Error('A diagnostic grid needs a cell at each named intersection.');
	}
	const records = cells.flat().map(({ facts }) => facts);
	return { rows, columns, cells, records, rest: Math.max(0, Math.min(restingColumn, columns.length - 1)) };
}
