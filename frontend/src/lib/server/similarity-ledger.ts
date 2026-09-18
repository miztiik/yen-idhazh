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

import { join } from 'node:path';
// Relative, not `$lib`, for the reason in `runtime-counters.ts`: the browser
// suite loads this module in plain Node, where no Vite alias resolves.
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
			maxDownStep: figure(row.max_down_step) ?? 0
		});
	}
	return [...newest.values()].sort((left, right) => left.date.localeCompare(right.date));
}
