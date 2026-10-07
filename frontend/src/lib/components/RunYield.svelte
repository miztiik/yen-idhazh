<script lang="ts">
	/** Articles published against planned, one group a day.
	 *
	 * The shape this replaced was a two-slice donut over the whole manifest set:
	 * one ratio, no window, no days. It could say 92 percent finished and it
	 * could not say which day went wrong, which is the only question an operator
	 * opens this page with. A month that publishes 95 percent on twenty-nine days
	 * and nothing at all on the thirtieth drew the same slice as a month that
	 * lost five percent every day.
	 *
	 * **The three counts are not a partition, and this chart never draws them as
	 * one.** `planned` and `failed` are per-run sums; `published` is the day's
	 * distinct published set, so a story a later run skipped is planned twice and
	 * published once. An item a run skipped belongs to none of the three. That is
	 * why they sit side by side rather than stacked, and why the yield line is
	 * not bounded above by 100 percent - a day over the ceiling draws at the
	 * ceiling and prints its true figure in the readout, never clamped in the
	 * number.
	 *
	 * **It hands its days to whatever stands under it.** `below` is drawn inside
	 * this figure with the very slots the bars were placed by, so a figure under
	 * the chart lands on the chart's days by construction rather than by a second
	 * calculation that happens to agree today. The readout that prints a picked
	 * day is its caller's: `Run health` prints one readout for this chart and the
	 * run squares together.
	 *
	 * The counts come from the committed day-metrics records the page already
	 * opens, so drawing this costs no file the console was not reading.
	 */
	import type { Snippet } from 'svelte';
	import { daySlots, type DaySlots } from '$lib/charts/day-slots';
	import {
		chartWidth,
		coverage,
		coverageRegions,
		dayTicks,
		frame,
		linearAxis,
		observeWidth
	} from '$lib/charts/frame';
	import { pointerReadout } from '$lib/charts/readout';
	import {
		placeOnYieldAxis,
		plannedDays,
		yieldCount,
		yieldPercent,
		yieldRuns,
		YIELD_AXIS_TICKS,
		YIELD_LINE_TOKEN,
		YIELD_SERIES,
		type RunYieldDay,
		type RunYieldLoad
	} from '$lib/charts/run-yield';
	import { grouped } from '$lib/charts/series';
	import { countDays, nameSpan } from '$lib/console/span-words';
	import { shortDate } from '$lib/format';

	let {
		load,
		height,
		width,
		tickDensity,
		selected = $bindable(null),
		onPick,
		below
	}: {
		/** One column a day of the window, from `runYield`. */
		load: RunYieldLoad;
		/** The whole SVG, margins included. */
		height: number;
		/** The column, until the element has been measured. */
		width: number;
		/** The most date labels the day axis may carry - `chart.tick_density`. */
		tickDensity: number;
		/** The day picked on this chart or on a figure beside it, or null for none. */
		selected?: number | null;
		/** A deliberate pick on this chart - a step key or a tap, never a hover. */
		onPick?: (index: number) => void;
		/** What stands under the chart's date row, handed the chart's own day slots
		 * and whether the chart is drawing its narrow shape. */
		below?: Snippet<[DaySlots, boolean]>;
	} = $props();

	/** Room on the right for the yield axis, on the left for an article count
	 * that reaches four digits, and above for the two axis titles - a chart with
	 * two y scales has to say which is which. Same frame as the failure chart,
	 * which is the same shape with the same two scales. */
	const CHART_MARGIN = { top: 26, right: 46, bottom: 26, left: 42 };

	/** Below this the three bars of a day are under two pixels each at a
	 * thirty-day window, which is a colour rather than a length. Measured on the
	 * built console at a 390px viewport: the panel draws 326px wide, leaving
	 * 242px of plot and a 8.1px slot. The narrow shape keeps the planned bar and
	 * the line, and the readout still prints all four numbers. */
	const NARROW_PX = 480;

	/** The widest a grouped set may be drawn, and the narrowest. A day with the
	 * plot to itself should not draw one bar half the frame wide. */
	const GROUP_MAX = 30;
	const GROUP_MIN = 3;

	let measured = $state<number | null>(null);

	const windowDays = $derived(load.columns.length);

	const box = $derived(frame(chartWidth(measured, width), height, CHART_MARGIN));
	/** Every day's slot, computed once and used by every mark on this chart and by
	 * whatever stands under it. */
	const slots = $derived(daySlots(box.width, load.columns.length, CHART_MARGIN));
	const volume = $derived(linearAxis([0, load.peak], [box.bottom, box.top]));
	// A count of items has no half. A domain of two draws ticks at 0.5, and a
	// console cell never prints a decimal.
	const volumeTicks = $derived(volume.ticks.filter((tick) => Number.isInteger(tick)));
	const narrow = $derived(box.width < NARROW_PX);
	/** The whole group, three bars wide, or one bar where the group will not fit. */
	const group = $derived(Math.max(GROUP_MIN, Math.min(GROUP_MAX, slots.slot - 2)));
	const barWidth = $derived(narrow ? group : group / YIELD_SERIES.length);
	/** Which series are drawn as bars. On a phone the published bar leaves the
	 * plot and stays in the readout: the line already carries it as a share, and
	 * three 2px bars carry nothing. */
	const bars = $derived(narrow ? YIELD_SERIES.slice(0, 1) : YIELD_SERIES);

	function centre(index: number): number {
		return slots.centres[index] ?? slots.left;
	}

	function barX(index: number, position: number): number {
		return narrow
			? centre(index) - group / 2
			: centre(index) - group / 2 + position * (group / YIELD_SERIES.length);
	}

	function barTop(value: number): number {
		return volume.scale(value);
	}

	function barHeight(value: number): number {
		return Math.max(value > 0 ? 1 : 0, volume.scale(0) - volume.scale(value));
	}

	/** One bar's sentence, kept on the bar as its name, with the day spelled the
	 * way the strip under the chart heads it. */
	function barTitle(column: RunYieldDay, entry: (typeof YIELD_SERIES)[number]): string {
		const value = yieldCount(column, entry.key);
		return `${shortDate(column.date)}: ${grouped(value)} ${entry.label.toLowerCase()}`;
	}

	const planned = $derived(plannedDays(load.columns));
	const covered = $derived(coverage(planned));
	const emptySpans = $derived(
		coverageRegions(
			covered,
			load.columns.map((column) => column.date),
			slots.centres,
			box
		)
	);

	/** Which columns carry a date. The columns are evenly spaced but the slot is
	 * not the plot, so the centres go to the helper rather than a width. */
	const dateAxis = $derived(
		dayTicks(
			load.columns.map((column) => column.date),
			{ density: tickDensity, columns: slots.centres }
		)
	);

	/** Where a share draws, in this frame's pixels. The ceiling rule is the
	 * module's, so the axis cannot drift from the arithmetic that places on it. */
	function rateY(rate: number): number {
		return box.bottom - placeOnYieldAxis(rate) * box.innerHeight;
	}

	/** The day in one sentence: the share, and what it is a share of. Never a
	 * bare percentage - a share with no denominator invites a trend that is not
	 * there. */
	function sentence(column: RunYieldDay): string {
		const day = shortDate(column.date);
		if (column.yield === null) {
			return `${day}: no article was planned`;
		}
		return `${day}: ${grouped(column.published)} published of the ${grouped(column.planned)} planned, ${grouped(column.failed)} failed, share published ${yieldPercent(column.yield)}`;
	}

	/** Each unbroken run of the line, placed in this frame's pixels. Where the
	 * line breaks is the module's rule; this only puts the runs on the page. */
	function segments(columns: readonly RunYieldDay[]): string[] {
		return yieldRuns(columns).map((run) =>
			run.map((index) => `${centre(index)},${rateY(columns[index].yield ?? 0)}`).join(' ')
		);
	}

	const totals = $derived(
		load.columns.reduce(
			(sum, column) => ({
				planned: sum.planned + column.planned,
				published: sum.published + column.published
			}),
			{ planned: 0, published: 0 }
		)
	);

	const headline = $derived(
		`Articles published against planned over ${countDays(windowDays)}: ${grouped(totals.published)} published of the ${grouped(totals.planned)} planned. The line is the share published, on the right axis.`
	);

	/** Where a pointer can land: one mark a day, on the day's own centre. */
	const marks = $derived(slots.centres.map((x) => ({ x })));
	const guide = $derived(selected === null ? null : (slots.centres[selected] ?? null));
</script>

<figure
	class="mt-4"
	data-run-yield-days={load.columns.length}
	use:observeWidth={(value) => (measured = value)}
>
	{#if load.empty}
		<p class="text-[0.9375rem] text-text-secondary" data-run-yield-empty>
			No run planned an article in {nameSpan(windowDays)}.
		</p>
	{:else}
		<!-- `max-w-full` because the server renders this before anything has measured
		     the column, so `width` is the `console.chart_width` fallback. Uncapped,
		     that fallback is the document's width until the page hydrates - 800px
		     inside a 360px phone, which is a sideways scrollbar on the first paint. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<svg
			class="block max-w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
			width={box.width}
			height={box.height}
			viewBox={`0 0 ${box.width} ${box.height}`}
			role="img"
			tabindex="0"
			aria-label={headline}
			data-run-yield-chart
			use:pointerReadout={{
				marks,
				width: box.width,
				onSelect: (index) => (selected = index),
				selected,
				onPick
			}}
		>
			<!-- The span nothing was planned on, drawn before the grid so the tint sits
			     under every mark rather than over one. It carries no words of its own:
			     the panel says what the tint is, and the strip says of each day in it
			     that nothing was planned. -->
			{#each emptySpans as span (span.from)}
				<rect
					x={span.x}
					y={box.top}
					width={span.width}
					height={box.innerHeight}
					fill="var(--color-surface-sunken)"
					data-coverage-empty={span.from}
					data-coverage-empty-to={span.to}
				/>
			{/each}
			{#if guide !== null}
				<line
					x1={guide}
					x2={guide}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--color-text-tertiary)"
					stroke-opacity="0.5"
					data-run-yield-chart="guide"
				/>
			{/if}
			<text x="0" y="11" fill="var(--color-text-tertiary)" font-size="11">Articles</text>
			<!-- Not `Share` on its own. The eye is on this axis at the moment it asks
			     "75 percent of what?", so the answer has to be here rather than in the
			     readout below. -->
			<text x={box.width} y="11" text-anchor="end" fill="var(--color-text-tertiary)" font-size="11"
				>Published, % of planned</text
			>

			{#each volumeTicks as tick (tick)}
				<line
					x1={box.left}
					x2={box.right}
					y1={volume.scale(tick)}
					y2={volume.scale(tick)}
					stroke="var(--chart-grid)"
				/>
				<text
					x={box.left - 5}
					y={volume.scale(tick) + 3.5}
					text-anchor="end"
					fill="var(--color-text-tertiary)"
					font-size="10">{grouped(tick)}</text
				>
			{/each}

			{#each YIELD_AXIS_TICKS as tick (tick)}
				<text
					x={box.right + 5}
					y={rateY(tick) + 3.5}
					text-anchor="start"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-yield-tick={tick}>{Math.round(tick * 100)}%</text
				>
			{/each}

			<line x1={box.left} x2={box.left} y1={box.top} y2={box.bottom} stroke="var(--chart-axis)" />
			<line x1={box.right} x2={box.right} y1={box.top} y2={box.bottom} stroke="var(--chart-axis)" />
			<line x1={box.left} x2={box.right} y1={box.bottom} y2={box.bottom} stroke="var(--chart-axis)" />

			{#each load.columns as column, index (column.date)}
				{#each bars as entry, position (entry.key)}
					{#if yieldCount(column, entry.key) > 0}
						<rect
							x={barX(index, position)}
							y={barTop(yieldCount(column, entry.key))}
							width={barWidth}
							height={barHeight(yieldCount(column, entry.key))}
							fill="var({entry.token})"
							role="img"
							aria-label={barTitle(column, entry)}
							data-run-bar={entry.key}
							data-run-bar-day={column.date}
						/>
					{/if}
				{/each}
			{/each}

			<!-- The mark stays where the date was dropped, so a reader counting
			     columns keeps the grid. -->
			{#each dateAxis as tick (tick.index)}
				<line
					x1={centre(tick.index)}
					x2={centre(tick.index)}
					y1={box.bottom}
					y2={box.bottom + 4}
					stroke="var(--color-text-tertiary)"
					data-day-tick={tick.date}
				/>
				{#if tick.text}
					<text
						x={centre(tick.index)}
						y={box.bottom + 16}
						text-anchor={tick.anchor}
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-day-axis>{tick.text}</text
					>
				{/if}
			{/each}

			{#each segments(load.columns) as points (points)}
				<polyline
					{points}
					fill="none"
					stroke="var({YIELD_LINE_TOKEN})"
					stroke-width="1.75"
					data-yield-line
				/>
			{/each}
			{#each load.columns as column, index (column.date)}
				{#if column.yield !== null}
					<circle
						cx={centre(index)}
						cy={rateY(column.yield)}
						r="2.5"
						fill="var({YIELD_LINE_TOKEN})"
						role="img"
						aria-label={sentence(column)}
						data-yield-mark={column.date}
					/>
				{/if}
			{/each}
		</svg>
	{/if}
	{#if below}{@render below(slots, narrow)}{/if}
</figure>

{#if !load.empty}
	<!-- Every day in words, for a reader who cannot point at a column. The readout
	     under the figures holds one day at a time and a pointer is how it changes. -->
	<ul class="sr-only" data-run-yield-values>
		{#each load.columns as column (column.date)}
			<li>{sentence(column)}</li>
		{/each}
	</ul>
{/if}
