<script lang="ts">
	/** Is it getting slower? That is the only question this section is asked.
	 *
	 * The block used to be one group of four bars per day. At a 30-day window
	 * that is about 150 rows and no trend at all, which answers the question by
	 * making the operator hold thirty numbers in their head.
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
	 * The x axis is the calendar, not the list of days that have rows. Three
	 * different facts used to arrive here as one missing number, and each one
	 * now draws as itself. A day nothing timed breaks the line. A day measured
	 * at zero breaks it too and draws an open dot on the baseline rule: zero has
	 * no position on a decade axis, and clamping it into the bottom decade draws
	 * a plunge that says the stage got a thousand times faster. A day timed for
	 * some of its items draws the items it timed. One line of type under the
	 * chart names whichever of the three happened, because a hole in a line is a
	 * mystery and three holes that look alike are worse than one.
	 *
	 * Four stages, four categorical colours, bound to the stage and never to
	 * its rank, so sorting the legend never repaints a line. The health ramp is
	 * not lent out: on a page where green means a clean run and red means a
	 * failed one, a red fetch line beside a green score line reads as "fetch is
	 * broken" when it only means "these are two different stages".
	 */
	import { chartWidth, frame, logAxis, MARGIN, observeWidth } from '$lib/charts/frame';
	import { axisLabels, type LabelAlign } from '$lib/charts/run-history';
	import type { StageTiming, StageTimingDay } from '$lib/charts/series';
	import { daysInWindow } from '$lib/charts/viewport';

	let {
		days,
		height,
		width
	}: { days: StageTimingDay[]; height: number; width: number } = $props();

	const STAGES = [
		{ key: 'fetch', label: 'fetch', colour: 'var(--series-1)' },
		{ key: 'extract', label: 'extract', colour: 'var(--series-2)' },
		{ key: 'summarize', label: 'summarize', colour: 'var(--series-3)' },
		{ key: 'score', label: 'score', colour: 'var(--series-4)' }
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
	const box = $derived(frame(chartWidth(measured, width), height, PLOT_MARGIN));

	const ordered = $derived([...days].sort((a, b) => a.date.localeCompare(b.date)));
	const calendar = $derived(
		ordered.length === 0
			? []
			: daysInWindow({
					start: ordered[0].date,
					end: ordered[ordered.length - 1].date
				})
	);
	const byDate = $derived(new Map(ordered.map((day) => [day.date, day])));
	const step = $derived(box.innerWidth / Math.max(1, calendar.length - 1));
	/** Whole decades, rounded outward to the decade that holds the data. That is
	 * the log form of the rounding rule, not an exception to it. */
	const scale = $derived(
		logAxis(
			ordered
				.flatMap((day) => STAGES.map((stage) => day[stage.key].ms))
				.filter((ms): ms is number => ms !== null),
			[box.bottom, box.top]
		)
	);
	const minorTicks = $derived(
		scale.ticks
			.flatMap((decade) => MINOR_STEPS.map((factor) => factor * decade))
			.filter((value) => value < scale.domain[1])
	);
	const axis = $derived(axisLabels(calendar));
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
	/** Every day a stage did not draw a plain point, counted by which of the
	 * three reasons it was. A stage the window never timed says so in the legend
	 * instead, once, rather than here and there. */
	const notes = $derived(
		drawn
			.map((stage) => {
				const part = calendar
					.map((date) => timingOn(date, stage.key))
					.filter(
						(day): day is StageTiming => day !== null && day.timed > 0 && day.timed < day.total
					);
				return {
					stage,
					blank: calendar.filter((date) => timedOn(date, stage.key) === 0).length,
					zero: calendar.filter((date) => at(date, stage.key) === 0).length,
					partDays: part.length,
					timed: part.reduce((total, day) => total + day.timed, 0),
					items: part.reduce((total, day) => total + day.total, 0)
				};
			})
			.filter((note) => note.blank > 0 || note.zero > 0 || note.partDays > 0)
	);

	const ANCHOR: Record<LabelAlign, 'start' | 'middle' | 'end'> = {
		start: 'start',
		centre: 'middle',
		end: 'end'
	};

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
		return calendar.length === 1 ? (box.left + box.right) / 2 : box.left + index * step;
	}

	function y(ms: number): number {
		return scale.scale(ms);
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

	/** What the legend prints for the newest day. `0 ms` would say the stage
	 * took no time, which is the sentence this chart exists not to say. */
	function newestValue(stage: Stage): string {
		const ms = newestOf(stage);
		if (ms === null) return 'not timed';
		return ms === 0 ? 'under 1 ms' : duration(ms);
	}

	function plural(count: number): string {
		return count === 1 ? 'day' : 'days';
	}

	/** Thousands grouped. A window of a month counts items in the thousands,
	 * and 1240 and 1,240 are not read at the same speed. */
	function group(count: number): string {
		return count.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
	}

	/** A decade label crosses from milliseconds to seconds at 1000 ms. Every
	 * decade is a whole number in one unit or the other, so neither end of the
	 * axis needs a decimal place to be read. */
	function decade(ms: number): string {
		return ms >= 1000 ? `${ms / 1000} s` : `${ms} ms`;
	}
</script>

<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Time per item, by stage</h2>

{#if calendar.length === 0}
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">No timings recorded yet.</p>
{:else}
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		Median per item, each day. Each gridline is ten times the one below, so the same slowdown looks
		the same at 40 ms and at 100 s. Median, not mean: one slow host would otherwise describe the
		whole day.
	</p>

	<div class="mt-4 rounded-md border border-rule bg-surface p-3" data-timing="chart">
		<div use:observeWidth={(next) => (measured = next)}>
			<svg
				class="w-full overflow-visible"
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				aria-label="Time per item by stage, oldest day on the left, on a ten-times scale"
				data-timing="plot"
			>
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

				{#each drawn as stage (stage.key)}
					{#each runs(stage.key) as run, index (`${stage.key}-${index}`)}
						{#if run.length === 1}
							<circle
								cx={run[0].x}
								cy={run[0].y}
								r="3.5"
								fill={stage.colour}
								data-stage-mark={stage.label}
							/>
						{:else}
							<polyline
								points={points(run)}
								fill="none"
								stroke={stage.colour}
								stroke-width="1.5"
								stroke-linejoin="round"
								data-stage-mark={stage.label}
							/>
						{/if}
					{/each}
					{#each zeros(stage.key) as mark, index (`${stage.key}-zero-${index}`)}
						<circle
							cx={mark.x}
							cy={mark.y}
							r="3.5"
							fill="none"
							stroke={stage.colour}
							stroke-width="1.5"
							data-stage-zero={stage.label}
						/>
					{/each}
				{/each}

				{#each axis as label (label.column)}
					<text
						x={x(label.column - 1)}
						y={box.bottom + 14}
						text-anchor={ANCHOR[label.align]}
						fill="var(--color-text-tertiary)"
						font-size="10"
					>
						{label.text}
					</text>
				{/each}
			</svg>
		</div>

		<ul class="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[0.75rem] text-text-tertiary">
			{#each legend as stage (stage.key)}
				<li
					class="flex items-center gap-2"
					class:opacity-50={!drawn.includes(stage)}
					data-stage={stage.label}
				>
					<span class="size-3 shrink-0 rounded-sm" style="background: {stage.colour}"></span>
					{stage.label}
					<span class="tabular-nums text-text-secondary">{newestValue(stage)}</span>
				</li>
			{/each}
		</ul>
		{#if newest}
			<p class="mt-2 text-[0.75rem] text-text-tertiary">
				Values are the newest day on record, {newest.date}.
			</p>
		{/if}
		{#each notes as note (note.stage.key)}
			<p class="mt-1 text-[0.75rem] text-text-tertiary" data-timing-note={note.stage.label}>
				{#if note.blank > 0}
					We timed no {note.stage.label} work on {note.blank} of the {calendar.length}
					{plural(calendar.length)}. The line breaks there.
				{/if}
				{#if note.zero > 0}
					{note.stage.label} took under 1 ms per item on {note.zero}
					{plural(note.zero)}, which is faster than we can time. The open dot on the baseline marks
					it.
				{/if}
				{#if note.partDays > 0}
					We timed {group(note.timed)} of the {group(note.items)} items for {note.stage.label} on {note.partDays}
					{plural(note.partDays)}. The line is the items we timed.
				{/if}
			</p>
		{/each}
	</div>
{/if}
