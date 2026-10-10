<script lang="ts">
	/** Where the merge line sits, day by day, on a corridor it cannot leave.
	 *
	 * Two lines. **Calculated, solid** - the nightly fit's final number, which a
	 * build need not have used. **Proposed, dotted** - what the evidence asked for before the
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
	 * **The pairs a person marked as two stories are a tinted strip across the
	 * plot.** This is the one chart on the route with time on one axis and score
	 * on the other, so the calculated line can be compared with that range.
	 * A crossing is not evidence that a build used the line. The holdout panel draws the same
	 * marks as four dots on a score axis, where the distance is legible and the
	 * date is not - the two answer different halves of one question.
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
		observeWidth
	} from '$lib/charts/frame';
	import { pointerReadout, readoutMarks, readoutOf } from '$lib/charts/readout';
	import { indexedRuns } from '$lib/charts/indexed-runs';
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { dayMonth } from '$lib/format';
	import { clampEnvelope, clampNote, corridorOf, heldNote, type LineDay } from '$lib/console/merge-line';
	import { nameSpan } from '$lib/console/span-words';

	let {
		days: inputDays,
		evidence = [],
		knobs,
		viewport,
		height,
		width,
		tickDensity,
		readoutMaxShare,
		builtWith,
		markedApart
	}: {
		/** Every day the record fitted a row for, oldest first. */
		days: LineDay[] | null;
		evidence?: string[];
		/** The band a fitted line may take, off `config/idhazh.json`. */
		knobs: { band_low: number; band_high: number };
		viewport: TimeWindow;
		height: number;
		width: number;
		tickDensity: number;
		readoutMaxShare: number;
		/** The line the newest day was built with. The dashed rule is drawn at it
		 * when no fitted day is in the window, so state K1 draws a rule rather
		 * than an empty box. */
		builtWith: number;
		/** The lowest and highest score among the pairs a person marked as two
		 * different stories, and how many there are. Null where nobody has marked
		 * one, which draws no strip rather than a zero-height one. */
		markedApart: { low: number; high: number; count: number } | null;
	} = $props();

	/** How many decimals a fitted line is reported at. One bin is 0.001, so a
	 * fourth decimal would print a precision the fit cannot produce. */
	const PLACES = 3;

	let measured = $state<number | null>(null);
	let selected = $state<number | null>(null);

	const windowDays = $derived(daysBetween(viewport.start, viewport.end));
	const days = $derived(inputDays ?? []);
	const drawn = $derived(
		days.filter((day) => day.date >= viewport.start && day.date <= viewport.end)
	);
	const corridor = $derived(corridorOf(knobs));
	/** Where the marked-apart pairs sit, cut to the corridor this chart draws.
	 *
	 * Null where none of them reaches it. The corridor is the range a fitted line
	 * may take and a hand mark is not a line - two articles about nothing in
	 * common score far under it - so a zone drawn from the raw scores would paint
	 * a rectangle past the bottom of the plot. */
	const holdoutZone = $derived.by(() => {
		if (markedApart === null) return null;
		const low = Math.max(corridor[0], markedApart.low);
		const high = Math.min(corridor[1], markedApart.high);
		return high <= low ? null : { low, high, count: markedApart.count };
	});
	const envelope = $derived(clampEnvelope(drawn));
	const clamp = $derived(clampNote(drawn, windowDays));
	const held = $derived(heldNote(drawn, windowDays));
	/** Which day the dashed rule is the line of, in words. At one day that day is
	 * the whole window, so it is named as the window, not as the newest of several. */
	const ruleDay = $derived(windowDays === 1 ? nameSpan(windowDays) : 'the newest day');

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

	/** The solid fit series. A held row retains its previous calculated value. */
	const appliedPath = $derived(marks.map((mark) => `${mark.x},${mark.appliedY}`).join(' '));

	/** The dotted series, BROKEN at every held day. A line drawn through a day
	 * nothing was fitted on claims a measurement nobody took. */
	const proposedRuns = $derived(
		indexedRuns(marks, (mark) => mark.proposedY !== null)
			.filter((run) => run.length > 1)
			.map((run) => run.map((index) => `${marks[index].x},${marks[index].proposedY}`).join(' '))
	);

	/** What the line did on a day, in the words the strip prints it under. */
	function lineDid(day: LineDay): string {
		if (day.heldReason !== 'none') return 'stayed where it was';
		if (day.clampKind === 'none') return 'was updated';
		return 'had its change limited';
	}

	const readout = $derived(
		readoutOf({
			type: 'dateSeries',
			columns: marks.map((mark) => dayMonth(mark.day.date)),
			series: [
				{
					label: 'Calculated line',
					swatch: 'var(--chart-1)',
					values: marks.map((mark) => mark.day.applied),
					format: reads
				},
				{
					label: 'Proposed line',
					swatch: 'var(--chart-2)',
					values: marks.map((mark) => mark.day.proposed ?? 'nothing was fitted'),
					format: reads
				},
				{
					label: 'Change',
					swatch: null,
					values: marks.map((mark) => lineDid(mark.day)),
					format: String
				}
			],
			notMeasured: 'No line was fitted on this day',
			resting: 'last'
		})
	);
	const count = $derived(readout.columns.length);

	/** A day's sentence, kept on its marks as their name. Every word of it is in
	 * the strip at that day: what the line did, and the two readings. */
	function columnTitle(day: LineDay): string {
		const on = dayMonth(day.date);
		if (day.heldReason !== 'none') {
			return `${on}: nothing was fitted. The calculated line stayed at ${reads(day.applied)}. A build may have used a different line.`;
		}
		if (day.clampKind === 'none') {
			return `${on}: proposed line ${reads(day.proposed ?? day.applied)}; calculated line ${reads(day.applied)} after limits on its change. A build may have used a different line.`;
		}
		return `${on}: proposed line ${reads(day.proposed ?? day.applied)}; calculated line ${reads(day.applied)}. Its change was limited. A build may have used a different line.`;
	}
</script>

<Panel
	id="merge-line"
	title="Where the merge line sits"
	note={drawn.length === 0
		? `The dashed rule shows the line ${ruleDay} was built with. The scale is the whole range a fitted line may take.${holdoutZone === null || markedApart === null ? '' : ` The tinted strip shows the part of the score range inside this plot for ${markedApart.count} pairs a person marked as two stories. Their scores run from ${markedApart.low.toFixed(4)} to ${markedApart.high.toFixed(4)}.`}`
		: `${windowDays === 1 ? "The applied reading is the nightly calculation's final score for grouping two stories as one, after limits on its change. The proposed reading is the score before those limits. The shaded band shows how far the calculated line was allowed to fall that day. A build may have used a different line." : "The solid line is the nightly calculation's final score for grouping two stories as one, after limits on its change. The dotted line is the proposed score before those limits. The shaded band shows how far the calculated line was allowed to fall each day. A build may have used a different line."}${holdoutZone === null || markedApart === null ? '' : ` The tinted strip shows the part of the score range inside this plot for ${markedApart.count} pairs a person marked as two stories. Their scores run from ${markedApart.low.toFixed(4)} to ${markedApart.high.toFixed(4)}. If used to group stories, ${windowDays === 1 ? 'an applied reading' : 'a calculated line'} inside this strip would clear the score threshold for at least one of those pairs. This does not show that a build grouped them.`}`}
>
	<div
		data-windowed="merge-line"
		data-panel-question="Where did the calculated merge line sit?"
		data-model-rule="no"
		data-model-rule-name="merge-line"
		data-model-rule-none="the judge's record, not how summaries are written"
		data-window-days={windowDays}
		data-line-domain={`${corridor[0]},${corridor[1]}`}
		data-line-days={drawn.length}
		data-readout-columns={count > 0 ? count : undefined}
		data-readout-none={count > 0
			? undefined
			: 'no calculated line was returned, so there is no column to read; agreed with Susan'}
	>
		<p class="comparison" data-comparison="Each calculated line against its proposal and the line the newest day used.">
			Each calculated line against its proposal and the line the newest day used.
		</p>
		{#each evidence as note}<p data-evidence-note>{note}</p>{/each}
		{#if inputDays === null}
			<p class="lede" data-lede data-empty="missing">The calculated merge lines are unavailable for {nameSpan(windowDays)}.</p>
		{:else}
		<p class="lede" data-lede>
			{drawn.length === 0 ? 'No calculated merge lines were returned for this window.' : `${reads(drawn[drawn.length - 1].applied)} was the newest calculated line`}
		</p>
		<div use:observeWidth={(next) => (measured = next)}>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<svg
				data-chart-type="dateSeries"
				data-chart-name="Calculated merge lines"
				class="block max-w-full overflow-visible focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				tabindex="0"
				aria-label={drawn.length === 0
					? `The line ${ruleDay} was built with, on the whole range a fitted line may take`
					: windowDays === 1
						? 'Nightly calculated merge readings for this one day, on the full allowed score range. A build may have used a different line.'
						: 'Nightly calculated merge lines, on the full allowed score range. Builds may have used different lines.'}
				use:pointerReadout={{
					marks: readoutMarks(marks.map((mark) => mark.x)),
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

				{#if holdoutZone !== null}
					<!-- A calculated line inside this strip would clear a marked-apart
					     pair's score threshold if used. It is not a recorded merge.
					     Drawn as a region rather than
					     one rule a mark: four rules inside ten pixels is one grey smear.
					     What it holds is one fact about the whole plot rather than about a
					     day, so the panel's note says it in words, figures and all. -->
					<rect
						x={box.left}
						y={px(yAxis.scale(holdoutZone.high))}
						width={box.right - box.left}
						height={px(yAxis.scale(holdoutZone.low) - yAxis.scale(holdoutZone.high))}
						fill="var(--tint-bad)"
						data-line-holdout={`${holdoutZone.low.toFixed(4)},${holdoutZone.high.toFixed(4)}`}
						data-line-holdout-count={holdoutZone.count}
					/>
					<text
						x={box.left + 4}
						y={px(yAxis.scale(holdoutZone.high)) - 4}
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-line-holdout-label
					>
						the pairs marked two stories
					</text>
				{/if}

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
						y1={yAxis.scale(builtWith)}
						y2={yAxis.scale(builtWith)}
						stroke="var(--color-text-tertiary)"
						stroke-dasharray="4 4"
						data-line-rule={reads(builtWith)}
					/>
					<text
						x={box.left + 8}
						y={yAxis.scale(builtWith) - 8}
						fill="var(--color-text-tertiary)"
						font-size="12"
						data-line-rule-label
					>
						The line {ruleDay} was built with
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
							role="img"
							aria-label={columnTitle(mark.day)}
							data-line-day={mark.date}
							data-line-clamp={mark.day.clampKind}
							data-line-held={mark.day.heldReason}
							data-line-applied={reads(mark.day.applied)}
							data-line-proposed={mark.day.proposed === null ? '' : reads(mark.day.proposed)}
						>
							{#if mark.day.heldReason !== 'none'}
								<!-- A square on the date axis, so a held day is findable without
								     stepping through every day. Grey, because a held day is not a
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
			at={selected}
			name="merge-line"
			maxShare={readoutMaxShare}
			restingNote=", the newest recorded day shown"
		/>

		<p class="line-note">
			{#if drawn.length === 0}
				<span data-line-state="no-days"
					>No calculated line was returned for {nameSpan(windowDays)}. The rule is the line {ruleDay} was built
					with, and the scale is the whole range a fitted line may take.</span
				>
			{:else}
				<span data-line-state="fitted" data-line-clamp-note>{clamp}</span>
				{#if held}
					<span data-line-held-note>{held}</span>
				{/if}
			{/if}
		</p>
		{/if}
	</div>
</Panel>

<style>
	.lede {
		margin: 0 0 var(--space-3);
		font-size: var(--text-xl);
		line-height: var(--leading-xl);
		color: var(--color-text);
	}
	.comparison {
		margin: 0 0 var(--space-3);
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
	}
	/* The secondary voice every console panel uses for a caveat under a chart
	   (design-system.md). */
	.line-note {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
