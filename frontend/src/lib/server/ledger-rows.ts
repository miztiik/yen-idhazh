/** Which rows of the item and score records does a console route read?
 *
 * The two build-time readers every console route shares for `state/item-health/`
 * and `state/scores/`. They sit apart from `payload.ts`, the one payload loader,
 * because reading a committed ledger is a different question from loading a
 * published day.
 *
 * Imports nothing at runtime beyond the shared readers: the browser suite loads
 * this module in plain Node, where no Vite alias resolves.
 */

import { join } from 'node:path';
// Relative, not `$lib`, for the reason in the module docstring.
import {
	ITEM_HEALTH_KEY,
	ITEM_HEALTH_RULE,
	LEDGER_WINDOW_DAYS,
	OBSERVATION_KEY,
	settledDayShards,
	STATE_ROOT,
	type CsvTable
} from './payload';

/** One row per scored measurement, read from the committed ledger and never recomputed.
 *
 * The ledger is a tree of day files, so this reads the newest `days` of them
 * oldest first and hands back one table. Pass `-1` to read every day, and say
 * beside the call why (`docs/concepts/growing-reads.md`).
 *
 * Settled under `OBSERVATION_KEY`, within each day, at this one read rather than
 * in each panel - the placement `itemHealthRows` and `feedResults` take below,
 * for the same reason. Two jobs write a score row for one observation, so the
 * day a run is publishing holds both accounts of it and a panel counting rows
 * counts the measurement twice. The key declares no preference, which the
 * backend reads as keep the first: a repeat here is one attempt written twice
 * and the rows agree. Measured 2026-09-23 over the committed ledger, they agree
 * cell for cell in all 204 repeated keys of the publishing day.
 *
 * **It is the newest day that carries the repeat.** A closed day has been folded
 * into one settled file by the gardener - `fold.after_days` in the declaration
 * under `config/gardener/` that owns the tree - and holds no repeated key at all.
 * Measured the same day: the publishing day held 441 rows over 237 keys, and the
 * thirty-two folded days before it held 0 repeats between them.
 *
 * There is no published mirror of this ledger. `frontend/public/scores/` was one
 * until 2026-09-16 and no route ever fetched it, so it went with its producer.
 */
export function evalRows(days: number = LEDGER_WINDOW_DAYS): CsvTable {
	return settledDayShards(join(STATE_ROOT, 'scores'), OBSERVATION_KEY, undefined, days);
}

/** One row per planned item per run, read from the newest `days` recorded days.
 *
 * Settled here, at the one read every console panel shares, rather than in each
 * panel - the placement `feedResults` takes below, for the same reason.
 *
 * **It is the newest day that carries the repeat, which is why this surfaced
 * late.** A closed day has been folded into one settled file by the gardener and
 * holds no repeated key at all; the day a run is publishing still holds one file
 * per writer, and that is the day every panel here opens on. Measured 2026-09-23
 * over the committed ledger: the thirteen folded days held 0 repeated keys
 * between them, and the unfolded day held 240 repeats over 240 items - every
 * item of it, twice.
 */
export function itemHealthRows(days: number = LEDGER_WINDOW_DAYS): CsvTable {
	return settledDayShards(join(STATE_ROOT, 'item-health'), ITEM_HEALTH_KEY, ITEM_HEALTH_RULE, days);
}
