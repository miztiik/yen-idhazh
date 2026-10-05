/** How the column rail groups column names under the ledger they came from.
 *
 * The page names a ledger's column `{ledger}.{column}`. A name that starts with
 * a declared ledger's name and a dot joins that ledger's group and is shown
 * without the prefix; any other name - an answer's column - stands in a group
 * with no ledger. Only neighbours share a group, and nothing is sorted, so the
 * rail keeps the order the engine described.
 */

// Relative, not `$lib`: the logic suite imports this module in plain Node.
import { LEDGER_NAMES, type Column, type LedgerName } from '../../data/slice-shapes';

export type RailColumn = Column & { shown: string };
export type ColumnGroup = { ledger: LedgerName | null; columns: RailColumn[] };

function ledgerOf(name: string): LedgerName | null {
	const prefix = name.slice(0, Math.max(0, name.indexOf('.')));
	return (LEDGER_NAMES as readonly string[]).includes(prefix) ? (prefix as LedgerName) : null;
}

export function groupColumns(columns: readonly Column[]): ColumnGroup[] {
	const groups: ColumnGroup[] = [];
	for (const column of columns) {
		const ledger = ledgerOf(column.name);
		const shown = ledger === null ? column.name : column.name.slice(ledger.length + 1);
		const last = groups.at(-1);
		if (last !== undefined && last.ledger === ledger) last.columns.push({ ...column, shown });
		else groups.push({ ledger, columns: [{ ...column, shown }] });
	}
	return groups;
}
