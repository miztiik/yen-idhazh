/** How many articles did each run read only the start of?
 *
 * What counts as a cut is `wasCut`, the one definition the Model route reads too,
 * so the run squares and that route cannot disagree about the same article.
 *
 * Its one runtime import is relative, because the browser suite loads this
 * module in plain Node, where no Vite alias resolves.
 */

import { wasCut } from './model-work';

/** Articles each run read only the start of, keyed by the run that read them.
 *
 * Counted per address, not per row: a run writes one row per planned item, and
 * the same article coming round on a later run is the same article.
 */
export function cutsByRun(rows: Record<string, string>[]): Map<string, number> {
	const seen = new Map<string, Set<string>>();
	for (const row of rows) {
		if (!wasCut(row)) continue;
		const runId = row.run_id ?? '';
		const found = seen.get(runId) ?? new Set<string>();
		found.add(row.url_key ?? row.item_id ?? '');
		seen.set(runId, found);
	}
	return new Map([...seen].map(([runId, keys]) => [runId, keys.size]));
}
