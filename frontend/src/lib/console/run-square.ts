/** What one run's square says: the colour it is painted, and the words it carries.
 *
 * Two places print a run. The square carries the whole run in one sentence, for
 * anybody who points at it or cannot tell its colour, and the readout under the
 * figures carries the short form, one line a run. Both are written here from one
 * set of facts, and the colour is decided here from the same facts, so a red
 * square, its sentence and its line cannot describe one run three ways.
 *
 * A date is read as text, never through a `Date`, so a square cannot shift by a
 * day because the machine that built the page sat west of UTC.
 */

import { shortDate } from '../format';

/** Green: it worked. Amber: look at it. Red: it did not work. */
export type Health = 'green' | 'amber' | 'red';

export interface RunSquare {
	runId: string;
	/** Which run of the day this was, in the order the runs landed. It is not a
	 * count of the runs before it: two runs finish in parallel and the numbers
	 * may skip. */
	n: number;
	health: Health;
	/** The whole run in one sentence, on the square itself. */
	label: string;
	/** The short form the readout prints beside `Run {n}`. */
	outcome: string;
}

/** One day, and every run that wrote a manifest on it. */
export interface DayColumn {
	date: string;
	squares: RunSquare[];
}

/** The fill ramp, not the band ramp. The band tokens are text colours and a
 * solid square is not text: at text weight the light theme drew olive and
 * brick. `tokens.css` carries both ramps, and `docs/concepts/design-system.md`
 * the band a fill has to land in. */
export const HEALTH_FILL: Record<Health, string> = {
	green: 'var(--fill-high)',
	amber: 'var(--fill-medium)',
	red: 'var(--fill-low)'
};

/** What a run wrote down about itself that its colour and its words are made of. */
export interface RunFacts {
	n: number;
	status: string;
	succeeded: number;
	failed: number;
	skipped: number;
	sourceListStale: boolean;
}

/** The articles a run tried: every one it did not skip. */
export function tried(run: RunFacts): number {
	return run.succeeded + run.failed;
}

/** Whether a run fell under the success floor on the articles it tried.
 *
 * The same test paints the square red, so a square cannot say `under 70%` in
 * words while it is painted amber. The floor is the knob CI reads to decide
 * whether a run opens an issue, so a red square and an open issue cannot
 * disagree either. */
export function underFloor(run: RunFacts, floorPct: number): boolean {
	const attempted = tried(run);
	return attempted > 0 && (run.succeeded / attempted) * 100 < floorPct;
}

/** One square's colour, from what the run wrote down about itself.
 *
 * Skipped items are not failures. An article already published, or one a feed
 * repeated, is skipped by design - counting it against the run would paint a
 * healthy day amber for doing its job. So the rate is over what was tried.
 */
export function health(run: RunFacts, floorPct: number): Health {
	if (run.status === 'failed') return 'red';
	// Nothing was tried. Not a failure, but never what you expect to see.
	if (tried(run) === 0) return 'amber';
	if (underFloor(run, floorPct)) return 'red';
	if (run.failed > 0 || run.status !== 'completed' || run.sourceListStale) return 'amber';
	return 'green';
}

/** A run that finished in part while failing nothing itself was held open by an
 * article another run of the day failed and nothing published afterwards. */
function heldByAnother(run: RunFacts): boolean {
	return run.status === 'partial' && run.failed === 0;
}

const STALE = "reused yesterday's list of sources";
const HELD = "another run's failed article was still missing";

/** The sentence on the square, for anybody who points at it or cannot see it.
 *
 * Only the clauses that are true, in one fixed order, so two squares side by
 * side read alike. The cut count rides here rather than on a figure of its own.
 * Measured 2026-08-29 over 19 committed runs it is 1 to 12 articles of 160 to
 * 200, and that swing is which articles the feeds carried that hour - so drawn
 * as a published number it would read as the cap moving when nothing moved. A
 * run is where run-level facts already live.
 */
export function squareLabel(
	date: string,
	run: RunFacts,
	floorPct: number,
	readInPart: number
): string {
	return `Run ${run.n} on ${shortDate(date)}: ${runOutcome(run, floorPct, readInPart)}`;
}

/** The line the readout prints beside `Run {n}`: every clause the square's own
 * sentence carries, in the same order, so the strip a keyboard or a thumb reads
 * is the whole run and not a shorter one than a mouse used to get. */
export function runOutcome(run: RunFacts, floorPct: number, readInPart: number): string {
	const attempted = tried(run);
	const parts = [attempted === 0 ? 'nothing new to try' : `${run.succeeded} of ${attempted} succeeded`];
	if (underFloor(run, floorPct)) parts.push(`under ${floorPct}%`);
	if (run.failed > 0) parts.push(`${run.failed} failed`);
	if (run.skipped > 0) parts.push(`${run.skipped} skipped`);
	if (readInPart > 0) parts.push(`${readInPart} read only in part`);
	if (run.sourceListStale) parts.push(STALE);
	if (heldByAnother(run)) parts.push(HELD);
	if (run.status === 'failed') parts.push('the run failed');
	return parts.join(', ');
}
