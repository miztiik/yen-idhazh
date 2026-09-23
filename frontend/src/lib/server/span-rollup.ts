/** The four sub-steps of a run's clock, read at build time from the span rollup.
 *
 * `state/span-rollup/<YYYY>/<MM>/<DD>/` holds one row per `(date, run_id, shard,
 * span_name)` for the five spans no ledger column already times - `item` and the
 * four sub-steps `robots`, `tag`, `render_prompt` and `parse_reply` that nest
 * inside it (`docs/concepts/telemetry.md`). The fold that writes it also files,
 * on the `item` row alone, the shard's `unattributed_ms`: its wall clock minus
 * the time inside its item spans. So one shard reconciles exactly -
 * `item.total_ms + unattributed_ms` is the wall clock - and this module reads
 * that back.
 *
 * **What it returns is figures, not a drawing.** A panel drew this split per
 * shard until 2026-09-20. Measured over 23 shard rows of the committed rollup,
 * the four sub-steps together came to 0.026 px of a 760 px track and the
 * residual to 0.039 px, so a browser painted neither and the legend taught a
 * reader that four categories were zero when they were only unmeasurable at that
 * scale. The figures survive as printed figures beside the merged timing panel
 * on the Pipeline route, which is where every one of them was already legible -
 * none of them was ever visible as a band.
 *
 * **Nothing here is published.** It sits under `$lib/server/` so SvelteKit
 * refuses to bundle it for a browser, the same place and for the same reason as
 * `machine-counters.ts`, and it adds no published telemetry column: `state/` is
 * not served and no cell of it crosses to a reader.
 *
 * **The record has a start, and a reader is told it.** The rollup committed its
 * first row on the day tracing went on across the pipeline (`SPAN_RECORD_STARTS`).
 * A run before then timed its stages but did not commit them, so there is nothing
 * to draw for any earlier day - a discontinuity, not a run that did no work. Both
 * states this module can be in name it.
 *
 * Imports nothing at runtime beyond the shared CSV reader: the browser suite
 * loads this module in plain Node, where no Vite alias resolves.
 */

import { join } from 'node:path';
// Relative, not `$lib`, for the reason in the module docstring.
import {
	LEDGER_WINDOW_DAYS,
	LEDGER_WINDOW_MONTHS,
	readDayShards,
	readShards,
	STATE_ROOT,
	type CsvTable
} from './payload';

/** The day the span record begins.
 *
 * The date the `span-rollup-row` contract's first changelog entry carries
 * (`backend/idhazh/contracts/span_rollup.py`): a fact about when the column was
 * added, restated here as prose the panel prints. Not a `config/` knob - tuning
 * it would move a historical boundary rather than a behaviour.
 */
export const SPAN_RECORD_STARTS = '2026-09-06';

/** The five spans the rollup commits, in the order the fold writes them: the
 * `item` parent first, then the four sub-steps in pipeline order. */
export const ROLLUP_SPANS = ['item', 'robots', 'tag', 'render_prompt', 'parse_reply'] as const;
export type RollupSpanName = (typeof ROLLUP_SPANS)[number];

/** The four sub-steps, `item` excluded: `item` is the parent the four nest
 * inside, so its time is not a sixth slice beside them. */
export const SUB_STEPS = ['robots', 'tag', 'render_prompt', 'parse_reply'] as const;
export type SubStep = (typeof SUB_STEPS)[number];

/** What each sub-step is called on the page. The id is the pipeline's; the label
 * is a reader's - a term from a stage is not a term for an operator. */
const STAGE_LABEL: Record<SubStep, string> = {
	robots: 'robots check',
	tag: 'tag read',
	render_prompt: 'prompt build',
	parse_reply: 'reply parse'
};

/** Where each sub-step runs, because none of the four is a stage of its own.
 *
 * `tag` opens inside the extract span and `render_prompt` and `parse_reply` open
 * inside the summary call (`backend/idhazh/stages/common.py`,
 * `backend/idhazh/stages/two_calls.py`), so their seconds are already counted by
 * the step they nest in. A reader who takes `tag read` for a step beside extract
 * adds it twice.
 */
const STAGE_INSIDE: Record<SubStep, string> = {
	robots: 'the robots check before a page is read',
	tag: 'the tagging step inside taking the article out',
	render_prompt: 'building the prompt inside the summary call',
	parse_reply: 'reading the reply inside the summary call'
};

/** One sub-step a shard committed. */
interface StageSpan {
	name: SubStep;
	/** How many spans of this name the shard opened. */
	count: number;
	/** Every span of this name added together, whole milliseconds. */
	totalMs: number;
}

/** One shard's spans, folded back out of the rollup rows.
 *
 * `itemMs` and `residualMs` are the two disjoint halves of the shard's wall
 * clock: the time inside its items, and the overhead outside every item. The
 * sub-steps are slices of `itemMs`, not additions to it.
 */
export interface ShardSpans {
	shard: number;
	/** The item row's count - how many items the shard timed. */
	itemCount: number;
	/** The item row's `total_ms` - the time inside the shard's item spans. */
	itemMs: number;
	/** The item row's `unattributed_ms` - the shard's overhead outside every
	 * item. Null on a row written before the column existed, which is absence and
	 * not zero overhead measured. */
	residualMs: number | null;
	/** `itemMs + (residualMs ?? 0)`: the shard's wall clock when the residual is
	 * known, its item time alone when it is not. */
	wallMs: number;
	/** The sub-steps the shard committed, in fold order. A step the shard never
	 * opened is absent, not a zero. */
	stages: StageSpan[];
	/** The sub-steps added together. */
	namedMs: number;
	/** `itemMs` minus the named sub-steps: the item time no committed sub-step
	 * covers - the fetch outside `robots`, the extract outside `tag`, the model
	 * call, the score. Never below zero, because the four nest in different stages
	 * of one item and so cannot together outrun it. */
	otherItemMs: number;
}

/** One run, made of the shards that committed an item row for it. */
export interface SpanRun {
	runId: string;
	date: string;
	/** One entry per shard that committed an item row, ascending. */
	shards: ShardSpans[];
}

/** Which run of the two is the newer: latest date first, then the higher run
 * ordinal, so `2026-09-06-10` sorts after `2026-09-06-2` rather than before it. */
function ordinalOf(runId: string): number {
	const tail = Number(runId.split('-').at(-1));
	return Number.isFinite(tail) ? tail : 0;
}

/** Fold the rollup rows to one entry per run, newest first.
 *
 * Pure: it reads a table and never the disk, so a header-only table - a rollup
 * truncated to its header - folds to no runs, and a test can reach the empty
 * state without a build. Every `(run, shard, span_name)` is one row by contract
 * (`SPAN_ROLLUP_KEY`), so there is nothing to add up here; the fold only groups.
 */
export function foldRollup(table: CsvTable): SpanRun[] {
	const runs = new Map<
		string,
		{ date: string; shards: Map<number, Map<string, { count: number; totalMs: number; residualMs: number | null }>> }
	>();

	for (const row of table.rows) {
		const runId = row.run_id ?? '';
		const name = row.span_name ?? '';
		const shard = Number(row.shard);
		if (runId === '' || !Number.isInteger(shard) || shard < 0) continue;
		if (!(ROLLUP_SPANS as readonly string[]).includes(name)) continue;

		const totalMs = Number(row.total_ms);
		const count = Number(row.count);
		if (!Number.isFinite(totalMs) || !Number.isFinite(count)) continue;

		// The residual rides on the item row only, and is empty on the other four
		// and on any row written before the column existed. Empty is absence, never
		// a measured zero.
		const residualCell = row.unattributed_ms ?? '';
		const residualMs =
			name === 'item' && residualCell !== '' && Number.isFinite(Number(residualCell))
				? Number(residualCell)
				: null;

		const run = runs.get(runId) ?? { date: row.date ?? '', shards: new Map() };
		const shardSpans = run.shards.get(shard) ?? new Map();
		shardSpans.set(name, { count, totalMs, residualMs });
		run.shards.set(shard, shardSpans);
		runs.set(runId, run);
	}

	const built: SpanRun[] = [];
	for (const [runId, run] of runs) {
		const shards: ShardSpans[] = [];
		for (const [shard, spanMap] of [...run.shards].sort((a, b) => a[0] - b[0])) {
			const item = spanMap.get('item');
			// A shard with no item row cannot be reconciled - the residual and the
			// wall clock both hang off it - so it is left out rather than drawn as a
			// shard whose time is unknown.
			if (item === undefined) continue;

			const stages: StageSpan[] = [];
			for (const step of SUB_STEPS) {
				const found = spanMap.get(step);
				if (found !== undefined) stages.push({ name: step, count: found.count, totalMs: found.totalMs });
			}
			const namedMs = stages.reduce((sum, stage) => sum + stage.totalMs, 0);
			const itemMs = item.totalMs;
			const residualMs = item.residualMs;
			shards.push({
				shard,
				itemCount: item.count,
				itemMs,
				residualMs,
				wallMs: itemMs + (residualMs ?? 0),
				stages,
				namedMs,
				otherItemMs: Math.max(0, itemMs - namedMs)
			});
		}
		built.push({ runId, date: run.date, shards });
	}

	built.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : ordinalOf(b.runId) - ordinalOf(a.runId)));
	return built;
}

/** The newest runs in the committed rollup, newest first, read through `STATE_ROOT`.
 *
 * `STATE_ROOT` and not a literal path, so the canary suite can point it at a
 * fixture tree and a page draws the fixture rollup rather than the real one -
 * the same switch every other `state/` reader is built on. A missing directory
 * is an empty read, never a throw.
 *
 * **It reads both grains and adds them together.** The rollup is a day tree
 * now that more than one job writes it, and a month shard is what a tree still
 * carrying pre-migration history holds. Only one of the two shapes is ever on
 * disk, so the sum is exactly what is there - and a reader that knew only one
 * of them would draw an empty panel against the other.
 *
 * `months` is the month grain's cover, and the caller wants the newest entry:
 * reading the newest few shards answers that and reading every one of them
 * answers it no better (`CLAUDE.md` Guardrail #12). The day grain takes
 * `LEDGER_WINDOW_DAYS`, the same 91 days every other day-grain ledger here is
 * read over, so the two covers reach about the same distance back.
 */
export function loadSpanRollup(months: number = LEDGER_WINDOW_MONTHS): SpanRun[] {
	const dir = join(STATE_ROOT, 'span-rollup');
	const byMonth = readShards(dir, months);
	const byDay = readDayShards(dir, LEDGER_WINDOW_DAYS);
	return foldRollup({
		rows: [...byMonth.rows, ...byDay.rows],
		columns: byMonth.columns.length > 0 ? byMonth.columns : byDay.columns
	});
}

// ---------------------------------------------------------------------------
// The printed readout
// ---------------------------------------------------------------------------

/** One sub-step as a figure a reader takes off the page.
 *
 * A figure and never a slice: the four together draw far under a pixel of the
 * configured track, and a band that small is a legend entry with no mark
 * (`docs/concepts/console-design.md`).
 */
export interface SubStepFigure {
	name: SubStep;
	/** What the step is called. */
	label: string;
	/** Where it runs. None of the four is a stage of its own - `tag read` is the
	 * tagging step inside taking the article out, not a step beside it - and a
	 * figure read as a stage is a figure read wrong. */
	inside: string;
	/** Every span of this name, across every shard of the run. */
	ms: number;
	/** How many spans of this name the run opened. */
	count: number;
	/** How wide this figure would draw on the configured track, in CSS pixels. */
	px: number;
}

/** The four sub-steps of one run, and the overhead outside every item.
 *
 * What survives of the panel that drew a shard's clock as a split. Every figure
 * it carried is here; none of them was ever visible, because the split it drew
 * was under a pixel wide.
 */
export interface SubStepReadout {
	empty: boolean;
	runId: string;
	date: string;
	/** How many shards of the run committed a reconcilable item row. */
	shardCount: number;
	/** One figure per sub-step the run committed a row for, in fold order. A step
	 * no shard opened gets no figure and no legend key - a key for an absent
	 * series is a claim the data does not support. */
	steps: SubStepFigure[];
	/** The figures above added together. */
	namedMs: number;
	/** The time inside the run's items - the clock the four are a slice of. */
	itemMs: number;
	/** The overhead outside every item, added over the shards that recorded it.
	 * Null where none did, which is a missing reading and not zero overhead. */
	residualMs: number | null;
	/** `itemMs` plus that overhead: the shards' wall clock added up. */
	wallMs: number;
	/** The narrowest figure's width on the configured track, in CSS pixels. */
	smallestPx: number;
	/** The track the widths were measured against, in CSS pixels. */
	trackPx: number;
	/** True where the narrowest band would draw under one pixel, so the split is
	 * printed rather than drawn. */
	printed: boolean;
	/** The day the record begins, for the note both states print. */
	recordStarts: string;
}

/** Reduce one run's rollup to the figures the merged timing panel prints.
 *
 * `trackPx` is `console.chart_width`, which is what decides whether a band is
 * paintable: the rule is measured in pixels of a real track, so the track has to
 * be handed in rather than assumed here.
 */
export function subStepReadout(run: SpanRun | null, trackPx: number): SubStepReadout {
	if (run === null || run.shards.length === 0) {
		return {
			empty: true,
			runId: run?.runId ?? '',
			date: run?.date ?? '',
			shardCount: 0,
			steps: [],
			namedMs: 0,
			itemMs: 0,
			residualMs: null,
			wallMs: 0,
			smallestPx: 0,
			trackPx,
			printed: true,
			recordStarts: SPAN_RECORD_STARTS
		};
	}

	const summed = new Map<SubStep, { ms: number; count: number }>();
	for (const shard of run.shards)
		for (const stage of shard.stages) {
			const found = summed.get(stage.name) ?? { ms: 0, count: 0 };
			summed.set(stage.name, { ms: found.ms + stage.totalMs, count: found.count + stage.count });
		}

	const itemMs = run.shards.reduce((sum, shard) => sum + shard.itemMs, 0);
	const recorded = run.shards.filter((shard) => shard.residualMs !== null);
	const residualMs =
		recorded.length === 0 ? null : recorded.reduce((sum, shard) => sum + (shard.residualMs ?? 0), 0);
	const wallMs = itemMs + (residualMs ?? 0);
	// Measured against the wall clock, because that is what a bar of this run
	// would be drawn to.
	const pxOf = (ms: number): number => (wallMs > 0 ? (ms / wallMs) * trackPx : 0);

	const steps: SubStepFigure[] = SUB_STEPS.filter((step) => summed.has(step)).map((step) => {
		const found = summed.get(step) as { ms: number; count: number };
		return {
			name: step,
			label: STAGE_LABEL[step],
			inside: STAGE_INSIDE[step],
			ms: found.ms,
			count: found.count,
			px: pxOf(found.ms)
		};
	});

	const namedMs = steps.reduce((sum, step) => sum + step.ms, 0);
	const smallestPx = steps.length === 0 ? 0 : Math.min(...steps.map((step) => step.px));

	return {
		empty: false,
		runId: run.runId,
		date: run.date,
		shardCount: run.shards.length,
		steps,
		namedMs,
		itemMs,
		residualMs,
		wallMs,
		smallestPx,
		trackPx,
		printed: steps.length === 0 || smallestPx < 1,
		recordStarts: SPAN_RECORD_STARTS
	};
}
