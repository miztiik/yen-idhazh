<script lang="ts">
	/** How many stories each day folded into another, and how big the biggest
	 * fold was.
	 *
	 * **This is the one figure on Judgement that involves no model.** It was true
	 * before the judge existed and it stays true if the judge is replaced: the
	 * grouping pass wrote `same_story_as` into the day we published, and this
	 * counts it. A reader who stops here has seen a fact about what shipped
	 * rather than an opinion about how well it was decided.
	 *
	 * One column a day is the merges. One dot a day is the biggest group. Both
	 * are counts of stories, so they share one axis honestly - a second axis
	 * would let two numbers of the same kind be read at two different scales.
	 *
	 * **There is no rate line.** A day publishes a few hundred stories and folds
	 * a handful, so the share runs at a few percent: on a 0 to 100 axis that is a
	 * flat line two pixels off the floor, and on an axis fitted to it the noise
	 * becomes drama. The share is in type under the chart with the denominator it
	 * is a share of.
	 */
	import {
		chartWidth,
		dayColumns,
		dayTicks,
		frame,
		linearAxis,
		observeWidth,
		pointerReadout,
		readoutMarks,
		type DayReadout
	} from '$lib/charts/frame';
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { dayMonth, plural } from '$lib/format';
	import {
		mergeNote,
		mergeRate,
		mergeState,
		mergeTotals,
		type MergeDay
	} from '$lib/console/merge-line';

	let {
		days,
		viewport,
		height,
		width,
		tickDensity,
		readoutMaxShare
	}: {
		/** Every published day the build read, oldest first. */
		days: MergeDay[];
		viewport: TimeWindow;
		/** `console.chart_height`. The plot is this tall in all three states. */
		height: number;
		/** `console.chart_width` - what the SERVER draws at, before a script
		 * re-measures the column. */
		width: number;
		/** The most date labels the day axis may carry - `chart.tick_density`. */
		tickDensity: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare: number;
	} = $props();

	/** What the panel says in place of a strip when the window holds no column.
	 * One string, because the sentence a reader sees and the reason the markup
	 * declares are the same sentence. */
	const NO_COLUMN = 'No column in this window, so there is nothing to point at.';

	/** Wide enough to read, narrow enough that 90 columns fit. */
	const MAX_BAR = 18;
	const MIN_BAR = 2;
	/** The biggest-group mark. A dot rather than a second column, so the two
	 * numbers on one axis never read as one stacked total. */
	const DOT_R = 3.5;
	/** The rotated axis title needs a column of its own beside the tick numbers. */
	const Y_TITLE_X = 8;

	let measured = $state<number | null>(null);
	let selected = $state<number | null>(null);

	const windowDays = $derived(daysBetween(viewport.start, viewport.end));
	const drawn = $derived(
		days.filter((day) => day.date >= viewport.start && day.date <= viewport.end)
	);
	const totals = $derived(mergeTotals(drawn));
	// Not `state`: a const of that name turns every `$state(...)` in this file
	// into a store subscription on it, and svelte-check says so three ways.
	const panelState = $derived(mergeState(totals));
	const note = $derived(mergeNote(totals, windowDays));
	const rate = $derived(mergeRate(totals, windowDays));

	const box = $derived(frame(chartWidth(measured, width), height));
	/** Zero-anchored, because a column's length carries the value. The biggest
	 * group is on the same axis, so the domain covers whichever is taller. */
	const tallest = $derived(
		drawn.reduce((high, day) => Math.max(high, day.merges, day.largest), 0)
	);
	const yAxis = $derived(linearAxis([0, tallest], [box.bottom, box.top], { tickCount: 4 }));
	/** A count has no halves. d3 offers them on a short domain, so they are
	 * dropped rather than rounded - a repeated `1` reads as a broken axis. */
	const yTicks = $derived(yAxis.ticks.filter((tick) => Number.isInteger(tick)));
	const bar = $derived(
		Math.max(MIN_BAR, Math.min(MAX_BAR, (box.innerWidth / Math.max(1, drawn.length)) * 0.7))
	);
	/** One array of column pixels, so the ticks, the columns and the dots cannot
	 * disagree about where a day sits. */
	const columnsX = $derived(dayColumns(drawn.length, box, Math.max(bar / 2, DOT_R)));
	const ticks = $derived(
		dayTicks(
			drawn.map((day) => day.date),
			{ density: tickDensity, columns: columnsX }
		)
	);

	function px(value: number): number {
		return Math.round(value * 10) / 10;
	}

	/** Every column's geometry, built once rather than per mark in the template. */
	const bars = $derived(
		drawn.map((day, index) => ({
			date: day.date,
			x: px(columnsX[index] - bar / 2),
			y: px(yAxis.scale(day.merges)),
			height: px(yAxis.scale(0) - yAxis.scale(day.merges)),
			dotX: px(columnsX[index]),
			dotY: px(yAxis.scale(day.largest)),
			day
		}))
	);

	/** Both marks at one column, in the order they are drawn. Built here from
	 * `columnsX` rather than by `columnStrip`, which leaves `x` at zero for a
	 * chart an engine lays out - this one knows its own pixels.
	 *
	 * Both rows print at every column, including a column where the count is
	 * zero. A row that disappears makes the reader compare a two-row strip with
	 * a one-row strip. */
	const columns = $derived<DayReadout[]>(
		drawn.map((day, index) => ({
			x: px(columnsX[index]),
			date: dayMonth(day.date),
			rows: [
				{
					label: 'Merged',
					// The denominator rides in the value. A third row carrying it would
					// be a key to something the picture does not draw.
					value:
						day.published === 0
							? 'no story published'
							: `${day.merges} of ${day.published} published`,
					colour: 'var(--chart-1)'
				},
				{
					label: 'Biggest group',
					value: day.largest === 0 ? 'none formed' : plural(day.largest, 'story', 'stories'),
					colour: 'var(--chart-2)'
				}
			]
		}))
	);
	const resting = $derived(selected === null);
	const readout = $derived(columns.length === 0 ? null : columns[selected ?? columns.length - 1]);

	function columnTitle(day: MergeDay): string {
		if (day.published === 0) return `${dayMonth(day.date)} - no story was published.`;
		if (day.merges === 0) {
			return `${dayMonth(day.date)} - none of the ${day.published} stories published was grouped with another.`;
		}
		return `${dayMonth(day.date)} - ${plural(day.merges, 'story', 'stories')} folded into another, in ${plural(day.groups, 'group', 'groups')}. The biggest held ${day.largest}. ${day.published} stories were published.`;
	}
</script>

<Panel
	title="Stories the day merged"
	note="One column is one day: the stories that day folded behind another because we read them as the same story. The dot is the biggest group that day, counting the one we kept."
>
	<div
		data-windowed="merged-stories"
		data-window-days={windowDays}
		data-merge-state={panelState}
		data-merge-days={drawn.length}
		data-readout-columns={columns.length > 0 ? columns.length : undefined}
		data-readout-none={columns.length > 0 ? undefined : NO_COLUMN}
	>
		<div use:observeWidth={(next) => (measured = next)}>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<svg
				class="block max-w-full overflow-visible focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				tabindex="0"
				aria-label="Stories folded into another a day, over {windowDays} days"
				use:pointerReadout={{
					marks: readoutMarks(columns),
					width: box.width,
					onSelect: (index) => (selected = index)
				}}
			>
				<line
					x1={box.left}
					x2={box.right}
					y1={box.bottom}
					y2={box.bottom}
					stroke="var(--color-rule)"
				/>
				<line x1={box.left} x2={box.left} y1={box.top} y2={box.bottom} stroke="var(--color-rule)" />

				{#each yTicks as tick (tick)}
					<line
						x1={box.left - 4}
						x2={box.left}
						y1={yAxis.scale(tick)}
						y2={yAxis.scale(tick)}
						stroke="var(--color-text-tertiary)"
					/>
					<text
						x={box.left - 6}
						y={yAxis.scale(tick)}
						dy="0.32em"
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-tick="y"
					>
						{tick}
					</text>
				{/each}

				{#if drawn.length === 0}
					<!-- The frame is drawn anyway. A panel that shrinks to one sentence on a
					     quiet day is a panel an operator stops opening. -->
					<line
						x1={box.left}
						x2={box.right}
						y1={(box.top + box.bottom) / 2}
						y2={(box.top + box.bottom) / 2}
						stroke="var(--color-text-tertiary)"
						stroke-dasharray="4 4"
					/>
					<text
						x={box.left + 8}
						y={(box.top + box.bottom) / 2 - 8}
						fill="var(--color-text-secondary)"
						font-size="12"
					>
						No published day in this window
					</text>
				{:else}
					{#each bars as column (column.date)}
						<g
							data-merge-day={column.date}
							data-merge-count={column.day.merges}
							data-merge-largest={column.day.largest}
						>
							<title>{columnTitle(column.day)}</title>
							{#if column.height > 0}
								<rect
									x={column.x}
									y={column.y}
									width={px(bar)}
									height={column.height}
									fill="var(--chart-1)"
								/>
							{/if}
							{#if column.day.largest > 0}
								<!-- A different shape as well as a different colour, so the two
								     marks stay apart in a screenshot printed in grey. -->
								<circle
									cx={column.dotX}
									cy={column.dotY}
									r={DOT_R}
									fill="var(--chart-2)"
									data-merge-dot={column.date}
								/>
							{/if}
						</g>
					{/each}
				{/if}

				<!-- The mark stays where the date was dropped, so a reader counting
				     columns keeps the grid. -->
				{#each ticks as tick (tick.index)}
					<line
						x1={px(columnsX[tick.index])}
						x2={px(columnsX[tick.index])}
						y1={box.bottom}
						y2={box.bottom + 4}
						stroke="var(--color-text-tertiary)"
						data-day-tick={tick.date}
					/>
					{#if tick.text}
						<text
							x={px(columnsX[tick.index])}
							y={box.bottom + 16}
							text-anchor={tick.anchor}
							fill="var(--color-text-tertiary)"
							font-size="10"
							data-day-axis
							data-day-label={tick.date}
						>
							{tick.text}
						</text>
					{/if}
				{/each}

				<text
					x={Y_TITLE_X}
					y={(box.top + box.bottom) / 2}
					transform={`rotate(-90 ${Y_TITLE_X} ${(box.top + box.bottom) / 2})`}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-axis="y"
				>
					Stories
				</text>
			</svg>
		</div>

		{#if columns.length === 0}
			<p class="no-column" data-merge-no-column>{NO_COLUMN}</p>
		{:else}
			<ChartReadout
				{readout}
				name="merged-stories"
				maxShare={readoutMaxShare}
				{resting}
				restingNote=", the newest published day"
			/>
		{/if}

		<p class="merge-note" data-merge-note={panelState}>
			{note}
			{#if rate}
				<span data-merge-rate>{rate}</span>
			{/if}
		</p>
	</div>
</Panel>

<style>
	/* The strip slot keeps its height whether or not there is a column to print.
	   A strip that is there at one window span and gone at another moves the
	   panel box, which is the one thing the box below is for. The reserved height
	   is the loaded strip: a day heading, two rows and the hint line, with the
	   margins between them, at the 0.75rem the strip is set in. */
	.no-column {
		margin: var(--space-3) 0 0;
		min-height: calc(4 * 1.5em + 2 * var(--space-1) + var(--space-2));
		font-size: 0.75rem;
		color: var(--color-text-tertiary);
	}

	/* Two lines are reserved whichever state the panel is in. The plot is a fixed
	   220px by construction and the strip slot above reserves its own height, so
	   the note is the last part of this panel that could change height - and a
	   panel that grows by a line when the operator widens the window pushes
	   everything below it down the page while he is reading it. */
	.merge-note {
		margin: var(--space-3) 0 0;
		min-height: calc(var(--leading-sm) * 2);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
