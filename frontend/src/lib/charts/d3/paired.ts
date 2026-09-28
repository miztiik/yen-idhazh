/** What the change moved: each measure before and after, on one axis centred on no change.
 *
 * Measures in different units cannot share a scale, so each is drawn against
 * itself: before sits at 100 percent on every row and after sits wherever it
 * landed. The axis is `swapScale`'s from `series.ts` - symmetric about no
 * change, with a least half-width - because a lopsided axis would draw a fifth
 * off as a longer track than a fifth on.
 *
 * **The floor is per row, and per side.** A rate over too few attempts is a
 * rounding error wearing a percentage, so a row either side of which made fewer
 * than `minAttempts` attempts draws nothing and says why, and the other rows
 * still draw. The geometry is null only where no row can be drawn at all.
 */
import { swapScale } from '../series';

export interface PairedInput {
	label: string;
	before: number;
	after: number;
	/** The attempts each side's rate was taken over. */
	attempts: { before: number; after: number };
}

export interface PairedOptions {
	/** The fewest attempts a rate is drawn from - `console.min_attempts_for_rate`. */
	minAttempts: number;
}

export interface PairedRow {
	label: string;
	before: number;
	after: number;
	/** After as a percent of before, or null where the row is not drawn. */
	percent: number | null;
	/** Where after sits, as a share of the plot from its left edge. Before is
	 * always at the centre. Null where the row is not drawn. */
	at: number | null;
	/** Why the row draws nothing, in words, or null where it draws. */
	reason: string | null;
}

export interface PairedGeometry {
	/** Percentage points either side of no change. */
	half: number;
	/** Low, no change, high. */
	ticks: [number, number, number];
	rows: PairedRow[];
}

function shortOn(row: PairedInput, floor: number): 'before' | 'after' | 'both' | null {
	const before = row.attempts.before < floor;
	const after = row.attempts.after < floor;
	if (before && after) return 'both';
	if (before) return 'before';
	if (after) return 'after';
	return null;
}

/** Why a row draws nothing, or null where it draws. */
function reasonFor(row: PairedInput, floor: number): string | null {
	const short = shortOn(row, floor);
	if (short === 'both') return `Fewer than ${floor} attempts before the change and after it, so there is no rate to compare.`;
	if (short !== null) return `Fewer than ${floor} attempts ${short} the change, so there is no rate to compare.`;
	if (!Number.isFinite(row.before) || !Number.isFinite(row.after)) {
		return 'Recorded on one side of the change only, so there is nothing to compare.';
	}
	if (row.before === 0) return 'Nothing before the change to compare against: a move away from nothing has no size.';
	return null;
}

/** Why there is no chart at all, in words, or null where at least one row draws.
 *
 * Only the attempts floor is a shortfall. A set with no rows is quiet, and a
 * set whose rows fail for another reason says so row by row.
 */
export function pairedShortfall(rows: readonly PairedInput[], opts: PairedOptions): string | null {
	if (rows.length === 0 || !rows.every((row) => shortOn(row, opts.minAttempts) !== null)) return null;
	return `Every measure made fewer than ${opts.minAttempts} attempts on one side of the change or both, so no rate is drawn.`;
}

/** The rows on one shared axis, or null where no row can be drawn. */
export function paired(rows: readonly PairedInput[], opts: PairedOptions): PairedGeometry | null {
	const judged = rows.map((row) => {
		const reason = reasonFor(row, opts.minAttempts);
		return { row, reason, percent: reason === null ? (row.after / row.before) * 100 : null };
	});
	const drawn = judged.flatMap((entry) => (entry.percent === null ? [] : [entry.percent]));
	if (drawn.length === 0) return null;
	const scale = swapScale(drawn);
	return {
		half: scale.half,
		ticks: scale.ticks,
		rows: judged.map(({ row, reason, percent }) => ({
			label: row.label,
			before: row.before,
			after: row.after,
			percent,
			at: percent === null ? null : scale.at(percent),
			reason
		}))
	};
}
