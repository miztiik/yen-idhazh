/** Whether the host gave our processor to somebody else's machine while we worked.
 *
 * A shared runner is one slice of a box somebody else is also renting. When the
 * hypervisor hands a time slice to another tenant, our kernel counts that slice
 * as stolen: we were ready to run and could not. A shard that loses a tenth of
 * its processor that way takes about a tenth longer for the same work, and
 * nothing in the job itself changed - so a run that reads as slow on every
 * other panel on this page can be a run that was never given the machine.
 *
 * **The busy figure used to hold both halves.** Until 2026-09-20 the item
 * ledger's busy share counted a slice the host gave elsewhere as our own work,
 * so a row older than that reports a clean machine whether or not it was one.
 * That is not recoverable after the fact: one number cannot be split back into
 * two. It is printed on the panel rather than left as a footnote, because a
 * reader comparing this month against last month would otherwise compare two
 * different measurements.
 *
 * **The expected reading is nothing.** Steal is a rare event, so a mean over a
 * day of mostly-quiet items hides the one item that lost a tenth of its
 * processor - which is the only item worth finding. Every tile here carries the
 * WORST item it covers, never a typical one.
 *
 * Pure. It reaches no disk and holds no window: the caller decides which rows a
 * tile row covers, so the day grain and the run grain are the same arithmetic
 * over different rows.
 */

/** The date the item ledger began recording the stolen share on its own.
 *
 * A source constant and not a setting (`CLAUDE.md` Guardrail #6): it is when a
 * change actually happened, and history cannot be reconfigured. The same date
 * is written into `cpu_busy_pct`'s own description in the generated contract,
 * and a test pins the two together so the correction printed here and the
 * correction recorded there cannot drift apart.
 */
export const BUSY_HELD_BOTH_BEFORE = '2026-09-20';

/** Which of the three states a tile is in.
 *
 * `unrecorded` is the one worth separating and the reason this enum exists. A
 * run that finished before the split landed recorded no stolen share at all,
 * and drawing that as a zero would tell a reader the host took nothing - which
 * is a claim this ledger cannot make about those runs. It is a fourth state
 * beside the three every other reading on this route has, and today it is what
 * every committed day draws.
 */
export type LostState = 'unrecorded' | 'quiet' | 'marked';

/** One day, or one shard, read across the items it covers. */
export interface LostTile {
	/** What the tile stands for - a date at day grain, a shard number at run grain. */
	key: string;
	/** The same, as a reader reads it. */
	label: string;
	/** The same again, in the width a tile has. Derived here rather than cut down
	 * in the markup, so no component has to know that a key is an ISO date. */
	short: string;
	state: LostState;
	/** The highest share any one item of this tile lost to another tenant. Null
	 * where no item of it carried the reading. */
	worstPct: number | null;
	/** The reading as it is printed. A quiet tile prints the share it stayed
	 * under rather than its own figure, because a true 0.04% rounds to `0.0%`
	 * and a printed zero reads as a promise the ledger did not make. */
	says: string;
	/** Items that carried the reading. */
	from: number;
	/** Items the tile covers, carried or not. */
	outOf: number;
}

/** What one span of days says, and what the page needs to say it. */
export interface ProcessorLostSpan {
	/** One tile a day, oldest first. Empty where the span holds no item row. */
	days: LostTile[];
	/** Items over the span that carried the reading. */
	from: number;
	/** Items over the span. */
	outOf: number;
	/** The worst day of the span, where one reached the share at which the panel
	 * names it. Null where none did, which is the quiet case and the common one. */
	named: LostTile | null;
	/** Days of the span that recorded the reading at all. Bounds every sentence
	 * the panel prints: a span with none says so about this span, never about
	 * every run there has ever been. */
	daysRecording: number;
}

/** One run's shards, which is a snapshot and does not follow the window. */
export interface ProcessorLostRun {
	/** The run those tiles came from. Null where no run was handed in. */
	runId: string | null;
	date: string | null;
	/** One tile a shard, by shard number. */
	shards: LostTile[];
	/** Items of the run that carried the reading. */
	from: number;
	/** Items of the run. */
	outOf: number;
}

/** The two shares the panel draws against, out of `console.*` rather than typed
 * here (Guardrail #6). */
export interface LostThresholds {
	/** At or above this share of an interval, a tile is drawn filled. */
	marked: number;
	/** At or above this share, the panel's headline sentence names the day. */
	named: number;
}

/** The run a shard row set belongs to, in the two fields that key it. */
export interface LostRunKey {
	runId: string;
	date: string;
}

function cell(value: string | undefined): number | null {
	if (value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** One tile over the rows handed in.
 *
 * The worst row wins. A row with no reading adds to `outOf` and to nothing
 * else, so a day half of whose items predate the split reports the half that
 * answered rather than a share diluted by the half that could not.
 */
function tileOf(
	key: string,
	label: string,
	short: string,
	rows: readonly Record<string, string>[],
	marked: number
): LostTile {
	let worst: number | null = null;
	let from = 0;
	for (const row of rows) {
		const share = cell(row.cpu_steal_pct);
		if (share === null) continue;
		from += 1;
		if (worst === null || share > worst) worst = share;
	}
	const counted = { key, label, short, worstPct: worst, from, outOf: rows.length };
	if (worst === null) return { ...counted, state: 'unrecorded', says: 'not recorded' };
	if (worst >= marked) return { ...counted, state: 'marked', says: `${worst.toFixed(1)}%` };
	return { ...counted, state: 'quiet', says: `under ${marked}%` };
}

function groupBy(
	rows: readonly Record<string, string>[],
	of: (row: Record<string, string>) => string
): Map<string, Record<string, string>[]> {
	const found = new Map<string, Record<string, string>[]>();
	for (const row of rows) {
		const key = of(row);
		if (key === '') continue;
		const held = found.get(key);
		if (held === undefined) found.set(key, [row]);
		else held.push(row);
	}
	return found;
}

/** What one span of days lost to another tenant, a tile a day. */
export function processorLostOverDays(
	health: readonly Record<string, string>[],
	thresholds: LostThresholds
): ProcessorLostSpan {
	const byDay = groupBy(health, (row) => row.date ?? '');
	// The year is the same on every tile of any window this control offers, so the
	// tile carries the month and day. `YYYY-` is five characters of an ISO date,
	// which is a format literal and not a setting (Guardrail #6).
	const days = [...byDay.keys()]
		.sort()
		.map((date) => tileOf(date, date, date.slice(5), byDay.get(date) ?? [], thresholds.marked));

	let named: LostTile | null = null;
	for (const day of days) {
		if (day.worstPct === null || day.worstPct < thresholds.named) continue;
		if (named === null || day.worstPct > (named.worstPct ?? 0)) named = day;
	}

	return {
		days,
		from: days.reduce((total, day) => total + day.from, 0),
		outOf: days.reduce((total, day) => total + day.outOf, 0),
		named,
		daysRecording: days.filter((day) => day.from > 0).length
	};
}

/** What one run lost to another tenant, a tile a shard.
 *
 * The newest run rather than the span, because a span cannot narrow a single
 * run: this is the row that says whether the loss landed on one shard of the
 * run or across all of them, and those are different faults.
 */
export function processorLostOverShards(
	health: readonly Record<string, string>[],
	run: LostRunKey | null,
	thresholds: LostThresholds
): ProcessorLostRun {
	if (run === null) return { runId: null, date: null, shards: [], from: 0, outOf: 0 };
	const mine = health.filter((row) => row.run_id === run.runId && (row.date ?? '') === run.date);
	const byShard = groupBy(mine, (row) => row.shard ?? '');
	const shards = [...byShard.keys()]
		.sort((left, right) => Number(left) - Number(right))
		.map((shard) =>
			tileOf(shard, `Shard ${shard}`, shard, byShard.get(shard) ?? [], thresholds.marked)
		);

	return {
		runId: run.runId,
		date: run.date,
		shards,
		from: shards.reduce((total, shard) => total + shard.from, 0),
		outOf: mine.length
	};
}
