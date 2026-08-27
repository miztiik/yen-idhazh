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
	 * The x axis is the calendar, not the list of days that have rows. A day
	 * with no census breaks the line rather than closing the gap, because "no
	 * data" and "no time spent" are different facts. A zero breaks it the same
	 * way and is never clamped to the axis floor: a clamped point draws a
	 * plunge to the bottom of the plot, which says the stage got a thousand
	 * times faster. A gap says "no number here", which is true.
	 *
	 * Four stages, four categorical colours, bound to the stage and never to
	 * its rank, so sorting the legend never repaints a line. The health ramp is
	 * not lent out: on a page where green means a clean run and red means a
	 * failed one, a red fetch line beside a green score line reads as "fetch is
	 * broken" when it only means "these are two different stages".
	 */
	import { chartWidth, frame, logAxis, MARGIN, observeWidth } from '$lib/charts/frame';
	import { axisLabels, type LabelAlign } from '$lib/charts/run-history';
	import type { StageTimingDay } from '$lib/charts/series';
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

	/** A stage is on the chart only where it has a number somewhere in view. */
	const drawn = $derived(STAGES.filter((stage) => calendar.some((date) => at(date, stage.key) > 0)));
	/** Tallest first, so a label is matched to a line by position and not by
	 * colour alone. It reorders only when two stages have changed places, which
	 * is when the operator wants to notice. */
	const legend = $derived([...drawn].sort((a, b) => newestOf(b) - newestOf(a)));
	/** A hole in a line is a mystery, so every hole is named in type. */
	const gaps = $derived(
		STAGES.map((stage) => ({
			stage,
			missing: calendar.filter((date) => at(date, stage.key) <= 0).length,
			everDrawn: drawn.includes(stage)
		})).filter((note) => note.missing > 0)
	);

	const ANCHOR: Record<LabelAlign, 'start' | 'middle' | 'end'> = {
		start: 'start',
		centre: 'middle',
		end: 'end'
	};

	function at(date: string, key: Stage['key']): number {
		return byDate.get(date)?.[key].ms ?? 0;
	}

	function newestOf(stage: Stage): number {
		const value = newest?.[stage.key].ms ?? 0;
		return value > 0 ? value : 0;
	}

	function x(index: number): number {
		return calendar.length === 1 ? (box.left + box.right) / 2 : box.left + index * step;
	}

	function y(ms: number): number {
		return scale.scale(ms);
	}

	/** Each unbroken stretch of days that has a number, so an absent day and a
	 * zero are both a gap and neither is a straight line drawn through nothing.
	 * A stretch of one is a dot: a stage that runs on alternate days used to
	 * draw nothing at all, because only a one-day window got dots. */
	function runs(key: Stage['key']): Point[][] {
		const paths: Point[][] = [];
		let current: Point[] = [];
		calendar.forEach((date, index) => {
			const value = at(date, key);
			if (value > 0) {
				current.push({ x: x(index), y: y(value) });
			} else if (current.length > 0) {
				paths.push(current);
				current = [];
			}
		});
		if (current.length > 0) paths.push(current);
		return paths;
	}

	function points(run: Point[]): string {
		return run.map((point) => `${point.x},${point.y}`).join(' ');
	}

	function duration(ms: number): string {
		return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
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

		{#if legend.length > 0}
			<ul class="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[0.75rem] text-text-tertiary">
				{#each legend as stage (stage.key)}
					<li class="flex items-center gap-2" data-stage={stage.label}>
						<span class="size-3 shrink-0 rounded-sm" style="background: {stage.colour}"></span>
						{stage.label}
						<span class="tabular-nums text-text-secondary"
							>{newestOf(stage) > 0 ? duration(newestOf(stage)) : 'no data'}</span
						>
					</li>
				{/each}
			</ul>
		{/if}
		{#if newest}
			<p class="mt-2 text-[0.75rem] text-text-tertiary">
				Values are the newest day on record, {newest.date}.
			</p>
		{/if}
		{#each gaps as note (note.stage.key)}
			<p class="mt-1 text-[0.75rem] text-text-tertiary" data-timing-gap={note.stage.label}>
				{#if note.everDrawn}
					No time recorded for {note.stage.label} on {note.missing}
					{note.missing === 1 ? 'day' : 'days'} in this window.
				{:else}
					No time recorded for {note.stage.label} in this window.
				{/if}
			</p>
		{/each}
	</div>
{/if}
