<script lang="ts">
	/** Where the merge line sits, day by day, on a corridor it cannot leave.
	 *
	 * Two lines. **Applied, solid** - the number that day's build actually
	 * grouped at. **Proposed, dotted** - what the evidence asked for before the
	 * damping and the clamps shaped it. On a normal day they sit on top of each
	 * other. They part on a day the record pulled hard and something held the
	 * line back, and that gap is the whole story of the panel.
	 *
	 * **The axis is the config band and never the data.** After the first
	 * fortnight the line moves under 0.002 a day. Auto-scaled, a two-thousandth
	 * move fills the panel top to bottom and a normal day reads as an incident;
	 * an operator who has seen three of those stops opening the panel. On 0 to 1
	 * the same move is a fifth of a pixel and the chart is flat whether or not
	 * anything is happening. The corridor is the answer to both.
	 *
	 * **The clamp gets no panel of its own.** A panel titled "the clamp" would
	 * draw a bar chart of a word. The dotted line leaving the shaded band IS the
	 * clamp firing, in the one place a reader is already looking. What the reader
	 * would lose is the count, so the count is a sentence under the chart.
	 *
	 * Hand-written SVG rather than the lazy engine chunk: two lines on a fixed
	 * domain need none of it, and this way the plot is complete before any script
	 * runs and both themes work with JavaScript off.
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
	import { dayMonth } from '$lib/format';
	import { clampEnvelope, clampNote, corridorOf, heldNote, type LineDay } from '$lib/console/merge-line';

	let {
		days,
		knobs,
		viewport,
		height,
		width,
		tickDensity,
		readoutMaxShare,
		configuredLine
	}: {
		/** Every day the record fitted a row for, oldest first. */
		days: LineDay[];
		/** The band and the daily step, off `config/idhazh.json`. */
		knobs: { band_low: number; band_high: number };
		viewport: TimeWindow;
		height: number;
		width: number;
		tickDensity: number;
		readoutMaxShare: number;
		/** The committed floor. What the newest day was built with when no fit has
		 * ever run, so state K1 draws a rule rather than an empty box. */
		configuredLine: number;
	} = $props();

	/** How many decimals a fitted line is reported at. One bin is 0.001, so a
	 * fourth decimal would print a precision the fit cannot produce. */
	const PLACES = 3;

	let measured = $state<number | null>(null);
	let selected = $state<number | null>(null);

	const windowDays = $derived(daysBetween(viewport.start, viewport.end));
	const drawn = $derived(
		days.filter((day) => day.date >= viewport.start && day.date <= viewport.end)
	);
	const corridor = $derived(corridorOf(knobs));
	const envelope = $derived(clampEnvelope(drawn));
	const clamp = $derived(clampNote(drawn, windowDays));
	const held = $derived(heldNote(drawn, windowDays));

	const box = $derived(frame(chartWidth(measured, width), height));
	/** `zero: false` and `nice: false`, and both are load-bearing. Anchoring at
	 * zero would put the whole corridor in the top eighth of the plot and a
	 * 0.005 step would draw under a pixel. Rounding the domain outward would move
	 * every mark to buy a label that reads the same, because the two ends are
	 * config knobs rather than a reading of the data. */
	const yAxis = $derived(
		linearAxis(corridor, [box.bottom, box.top], { tickCount: 4, zero: false, nice: false })
	);
	const columnsX = $derived(dayColumns(drawn.length, box, 2));
	const ticks = $derived(
		dayTicks(
			drawn.map((day) => day.date),
			{ density: tickDensity, columns: columnsX }
		)
	);

	function px(value: number): number {
		return Math.round(value * 10) / 10;
	}

	function reads(value: number): string {
		return value.toFixed(PLACES);
	}

	const marks = $derived(
		drawn.map((day, index) => ({
			date: day.date,
			x: px(columnsX[index]),
			appliedY: px(yAxis.scale(day.applied)),
			proposedY: day.proposed === null ? null : px(yAxis.scale(day.proposed)),
			bandY: px(yAxis.scale(envelope[index].high)),
			bandHeight: px(yAxis.scale(envelope[index].low) - yAxis.scale(envelope[index].high)),
			day
		}))
	);

	/** The solid series. One polyline, because the applied line is continuous:
	 * a held day still applied a number. */
	const appliedPath = $derived(marks.map((mark) => `${mark.x},${mark.appliedY}`).join(' '));

	/** The dotted series, BROKEN at every held day. A line drawn through a day
	 * nothing was fitted on claims a measurement nobody took. */
	const proposedRuns = $derived(
		marks.reduce<string[][]>((runs, mark) => {
			if (mark.proposedY === null) {
				if (runs.length === 0 || runs[runs.length - 1].length > 0) runs.push([]);
				return runs;
			}
			if (runs.length === 0) runs.push([]);
			runs[runs.length - 1].push(`${mark.x},${mark.proposedY}`);
			return runs;
		}, [])
			.filter((run) => run.length > 1)
			.map((run) => run.join(' '))
	);

	const columns = $derived<DayReadout[]>(
		marks.map((mark) => ({
			x: mark.x,
			date: dayMonth(mark.day.date),
			rows: [
				{ label: 'Applied', value: reads(mark.day.applied), colour: 'var(--chart-1)' },
				{
					label: 'Proposed',
					value: mark.day.proposed === null ? 'nothing was fitted' : reads(mark.day.proposed),
					colour: 'var(--chart-2)'
				}
			]
		}))
	);
	const resting = $derived(selected === null);
	const readout = $derived(columns.length === 0 ? null : columns[selected ?? columns.length - 1]);

	function columnTitle(day: LineDay): string {
		if (day.heldReason !== 'none') {
			return `${dayMonth(day.date)} - nothing was fitted. The line stayed at ${reads(day.applied)}.`;
		}
		if (day.clampKind === 'none') {
			return `${dayMonth(day.date)} - the line moved to ${reads(day.applied)}, which is what the evidence asked for.`;
		}
		return `${dayMonth(day.date)} - the evidence asked for ${reads(day.proposed ?? day.applied)} and the line was held at ${reads(day.applied)}.`;
	}
</script>

<Panel
	title="Where the merge line sits"
	note="The solid line is the score two stories had to reach that day to be read as one story. The dotted line is what the evidence asked for. The shaded band is as far as the line was allowed to fall in one day."
>
	<div
		data-windowed="merge-line"
		data-window-days={windowDays}
		data-line-domain={`${corridor[0]},${corridor[1]}`}
		data-line-days={drawn.length}
		data-readout-columns={columns.length > 0 ? columns.length : undefined}
		data-readout-none={columns.length > 0
			? undefined
			: 'no day has fitted a line, so there is no column to read'}
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
				aria-label="The merge line a day, on the whole range a fitted line may take"
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

				{#each yAxis.ticks as tick (tick)}
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
						{reads(tick)}
					</text>
				{/each}

				{#if drawn.length === 0}
					<!-- State K1. A full axis, a labelled corridor and the line in force -
					     never a blank box with an apology. -->
					<line
						x1={box.left}
						x2={box.right}
						y1={yAxis.scale(configuredLine)}
						y2={yAxis.scale(configuredLine)}
						stroke="var(--color-text-tertiary)"
						stroke-dasharray="4 4"
						data-line-rule={reads(configuredLine)}
					/>
					<text
						x={box.left + 8}
						y={yAxis.scale(configuredLine) - 8}
						fill="var(--color-text-tertiary)"
						font-size="12"
					>
						The line the newest day was built with
					</text>
				{:else}
					<!-- The band first, so every line sits on top of it. -->
					{#each marks as mark (mark.date)}
						{#if mark.bandHeight > 0}
							<rect
								x={px(mark.x - 3)}
								y={mark.bandY}
								width={6}
								height={mark.bandHeight}
								fill="var(--color-surface-sunken)"
								data-line-band={mark.date}
							/>
						{/if}
					{/each}

					{#each proposedRuns as run, index (index)}
						<polyline
							points={run}
							fill="none"
							stroke="var(--chart-2)"
							stroke-width="1.5"
							stroke-dasharray="4 3"
							data-line-series="proposed"
						/>
					{/each}

					<polyline
						points={appliedPath}
						fill="none"
						stroke="var(--chart-1)"
						stroke-width="2"
						data-line-series="applied"
					/>

					{#each marks as mark (mark.date)}
						<g
							data-line-day={mark.date}
							data-line-clamp={mark.day.clampKind}
							data-line-held={mark.day.heldReason}
							data-line-applied={reads(mark.day.applied)}
							data-line-proposed={mark.day.proposed === null ? '' : reads(mark.day.proposed)}
						>
							<title>{columnTitle(mark.day)}</title>
							{#if mark.day.heldReason !== 'none'}
								<!-- A square on the date axis, so a held day is findable without
								     reading every tooltip. Grey, because a held day is not a
								     failure and painting it in the low band would teach an
								     operator to ignore the low band. -->
								<rect
									x={px(mark.x - 2.5)}
									y={box.bottom + 2}
									width={5}
									height={5}
									fill="var(--chart-8)"
									data-line-held-mark={mark.date}
								/>
							{/if}
						</g>
					{/each}
				{/if}

				{#each ticks as tick (tick.index)}
					<line
						x1={px(columnsX[tick.index])}
						x2={px(columnsX[tick.index])}
						y1={box.bottom}
						y2={box.bottom + 4}
						stroke="var(--color-text-tertiary)"
						data-day-tick={tick.date}
					/>
					<text
						x={px(columnsX[tick.index])}
						y={box.bottom + 16}
						text-anchor={tick.anchor}
						fill="var(--color-text-tertiary)"
						font-size="10"
					>
						{dayMonth(tick.date)}
					</text>
				{/each}
			</svg>
		</div>

		<ChartReadout
			{readout}
			name="merge-line"
			maxShare={readoutMaxShare}
			{resting}
			restingNote="the newest day"
		/>

		<p class="line-note">
			{#if drawn.length === 0}
				<span data-line-state="no-days"
					>No day has fitted a line yet. The rule is the line the newest day was built
					with, and the scale is the whole range a fitted line may take.</span
				>
			{:else}
				<span data-line-state="fitted" data-line-clamp-note>{clamp}</span>
				{#if held}
					<span data-line-held-note>{held}</span>
				{/if}
			{/if}
		</p>
	</div>
</Panel>

<style>
	/* The secondary voice every console panel uses for a caveat under a chart
	   (design-system.md). */
	.line-note {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
