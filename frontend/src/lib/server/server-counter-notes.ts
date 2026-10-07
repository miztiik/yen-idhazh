/** What Hardware says about the model server's own counters over one window.
 *
 * Three lines: the route's first line, which counts the window's runs and how
 * many of them carry the server's own counters; the "Measurement is off" line;
 * and the recording notes of those counters. They are worked out here rather
 * than in the route, because a route's server module may export only its load,
 * and no test can run a load. A test hands this the facts the route hands it,
 * built for the test, and reads every line.
 *
 * **A run carries the server's counters only where a shard reported one of
 * the two cells the server itself wrote** (`carriesServerCounters`). A run is
 * formed from either record, so a run made of article rows alone, or of a
 * machine record that holds the probe and the clocks and neither cell, is a run
 * with no server figures: it counts in the intro's first number and in no line
 * that dates or names a day of the server's figures. Those cells live in the
 * machine record alone, so only that record's read bounds where they start.
 *
 * **Nothing samples the server's counters.** `observability.sample_rate` is the
 * share of runs the scorer scores, and only `observability.host_fingerprint`
 * switches the machine record off, so the counters take no rate and owe no
 * sampling caveat.
 *
 * Imports nothing that needs a Vite alias: the browser suite loads this module
 * in plain Node, where no alias resolves.
 */

import type { ObservabilityConfig } from './config';
import { carriesServerCounters, type MachineRun } from './machine-counters';
import {
	measurementOff,
	recordingNotes,
	type OfferedWindow,
	type RecordingNotes,
	type RecordRead
} from '../console/recording';
import { nameSpan, openWithSpan } from '../console/span-words';

/** What the route hands, for one window. */
export interface ServerCounterFacts {
	/** Every run the route formed over its read, refused runs left out. */
	runs: readonly MachineRun[];
	/** Every day the route has a run on over its read, from either record. */
	ran: readonly string[];
	/** Every day the article record holds a row for over the read. */
	articleDays: readonly string[];
	/** How the read of the machine record went. */
	machineRead: RecordRead;
	/** The first day the route read. */
	from: string;
	/** The window the lines are for. */
	open: OfferedWindow;
	/** Every window the control offers. */
	offered: readonly OfferedWindow[];
	/** The observability block of `config/idhazh.json`, as the route holds it.
	 * Only `host_fingerprint` is read. */
	observability: ObservabilityConfig;
}

/** The lines for one window. */
export interface ServerCounterNotes {
	/** The route's first line. */
	intro: string;
	/** The "Measurement is off" line, null while the counters are recorded. */
	measurementOff: string | null;
	/** What the recording of the server's counters was doing. */
	recording: RecordingNotes;
}

/** How many of a window's runs carry the server's figures, after the run count. */
function shareClause(runs: number, served: number): string {
	const figures = 'figures from the model server itself';
	if (runs === 1) return served === 1 ? `with ${figures}` : `with no ${figures}`;
	if (served === runs) return `each with ${figures}`;
	if (served === 0) return `none with ${figures}`;
	return `${served} of them with ${figures}`;
}

/** The route's first line: every run the window holds, how many of them carry
 * the server's figures, and the days they span.
 *
 * The count leads, because it is every run the page read, and the share
 * follows in the same sentence as the count it is out of. "On record" claims
 * only what the records hold: a day the records have not reached yet is not a
 * day nothing ran. One day has no range, and "1 run in this one day" trips on
 * its two ones, so the one-day line names the day once and leads with it.
 * Reader chose the words, and Jony agreed, on 2026-10-07.
 */
function introSentence(runs: number, served: number, open: OfferedWindow): string {
	const counted = `${runs} ${runs === 1 ? 'run' : 'runs'}`;
	if (open.days === 1) {
		return runs === 0
			? `${openWithSpan(open.days)} has no run on record. ${open.end}.`
			: `${openWithSpan(open.days)} had ${counted}, ${shareClause(runs, served)}. ${open.end}.`;
	}
	return runs === 0
		? `No run in ${nameSpan(open.days)} is on record. ${open.start} to ${open.end}.`
		: `${counted} in ${nameSpan(open.days)}, ${shareClause(runs, served)}. ${open.start} to ${open.end}.`;
}

/** The lines Hardware prints about the model server's own counters over `facts.open`. */
export function describeServerCounters(facts: ServerCounterFacts): ServerCounterNotes {
	const { open, observability } = facts;
	const shown = (run: MachineRun): boolean => run.date >= open.start && run.date <= open.end;
	const served = facts.runs.filter(carriesServerCounters);
	// The days the server's counters were written down, over the whole read: the
	// off line names the newest the window shows, and the started line the first.
	const days = [...new Set(served.map((run) => run.date))].sort();
	return {
		intro: introSentence(facts.runs.filter(shown).length, served.filter(shown).length, open),
		measurementOff: measurementOff({
			enabled: observability.host_fingerprint,
			recorded: days,
			read: facts.machineRead,
			open,
			offered: facts.offered
		}),
		recording: recordingNotes({
			enabled: observability.host_fingerprint,
			recorded: days,
			window: facts.ran,
			reads: [facts.machineRead],
			from: facts.from,
			open,
			figures: 'server figures',
			coveredElsewhere: facts.articleDays,
			missing: 'server-counters'
		})
	};
}