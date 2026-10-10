/** Where the content-similarity judge's merge line sat each day, read at build time.
 *
 * `state/compact/content-similarity-judge/fitted-thresholds/` holds one row a
 * run, filed through the ledger door by the council's save job and packed by
 * the gardener: what the line was, what the evidence proposed, what the run
 * applied, and which clamp shaped it. Nothing on the published site reads it,
 * and nothing here is fetched by a browser - the route inlines what it needs
 * and the window control filters what is already in the document.
 *
 * **Bounded, like every other read on this route.** It asks the query door for
 * the packed days a window reaches and no more, so another judged day adds a
 * file this call never opens once the window is filled (`CLAUDE.md` Guardrail
 * #12). A day reaches the page once the gardener has packed it.
 *
 * Nothing here is published. It sits under `$lib/server/` so SvelteKit refuses
 * to bundle it for a browser, the same place and for the same reason as
 * `host-fingerprint.ts`.
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
// Relative, not `$lib`, for the reason in `machine-counters.ts`: the browser
// suite loads this module in plain Node, where no Vite alias resolves.
import type { TimeWindow } from '../charts/viewport';
import type { ScoreRecord } from '../console/verdict-split';
import type { RecordRead } from '../console/recording';
import type { JudgeDay } from '../console/merge-line';
import { sliceFromDisk } from './ledger-disk';
import { datedFirst, windowRows } from './ledger-rows';
import { STATE_ROOT } from './payload';

/** One run's fit. Absence is null, never zero - a held day proposed nothing,
 * which is a different fact from a day that proposed the line it already had. */
export interface FittedLine {
	date: string;
	runId: string;
	/** The line the previous run applied. Where this day started. */
	previous: number;
	/** What the walk read off the record. Null on a held day. */
	proposed: number | null;
	/** The proposal after the one-directional damping. Null when the proposal is. */
	afterDamping: number | null;
	/** The line this run wrote. Never null: a held day applies what it inherited. */
	applied: number;
	/** `none`, `step` or `guard`. Which clamp shaped the applied value. */
	clampKind: string;
	/** How far the clamp held the line back. Zero when nothing clamped. */
	clampMovement: number;
	/** `none` means a fit ran. Anything else names the gate that stopped it. */
	heldReason: string;
	/** The furthest the line could fall that day, so the band can be drawn. */
	maxDownStep: number;
	maxUpStep: number;
	/** What share of the judged pairs the two readings disagreed about. */
	disagreementRate: number;
	/** What share of the agreed readings were UNCLEAR. */
	unclearRate: number;
	/** How many distinct pairs the day file holds - what the draw dealt. */
	pairsInBand: number | null;
	/** How many pairs a judging shard read: what the disagreement rate is a share
	 * of, so a panel can print it in the same sentence as that share. Null where
	 * the row carries no answer, which is a different fact from a day that judged
	 * none. */
	pairsJudged: number | null;
	/** How many got two readings that agreed: what the unclear rate is a share
	 * of. Only these went into the record. */
	pairsUsable: number | null;
	/** Agreed NO readings the whole record holds. The slowest gate to fill. */
	negativesOnRecord: number;
	/** Judged pairs at or above the applied line. The precision reading. */
	aboveLineOnRecord: number;
	/** How many dates the record has counted. */
	daysOnRecord: number;
	/** What the cosine was worth in the record this fit read. Null on a row
	 * written before the column existed, so the caller falls back to the
	 * committed config rather than scoring at a zero nothing chose. */
	cosineWeight: number | null;
}

/** The columns of `FittedSimilarityThreshold` this reader reads, in the contract's own order.
 *
 * The door answers only the columns it is asked for. A backend contract test
 * fails when the contract renames or drops one of these, or when this order is
 * not the contract's.
 */
export const FITTED_LINE_COLUMNS = [
	'date',
	'run_id',
	'previous',
	'proposed',
	'after_damping',
	'applied',
	'clamp_kind',
	'clamp_movement',
	'held_reason',
	'max_down_step',
	'max_up_step',
	'pairs_in_band',
	'pairs_judged',
	'pairs_usable',
	'disagreement_rate',
	'unclear_rate',
	'negatives_on_record',
	'above_line_on_record',
	'days_on_record',
	'cosine_weight'
] as const;

function text(cell: string | undefined): string | null {
	const trimmed = (cell ?? '').trim();
	return trimmed === '' ? null : trimmed;
}

function figure(cell: string | undefined): number | null {
	const raw = text(cell);
	if (raw === null) return null;
	const parsed = Number(raw);
	return Number.isFinite(parsed) ? parsed : null;
}

/** The packed fitted rows inside `window`, oldest day first.
 *
 * A row with no applied value is skipped rather than refused. The panel degrades
 * to the days it can draw, and a refusal here would take a console route down
 * over one stray line (`CLAUDE.md` section 1a).
 *
 * At most one row a date survives, and it is the newest run of that date: two
 * runs of one day fitted two records and the chart draws one column a day, so
 * drawing both would put two marks on one x with nothing saying which is which.
 *
 * **No row is an ordinary state.** A record the gardener has not packed yet,
 * and a window that starts after its newest packed day, both read no row.
 */
export interface FittedReading {
	rows: FittedLine[];
	read: RecordRead;
	rates: (Pick<JudgeDay, 'date' | 'disagreementRate' | 'unclearRate' | 'pairsJudged' | 'pairsUsable' | 'heldReason'> & { runId: string })[];
	rejected: { date: string; rates: boolean }[];
}

export async function fittedLines(window: TimeWindow, root: string = STATE_ROOT): Promise<FittedReading> {
	const table = await windowRows(root, 'fitted-thresholds', window, FITTED_LINE_COLUMNS, (start, end) =>
		sliceFromDisk(root, 'fitted-thresholds', {
			columns: [...datedFirst(FITTED_LINE_COLUMNS)],
			from: start,
			to: end
		})
	);
	const newest = new Map<string, FittedLine>();
	const rates: FittedReading['rates'] = [];
	const rejected: FittedReading['rejected'] = [];
	const latest = new Map<string, (typeof table.rows)[number]>();
	for (const row of table.rows) {
		const date = text(row.date);
		const runId = text(row.run_id);
		if (date === null || runId === null) {
			console.warn('The fitted judge record contains a row without its date or run id.');
			continue;
		}
		const held = latest.get(date);
		if (held === undefined || runId > (held.run_id ?? '')) latest.set(date, { ...row, run_id: runId });
	}
	for (const [date, row] of latest) {
		const runId = row.run_id;
		const applied = figure(row.applied);
		const previous = figure(row.previous);
		const disagreementRate = figure(row.disagreement_rate);
		const unclearRate = figure(row.unclear_rate);
		if (disagreementRate !== null && unclearRate !== null) {
			rates.push({
				date, runId, disagreementRate, unclearRate,
				pairsJudged: figure(row.pairs_judged),
				pairsUsable: figure(row.pairs_usable),
				heldReason: text(row.held_reason) ?? 'none'
			});
		} else {
			rejected.push({ date, rates: true });
			console.warn(`The fitted judge record has unavailable rate measurements on ${date}.`);
		}
		const required = {
			clampMovement: figure(row.clamp_movement),
			maxDownStep: figure(row.max_down_step),
			maxUpStep: figure(row.max_up_step),
			disagreementRate,
			unclearRate,
			negativesOnRecord: figure(row.negatives_on_record),
			aboveLineOnRecord: figure(row.above_line_on_record),
			daysOnRecord: figure(row.days_on_record)
		};
		// Required measurements cannot be manufactured from blank cells.
		if (applied === null || previous === null || Object.values(required).some((value) => value === null)) {
			rejected.push({ date, rates: false });
			console.warn(`The fitted judge record has unavailable line or gate measurements on ${date}; valid rate readings are retained.`);
			continue;
		}
		newest.set(date, {
			date,
			runId,
			previous,
			proposed: figure(row.proposed),
			afterDamping: figure(row.after_damping),
			applied,
			clampKind: text(row.clamp_kind) ?? 'none',
			clampMovement: required.clampMovement!,
			heldReason: text(row.held_reason) ?? 'none',
			maxDownStep: required.maxDownStep!,
			maxUpStep: required.maxUpStep!,
			disagreementRate: required.disagreementRate!,
			unclearRate: required.unclearRate!,
			pairsInBand: figure(row.pairs_in_band),
			pairsJudged: figure(row.pairs_judged),
			pairsUsable: figure(row.pairs_usable),
			negativesOnRecord: required.negativesOnRecord!,
			aboveLineOnRecord: required.aboveLineOnRecord!,
			daysOnRecord: required.daysOnRecord!,
			cosineWeight: figure(row.cosine_weight)
		});
	}
	return {
		rows: [...newest.values()].sort((left, right) => left.date.localeCompare(right.date)),
		read: table.read,
		rates: rates.sort((left, right) => left.date.localeCompare(right.date)),
		rejected
	};
}

/** The whole score record, or null where no day has been counted into one.
 *
 * `state/content-similarity-judge/score-distribution.json` is read whole and that is the
 * point of its shape: 120 slots is a fixed size whatever the archive grows to,
 * so this costs the same on the thousandth day as on the third (Guardrail #12).
 * A record that will not parse is nothing to draw rather than a console route
 * that fails to build.
 */
export function scoreRecord(root: string = STATE_ROOT): ScoreRecord | null {
	const path = join(root, 'content-similarity-judge', 'score-distribution.json');
	if (!existsSync(path)) return null;
	try {
		const raw = JSON.parse(readFileSync(path, 'utf8'));
		const slots = Array.isArray(raw.slots) ? raw.slots : [];
		return {
			bandLow: Number(raw.band_low ?? 0),
			bandHigh: Number(raw.band_high ?? 1),
			binWidth: Number(raw.bin_width ?? 0.001),
			daysCounted: Array.isArray(raw.counted_dates) ? raw.counted_dates.length : 0,
			slots: slots.map((slot: Record<string, unknown>) => ({
				binLow: Number(slot.bin_low ?? 0),
				same: Number(slot.same_count ?? 0),
				different: Number(slot.different_count ?? 0),
				unclear: Number(slot.unclear_count ?? 0)
			}))
		};
	} catch {
		return null;
	}
}
