/** Where each shard's wall clock went, read at build time from the span rollup.
 *
 * `state/span-rollup/<YYYY-MM>.csv` holds one row per `(date, run_id, shard,
 * span_name)` for the five spans no ledger column already times - `item` and the
 * four sub-steps `robots`, `tag`, `render_prompt` and `parse_reply` that nest
 * inside it (`docs/concepts/telemetry.md`). The fold that writes it also files,
 * on the `item` row alone, the shard's `unattributed_ms`: its wall clock minus
 * the time inside its item spans. So one shard reconciles exactly -
 * `item.total_ms + unattributed_ms` is the wall clock - and this module reads
 * that back so a page can draw where a shard's seconds went and how many of them
 * no span covered.
 *
 * **Nothing here is published.** It sits under `$lib/server/` so SvelteKit
 * refuses to bundle it for a browser, the same place and for the same reason as
 * `runtime-counters.ts`, and it adds no published telemetry column: `state/` is
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
import { readShards, STATE_ROOT, type CsvTable } from './payload';

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

/** Every run in the committed rollup, newest first, read through `STATE_ROOT`.
 *
 * `STATE_ROOT` and not a literal path, so the canary suite can point it at a
 * fixture tree and a page draws the fixture rollup rather than the real one -
 * the same switch every other `state/` reader is built on. A missing directory
 * is an empty read, never a throw.
 */
export function loadSpanRollup(): SpanRun[] {
	return foldRollup(readShards(join(STATE_ROOT, 'span-rollup')));
}

// ---------------------------------------------------------------------------
// The drawable view
// ---------------------------------------------------------------------------

/** One drawn slice of a shard's wall clock. */
export interface SpanSegment {
	/** A stable id: a sub-step name, `other` for the rest of the item time, or
	 * `residual` for the overhead outside every item. */
	kind: SubStep | 'other' | 'residual';
	/** What the slice is called beside the bar. */
	label: string;
	ms: number;
	/** CSS length against the widest shard's wall clock, so a short bar means a
	 * short shard rather than a differently scaled one. */
	width: string;
}

/** One shard as a bar a reader takes left to right. */
export interface SpanShardBar {
	shard: number;
	/** The shard's whole clock: the sum of every segment below. */
	wallMs: number;
	/** The time inside items - every segment but the residual. */
	itemMs: number;
	/** The overhead outside every item. Null where the shard's row predates the
	 * column, and then no residual segment is drawn. */
	residualMs: number | null;
	itemCount: number;
	/** Left to right: the four sub-steps, the rest of the item time, then the
	 * residual last - so the overhead is always the right-hand end, beside the
	 * item work and never buried inside it. */
	segments: SpanSegment[];
	/** The residual as a share of the shard's wall clock, whole percent. Null
	 * where the residual was not recorded. */
	residualPct: number | null;
}

/** Everything the panel draws, worked out once on the server.
 *
 * A snapshot of one run and not a window: the residual is a per-shard quantity
 * of one run, and narrowing a span cannot narrow a single run. The panel names
 * the run it drew instead.
 */
export interface SpanBreakdown {
	empty: boolean;
	runId: string;
	date: string;
	/** One bar per shard, ascending. */
	shards: SpanShardBar[];
	/** The milliseconds the widest bar stands for. Every bar shares it. */
	scaleMs: number;
	/** The day the record begins, for the note both states print. */
	recordStarts: string;
}

/** Turn one run into the bars the panel draws, or an empty view.
 *
 * Empty when there is no run or the run committed no reconcilable shard: the
 * real rollup is empty until a traced run folds its spans, so the empty view is
 * the ordinary state and not a failure. It carries `recordStarts` so the panel
 * can say why it is empty.
 */
export function spanBreakdown(run: SpanRun | null): SpanBreakdown {
	if (run === null || run.shards.length === 0) {
		return {
			empty: true,
			runId: run?.runId ?? '',
			date: run?.date ?? '',
			shards: [],
			scaleMs: 0,
			recordStarts: SPAN_RECORD_STARTS
		};
	}

	const scaleMs = Math.max(...run.shards.map((shard) => shard.wallMs));
	const width = (ms: number): string => `${scaleMs > 0 ? ((ms / scaleMs) * 100).toFixed(3) : 0}%`;

	const shards: SpanShardBar[] = run.shards.map((shard) => {
		const segments: SpanSegment[] = [];
		for (const stage of shard.stages) {
			segments.push({ kind: stage.name, label: STAGE_LABEL[stage.name], ms: stage.totalMs, width: width(stage.totalMs) });
		}
		segments.push({ kind: 'other', label: 'the rest of the item time', ms: shard.otherItemMs, width: width(shard.otherItemMs) });
		// The residual only where it was measured. A null residual means the wall
		// clock is unknown, so drawing a zero-width slice would claim no overhead.
		if (shard.residualMs !== null) {
			segments.push({ kind: 'residual', label: 'overhead between items', ms: shard.residualMs, width: width(shard.residualMs) });
		}
		return {
			shard: shard.shard,
			wallMs: shard.wallMs,
			itemMs: shard.itemMs,
			residualMs: shard.residualMs,
			itemCount: shard.itemCount,
			segments,
			residualPct: shard.residualMs === null || shard.wallMs === 0 ? null : Math.round((shard.residualMs / shard.wallMs) * 100)
		};
	});

	return { empty: false, runId: run.runId, date: run.date, shards, scaleMs, recordStarts: SPAN_RECORD_STARTS };
}
