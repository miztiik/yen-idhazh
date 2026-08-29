<script lang="ts">
	/** Source words against summary words, once.
	 *
	 * There used to be a second `uplot` canvas below this SVG drawing the same
	 * dataset with neither the band reference nor the truncation mark. Two
	 * drawings of one dataset disagree; the pan and zoom the dependency was
	 * bought for live in the viewport control, not in the plot.
	 *
	 * The band reference used to be one vertical `<line>` per point - 1166 nodes
	 * on the committed ledger, measured 2026-08-25, for a fact that has one value
	 * per configured band. It is one step outline now, so the node count no
	 * longer follows the point count.
	 */
	import {
		chartWidth,
		frame,
		linearAxis,
		logAxis,
		MARGIN,
		observeWidth,
		pointerReadout,
		type ReadoutMark
	} from '$lib/charts/frame';
	import {
		capLabel,
		capsInView,
		grouped,
		rowsInWindow,
		seenWords,
		type CompressionPoint,
		type SummaryBand,
		type UnplottedDay
	} from '$lib/charts/series';
	import { dayMonth } from '$lib/format';
	import type { TimeWindow } from '$lib/charts/viewport';

	let {
		points,
		viewport,
		bands,
		unplotted,
		height,
		width
	}: {
		points: CompressionPoint[];
		viewport: TimeWindow;
		bands: SummaryBand[];
		unplotted: UnplottedDay[];
		height: number;
		width: number;
	} = $props();

	/** Two rows under the plot: the decade labels, then the axis title. Nothing
	 * above it, so the plot still runs from the top edge down to `height` and
	 * this redraw changes the units without moving a point. */
	const AXIS_ROOM = 40;
	/** The 34px in `MARGIN.left` is the tick numbers' room. The rotated title
	 * gets a column of its own, because two labels in one margin overlap - at
	 * 34px flat, `200` and the title share three pixels. */
	const Y_TITLE_ROOM = 14;
	const PLOT_MARGIN = {
		...MARGIN,
		top: 0,
		bottom: AXIS_ROOM,
		left: MARGIN.left + Y_TITLE_ROOM
	};
	const MINOR_STEPS = [2, 3, 4, 5, 6, 7, 8, 9];
	/** The title sits at the outer edge of the margin it was given. */
	const Y_TITLE_X = 8;
	/** Past this the label would run off the right edge, so it flips inward. */
	const LABEL_ROOM = 90;
	/** Enough that two cap labels stack instead of sharing pixels at 10px. */
	const LABEL_STEP = 12;

	interface Segment {
		x0: number;
		x1: number;
		band: SummaryBand;
	}

	let measured = $state<number | null>(null);
	let selected = $state<number | null>(null);

	const visible = $derived(rowsInWindow(points, viewport));
	const box = $derived(frame(chartWidth(measured, width), height + AXIS_ROOM, PLOT_MARGIN));

	const xAxis = $derived(
		logAxis([100, ...visible.map((point) => point.source_words)], [box.left, box.right])
	);

	// The domain the chart has always drawn: zero to the longest summary in
	// view, floored by the widest target band. Rounding it outward would move
	// every point down the plot to buy a tick label that reads the same either
	// way - d3 picks 0, 50, 100, 150, 200 on this domain as it stands.
	const yAxis = $derived(
		linearAxis(
			[
				100,
				...visible.map((point) => point.summary_words),
				...bands.map((band) => band.target_words_max)
			],
			[box.bottom, box.top],
			{ nice: false }
		)
	);

	/** Whole decades read; the eight steps between them are what says the axis
	 * is a log one rather than a linear one with odd labels. */
	const minorTicks = $derived(
		xAxis.ticks
			.flatMap((decade) => MINOR_STEPS.map((step) => step * decade))
			.filter((value) => value < xAxis.domain[1])
	);

	const segments = $derived(
		bands
			.map((band, index) => ({
				band,
				x0: acrossPlot(band.min_source_words),
				x1: index + 1 < bands.length ? acrossPlot(bands[index + 1].min_source_words) : box.right
			}))
			.filter((segment) => segment.x1 > segment.x0)
	);

	const zone = $derived(zonePath(segments));

	/** Where the cut falls, from the points that were cut and nothing else. */
	const caps = $derived(capsInView(visible));

	/** How many rows in this window the plot could not place, because the length
	 * before the cut was never written down. Counted from the rows the server
	 * dropped, so the sentence and the plot answer out of one decision. */
	const notPlotted = $derived(
		rowsInWindow(unplotted, viewport).reduce((total, day) => total + day.n, 0)
	);

	/** A cut point whose diamond sits on its own cap line rather than past it.
	 *
	 * Those rows were measured after the cut, so their recorded article length
	 * is the length the model saw. Saying so is the only thing that stops the
	 * plot reading as "the cut removed nothing".
	 */
	const measuredAfterCut = $derived(
		visible.some((point) => point.truncation_flagged && seenWords(point) >= point.source_words)
	);

	/** One entry per drawn mark, in the order the day ran. The pointer takes the
	 * nearest by x; the arrow keys walk this order, so a step moves forward in
	 * time rather than to whatever is nearest on screen. */
	const marks = $derived<ReadoutMark[]>(
		visible.map((point) => ({
			x: xAxis.scale(point.source_words),
			lines: [
				`${dayMonth(point.date)} - ${point.item_id}`,
				point.truncation_flagged && seenWords(point) < point.source_words
					? `Article ${grouped(point.source_words)} words, cut to ${grouped(
							seenWords(point)
						)}. Summary ${grouped(point.summary_words)} words.`
					: `Article ${grouped(point.source_words)} words. Summary ${grouped(
							point.summary_words
						)} words.`
			]
		}))
	);

	const readout = $derived(selected === null ? null : (marks[selected] ?? null));

	function capX(words: number): number {
		return xAxis.scale(words);
	}

	function acrossPlot(sourceWords: number): number {
		return Math.min(box.right, Math.max(box.left, xAxis.scale(sourceWords)));
	}

	function px(value: number): number {
		return Math.round(value * 10) / 10;
	}

	/** The target zone as one closed step outline: left to right along every
	 * band's upper target, then back along its lower one.
	 *
	 * One node rather than three, because a fill and its two boundary strokes
	 * are the same two polylines drawn three times, and drawing one fact more
	 * than once is what this chart is being fixed for.
	 */
	function zonePath(steps: Segment[]): string {
		if (steps.length === 0) return '';
		const upper = steps.map((step, index) => {
			const edge = px(yAxis.scale(step.band.target_words_max));
			return `${index === 0 ? 'M' : 'L'}${px(step.x0)} ${edge} L${px(step.x1)} ${edge}`;
		});
		const lower = [...steps].reverse().map((step) => {
			const edge = px(yAxis.scale(step.band.target_words_min));
			return `L${px(step.x1)} ${edge} L${px(step.x0)} ${edge}`;
		});
		return [...upper, ...lower, 'Z'].join(' ');
	}
</script>

<section class="mt-8">
	<h2 class="text-[1.0625rem] font-semibold text-text">Compression</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		Article length uses a log x axis, so a 100-word note and a 10,000-word feature both fit. A
		diamond is an article that ran past the cap, so the machine read the start and stopped there.
		{#if measuredAfterCut}
			<span data-compression-note="measured-after"
				>Articles read before 28 August were measured after the cut, so their diamonds sit on the
				line rather than past it.</span
			>
		{/if}
		{#if notPlotted > 0}
			<span data-compression-note="not-plotted"
				>{notPlotted} articles in this window recorded no length before the cut, so they are not
				plotted.</span
			>
		{/if}
	</p>
	<div class="relative mt-4 rounded-md border border-rule bg-surface p-3" data-compression>
		<div use:observeWidth={(next) => (measured = next)}>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<svg
				class="block max-w-full overflow-visible focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				tabindex="0"
				aria-label="Article length against summary length"
				use:pointerReadout={{
					marks,
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
						{tick}
					</text>
				{/each}

				{#if visible.length === 0}
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
						fill="var(--color-text-tertiary)"
						font-size="12"
					>
						No scored items in this window
					</text>
				{:else}
					<path
						d={zone}
						fill="var(--color-accent)"
						fill-opacity="0.12"
						stroke="var(--color-accent)"
						stroke-opacity="0.5"
						data-band-zone
					>
						<title>The target summary length for each source size</title>
					</path>
					<!-- After the zone and before the points: a reference the marks sit
					     against, never one drawn over them. Not `--band-low` - a red
					     vertical says the cap is a failure, and the cap is a setting. -->
					{#each caps as cap, index (cap.words)}
						<line
							x1={capX(cap.words)}
							x2={capX(cap.words)}
							y1={box.top}
							y2={box.bottom}
							stroke="var(--color-text-tertiary)"
							stroke-opacity="0.7"
							stroke-width="1"
							stroke-dasharray="3 3"
							data-cap-line={cap.words}
						/>
						<text
							x={capX(cap.words) > box.right - LABEL_ROOM
								? capX(cap.words) - 4
								: capX(cap.words) + 4}
							y={box.top + 9 + index * LABEL_STEP}
							text-anchor={capX(cap.words) > box.right - LABEL_ROOM ? 'end' : 'start'}
							fill="var(--color-text-tertiary)"
							font-size="10"
							data-cap-label={cap.words}
						>
							{capLabel(caps, index)}
						</text>
					{/each}
					{#each visible as point (`${point.date}-${point.item_id}`)}
						{#if point.truncation_flagged}
							<rect
								x={xAxis.scale(point.source_words) - 4}
								y={yAxis.scale(point.summary_words) - 4}
								width="8"
								height="8"
								transform={`rotate(45 ${xAxis.scale(point.source_words)} ${yAxis.scale(
									point.summary_words
								)})`}
								fill="var(--band-low)"
							>
								<title>{point.date} {point.item_id}: {point.summary_words} of {point.source_words}</title>
							</rect>
						{:else}
							<circle
								cx={xAxis.scale(point.source_words)}
								cy={yAxis.scale(point.summary_words)}
								r="4"
								fill="var(--color-text)"
							>
								<title>{point.date} {point.item_id}: {point.summary_words} of {point.source_words}</title>
							</circle>
						{/if}
					{/each}
				{/if}

				{#each minorTicks as tick (tick)}
					<line
						x1={xAxis.scale(tick)}
						x2={xAxis.scale(tick)}
						y1={box.bottom}
						y2={box.bottom + 4}
						stroke="var(--color-text-tertiary)"
						stroke-opacity="0.4"
					/>
				{/each}
				{#each xAxis.ticks as tick (tick)}
					<line
						x1={xAxis.scale(tick)}
						x2={xAxis.scale(tick)}
						y1={box.bottom}
						y2={box.bottom + 7}
						stroke="var(--color-text-tertiary)"
					/>
					<text
						x={xAxis.scale(tick)}
						y={box.bottom + 18}
						text-anchor="middle"
						fill="var(--color-text-tertiary)"
						font-size="10"
					>
						{tick}
					</text>
				{/each}

				<text
					x={(box.left + box.right) / 2}
					y={box.bottom + 33}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="11"
					data-axis="x"
				>
					source words
				</text>
				<!-- Beside the axis it measures, not on the row below it. A y variable
				     labelled on the x axis is why this chart read as unfinished. -->
				<text
					x={Y_TITLE_X}
					y={(box.top + box.bottom) / 2}
					transform={`rotate(-90 ${Y_TITLE_X} ${(box.top + box.bottom) / 2})`}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-axis="y"
				>
					summary words
				</text>
			</svg>
		</div>
		{#if readout}
			<!-- Pinned to the top of the plot, never to the pointer: a readout under
			     a thumb is a readout nobody reads. It takes no pointer events, so it
			     can sit over the plot without standing between the two. -->
			<div
				class="pointer-events-none absolute inset-x-3 top-3 rounded-sm border border-rule bg-surface/95 px-2 py-1 text-[0.75rem] leading-snug"
				data-readout="compression"
				aria-live="polite"
			>
				{#each readout.lines as line, index (index)}
					<span class="block {index === 0 ? 'text-text-tertiary' : 'text-text'}">{line}</span>
				{/each}
			</div>
		{/if}
		<p class="mt-3 text-[0.75rem] text-text-tertiary">
			Dot - one article. Diamond - an article cut at the line. Dashed line - where the cut falls.
			Shaded band - the summary length we aim for at that article length.
		</p>
		<p class="mt-1 text-[0.75rem] text-text-tertiary" data-readout-hint="compression">
			Keyboard: Left and Right step through the days. Escape closes.
		</p>
	</div>
</section>
