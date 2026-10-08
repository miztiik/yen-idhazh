/** Which days had a run, from either record?
 *
 * Hardware reads this one list wherever it counts or names days with a run: the
 * started lines of the server's own figures and of the machine record count the
 * days of a window before their instrument began, and the two charts that mark a
 * setup change name the days they cannot show one for. A route's server module
 * may export only its load, so the rule lives here, where a test calls the
 * function the route calls.
 *
 * Imports nothing at run time: the browser suite loads this module in plain
 * Node, where no Vite alias resolves.
 */

import type { MachineCounters } from './machine-counters';

/** Every day with a run, ascending: the day of each run the counters kept, and
 * each day the article record holds a row for. */
export function listRunDays(counters: MachineCounters, articleDays: readonly string[]): string[] {
	return [...new Set([...counters.runs.map((run) => run.date), ...articleDays])]
		.filter((date) => date !== '')
		.sort();
}
