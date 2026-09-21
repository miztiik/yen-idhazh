/** Whether the machine took the model's memory back, day by day over one span.
 *
 * The model's weights are read off a file, so the pages holding them are file
 * pages: the machine may hand them to something else at any moment and the
 * server only finds out when it next reads one and has to wait for the disk.
 * Nothing on the machine counts that as swap, so the ordinary swap reading says
 * a run was fine while every article paid for the disk twice. The one counter
 * that sees it is the wait-for-disk count on the server's own process, and this
 * module folds it into one reading a day.
 *
 * **The first item of a shard is excluded.** A server that has just started
 * reads its own weights in, and those reads are the server arriving rather than
 * the machine taking anything back. Every day therefore reports how much of
 * itself the figure covers, so the exclusion is a number on the page rather
 * than a silent subtraction.
 *
 * Pure: the caller decides which rows are in the span and reads the two marks
 * off `console`, so nothing here opens a file and no threshold is written down.
 */

/** Which of the three marks a day takes.
 *
 * `unrecorded` is a day whose rows carry no count, which every day before the
 * column was added is in and which must never draw as a quiet day. `quiet` is a
 * day that counted and found less than the mark. `fired` reached it.
 */
export type DiskReadState = 'unrecorded' | 'quiet' | 'fired';

/** One day's reading. */
export interface DiskReadDay {
	date: string;
	/** Waits for the disk over the items that were not first in their shard.
	 * Null where no such row recorded the count, and null is not zero. */
	reads: number | null;
	/** Rows that recorded the count away from the first item of a shard. */
	counted: number;
	/** Rows that recorded it ON the first item of a shard, or without saying
	 * where in the shard they sat. Left out of `reads`; carried so the page can
	 * say what leaving them out costs. */
	excluded: number;
	/** The most and the least memory the machine was holding disk copies in
	 * over the day, in bytes. Null where the day recorded neither. */
	copiesHigh: number | null;
	copiesLow: number | null;
	/** The share of its own high that reading fell to, 0 to 1. A day that ends
	 * where it started reads 0; a day the machine emptied reads near 1. Null
	 * where the day recorded no reading at all. */
	copiesFell: number | null;
	state: DiskReadState;
}

/** What the runs in the span said about holding the model's memory down.
 *
 * Counted per run rather than per row, because the setting belongs to the
 * server a run started and every item of that run inherits it.
 */
export interface Pinning {
	/** Runs whose every recorded row said the memory was held down, so the
	 * machine could not take it back. */
	held: number;
	/** Runs that recorded the setting and were not holding it down. */
	loose: number;
	/** Runs that recorded nothing either way. */
	silent: number;
}

/** Everything the panel draws for one span. */
export interface DiskReads {
	days: DiskReadDay[];
	/** Days that counted at all. */
	recorded: number;
	/** Days that reached the mark. */
	fired: number;
	/** Waits for the disk summed over every day that counted. */
	reads: number;
	/** The worst day, where it reached the naming threshold. Null where no day
	 * did, which is what keeps the panel's sentence off a day nobody would call
	 * a problem. */
	worst: DiskReadDay | null;
	pinning: Pinning;
}

/** The two thresholds, out of `console`. */
export interface DiskReadMarks {
	/** Waits at or above this fill the day's tile. */
	marked: number;
	/** Waits at or above this put the day in the panel's sentence. */
	named: number;
}

/** A cell as the ledger holds it: absent and empty both mean never filled, and
 * neither means zero. */
function cell(row: Record<string, string>, name: string): string {
	return row[name] ?? '';
}

interface DayTally {
	reads: number;
	counted: number;
	excluded: number;
	copiesHigh: number | null;
	copiesLow: number | null;
}

function emptyTally(): DayTally {
	return { reads: 0, counted: 0, excluded: 0, copiesHigh: null, copiesLow: null };
}

/** One run's setting, as its rows recorded it. A run that recorded both is
 * loose: the machine was free to take the memory back on at least one of its
 * shards, and that is the fact the reader needs. */
function pinningOf(recorded: Set<string>): 'held' | 'loose' | 'silent' {
	if (recorded.size === 0) return 'silent';
	return recorded.has('False') ? 'loose' : 'held';
}

/** Fold one span's item rows into one reading a day, plus what the runs said
 * about holding the model's memory down. */
export function diskReads(
	health: readonly Record<string, string>[],
	marks: DiskReadMarks
): DiskReads {
	const tallies = new Map<string, DayTally>();
	const runs = new Map<string, Set<string>>();

	for (const row of health) {
		const date = cell(row, 'date');
		if (date === '') continue;
		const tally = tallies.get(date) ?? emptyTally();
		tallies.set(date, tally);

		const waits = cell(row, 'llama_major_faults');
		if (waits !== '') {
			const seat = cell(row, 'item_index');
			// A row that never said where in its shard it sat cannot be placed, so
			// it cannot be counted either - it joins the first items rather than
			// quietly landing in the total.
			if (seat !== '' && Number(seat) !== 0) {
				tally.counted += 1;
				tally.reads += Number(waits);
			} else {
				tally.excluded += 1;
			}
		}

		const copies = cell(row, 'os_mem_cached_bytes');
		if (copies !== '') {
			const value = Number(copies);
			tally.copiesHigh = tally.copiesHigh === null ? value : Math.max(tally.copiesHigh, value);
			tally.copiesLow = tally.copiesLow === null ? value : Math.min(tally.copiesLow, value);
		}

		const run = cell(row, 'run_id');
		if (run !== '') {
			const said = runs.get(run) ?? new Set<string>();
			runs.set(run, said);
			const pinned = cell(row, 'weights_pinned');
			if (pinned !== '') said.add(pinned);
		}
	}

	const days: DiskReadDay[] = [...tallies.entries()]
		.sort(([left], [right]) => left.localeCompare(right))
		.map(([date, tally]) => {
			const reads = tally.counted === 0 ? null : tally.reads;
			const high = tally.copiesHigh;
			const low = tally.copiesLow;
			return {
				date,
				reads,
				counted: tally.counted,
				excluded: tally.excluded,
				copiesHigh: high,
				copiesLow: low,
				copiesFell: high === null || low === null || high <= 0 ? null : (high - low) / high,
				state: reads === null ? 'unrecorded' : reads >= marks.marked ? 'fired' : 'quiet'
			};
		});

	const counted = days.filter((day) => day.reads !== null);
	const named = counted.filter((day) => (day.reads ?? 0) >= marks.named);
	const pinning: Pinning = { held: 0, loose: 0, silent: 0 };
	for (const said of runs.values()) pinning[pinningOf(said)] += 1;

	return {
		days,
		recorded: counted.length,
		fired: days.filter((day) => day.state === 'fired').length,
		reads: counted.reduce((total, day) => total + (day.reads ?? 0), 0),
		worst:
			named.length === 0
				? null
				: named.reduce((worst, day) => ((day.reads ?? 0) >= (worst.reads ?? 0) ? day : worst)),
		pinning
	};
}
