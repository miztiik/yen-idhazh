<script lang="ts">
	/** Is it getting slower? That is the only question this section is asked.
	 *
	 * The block used to be one group of four bars per day. At a 30-day window
	 * that is about 150 rows and no trend at all, which answers the question by
	 * making the operator hold thirty numbers in their head.
	 *
	 * Three stages, and they are the three an item waits on. Scoring was a fourth
	 * line here until 2026-08-31, and on a chart titled `Time per item, by stage`
	 * a fourth line reads as a fourth thing the run is held up by. It is not: the
	 * scorer reads a summary the model has already finished. It moved to the Model
	 * route, beside the cost of writing the summary it checks.
	 *
	 * The y axis is decades. Four stages on one linear scale answered for one
	 * of them: `summarize` at 110.6 s set the domain on its own and `extract`
	 * at 42 ms drew flat on the baseline, so three stages shared 2.5% of the
	 * plot height (measured 2026-08-25 on the committed ledger). On a log axis
	 * a tenth added to `extract` and a tenth added to `summarize` are the same
	 * vertical move, so the axis measures change at every size. The composition
	 * survives it: `summarize` is still on top, `extract` still at the bottom,
	 * and the gap still reads as about three decades. The padded linear domain
	 * in `frame.ts` remains the rule for series of comparable size; it yields
	 * here because the drawn extent spans more than two decades.
	 *
	 * The x axis is the window the page's control set, not the list of days that
	 * have rows. A chart that sized itself to its own data drew six columns under
	 * a control reading thirty, and two spans on one page cannot be compared.
	 * Three different facts used to arrive here as one missing number, and each
	 * one now draws as itself. A day nothing timed breaks the line. A day measured
	 * at zero breaks it too and draws an open dot on the baseline rule: zero has
	 * no position on a decade axis, and clamping it into the bottom decade draws
	 * a plunge that says the stage got a thousand times faster. A day timed for
	 * some of its items draws the items it timed. One line of type under the
	 * chart names whichever of the three happened, because a hole in a line is a
	 * mystery and three holes that look alike are worse than one.
	 *
	 * Three stages, three categorical colours, bound to the stage and never to
	 * its rank, so sorting the legend never repaints a line. The health ramp is
	 * not lent out: on a page where green means a clean run and red means a
	 * failed one, a red fetch line beside a green extract line reads as "fetch is
	 * broken" when it only means "these are two different stages".
	 *
	 * The strip under the plot is the legend AND the readout, because they were
	 * the same four numbers. It opens on the newest day and follows a pointer or
	 * an arrow key; the row order is fixed by the newest day and never re-sorts
	 * under the eye.
	 */
	import {
		chartWidth,
		coverage,
		coverageRegions,
		coverageRegionTitle,
		coverageSentence,
		dayColumns,
		dayColumnX,
		dayTicks,
		frame,
		logAxis,
		MARGIN,
		MODEL_RULE_ROW,
		modelRules,
		modelRuleTitle,
		noModelRuleNote,
		notMeasuredRow,
		observeWidth,
		pointerReadout,
		readoutMarks,
		type DayReadout
	} from '$lib/charts/frame';
	import ChartReadout from './ChartReadout.svelte';
	import { shortDate } from '$lib/format';
	import type { StageTiming, StageTimingDay } from '$lib/charts/series';
	import { daysInWindow, type TimeWindow } from '$lib/charts/viewport';

	let {
		days,
		span,
		height,
		width,
		tickDensity,
		readoutMaxShare,
		modelChanges = []
	}: {
		days: StageTimingDay[];
		span: TimeWindow;
		height: number;
		width: number;
		tickDensity: number;
		readoutMaxShare: number;
		/** Every day the summarizing pipeline changed, derived once on the server.
		 *
		 * This chart qualifies for the rule because two of its three lines are
		 * drawn by things the stamp covers: `summarize` is the model writing, and
		 * `extract` moves with the extractor version the same stamp digests. A step
		 * in either that lines up with a rule has a candidate cause. */
		modelChanges?: string[];
	} = $props();

	const STAGES = [
		{ key: 'fetch', label: 'fetch', colour: 'var(--series-1)' },
		{ key: 'extract', label: 'extract', colour: 'var(--series-2)' },
		{ key: 'summarize', label: 'summarize', colour: 'var(--series-3)' }
	] as const;

	type Stage = (typeof STAGES)[number];

	/** A decade label is `1000 s`, not `150`. The shared margin sizes the left
	 * column for a tick number, so this axis buys one more column of its own. */
	const LABEL_ROOM = 16;
	const PLOT_MARGIN = { ...MARGIN, left: MARGIN.left + LABEL_ROOM };
	/** The eight steps inside a decade. Without them a log axis reads as a
	 * linear one with odd labels; the bunching towards the top of each decade
	 * is the signature of the scale. Stubs on the axis only - 32 full-width
	 * rules is a hatch, not an axis. */
	const MINOR_STEPS = [2, 3, 4, 5, 6, 7, 8, 9];

	interface Point {
		x: number;
		y: number;
	}

	/** The server draws at the knob; the client redraws once it has measured the
	 * column it actually got, so one unit is one CSS pixel. */
	let measured = $state<number | null>(null);
	/** Which column the pointer or the arrow keys are on, or null for none. */
	let selected = $state<number | null>(null);
	const box = $derived(frame(chartWidth(measured, width), height, PLOT_MARGIN));

	/** The columns are the window the operator set, not the days that happen to
	 * carry a row. A chart that shrinks to its own data while the control above it
	 * reads 30 days puts two spans on one page, and the two cannot be compared -
	 * which is the question the operator came here to ask. */
	const calendar = $derived(daysInWindow(span));
	const ordered = $derived(
		days
			.filter((day) => day.date >= span.start && day.date <= span.end)
			.sort((a, b) => a.date.localeCompare(b.date))
	);
	const byDate = $derived(new Map(ordered.map((day) => [day.date, day])));
	/** Every stage timing in the window, data only. Split from the scale so a
	 * resize reuses this pass instead of walking the window again for a new plot
	 * height. */
	const stageValues = $derived(
		ordered
			.flatMap((day) => STAGES.map((stage) => day[stage.key].ms))
			.filter((ms): ms is number => ms !== null)
	);
	/** Whole decades, rounded outward to the decade that holds the data. That is
	 * the log form of the rounding rule, not an exception to it. */
	const scale = $derived(logAxis(stageValues, [box.bottom, box.top]));
	/** The raw extent of the timings, bound to the data alone: a resize cannot
	 * move it and a window change can. Published so a test can hold the split. */
	const timingExtent = $derived(
		stageValues.length === 0
			? ''
			: `${Math.min(...stageValues)},${Math.max(...stageValues)}`
	);
	const minorTicks = $derived(
		scale.ticks
			.flatMap((decade) => MINOR_STEPS.map((factor) => factor * decade))
			.filter((value) => value < scale.domain[1])
	);
	/** One array of column pixels, so the ticks, the marks and the model rules
	 * cannot disagree about where a day sits. */
	const columnsX = $derived(dayColumns(calendar.length, box));
	const axis = $derived(dayTicks(calendar, { density: tickDensity, columns: columnsX }));
	/** The days the pipeline changed, of the days this chart drew. */
	const rules = $derived(modelRules(modelChanges, calendar, columnsX));
	const changedOn = $derived(new Set(rules.map((rule) => rule.date)));
	const newest = $derived(ordered[ordered.length - 1] ?? null);

	/** A stage is on the chart where the window timed it at all, a zero
	 * included: a measured zero is a number, and it has a mark of its own. */
	const drawn = $derived(
		STAGES.filter((stage) => calendar.some((date) => timedOn(date, stage.key) > 0))
	);
	/** Tallest first, so a label is matched to a line by position and not by
	 * colour alone. It reorders only when two stages have changed places, which
	 * is when the operator wants to notice. A stage with no number on the newest
	 * day has nothing to sort on and sits last. */
	const legend = $derived([...STAGES].sort((a, b) => (newestOf(b) ?? -1) - (newestOf(a) ?? -1)));

	/** Which columns carry a timing at all. A day the window covered and nothing
	 * timed is the fact this chart used to draw as a hole in three lines. */
	const timed = $derived(
		calendar.map((date) => STAGES.some((stage) => timedOn(date, stage.key) > 0))
	);
	const covered = $derived(coverage(timed));
	/** The spans nothing timed, drawn under everything else so a tint never
	 * covers a mark. */
	const emptySpans = $derived(coverageRegions(covered, calendar, columnsX, box));
	/** The days this chart drew a timing on, and the items behind them.
	 *
	 * The denominator is the day's own item count, never the sum of the three
	 * stages' totals - one item waits on all three, so summing counts it three
	 * times. Where the stages reached different amounts of the same days the
	 * numerator is a range, because picking one of them would be arbitrary. */
	const timedItems = $derived.by(() => {
		const withTiming = calendar
			.filter((_, index) => timed[index])
			.map((date) => byDate.get(date));
		const total = withTiming.reduce((sum, day) => sum + (day?.items ?? 0), 0);
		const perStage = drawn.map((stage) =>
			withTiming.reduce((sum, day) => sum + (day?.[stage.key].timed ?? 0), 0)
		);
		if (perStage.length === 0 || total === 0) return null;
		return { low: Math.min(...perStage), high: Math.max(...perStage), total };
	});
	/** One sentence for the whole chart, whatever the series count.
	 *
	 * It was one note per stage, and the three said the same window-level fact
	 * three times in near-identical words - so a fourth stage would have made it
	 * four. Null where every day was timed in full: a sentence that only ever
	 * says "all of it" is noise. */
	const coverageNote = $derived(coverageSentence(covered, 'We timed', timedItems));
	/** Every drawn stage's geometry, built once. The runs, the marks and the
	 * zeros were three functions the template called per stage on every render,
	 * so a pointer move walked the window three times a stage for a picture that
	 * had not moved. Held here they rebuild only when the data or the plot box
	 * does. */
	const paths = $derived(
		drawn.map((stage) => ({
			stage,
			runs: runs(stage.key),
			marks: marksOf(stage.key),
			zeros: zeros(stage.key)
		}))
	);
	/** Whether any stage drew an open dot, so the sentence that explains one is
	 * printed where there is one and nowhere else. */
	const anyZero = $derived(paths.some((path) => path.zeros.length > 0));

	/** One column per day, whether or not the day timed anything. A column the
	 * strip skipped would be a day an arrow key steps over without saying so.
	 *
	 * A day nothing timed prints one sentence rather than three `not timed`
	 * rows. Measured, the hover worked on those columns and still read as broken,
	 * because four columns in five carried a date and no values. */
	const columns = $derived<DayReadout[]>(
		calendar.map((date, index) => ({
			x: x(index),
			date: shortDate(date),
			rows: timed[index]
				? [
						...legend.map((stage) => ({
							label: stage.label,
							value: reading(at(date, stage.key)),
							colour: stage.colour
						})),
						// The rule is a mark on the plot and a line in the strip, so a reader
						// stepping the days with an arrow key meets it without a pointer.
						...(changedOn.has(date) ? [MODEL_RULE_ROW] : [])
					]
				: [
						notMeasuredRow('Nothing was timed on this day'),
						...(changedOn.has(date) ? [MODEL_RULE_ROW] : [])
					]
		}))
	);
	const marks = $derived(readoutMarks(columns));
	/** The strip opens on the newest day the window timed, so it is never blank
	 * and never shifts the page as it fills. Not the window's last column: a
	 * window runs to today and a run can be hours away, so that column is often
	 * four `not timed` rows, which is not a resting state anybody can read. */
	const resting = $derived(
		columns.length === 0
			? null
			: (columns[newest === null ? columns.length - 1 : calendar.indexOf(newest.date)] ??
				columns[columns.length - 1])
	);
	const readout = $derived(selected === null ? resting : (columns[selected] ?? resting));
	const guide = $derived(selected === null ? null : (columns[selected]?.x ?? null));

	function timingOn(date: string, key: Stage['key']): StageTiming | null {
		return byDate.get(date)?.[key] ?? null;
	}

	/** How many of the day's items the stage timed. No row at all is none. */
	function timedOn(date: string, key: Stage['key']): number {
		return timingOn(date, key)?.timed ?? 0;
	}

	/** The day's median, or null where the stage timed nothing that day. */
	function at(date: string, key: Stage['key']): number | null {
		return timingOn(date, key)?.ms ?? null;
	}

	function newestOf(stage: Stage): number | null {
		return newest?.[stage.key].ms ?? null;
	}

	function x(index: number): number {
		return columnsX[index] ?? dayColumnX(index, calendar.length, box);
	}

	function y(ms: number): number {
		return scale.scale(ms);
	}

	/** Every day a stage has a positive number for, as a point of its own.
	 *
	 * The line carries the trend and the point carries the day: without a mark
	 * there is nothing to aim a pointer at and nothing for an arrow key to land
	 * on, and a spike between two labelled columns could not be dated at all. */
	function marksOf(key: Stage['key']): Point[] {
		return calendar
			.map((date, index) => ({ ms: at(date, key), index }))
			.filter((day): day is { ms: number; index: number } => day.ms !== null && day.ms > 0)
			.map((day) => ({ x: x(day.index), y: y(day.ms) }));
	}

	/** Each unbroken stretch of days with a positive number, so an absent day
	 * and a measured zero both break the line and neither is a straight line
	 * drawn through nothing. A stretch of one is a dot: a stage that runs on
	 * alternate days used to draw nothing at all, because only a one-day window
	 * got dots. */
	function runs(key: Stage['key']): Point[][] {
		const paths: Point[][] = [];
		let current: Point[] = [];
		calendar.forEach((date, index) => {
			const ms = at(date, key);
			if (ms !== null && ms > 0) {
				current.push({ x: x(index), y: y(ms) });
			} else if (current.length > 0) {
				paths.push(current);
				current = [];
			}
		});
		if (current.length > 0) paths.push(current);
		return paths;
	}

	/** The days a stage was measured at zero. They sit on the baseline rule,
	 * which is the one place on a decade axis that is not a claim about size. */
	function zeros(key: Stage['key']): Point[] {
		return calendar
			.map((date, index) => ({ date, index }))
			.filter((day) => at(day.date, key) === 0)
			.map((day) => ({ x: x(day.index), y: box.bottom }));
	}

	function points(run: Point[]): string {
		return run.map((point) => `${point.x},${point.y}`).join(' ');
	}

	function duration(ms: number): string {
		return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
	}

	/** What a stage's number reads as, in the strip and in the announcement.
	 * `0 ms` would say the stage took no time, which is the sentence this chart
	 * exists not to say, and a blank would say the same thing more quietly. */
	function reading(ms: number | null): string {
		if (ms === null) return 'not timed';
		return ms === 0 ? 'under 1 ms' : duration(ms);
	}

	function plural(count: number): string {
		return count === 1 ? 'day' : 'days';
	}

	/** A decade label crosses from milliseconds to seconds at 1000 ms. Every
	 * decade is a whole number in one unit or the other, so neither end of the
	 * axis needs a decimal place to be read. */
	function decade(ms: number): string {
		return ms >= 1000 ? `${ms / 1000} s` : `${ms} ms`;
	}
</script>

<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Time per item, by stage</h2>

{#if ordered.length === 0}
	<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-timing="empty">
		We timed nothing in these {calendar.length}
		{plural(calendar.length)}. Widen the window to look further back.
	</p>
{:else}
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		Median per item, each day. Each gridline is ten times the one below, so the same slowdown looks
		the same at 40 ms and at 100 s.
		{#if coverageNote}
			<!-- One sentence for the whole chart, above the plot. It was one note per
			     stage under it, and the three said one window-level fact three times -
			     so a fourth stage would have made it four. A reader meets a broken
			     line before he meets the sentence that explains it. -->
			<span data-coverage-note="timings" data-timing-coverage
				data-coverage-days={covered.days}
				data-coverage-measured={covered.measured}
				data-coverage-items={timedItems?.total ?? 0}
				data-coverage-timed-low={timedItems?.low ?? 0}
				data-coverage-timed-high={timedItems?.high ?? 0}>{coverageNote}</span
			>
		{/if}
		{#if anyZero}
			<span data-timing-zero-key
				>An open dot on the baseline is a day a stage took under 1 ms an item, which is faster than
				we can time.</span
			>
		{/if}
		{#if rules.length === 0}
			<!-- Stated, not omitted. A chart that draws no rule and says nothing about
			     it is indistinguishable from one where the rule was forgotten. -->
			<span data-model-rule-empty="timings">{noModelRuleNote(calendar.length)}</span>
		{/if}
	</p>

	<div
		class="mt-4 rounded-md border border-rule bg-surface p-3"
		data-timing="chart"
		data-readout-columns={columns.length}
		data-model-rule="yes"
		data-model-rule-name="timings"
		data-model-rule-from={calendar[0] ?? ''}
		data-model-rule-to={calendar[calendar.length - 1] ?? ''}
	>
		<div use:observeWidth={(next) => (measured = next)}>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<svg
				class="w-full overflow-visible focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				tabindex="0"
				aria-label={`Time per item by stage over ${calendar.length} ${plural(calendar.length)}, ${shortDate(calendar[0])} to ${shortDate(calendar[calendar.length - 1])}, oldest day on the left, on a ten-times scale`}
				data-timing="plot"
				data-timing-days={calendar.length}
				data-timing-series={drawn.length}
				data-timing-domain={timingExtent}
				data-timing-first={calendar[0] ?? ''}
				data-timing-last={calendar[calendar.length - 1] ?? ''}
				use:pointerReadout={{
					marks,
					width: box.width,
					onSelect: (index) => (selected = index)
				}}
			>
				<!-- The span nothing timed, drawn before everything else so the tint sits
				     under the grid and never over a mark. A tint rather than a hatch: a
				     hatch is a pattern a reader stops to decode, and this one only says
				     that no measurement reached here. -->
				{#each emptySpans as span (span.from)}
					<rect
						x={span.x}
						y={box.top}
						width={span.width}
						height={box.innerHeight}
						fill="var(--color-surface-sunken)"
						data-coverage-empty={span.from}
						data-coverage-empty-to={span.to}
					>
						<title>{coverageRegionTitle(span)}</title>
					</rect>
				{/each}
				{#each scale.ticks as tick (tick)}
					<line
						x1={box.left}
						x2={box.right}
						y1={y(tick)}
						y2={y(tick)}
						stroke="var(--color-rule)"
						stroke-opacity="0.6"
						data-decade-line={tick}
					/>
					<text
						x={box.left - 6}
						y={y(tick)}
						dy="0.32em"
						class="tabular-nums"
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-decade={tick}
					>
						{decade(tick)}
					</text>
				{/each}
				{#each minorTicks as tick (tick)}
					<line
						x1={box.left - 3}
						x2={box.left}
						y1={y(tick)}
						y2={y(tick)}
						stroke="var(--color-text-tertiary)"
						stroke-opacity="0.4"
						data-minor-tick={tick}
					/>
				{/each}

				<line
					x1={box.left}
					x2={box.right}
					y1={box.bottom}
					y2={box.bottom}
					stroke="var(--color-rule)"
				/>
				<line x1={box.left} x2={box.left} y1={box.top} y2={box.bottom} stroke="var(--color-rule)" />

				<!-- Dashed and in the neutral rule ink, never on the health ramp: a
				     pipeline change is an event, not a verdict. Drawn under the series,
				     so a dash never hides a day's own point. -->
				{#each rules as rule (rule.date)}
					<line
						x1={rule.x}
						x2={rule.x}
						y1={box.top}
						y2={box.bottom}
						stroke="var(--color-text-tertiary)"
						stroke-dasharray="3 3"
						data-model-rule-line={rule.date}
					>
						<title>{modelRuleTitle(rule.date)}</title>
					</line>
				{/each}

				{#if guide !== null}
					<line
						x1={guide}
						x2={guide}
						y1={box.top}
						y2={box.bottom}
						stroke="var(--color-text-tertiary)"
						stroke-opacity="0.5"
						data-timing="guide"
					/>
				{/if}

				{#each paths as path (path.stage.key)}
					{#each path.runs as run, index (`${path.stage.key}-${index}`)}
						{#if run.length > 1}
							<polyline
								points={points(run)}
								fill="none"
								stroke={path.stage.colour}
								stroke-width="1.5"
								stroke-linejoin="round"
								data-stage-mark={path.stage.label}
							/>
						{/if}
					{/each}
					{#each path.marks as mark, index (`${path.stage.key}-point-${index}`)}
						<circle
							cx={mark.x}
							cy={mark.y}
							r="2.5"
							fill={path.stage.colour}
							data-stage-mark={path.stage.label}
						/>
					{/each}
					{#each path.zeros as mark, index (`${path.stage.key}-zero-${index}`)}
						<circle
							cx={mark.x}
							cy={mark.y}
							r="3.5"
							fill="none"
							stroke={path.stage.colour}
							stroke-width="1.5"
							data-stage-zero={path.stage.label}
						/>
					{/each}
				{/each}

				<!-- The mark stays where the date is dropped: a reader counting columns
				     needs the grid whether or not the label survived the fit. -->
				{#each axis as label (label.index)}
					<line
						x1={x(label.index)}
						x2={x(label.index)}
						y1={box.bottom}
						y2={box.bottom + 4}
						stroke="var(--color-text-tertiary)"
						data-day-tick={label.date}
					/>
					{#if label.text}
						<text
							x={x(label.index)}
							y={box.bottom + 16}
							text-anchor={label.anchor}
							fill="var(--color-text-tertiary)"
							font-size="10"
							data-day-axis
							data-timing-label={label.date}
						>
							{label.text}
						</text>
					{/if}
				{/each}
			</svg>
		</div>

		<!-- Below the plot, never over it, and the same strip every chart on this
		     console prints - see `ChartReadout.svelte` for the rules it holds. -->
		<ChartReadout
			{readout}
			name="timings"
			maxShare={readoutMaxShare}
			resting={selected === null}
			restingNote=", the newest day we timed"
			hint="Point at a day to read it. Left and Right step through the days, Escape returns to the newest."
		/>
	</div>
{/if}
