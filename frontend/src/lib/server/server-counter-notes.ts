/** What Hardware says about the model server's own counters over one window.
 *
 * Three lines: the route's first line, which counts the window's runs; the
 * "Measurement is off" line; and the recording notes of the server's counters.
 * They are worked out here rather than in the route, because a route's server
 * module may export only its load, and no test can run a load. A test hands
 * this the facts the route hands it, built for the test, and reads every line.
 *
 * Imports nothing that needs a Vite alias: the browser suite loads this module
 * in plain Node, where no alias resolves.
 */

import type { ObservabilityConfig } from './config';
import type { MachineRun } from './machine-counters';
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
	/** The observability block of `config/idhazh.json`, as the route holds it. */
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

/** The route's first line: the runs this window holds, and the days they span.
 *
 * One day has no range, and "1 run in this one day" trips on its two ones, so
 * the one-day line names the day once and leads with it.
 */
function introSentence(runsRead: number, open: OfferedWindow): string {
	const runs = `${runsRead} ${runsRead === 1 ? 'run' : 'runs'}`;
	if (open.days === 1) {
		return runsRead === 0
			? `${openWithSpan(open.days)} had no run that committed a counters row. ${open.end}.`
			: `${openWithSpan(open.days)} had ${runs} that committed counters the model server wrote itself. ${open.end}.`;
	}
	return runsRead === 0
		? `No run in ${nameSpan(open.days)} committed a counters row. ${open.start} to ${open.end}.`
		: `${runs} in ${nameSpan(open.days)} committed counters the model server wrote itself. ${open.start} to ${open.end}.`;
}

/** The lines Hardware prints about the model server's own counters over `facts.open`. */
export function describeServerCounters(facts: ServerCounterFacts): ServerCounterNotes {
	const { open, observability } = facts;
	const shown = facts.runs.filter((run) => run.date >= open.start && run.date <= open.end);
	const days = [...new Set(facts.runs.map((run) => run.date))].sort();
	return {
		intro: introSentence(shown.length, open),
		measurementOff: measurementOff({
			enabled: observability.host_fingerprint,
			recorded: days,
			read: facts.machineRead,
			open,
			offered: facts.offered
		}),
		recording: recordingNotes({
			enabled: observability.host_fingerprint,
			rate: observability.sample_rate,
			recorded: days,
			window: facts.ran,
			reads: [facts.machineRead],
			from: facts.from,
			open,
			coveredElsewhere: facts.articleDays,
			missing: 'server-counters'
		})
	};
}
