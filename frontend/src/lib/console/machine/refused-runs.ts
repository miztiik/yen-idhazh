/** The words of Hardware's box that names the runs the counters refuse.
 *
 * A run whose rows cannot be made into one run is named on the page with the
 * reason, never dropped: a run count that quietly leaves one out is a run count
 * nobody can check. The box says what leaves such a run out and what still
 * counts it. The route's first line counts only the runs the counters keep, and
 * every figure that picks article rows by date takes the run's articles with
 * the rest. The words are worked out here rather than in the page, so a test
 * can hand them a run `machineCounters` refuses and check each claim against
 * the figures it names. Reader chose the words on 2026-10-07.
 */

import { plural } from '../../format';
import type { RefusedRun } from '../../server/machine-counters';

/** What the box prints: its head, and for each run the sentence after its id. */
export interface RefusedRunsBox {
	head: string;
	runs: { runId: string; says: string }[];
}

/** The box for the refused runs one window holds, or null where it holds none. */
export function describeRefusedRuns(refused: readonly RefusedRun[]): RefusedRunsBox | null {
	if (refused.length === 0) return null;
	const many = refused.length > 1;
	return {
		head:
			`${plural(refused.length, 'run has', 'runs have')} records that do not fit together. ` +
			`The run count above does not include ${many ? 'them' : 'it'}. ` +
			`Figures that pick articles by date still include the articles of ${many ? 'these runs' : 'this run'}.`,
		runs: refused.map((run) => ({
			runId: run.runId,
			says: `has ${plural(run.rows, 'row', 'rows')}: ${run.why}.`
		}))
	};
}
