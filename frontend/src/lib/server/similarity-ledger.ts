/** Where the merge line sat each day, read at build time from `state/`.
 *
 * `state/story-similarity/fitted-thresholds/<YYYY>/<MM>/<DD>.csv` is one row a
 * run: what the line was, what the evidence proposed, what the run applied, and
 * which clamp shaped it. Nothing on the published site reads it, and nothing
 * here is fetched by a browser - the route inlines what it needs and the window
 * control filters what is already in the document.
 *
 * **Bounded, like every other read on this route.** It takes the day files a
 * window reaches and no more, so another judged day adds a file this call never
 * opens once the cover is filled (`CLAUDE.md` Guardrail #12).
 *
 * Nothing here is published. It sits under `$lib/server/` so SvelteKit refuses
 * to bundle it for a browser, the same place and for the same reason as
 * `host-fingerprint.ts`.
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
// Relative, not `$lib`, for the reason in `machine-counters.ts`: the browser
// suite loads this module in plain Node, where no Vite alias resolves.
import type { ScoreRecord } from '../console/verdict-split';
import { LEDGER_WINDOW_DAYS, readDayShards, STATE_ROOT } from './payload';

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
	/** How many pairs a judging leg read. The denominator both rates share, so a
	 * panel can print it in the same sentence as the share. Null where the row
	 * carries no answer, which is a different fact from a day that judged none. */
	pairsJudged: number | null;
	/** How many got two readings that agreed. Only these went into the record. */
	pairsUsable: number | null;
	/** Agreed NO readings the whole record holds. The slowest gate to fill. */
	negativesOnRecord: number;
	/** Judged pairs at or above the applied line. The precision reading. */
	aboveLineOnRecord: number;
	/** How many dates the record has folded. */
	daysOnRecord: number;
}

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

/** The newest `days` day files of the fitted record, oldest first.
 *
 * A row with no applied value is skipped rather than refused. The panel degrades
 * to the days it can draw, and a refusal here would take a console route down
 * over one stray line (`CLAUDE.md` section 1a).
 *
 * At most one row a date survives, and it is the newest run of that date: two
 * runs of one day fitted two records and the chart draws one column a day, so
 * drawing both would put two marks on one x with nothing saying which is which.
 */
export function fittedLines(
	days: number = LEDGER_WINDOW_DAYS,
	root: string = STATE_ROOT
): FittedLine[] {
	const table = readDayShards(join(root, 'story-similarity', 'fitted-thresholds'), days);
	const newest = new Map<string, FittedLine>();
	for (const row of table.rows) {
		const date = text(row.date);
		const runId = text(row.run_id);
		const applied = figure(row.applied);
		const previous = figure(row.previous);
		if (date === null || runId === null || applied === null || previous === null) continue;
		const held = newest.get(date);
		if (held !== undefined && held.runId >= runId) continue;
		newest.set(date, {
			date,
			runId,
			previous,
			proposed: figure(row.proposed),
			afterDamping: figure(row.after_damping),
			applied,
			clampKind: text(row.clamp_kind) ?? 'none',
			clampMovement: figure(row.clamp_movement) ?? 0,
			heldReason: text(row.held_reason) ?? 'none',
			maxDownStep: figure(row.max_down_step) ?? 0,
			maxUpStep: figure(row.max_up_step) ?? 0,
			disagreementRate: figure(row.disagreement_rate) ?? 0,
			unclearRate: figure(row.unclear_rate) ?? 0,
			pairsInBand: figure(row.pairs_in_band),
			pairsJudged: figure(row.pairs_judged),
			pairsUsable: figure(row.pairs_usable),
			negativesOnRecord: figure(row.negatives_on_record) ?? 0,
			aboveLineOnRecord: figure(row.above_line_on_record) ?? 0,
			daysOnRecord: figure(row.days_on_record) ?? 0
		});
	}
	return [...newest.values()].sort((left, right) => left.date.localeCompare(right.date));
}

/** The whole score record, or null where no day has folded one.
 *
 * `state/story-similarity/score-distribution.json` is read whole and that is the
 * point of its shape: 120 slots is a fixed size whatever the archive grows to,
 * so this costs the same on the thousandth day as on the third (Guardrail #12).
 * A record that will not parse is nothing to draw rather than a console route
 * that fails to build.
 */
export function scoreRecord(root: string = STATE_ROOT): ScoreRecord | null {
	const path = join(root, 'story-similarity', 'score-distribution.json');
	if (!existsSync(path)) return null;
	try {
		const raw = JSON.parse(readFileSync(path, 'utf8'));
		const slots = Array.isArray(raw.slots) ? raw.slots : [];
		return {
			bandLow: Number(raw.band_low ?? 0),
			bandHigh: Number(raw.band_high ?? 1),
			binWidth: Number(raw.bin_width ?? 0.001),
			daysFolded: Array.isArray(raw.folded_dates) ? raw.folded_dates.length : 0,
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
