/** Where one run's time went, item by item, read at build time from the published mirror.
 *
 * `frontend/public/run-timeline/<YYYY-MM>.csv` holds one row per item of one run:
 * where the item's own work began on the run's clock, how long it took, and what
 * each named step of it cost (`docs/architecture/publishing/run-timeline.md`).
 * `backend/idhazh/telemetry/publish/run_timeline.py` writes it from the per-item
 * census. This module reads it back and works out the bars, so the panel beside
 * it holds no arithmetic at all.
 *
 * **Read at build time, not fetched.** It sits under `$lib/server/` so SvelteKit
 * refuses to bundle it for a browser, the same place and for the same reason as
 * `span-rollup.ts`. Nothing on the Pipeline route waits on a network for its
 * first frame and this does not change that.
 *
 * **Two grains, one fold.** The view carries a bar per item and a bar per shard,
 * both built here in one call over one set of rows - so a step's seconds are the
 * same seconds at either grain, and the panel's switch cannot put two answers to
 * one question on the page. A shard bar was a panel of its own on a second
 * ledger until 2026-09-20, and the two panels disagreed about which run was the
 * newest because they read different files.
 *
 * **Which steps are drawn comes from the data, never from a list here.** Two of
 * the contract's eight steps - `plan` and `publish` - have no producer anywhere
 * in the pipeline today, so they are empty on every row. A hard-coded list of six
 * would draw the right thing now and the wrong thing on the day somebody times
 * one of them; folding it out of the rows means the panel picks the step up with
 * no code change, and names the absent ones to the reader in the meantime.
 *
 * Imports nothing at runtime beyond the shared CSV reader: the browser suite
 * loads this module in plain Node, where no Vite alias resolves.
 */

import { join } from 'node:path';
// Relative, not `$lib`, for the reason in the module docstring.
import { PUBLIC_ROOT, readShards, type CsvTable } from './payload';

/** Where the published mirror sits, under whichever public root this build reads. */
const TIMELINE_DIR = 'run-timeline';

/** How many month shards a read of this series opens.
 *
 * Two, which is the whole series: the panel draws ONE run and names it, so a
 * month older than the newest answers nothing, and
 * `observability.public_run_timeline_keep_months` publishes exactly two for the
 * same reason. The second is there so a run on the first of a month can still
 * reach the day before it (`CLAUDE.md` Guardrail #12).
 */
export const TIMELINE_WINDOW_MONTHS = 2;

/** The eight steps the contract declares, in the order the pipeline runs them.
 *
 * The order IS the drawing order and the index IS the colour: step `n` takes
 * `--chart-{n+1}`, eight steps against an eight-stop ramp. Fixing the pair here
 * means a step that is absent on one run and present on the next does not move
 * any other step's colour, so two runs drawn a day apart are comparable by eye.
 */
export const TIMELINE_STEPS = [
	'plan_ms',
	'fetch_ms',
	'extract_ms',
	'label_ms',
	'summary_ms',
	'visual_plan_ms',
	'score_ms',
	'publish_ms'
] as const;
export type TimelineStep = (typeof TIMELINE_STEPS)[number];

/** The two steps nothing in the pipeline times yet.
 *
 * A fact about the producer, restated here as prose the panel prints - the way
 * `SPAN_RECORD_STARTS` restates a contract changelog date. It is what lets the
 * panel tell two different silences apart: a step nothing has ever timed, and a
 * step this particular run did not record. Those are different sentences and an
 * operator acts on only one of them.
 *
 * `backend/idhazh/telemetry/publish/run_timeline.py` is where it is decided;
 * `UNTIMED_STEPS` there is the same pair, and the projection writes both columns
 * empty on every row it publishes.
 */
export const UNPRODUCED_STEPS: readonly TimelineStep[] = ['plan_ms', 'publish_ms'];

/** What each step is called beside a bar. The column is the pipeline's name; the
 * label is a reader's - a term from a stage is not a term for an operator
 * (`CLAUDE.md` section 0b). */
const STEP_LABEL: Record<TimelineStep, string> = {
	plan_ms: 'choosing it',
	fetch_ms: 'reading the page',
	extract_ms: 'taking the article out',
	label_ms: 'the label call',
	summary_ms: 'the summary call',
	visual_plan_ms: 'the visual plan',
	score_ms: 'scoring it',
	publish_ms: 'placing it'
};

/** The columns the panel reads off every row, steps excluded.
 *
 * Declared rather than implied, because the empty-column gate is written against
 * this list: a column named here that is empty on every row of the canary day is
 * a panel drawing against nothing, and the gate fails rather than letting it ship
 * (`frontend/tests/console-pipeline-timeline.spec.ts`).
 */
export const TIMELINE_COLUMNS = [
	'date',
	'run_id',
	'shard',
	'item_id',
	'start_offset_ms',
	'item_total_ms',
	'residual_ms'
] as const;

/** One item's row, as the published file holds it. */
export interface TimelineRow {
	date: string;
	runId: string;
	shard: number;
	itemId: string;
	startOffsetMs: number;
	totalMs: number;
	residualMs: number;
	/** Every step that carried a number on this row, in pipeline order. A step the
	 * row left empty is absent here, never a zero: absent means nothing timed it. */
	steps: { name: TimelineStep; ms: number }[];
}

/** One run's rows, in the order the file holds them - by start, then by item. */
export interface TimelineRun {
	runId: string;
	date: string;
	rows: TimelineRow[];
}

function whole(cell: string | undefined): number | null {
	if (cell === undefined || cell === '') return null;
	const value = Number(cell);
	return Number.isFinite(value) ? value : null;
}

/** Which run of two is the newer: latest date first, then the higher run ordinal.
 *
 * The same rule `span-rollup.ts` sorts by, so the two panels on this page cannot
 * disagree about which run is the newest one. */
function ordinalOf(runId: string): number {
	const tail = Number(runId.split('-').at(-1));
	return Number.isFinite(tail) ? tail : 0;
}

/** Fold the published rows into one entry per run, newest first.
 *
 * Pure: it reads a table and never the disk, so a header-only table folds to no
 * runs and a test reaches the empty state without a build.
 */
export function foldTimeline(table: CsvTable): TimelineRun[] {
	const runs = new Map<string, TimelineRun>();
	for (const row of table.rows) {
		const runId = row.run_id ?? '';
		const shard = whole(row.shard);
		const startOffsetMs = whole(row.start_offset_ms);
		const totalMs = whole(row.item_total_ms);
		const residualMs = whole(row.residual_ms);
		const itemId = row.item_id ?? '';
		if (runId === '' || itemId === '') continue;
		if (shard === null || startOffsetMs === null || totalMs === null || residualMs === null) continue;

		const steps: { name: TimelineStep; ms: number }[] = [];
		for (const name of TIMELINE_STEPS) {
			const ms = whole(row[name]);
			if (ms !== null) steps.push({ name, ms });
		}
		const run = runs.get(runId) ?? { runId, date: row.date ?? '', rows: [] };
		run.rows.push({ date: row.date ?? '', runId, shard, itemId, startOffsetMs, totalMs, residualMs, steps });
		runs.set(runId, run);
	}
	const built = [...runs.values()];
	built.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : ordinalOf(b.runId) - ordinalOf(a.runId)));
	return built;
}

/** Every run in the published mirror, newest first. A missing directory is empty. */
export function loadRunTimeline(months: number = TIMELINE_WINDOW_MONTHS): TimelineRun[] {
	return foldTimeline(readShards(join(PUBLIC_ROOT, TIMELINE_DIR), months));
}

// ---------------------------------------------------------------------------
// The drawable view
// ---------------------------------------------------------------------------

/** One drawn slice of an item's bar. */
export interface TimelineSegment {
	/** The step's column name. */
	name: TimelineStep;
	label: string;
	/** Which chart-ramp stop the slice takes, one-based. */
	stop: number;
	ms: number;
	/** CSS length against the run's own span, so every bar shares one clock. */
	width: string;
}

/** Which grain the panel is drawing.
 *
 * Both come out of one builder call over one set of rows, so a step's seconds
 * are the same seconds at either grain and the switch cannot put two answers to
 * one question on the page.
 */
export type TimelineGrain = 'item' | 'shard';

/** One bar placed on the run's clock - an item at the item grain, a shard at the
 * shard grain. */
export interface TimelineBar {
	/** Stable and unique within its grain: the item id, or `shard-<n>`. */
	id: string;
	/** What the gutter prints beside the bar. */
	label: string;
	shard: number;
	startOffsetMs: number;
	/** How long the bar is. An item's own clock at the item grain; at the shard
	 * grain the stretch from that shard's first item start to its last item end. */
	totalMs: number;
	/** The time inside items. The same as `totalMs` at the item grain; at the shard
	 * grain it is that shard's items added up, and it is shorter than the stretch
	 * wherever the shard spent time between them. */
	workMs: number;
	/** How many items the bar covers. One at the item grain. */
	itemCount: number;
	/** Signed, and one meaning at both grains: the stretch the named steps do not
	 * account for. Negative means two steps overlapped - the visual plan is decoded
	 * inside the summary call, so it is apportioned out of it rather than timed
	 * beside it (`backend/idhazh/contracts/run_timeline.py`). */
	residualMs: number;
	/** The steps that carried a number, in pipeline order, left to right. */
	segments: TimelineSegment[];
	/** CSS offset of the bar's left edge from the run's start. */
	offset: string;
	/** CSS length of the hollow residual drawn after the steps. Empty when the
	 * residual is not positive, and then nothing is drawn there. */
	residualWidth: string;
	/** CSS offset and length of the hatched overrun, drawn only when the residual
	 * is negative: it starts where the item actually ended and covers the part of
	 * the drawing that is counted twice. Both empty otherwise. */
	overrunOffset: string;
	overrunWidth: string;
}

/** One labelled position on the run's clock. */
export interface TimelineTick {
	/** CSS offset from the left edge. */
	at: string;
	/** What the tick stands for, in milliseconds from the run's start. */
	ms: number;
}

/** Everything the panel draws, worked out once on the server.
 *
 * A snapshot of one run and not a window: the clock is a per-run quantity and
 * narrowing a span cannot narrow a single run. The panel names the run it drew
 * instead.
 */
export interface RunTimelineView {
	empty: boolean;
	runId: string;
	date: string;
	/** One bar per item, in start order, capped at `console.timeline_bars`. */
	bars: TimelineBar[];
	/** `bars` re-ordered by the shard that ran each item, then by start - so a
	 * reader chasing one worker reads its stretch contiguously instead of picking
	 * its rows out of the run's queue. Indices into `bars`, because the same bars
	 * carried twice would put every figure in the document twice. */
	shardOrder: number[];
	/** One bar per shard, folded from the same rows `bars` draws. */
	shardBars: TimelineBar[];
	/** Every item of the run, cap included - so the panel can say what it left out. */
	itemCount: number;
	/** Shards that worked at least one item of this run, ascending. */
	shards: number[];
	/** The milliseconds the full width stands for: the run's own span, first item
	 * start to last item end. */
	spanMs: number;
	/** What the full width of the panel stands for. The same as `spanMs` unless a
	 * bar's steps overrun its own clock, and then it is the wider of the two. */
	scaleMs: number;
	/** Five labelled positions along the clock, the first at zero. */
	ticks: TimelineTick[];
	/** Every item's own time added up. Larger than `spanMs` when shards overlap,
	 * which is what parallel work looks like. */
	workMs: number;
	/** The steps that carried a number on at least one bar, in pipeline order. */
	drawn: TimelineStep[];
	/** The same steps with the word and the ramp stop the legend prints. */
	legend: { name: TimelineStep; label: string; stop: number }[];
	/** The steps of the eight that no bar of this run timed, and that nothing in
	 * the pipeline times at all. Named to the reader rather than quietly dropped:
	 * absent by design and absent because a run failed are different sentences. */
	unproduced: TimelineStep[];
	/** The steps no bar of this run timed that a producer does exist for - so this
	 * run recorded none, which is a gap in the recording rather than in the code. */
	unrecorded: TimelineStep[];
	/** How many bars carry a negative residual - two steps counted over one clock. */
	overrunCount: number;
	/** Every bar's residual added up, signed, over the whole run. */
	residualMs: number;
	/** The same at the shard grain: every shard's stretch that its named steps do
	 * not account for, added up. Larger than `residualMs`, because a shard's
	 * stretch holds the time between its items as well as the time inside one that
	 * nothing timed. */
	shardResidualMs: number;
}

/** Which chart-ramp stop a step takes: its position in `TIMELINE_STEPS`, one-based.
 *
 * Eight steps against `--chart-1` to `--chart-8` is an exact fit, and that ramp
 * deliberately holds none of the confidence hues - so no step of a pipeline can
 * be told by its colour that it is the failing one
 * (`docs/concepts/design-system.md`).
 */
export function stopOf(step: TimelineStep): number {
	return TIMELINE_STEPS.indexOf(step) + 1;
}

const EMPTY: RunTimelineView = {
	empty: true,
	runId: '',
	date: '',
	bars: [],
	shardOrder: [],
	shardBars: [],
	itemCount: 0,
	shards: [],
	spanMs: 0,
	scaleMs: 0,
	ticks: [],
	workMs: 0,
	drawn: [],
	legend: [],
	unproduced: [...UNPRODUCED_STEPS],
	unrecorded: TIMELINE_STEPS.filter((step) => !UNPRODUCED_STEPS.includes(step)),
	overrunCount: 0,
	residualMs: 0,
	shardResidualMs: 0
};

/** What one bar of either grain is made of, before it is placed on the clock. */
interface BarSource {
	id: string;
	label: string;
	shard: number;
	startOffsetMs: number;
	totalMs: number;
	workMs: number;
	itemCount: number;
	residualMs: number;
	steps: readonly { name: TimelineStep; ms: number }[];
}

/** How far right a bar reaches, steps included.
 *
 * Not the bar's own length: a bar whose steps overrun its clock is drawn past
 * its end, and a scale taken off the clock alone would push that overrun off the
 * right of the panel.
 */
function reachOf(start: number, total: number, steps: readonly { ms: number }[]): number {
	return start + Math.max(total, steps.reduce((sum, step) => sum + step.ms, 0));
}

/** Fold the run's rows to one source per shard, ascending.
 *
 * The SAME rows the item grain draws, so a step's seconds are the same seconds
 * at either grain. A shard's bar runs from its first item's start to its last
 * item's end - the stretch it held a worker for - and `workMs` is the time
 * inside its items, so the two differ by whatever the shard spent between them.
 */
function shardSources(rows: readonly TimelineRow[]): BarSource[] {
	const byShard = new Map<number, TimelineRow[]>();
	for (const row of rows) byShard.set(row.shard, [...(byShard.get(row.shard) ?? []), row]);

	return [...byShard.entries()]
		.sort((left, right) => left[0] - right[0])
		.map(([shard, own]) => {
			const startOffsetMs = Math.min(...own.map((row) => row.startOffsetMs));
			const endMs = Math.max(...own.map((row) => row.startOffsetMs + row.totalMs));
			const summed = new Map<TimelineStep, number>();
			for (const row of own)
				for (const step of row.steps) summed.set(step.name, (summed.get(step.name) ?? 0) + step.ms);
			const steps = TIMELINE_STEPS.filter((step) => summed.has(step)).map((step) => ({
				name: step,
				ms: summed.get(step) as number
			}));
			const totalMs = endMs - startOffsetMs;
			return {
				id: `shard-${shard}`,
				label: `Shard ${shard}`,
				shard,
				startOffsetMs,
				totalMs,
				workMs: own.reduce((sum, row) => sum + row.totalMs, 0),
				itemCount: own.length,
				// One meaning at both grains: the stretch the named steps do not
				// account for. At this grain it holds the time between items as well as
				// the time inside one that nothing timed, which is what the shard-clock
				// panel used to draw on a ledger of its own.
				steps,
				residualMs: totalMs - steps.reduce((sum, step) => sum + step.ms, 0)
			};
		});
}

/** Turn one run into the bars the panel draws, or an empty view.
 *
 * `bars` is capped at `barLimit` and every figure beside it is not: a cap on the
 * drawing must never become a cap on the arithmetic, or the panel reports the
 * run it drew rather than the run that ran. The shard grain is folded over every
 * row and never over the drawn ones, for the same reason.
 */
export function runTimelineView(run: TimelineRun | null, barLimit: number): RunTimelineView {
	if (run === null || run.rows.length === 0) return EMPTY;

	const spanMs = Math.max(...run.rows.map((row) => row.startOffsetMs + row.totalMs));
	const folds = shardSources(run.rows);
	// The scale covers the widest DRAWING of either grain, so a switch of grain
	// never moves a bar that did not change.
	const scaleMs = Math.max(
		spanMs,
		...run.rows.map((row) => reachOf(row.startOffsetMs, row.totalMs, row.steps)),
		...folds.map((fold) => reachOf(fold.startOffsetMs, fold.totalMs, fold.steps))
	);
	const width = (ms: number): string => `${scaleMs > 0 ? ((ms / scaleMs) * 100).toFixed(4) : 0}%`;

	const barOf = (source: BarSource): TimelineBar => {
		const named = source.steps.reduce((sum, step) => sum + step.ms, 0);
		const overruns = source.residualMs < 0;
		return {
			id: source.id,
			label: source.label,
			shard: source.shard,
			startOffsetMs: source.startOffsetMs,
			totalMs: source.totalMs,
			workMs: source.workMs,
			itemCount: source.itemCount,
			residualMs: source.residualMs,
			segments: source.steps.map((step) => ({
				name: step.name,
				label: STEP_LABEL[step.name],
				stop: stopOf(step.name),
				ms: step.ms,
				width: width(step.ms)
			})),
			offset: width(source.startOffsetMs),
			residualWidth: source.residualMs > 0 ? width(source.residualMs) : '',
			overrunOffset: overruns ? width(source.startOffsetMs + named + source.residualMs) : '',
			overrunWidth: overruns ? width(-source.residualMs) : ''
		};
	};

	const bars: TimelineBar[] = run.rows.slice(0, barLimit).map((row) =>
		barOf({
			id: row.itemId,
			label: row.itemId,
			shard: row.shard,
			startOffsetMs: row.startOffsetMs,
			totalMs: row.totalMs,
			workMs: row.totalMs,
			itemCount: 1,
			residualMs: row.residualMs,
			steps: row.steps
		})
	);

	const timed = new Set<TimelineStep>();
	for (const row of run.rows) for (const step of row.steps) timed.add(step.name);
	const drawn = TIMELINE_STEPS.filter((step) => timed.has(step));

	return {
		empty: false,
		runId: run.runId,
		date: run.date,
		bars,
		// Decided here rather than in the component: one builder call owns every
		// shape the switch offers, indices rather than a second copy of the bars.
		shardOrder: bars
			.map((bar, at) => ({ at, shard: bar.shard, start: bar.startOffsetMs }))
			.sort((left, right) => left.shard - right.shard || left.start - right.start || left.at - right.at)
			.map((one) => one.at),
		shardBars: folds.map(barOf),
		itemCount: run.rows.length,
		shards: folds.map((fold) => fold.shard),
		spanMs,
		scaleMs,
		// Five positions, the first at zero and the last at the full width. Evenly
		// spaced rather than rounded to friendly numbers: the bars are placed against
		// the run's own span, so a rounded tick would sit where no bar can reach.
		ticks: [0, 1, 2, 3, 4].map((step) => ({
			at: `${step * 25}%`,
			ms: Math.round((scaleMs * step) / 4)
		})),
		workMs: run.rows.reduce((sum, row) => sum + row.totalMs, 0),
		drawn,
		legend: drawn.map((step) => ({ name: step, label: STEP_LABEL[step], stop: stopOf(step) })),
		unproduced: TIMELINE_STEPS.filter((step) => !timed.has(step) && UNPRODUCED_STEPS.includes(step)),
		unrecorded: TIMELINE_STEPS.filter((step) => !timed.has(step) && !UNPRODUCED_STEPS.includes(step)),
		overrunCount: run.rows.filter((row) => row.residualMs < 0).length,
		residualMs: run.rows.reduce((sum, row) => sum + row.residualMs, 0),
		shardResidualMs: folds.reduce((sum, fold) => sum + fold.residualMs, 0)
	};
}
