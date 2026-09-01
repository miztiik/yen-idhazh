/** The quarantine rule, restated on the read side, and the day roll-up under it.
 *
 * The console has to print the number the pipeline rested a feed on. That is a
 * run of failures ending at the newest read - not every failure the ledger ever
 * held. The two are different the moment a feed comes back: a source that
 * failed twelve times in July and answered this morning is healthy, and a total
 * printed beside a quarantine marker says the pipeline dropped it for a reason
 * it never used.
 *
 * So the rule lives here rather than in the page, in one place a test can drive
 * with rows it made up, and it is the same loop `discover._rests` runs.
 * `backend/idhazh/contracts/feed_health.py` and `backend/idhazh/discover.py`
 * are the source of truth; this is a reader of the same ledger and it has to
 * agree with them.
 */

import { plural, shortDate } from './format';

/** What this module needs off a feed-health row, and nothing more. */
export interface FeedRead {
	date: string;
	runId: string;
	outcome: string;
	items: number;
}

/** The same set as `FAILING_OUTCOMES` in the contract. A robots refusal is not
 * one of them: the source is working exactly as it asked to be treated, and
 * resting it would be us punishing a site for saying no. */
const FAILING_OUTCOMES = new Set(['blocked', 'permanent', 'transient']);

/** Did this read count against the feed?
 *
 * A successful read that parsed to no entries counts. The most common way a
 * feed dies is not a 500 - it is a silent reshape that still returns 200.
 */
export function failing(row: FeedRead): boolean {
	if (row.outcome === 'ok') return row.items === 0;
	return FAILING_OUTCOMES.has(row.outcome);
}

/** We did not ask. A rest is a record, not a measurement. */
export function skipped(row: FeedRead): boolean {
	return row.outcome === 'skipped';
}

/** Oldest run first, which is the order the rules below read in.
 *
 * A date alone does not order five runs of one day, and a stable sort then
 * leaves the newest read as whichever row the shard happened to carry last.
 */
export function chronological<T extends FeedRead>(rows: readonly T[]): T[] {
	return [...rows].sort((a, b) => a.date.localeCompare(b.date) || a.runId.localeCompare(b.runId));
}

/** Failures in a row, ending at the newest read. `rows` are oldest run first.
 *
 * This is `discover._rests`'s strike loop and it has to stay that loop. A rest
 * is transparent to it: the run it stands for never asked the question, so it
 * neither adds a strike nor clears one.
 */
export function streak(rows: readonly FeedRead[]): number {
	let strikes = 0;
	for (let index = rows.length - 1; index >= 0; index -= 1) {
		const row = rows[index];
		if (skipped(row)) continue;
		if (!failing(row)) break;
		strikes += 1;
	}
	return strikes;
}

/** Is the pipeline resting this feed right now? The same rule as `_rests`.
 *
 * The rest ends on its own, or a bad afternoon becomes a permanent removal: a
 * feed skipped as many times as it was struck is asked again regardless. Both
 * counters read the one knob, because there is only one question here - how
 * much evidence is enough.
 */
export function resting(rows: readonly FeedRead[], after: number): boolean {
	let skips = 0;
	for (let index = rows.length - 1; index >= 0; index -= 1) {
		if (!skipped(rows[index])) break;
		skips += 1;
	}
	if (skips >= after) return false;
	return streak(rows) >= after;
}

/** What a feed did on one day, as the worst thing that happened to it.
 *
 * Four states rather than three: a source that said no in `robots.txt` neither
 * failed nor delivered, and drawing it as either would say something the ledger
 * does not.
 */
export type FeedDayOutcome = 'answered' | 'failed' | 'refused' | 'resting';

export interface FeedDay {
	date: string;
	outcome: FeedDayOutcome;
	/** The day and its whole tally, as a sentence. Colour is one signal and
	 * never the only one, and this is the other one. */
	label: string;
}

/** One square a day, oldest first, and the sentence under each.
 *
 * A day is drawn by its worst outcome, because the day an operator has to look
 * at is the day something failed. The label carries the whole tally, so a day
 * that mostly worked is never reported as a day that did not.
 */
export function feedDays(rows: readonly FeedRead[]): FeedDay[] {
	const byDay = new Map<string, FeedRead[]>();
	for (const row of rows) byDay.set(row.date, [...(byDay.get(row.date) ?? []), row]);

	return [...byDay]
		.map(([date, group]) => {
			const tally = {
				answered: group.filter((row) => row.outcome === 'ok' && row.items > 0).length,
				failed: group.filter(failing).length,
				refused: group.filter((row) => row.outcome === 'robots_denied').length,
				resting: group.filter(skipped).length
			};
			const outcome: FeedDayOutcome =
				tally.failed > 0
					? 'failed'
					: tally.refused > 0
						? 'refused'
						: tally.answered > 0
							? 'answered'
							: 'resting';
			const parts = [
				tally.answered > 0 ? `${tally.answered} answered` : '',
				tally.failed > 0 ? `${tally.failed} failed` : '',
				tally.refused > 0 ? `${tally.refused} politely refused` : '',
				tally.resting > 0 ? `${tally.resting} not asked` : ''
			].filter(Boolean);
			return {
				date,
				outcome,
				label: `${shortDate(date)}, ${plural(group.length, 'run', 'runs')}: ${parts.join(', ')}.`
			};
		})
		.sort((a, b) => a.date.localeCompare(b.date));
}

/** What to print in the last-result cell.
 *
 * The ledger's own word for a feed that answered 200 with no entries is `ok`,
 * because that is what the fetch did. Printed raw it sits on the same row as a
 * count of fourteen failures and contradicts it, which is how a dead feed reads
 * as a healthy one.
 */
export function resultLabel(row: FeedRead): string {
	if (row.outcome === 'ok' && row.items === 0) return 'answered with nothing';
	return row.outcome;
}

/** One read, and which feed made it. */
export interface FeedRecord extends FeedRead {
	feedId: string;
}

/** How many feeds have never failed, out of how many were asked, over how many
 * runs.
 *
 * The console lists only the feeds that broke, which is the right list and half
 * an answer: four broken feeds out of eight is a collapse and four out of two
 * hundred is a Tuesday, and the page drew both identically. This is the
 * denominator, and it is a count rather than a share - the number an operator
 * acts on is how many are named below, not a percentage.
 */
export interface Reliability {
	/** Feed ids with at least one read and no failing one, alphabetically.
	 * Alphabetical because there is no order: a feed is read once a run, so
	 * every clean feed has the same record. */
	clean: string[];
	/** Feeds the pipeline has actually asked. A feed the ledger has only ever
	 * rested was never asked, so it can be neither clean nor broken and belongs
	 * in neither number. */
	checked: number;
	/** Feeds with at least one failing read. `clean.length + failed` is
	 * `checked`, always. */
	failed: number;
	/** Runs the ledger holds. This is the span "never failed" is read over, and
	 * a shallow record is why the page has a third sentence: two runs deep,
	 * "never failed" means "did not fail twice". */
	runs: number;
}

/** The whole record, not a window.
 *
 * The same span the streak beside each feed is read over, because the pipeline
 * rests on the whole count and not on a windowed one. Two spans in one section
 * is the defect the shared window exists to remove.
 */
export function reliability(rows: readonly FeedRecord[]): Reliability {
	const asked = new Map<string, FeedRecord[]>();
	for (const row of rows) {
		if (skipped(row)) continue;
		asked.set(row.feedId, [...(asked.get(row.feedId) ?? []), row]);
	}

	const clean: string[] = [];
	let failed = 0;
	for (const [feedId, reads] of asked) {
		if (reads.some(failing)) failed += 1;
		else clean.push(feedId);
	}

	return {
		clean: clean.sort((a, b) => a.localeCompare(b)),
		checked: asked.size,
		failed,
		runs: new Set(rows.map((row) => row.runId)).size
	};
}
