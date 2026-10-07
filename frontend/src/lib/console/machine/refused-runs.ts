/** The words of Hardware's box that names the runs the counters refuse.
 *
 * A run whose rows cannot be made into one run is named on the page with the
 * reason, never dropped: a run count that quietly leaves one out is a run count
 * nobody can check. The words are worked out here rather than in the page, so a
 * test can hand them a run `machineCounters` refuses and read what the box
 * claims beside what each figure the page builds from article rows counts.
 */

import type { RefusedRun } from '../../server/machine-counters';

/** What the box prints: its head, and for each run the sentence after its id. */
export interface RefusedRunsBox {
	head: string;
	runs: { runId: string; says: string }[];
}

/** The box for the refused runs one window holds, or null where it holds none. */
export function describeRefusedRuns(refused: readonly RefusedRun[]): RefusedRunsBox | null {
	if (refused.length === 0) return null;
	const counted = refused.length === 1 ? '1 run is' : `${refused.length} runs are`;
	return {
		head: `${counted} left out of every windowed figure on this page.`,
		runs: refused.map((run) => ({
			runId: run.runId,
			says:
				`holds ${run.rows} rows: ${run.why}. Summing them would report a machine that never ` +
				'existed, so nothing here reads the run at all.'
		}))
	};
}
