<script lang="ts">
	/** Items published against items planned, one group a day.
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
	 * ceiling and prints its true figure in the strip, never clamped in the
	 * number.
	 *
	 * The counts come from the committed day-metrics records the page already
	 * opens, so drawing this costs no file the console was not reading.
	 */
	import {
		chartWidth,
		coverage,
		coverageRegions,
		coverageRegionTitle,
		coverageSentence,
		dayTicks,
		frame,
		linearAxis,
		notMeasuredRow,
		observeWidth,
		pointerReadout,
		readoutMarks,
		type DayReadout
	} from '$lib/charts/frame';
	import ChartReadout from './ChartReadout.svelte';
	import {
		placeOnYieldAxis,
		plannedDays,
		runYield,
		yieldRuns,
		YIELD_AXIS_TICKS,
		type RunYieldDay,
		type RunYieldSource
	} from '$lib/charts/run-yield';
	import { grouped } from '$lib/charts/series';
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';

	let {
		days,
		window,
		height,
		width,
		tickDensity,
		readoutMaxShare = 0.33
	}: {
		days: RunYieldSource[];
		window: TimeWindow;
		/** The whole SVG, margins included. */
		height: number;
		/** The column, until the element has been measured. */
		width: number;
		/** The most date labels the day axis may carry - `chart.tick_density`. */
		tickDensity: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare?: number;
	} = $props();

	/** Room on the right for the yield axis, on the left for an item count that
	 * reaches four digits, and above for the two axis titles - a chart with two y
	 * scales has to say which is which. Same frame as the failure chart, which is
	 * the same shape with the same two scales. */
	const CHART_MARGIN = { top: 26, right: 46, bottom: 26, left: 42 };

	/** Below this the three bars of a day are under two pixels each at a
	 * thirty-day window, which is a colour rather than a length. Measured on the
	 * built console at a 390px viewport: the panel draws 326px wide, leaving
	 * 242px of plot and a 8.1px slot. The narrow shape keeps the planned bar and
	 * the line, and the strip still prints all four numbers. */
	const NARROW_PX = 480;

	/** The widest a grouped set may be drawn, and the narrowest. A day with the
	 * plot to itself should not draw one bar half the frame wide. */
	const GROUP_MAX = 30;
	const GROUP_MIN = 3;

	/** Three categorical fills, and none of them `--chart-axis`.
	 *
	 * The donut this replaced painted its larger slice with the axis token, which
	 * an arc gap held apart from its neighbour. Three bars two pixels apart have
	 * no such gap, and this chart draws its own three axis rules in that same
	 * colour - so the quantity everything else is measured against would have
	 * been painted as the frame it sits in. */
	const SERIES = [
		{ key: 'planned', label: 'Planned', token: '--chart-1' },
		{ key: 'published', label: 'Published', token: '--chart-2' },
		{ key: 'failed', label: 'Failed', token: '--chart-8' }
	] as const;

	/** The line's own colour, so it reads as the one mark on the other axis. */
	const YIELD_TOKEN = '--chart-marker';

	let measured = $state<number | null>(null);

	const windowDays = $derived(daysBetween(window.start, window.end));
	const load = $derived(runYield(days, window));

	const box = $derived(frame(chartWidth(measured, width), height, CHART_MARGIN));
	const volume = $derived(linearAxis([0, load.peak], [box.bottom, box.top]));
	// A count of items has no half. A domain of two draws ticks at 0.5, and a
	// console cell never prints a decimal.
	const volumeTicks = $derived(volume.ticks.filter((tick) => Number.isInteger(tick)));
	const slot = $derived(box.innerWidth / Math.max(1, load.columns.length));
	const narrow = $derived(box.width < NARROW_PX);
	/** The whole group, three bars wide, or one bar where the group will not fit. */
	const group = $derived(Math.max(GROUP_MIN, Math.min(GROUP_MAX, slot - 2)));
	const barWidth = $derived(narrow ? group : group / SERIES.length);
	/** Which series are drawn as bars. On a phone the published bar leaves the
	 * plot and stays in the strip: the line already carries it as a share, and
	 * three 2px bars carry nothing. */
	const bars = $derived(narrow ? SERIES.slice(0, 1) : SERIES);

	function centre(index: number): number {
		return box.left + index * slot + slot / 2;
	}

	function barX(index: number, position: number): number {
		return narrow
			? centre(index) - group / 2
			: centre(index) - group / 2 + position * (group / SERIES.length);
	}

	function count(column: RunYieldDay, key: (typeof SERIES)[number]['key']): number {
		return key === 'planned' ? column.planned : key === 'published' ? column.published : column.failed;
	}

	function barTop(value: number): number {
		return volume.scale(value);
	}

	function barHeight(value: number): number {
		return Math.max(value > 0 ? 1 : 0, volume.scale(0) - volume.scale(value));
	}

	function barTitle(column: RunYieldDay, entry: (typeof SERIES)[number]): string {
		const value = count(column, entry.key);
		return `${column.date}: ${grouped(value)} ${entry.label.toLowerCase()}`;
	}

	const planned = $derived(plannedDays(load.columns));
	const covered = $derived(coverage(planned));
	const emptySpans = $derived(
		coverageRegions(
			covered,
			load.columns.map((column) => column.date),
			load.columns.map((_, index) => centre(index)),
			box
		)
	);
	const coverageNote = $derived(coverageSentence(covered, 'The pipeline planned items on'));

	/** Which columns carry a date. The columns are evenly spaced but the slot is
	 * not the plot, so the centres go to the helper rather than a width. */
	const dateAxis = $derived(
		dayTicks(
			load.columns.map((column) => column.date),
			{
				density: tickDensity,
				columns: load.columns.map((_, index) => centre(index))
			}
		)
	);

	/** Where a share draws, in this frame's pixels. The ceiling rule is the
	 * module's, so the axis cannot drift from the arithmetic that places on it. */
	function rateY(rate: number): number {
		return box.bottom - placeOnYieldAxis(rate) * box.innerHeight;
	}

	/** Whole percent, and `<1%` where a real measurement rounds away. A `0%`
	 * there would say the day published nothing. */
	function percent(rate: number | null): string {
		if (rate === null) return '-';
		const pct = rate * 100;
		if (pct > 0 && pct < 1) return '<1%';
		return `${Math.round(pct)}%`;
	}

	/** The day in one sentence: the share, and what it is a share of. Never a
	 * bare percentage - a share with no denominator invites a trend that is not
	 * there. */
	function sentence(column: RunYieldDay): string {
		if (column.yield === null) {
			return `${column.date}: no item was planned`;
		}
		return `${column.date}: ${grouped(column.published)} published of the ${grouped(column.planned)} planned, ${grouped(column.failed)} failed, share published ${percent(column.yield)}`;
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
		load.empty
			? `Nothing was planned in these ${windowDays} days.`
			: `Items published against items planned, ${windowDays} days. ${grouped(totals.published)} published of the ${grouped(totals.planned)} planned.`
	);

	/** The column a pointer or an arrow key has picked. */
	let selected = $state<number | null>(null);

	/** Three counts and the share they make, at one column. The share and its
	 * two counts sit on two axes, which is the shape where reading them together
	 * by eye is hardest, and it is the whole reason both are drawn. */
	const columns = $derived<DayReadout[]>(
		load.columns.map((column, index) => ({
			x: centre(index),
			date: column.date,
			rows:
				column.planned > 0
					? [
							...SERIES.map((entry) => ({
								label: entry.label,
								value: grouped(count(column, entry.key)),
								colour: `var(${entry.token})`
							})),
							{
								label: 'Share published',
								value: percent(column.yield),
								colour: `var(${YIELD_TOKEN})`
							}
						]
					: [notMeasuredRow('No item was planned on this day')]
		}))
	);
	const marks = $derived(readoutMarks(columns));
	const at = $derived(selected ?? (columns.length === 0 ? null : columns.length - 1));
	const readout = $derived(at === null ? null : (columns[at] ?? null));
	const guide = $derived(selected === null ? null : (columns[selected]?.x ?? null));
</script>

{#if load.empty}
	<p class="mt-4 text-[0.9375rem] text-text-secondary" data-run-yield-empty>
		Nothing was planned in these {windowDays} days, so there is nothing to show.
	</p>
{:else}
	<figure
		class="mt-4"
		data-readout-columns={columns.length}
		data-run-yield-days={load.columns.length}
		use:observeWidth={(value) => (measured = value)}
	>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<svg
			class="focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
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
				onSelect: (index) => (selected = index)
			}}
		>
			<!-- The span nothing was planned on, drawn before the grid so the tint sits
			     under every mark rather than over one. -->
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
			<text x="0" y="11" fill="var(--color-text-tertiary)" font-size="11">Items</text>
			<!-- Not `Share` on its own. The eye is on this axis at the moment it asks
			     "75 percent of what?", so the answer has to be here rather than in the
			     strip below. -->
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
					{#if count(column, entry.key) > 0}
						<rect
							x={barX(index, position)}
							y={barTop(count(column, entry.key))}
							width={barWidth}
							height={barHeight(count(column, entry.key))}
							fill="var({entry.token})"
							data-run-bar={entry.key}
						>
							<title>{barTitle(column, entry)}</title>
						</rect>
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
					stroke="var({YIELD_TOKEN})"
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
						fill="var({YIELD_TOKEN})"
						data-yield-mark={column.date}
					>
						<title>{sentence(column)}</title>
					</circle>
				{/if}
			{/each}
		</svg>
		<!-- Below the plot, never over it, and the same strip every chart on this
		     console prints - see `ChartReadout.svelte` for the rules. It is also
		     the key: the three counts and the share each carry their own colour
		     here, so the plot needs no legend of its own. -->
		<ChartReadout
			{readout}
			name="run-yield"
			maxShare={readoutMaxShare}
			resting={selected === null}
			restingNote=", the newest day"
			hint="Point at a day to read its three counts and the share it published. Left and Right step through the days, Escape returns to the newest."
		/>
		{#if coverageNote}
			<!-- The window is not narrowed to the days that ran: a day nothing was
			     planned on is a fact about the record, and hiding it would report a
			     fuller one than exists. -->
			<figcaption
				class="mt-2 text-[0.75rem] text-text-tertiary"
				data-coverage-note="run-yield"
				data-coverage-days={covered.days}
				data-coverage-measured={covered.measured}
			>
				{coverageNote}
			</figcaption>
		{/if}
	</figure>

	<!-- Every day in words, for a reader who cannot point at a column. The strip
	     above holds one day at a time and a pointer is how it changes. -->
	<ul class="sr-only" data-run-yield-values>
		{#each load.columns as column (column.date)}
			<li>{sentence(column)}</li>
		{/each}
	</ul>
{/if}
