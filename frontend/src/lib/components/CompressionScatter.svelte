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
	import { chartWidth, frame, linearAxis, logAxis, MARGIN, observeWidth } from '$lib/charts/frame';
	import { rowsInWindow, type CompressionPoint, type SummaryBand } from '$lib/charts/series';
	import type { TimeWindow } from '$lib/charts/viewport';

	let {
		points,
		viewport,
		bands,
		height,
		width
	}: {
		points: CompressionPoint[];
		viewport: TimeWindow;
		bands: SummaryBand[];
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

	interface Segment {
		x0: number;
		x1: number;
		band: SummaryBand;
	}

	let measured = $state<number | null>(null);

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
		Source words use a log x axis. Diamonds mark summaries that carried the truncation flag.
	</p>
	<div class="mt-4 rounded-md border border-rule bg-surface p-3" data-compression>
		<div use:observeWidth={(next) => (measured = next)}>
			<svg
				class="block max-w-full overflow-visible"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				aria-label="Source words against summary words"
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
		<p class="mt-3 text-[0.75rem] text-text-tertiary">
			Dot - one scored item. Diamond - the source was truncated. Shaded band - the target summary
			length for that source size.
		</p>
	</div>
</section>
