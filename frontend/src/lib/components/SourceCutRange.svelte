<script lang="ts">
	/** How long the articles are, per source, against the cap that cuts them.
	 *
	 * This was five columns of numbers. The single number every one of them had
	 * to be compared against - where the cut falls - appeared nowhere in the
	 * section, so reading it meant holding a figure the page never printed. The
	 * cut point is a rule across every row now, and the distance right of it is
	 * the text the machine never read.
	 *
	 * The axis is a log one because article lengths here span more than two
	 * decades: a release note and a long read sit on the same row set, and a
	 * linear axis crushes every short source against the left edge.
	 *
	 * Hand-written SVG, so the plot is complete before any script runs and both
	 * themes work with no JavaScript at all - every colour leaves as a custom
	 * property rather than a hex.
	 */
	import {
		chartWidth,
		frame,
		logAxis,
		observeWidth,
		type Margin
	} from '$lib/charts/frame';
	import { capLabel, grouped, rangeMarks } from '$lib/charts/series';
	import type { CapPoint, SourceCut } from '../../routes/console/+page.server';

	let {
		rows,
		caps,
		width
	}: {
		rows: SourceCut[];
		/** Every cut point in the window, oldest first. Empty draws no rule. */
		caps: CapPoint[];
		width: number;
	} = $props();

	/** One source: the name, the count under it, and the track between them. */
	const ROW = 34;
	/** The longest source id in the committed ledger is 23 characters, measured
	 * 2026-08-30 over 143 distinct sources, and the count sits on its own line
	 * below - so the margin holds a name and never a name plus a sentence. */
	const LABEL_ROOM = 168;
	/** Enough that two cap labels stack instead of sharing pixels at 10px. */
	const LABEL_STEP = 12;
	/** The decade labels, then the axis title under them. */
	const AXIS_ROOM = 40;
	/** Whole decades read; the eight steps between them are what says the axis is
	 * a log one rather than a linear one with odd labels. */
	const MINOR_STEPS = [2, 3, 4, 5, 6, 7, 8, 9];
	/** Past this the cap label would run off the right edge, so it flips inward. */
	const LABEL_ROOM_RIGHT = 130;

	let measured = $state<number | null>(null);

	/** The labels sit above the first row rather than beside their rules, where
	 * they would cross a track, so the room they need is the room they take. */
	const top = $derived(10 + Math.max(1, caps.length) * LABEL_STEP);

	const box = $derived(
		frame(chartWidth(measured, width), top + rows.length * ROW + AXIS_ROOM, {
			top,
			right: 12,
			bottom: AXIS_ROOM,
			left: LABEL_ROOM
		} satisfies Margin)
	);

	const xAxis = $derived(
		logAxis(
			[
				...rows.flatMap((source) => [source.lengths.min, source.lengths.max]),
				...caps.map((cap) => cap.words)
			],
			[box.left, box.right]
		)
	);

	const minorTicks = $derived(
		xAxis.ticks
			.flatMap((decade) => MINOR_STEPS.map((step) => step * decade))
			.filter((value) => value > xAxis.domain[0] && value < xAxis.domain[1])
	);

	/** The widest cut point, and where the emphasised span starts.
	 *
	 * A window can hold two: over the committed ledger a thirty-day one holds a
	 * cut at 1,923 words and another at 3,846. Past the widest, an article lost
	 * text whichever cut was in force; between the two, only some did. So the
	 * emphasis takes the widest and says the strong thing, and the narrower rule
	 * is drawn with its own dates so the move is visible rather than averaged.
	 */
	const widest = $derived(caps.length === 0 ? null : Math.max(...caps.map((cap) => cap.words)));

	const placed = $derived(
		rows.map((source, index) => ({
			source,
			top: box.top + index * ROW,
			marks: rangeMarks(source.lengths, widest, (words) => xAxis.scale(words))
		}))
	);

	function px(value: number): number {
		return Math.round(value * 10) / 10;
	}

	function flips(x: number): boolean {
		return x > box.right - LABEL_ROOM_RIGHT;
	}

	function sentence(source: SourceCut): string {
		return `${source.sourceId}: ${source.cut} of ${source.articles} articles cut. Shortest article ${grouped(source.lengths.min)} words, middle ${grouped(source.lengths.median)}, longest ${grouped(source.lengths.max)}.`;
	}
</script>

<div class="plot" data-source-cuts="range">
	<div use:observeWidth={(next) => (measured = next)}>
		<svg
			class="block max-w-full"
			width={box.width}
			height={box.height}
			viewBox={`0 0 ${box.width} ${box.height}`}
			role="img"
			aria-label="Article length by source, against the cut point"
		>
			<line
				x1={box.left}
				x2={box.right}
				y1={box.bottom}
				y2={box.bottom}
				stroke="var(--color-rule)"
			/>

			{#each minorTicks as tick (tick)}
				<line
					x1={px(xAxis.scale(tick))}
					x2={px(xAxis.scale(tick))}
					y1={box.bottom}
					y2={box.bottom + 3}
					stroke="var(--color-rule-strong)"
				/>
			{/each}

			{#each xAxis.ticks as tick (tick)}
				<line
					x1={px(xAxis.scale(tick))}
					x2={px(xAxis.scale(tick))}
					y1={box.bottom}
					y2={box.bottom + 5}
					stroke="var(--color-text-tertiary)"
				/>
				<text
					x={px(xAxis.scale(tick))}
					y={box.bottom + 17}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-tick="x"
				>
					{grouped(tick)}
				</text>
			{/each}

			<text
				x={box.left}
				y={box.bottom + 32}
				fill="var(--color-text-tertiary)"
				font-size="10"
				data-axis-title
			>
				Article length, words
			</text>

			<!-- The reference every track is read against, drawn before them so a
			     mark sits on top of a rule rather than under it. Not the confidence
			     ramp: a red vertical would say the cap is a fault, and the cap is a
			     setting somebody chose. -->
			{#each caps as cap, index (cap.words)}
				{@const x = xAxis.scale(cap.words)}
				<line
					x1={px(x)}
					x2={px(x)}
					y1={box.top - 6}
					y2={box.bottom}
					stroke="var(--color-text-tertiary)"
					stroke-dasharray="3 3"
					data-cap-line={cap.words}
				/>
				<text
					x={flips(x) ? px(x) - 4 : px(x) + 4}
					y={box.top - 10 - (caps.length - 1 - index) * LABEL_STEP}
					text-anchor={flips(x) ? 'end' : 'start'}
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-cap-label={cap.words}
				>
					{capLabel(caps, index)}
				</text>
			{/each}

			{#each placed as row (row.source.sourceId)}
				<g
					data-source-cut={row.source.sourceId}
					data-range-min={row.source.lengths.min}
					data-range-median={row.source.lengths.median}
					data-range-max={row.source.lengths.max}
					data-range-past={row.marks.past ? 'yes' : 'no'}
				>
					<title>{sentence(row.source)}</title>
					<text
						x={box.left - 10}
						y={row.top + 15}
						text-anchor="end"
						fill="var(--color-text)"
						font-size="11"
						data-source-cell="name"
					>
						{row.source.sourceId}
					</text>
					<text
						x={box.left - 10}
						y={row.top + 27}
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-source-cell="count"
					>
						{row.source.cut} of {row.source.articles} cut
					</text>

					<line
						x1={px(row.marks.x0)}
						x2={px(row.marks.x1)}
						y1={row.top + 17}
						y2={row.top + 17}
						stroke="var(--chart-8)"
						stroke-width="4"
						stroke-linecap="round"
						data-range-cell="track"
					/>
					{#if row.marks.past}
						<line
							x1={px(row.marks.xCut)}
							x2={px(row.marks.x1)}
							y1={row.top + 17}
							y2={row.top + 17}
							stroke="var(--chart-1)"
							stroke-width="10"
							stroke-linecap="round"
							data-range-cell="past"
						/>
					{/if}
					<circle
						cx={px(row.marks.xMid)}
						cy={row.top + 17}
						r="3.5"
						fill="var(--color-text)"
						stroke="var(--color-surface)"
						stroke-width="1"
						data-range-cell="median"
					/>
				</g>
			{/each}
		</svg>
	</div>

	<ul class="key" data-source-cuts="key">
		<li><span class="swatch swatch-range"></span>shortest to longest article, dot at the middle one</li>
		<li><span class="swatch swatch-past"></span>past the cut - the part the machine never read</li>
	</ul>
</div>

<style>
	.plot {
		overflow-x: auto;
		padding: var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
		box-shadow: var(--shadow-sm);
	}

	.key {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-5);
		margin-block-start: var(--space-3);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}

	.key li {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.swatch {
		display: inline-block;
		inline-size: 18px;
		border-radius: var(--radius-full);
		flex: none;
	}

	.swatch-range {
		block-size: 4px;
		background: var(--chart-8);
	}

	.swatch-past {
		block-size: 10px;
		background: var(--chart-1);
	}
</style>
