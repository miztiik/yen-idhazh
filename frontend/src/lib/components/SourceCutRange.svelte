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
		labelGutter,
		labelWidth,
		logAxis,
		observeWidth,
		ROW_PITCH_MIN,
		rowPitch,
		tickAnchor,
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

	/** The row label, and the count on the line under it. */
	const NAME_PX = 11;
	const COUNT_PX = 10;
	/** Clear pixels between the name column and the plot. */
	const GUTTER_GAP = 10;
	/** A row carries two lines of type and a 10px bar. The floor is that ink plus
	 * a line of air; below it the rows touch and the plot reads as a list. */
	const PITCH_MIN = ROW_PITCH_MIN;
	/** Where the name sits above the track instead of beside it, the row is one
	 * line of type, then the track, then the air that separates two rows. */
	const PITCH_MIN_STACKED = ROW_PITCH_MIN + 12;
	/** Past this a row is spaced rather than tall, and six of them stop reading
	 * as one set. */
	const PITCH_MAX = 56;
	/** Enough that two cap labels stack instead of sharing pixels at 10px. */
	const LABEL_STEP = 12;
	/** The decade labels, then the axis title under them. */
	const AXIS_ROOM = 40;
	/** Whole decades read; the eight steps between them are what says the axis is
	 * a log one rather than a linear one with odd labels. */
	const MINOR_STEPS = [2, 3, 4, 5, 6, 7, 8, 9];
	/** The right-most decade label anchors `end`, so it needs no room outside the
	 * plot. This is the stroke of the track's round cap and nothing more. */
	const RIGHT_ROOM = 12;
	/** Where the name column has to go when it cannot sit beside the plot. */
	const STACK_NAME_Y = 11;
	const STACK_TRACK_Y = 30;

	let measured = $state<number | null>(null);

	const chartBox = $derived(chartWidth(measured, width));

	function countText(source: SourceCut): string {
		return `${source.cut} of ${source.articles} cut`;
	}

	/** The room the two label lines need, or null where the frame cannot spare
	 * it.
	 *
	 * A fixed 168px gutter was 12 percent of a 1,342px frame and 52 percent of a
	 * 324px one, measured 2026-09-01 - so on a phone the labels took more of the
	 * chart than the plot did, and the six tracks drew inside 91px. A source id is
	 * the ledger's own spelling of a name, so there is no shorter true form of it:
	 * where it will not fit beside the plot it goes above it.
	 */
	const gutter = $derived.by(() => {
		const names = labelGutter(
			rows.map((source) => source.sourceId),
			NAME_PX,
			GUTTER_GAP,
			chartBox
		);
		const counts = labelGutter(rows.map(countText), COUNT_PX, GUTTER_GAP, chartBox);
		return names === null || counts === null ? null : Math.max(names, counts);
	});
	const stacked = $derived(gutter === null);
	/** The value axis anchors its first decade `start`, so a stacked plot needs
	 * no left margin beyond the track's own round cap. */
	const leftRoom = $derived(gutter ?? RIGHT_ROOM);
	const innerRoom = $derived(Math.max(1, chartBox - leftRoom - RIGHT_ROOM));
	const pitch = $derived(
		rowPitch(innerRoom, stacked ? PITCH_MIN_STACKED : PITCH_MIN, PITCH_MAX)
	);

	/** The labels sit above the first row rather than beside their rules, where
	 * they would cross a track, so the room they need is the room they take. */
	const top = $derived(10 + Math.max(1, caps.length) * LABEL_STEP);

	const box = $derived(
		frame(chartBox, top + rows.length * pitch + AXIS_ROOM, {
			top,
			right: RIGHT_ROOM,
			bottom: AXIS_ROOM,
			left: leftRoom
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
			top: box.top + index * pitch,
			marks: rangeMarks(source.lengths, widest, (words) => xAxis.scale(words))
		}))
	);

	/** Where the track sits inside a row, and where the two label lines sit
	 * against it. Beside the plot the pair is centred on the track; above it the
	 * name leads and the track follows. */
	function trackY(rowTop: number): number {
		return stacked ? rowTop + STACK_TRACK_Y : rowTop + pitch / 2;
	}

	function px(value: number): number {
		return Math.round(value * 10) / 10;
	}

	/** Whether a cap label would run past the right edge if it read left to
	 * right, from the room the label itself needs rather than from a constant.
	 * A constant is what stopped being big enough the last time. */
	function flips(x: number, index: number): boolean {
		return x + 4 + labelWidth(capLabel(caps, index), 10) > box.right;
	}

	function sentence(source: SourceCut): string {
		return `${source.sourceId}: ${source.cut} of ${source.articles} articles cut. Shortest article ${grouped(source.lengths.min)} words, middle ${grouped(source.lengths.median)}, longest ${grouped(source.lengths.max)}.`;
	}
</script>

<div
	class="plot"
	data-source-cuts="range"
	data-readout-none="one row per source, so a pointer is already on the row a strip would print"
>
	<div use:observeWidth={(next) => (measured = next)}>
		<svg
			class="block max-w-full"
			width={box.width}
			height={box.height}
			viewBox={`0 0 ${box.width} ${box.height}`}
			role="img"
			aria-label="Article length by source, against the cut point"
			data-source-cuts-layout={stacked ? 'stacked' : 'beside'}
			data-source-cuts-pitch={pitch}
			data-source-cuts-plot={px(box.innerWidth)}
			data-source-cuts-frame={box.width}
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

			{#each xAxis.ticks as tick, index (tick)}
				<line
					x1={px(xAxis.scale(tick))}
					x2={px(xAxis.scale(tick))}
					y1={box.bottom}
					y2={box.bottom + 5}
					stroke="var(--color-text-tertiary)"
				/>
				<!-- The end decades sit ON the plot edges, so a centred label there hangs
				     half its width outside the frame and the `svg` cuts it: measured
				     2026-08-31 at 1440, `10,000` lost 3.2px off its right. -->
				<text
					x={px(xAxis.scale(tick))}
					y={box.bottom + 17}
					text-anchor={tickAnchor(index, xAxis.ticks.length)}
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
					x={flips(x, index) ? px(x) - 4 : px(x) + 4}
					y={box.top - 10 - (caps.length - 1 - index) * LABEL_STEP}
					text-anchor={flips(x, index) ? 'end' : 'start'}
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-cap-label={cap.words}
				>
					{capLabel(caps, index)}
				</text>
			{/each}

			{#each placed as row (row.source.sourceId)}
				{@const y = trackY(row.top)}
				<g
					data-source-cut={row.source.sourceId}
					data-range-min={row.source.lengths.min}
					data-range-median={row.source.lengths.median}
					data-range-max={row.source.lengths.max}
					data-range-past={row.marks.past ? 'yes' : 'no'}
				>
					<title>{sentence(row.source)}</title>
					<!-- Beside the plot where the frame can hold the widest name, above it
					     where it cannot. A name is a source id and there is no shorter true
					     form of it, so the gutter moves rather than the word. -->
					<text
						x={stacked ? box.left : box.left - GUTTER_GAP}
						y={stacked ? row.top + STACK_NAME_Y : y - 2}
						text-anchor={stacked ? 'start' : 'end'}
						fill="var(--color-text)"
						font-size={NAME_PX}
						data-source-cell="name"
					>
						{row.source.sourceId}
					</text>
					<text
						x={stacked ? box.right : box.left - GUTTER_GAP}
						y={stacked ? row.top + STACK_NAME_Y : y + 10}
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size={COUNT_PX}
						data-source-cell="count"
					>
						{countText(row.source)}
					</text>

					<line
						x1={px(row.marks.x0)}
						x2={px(row.marks.x1)}
						y1={y}
						y2={y}
						stroke="var(--chart-8)"
						stroke-width="4"
						stroke-linecap="round"
						data-range-cell="track"
					/>
					{#if row.marks.past}
						<line
							x1={px(row.marks.xCut)}
							x2={px(row.marks.x1)}
							y1={y}
							y2={y}
							stroke="var(--chart-1)"
							stroke-width="10"
							stroke-linecap="round"
							data-range-cell="past"
						/>
					{/if}
					<circle
						cx={px(row.marks.xMid)}
						cy={y}
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
