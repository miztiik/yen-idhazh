<script lang="ts">
	/** Draws a `dateSeries` geometry: lines, or one stacked bar a day, over the days of a window.
	 *
	 * Hand-written SVG from the geometry and nothing else, so the chart is
	 * whole before any script runs and every number on it came out of the one
	 * call that decided it. A reading with no neighbour on either side gets a
	 * dot, because a line cannot draw a single point and a missing mark would
	 * read as a missing day. Where there is no geometry it draws the empty
	 * state it was handed, at the chart's own height.
	 *
	 * **Its hover data is the readout strip under the plot, never a tooltip.**
	 * The plot is one tab stop; a pointer, a key or a tap picks a day and the
	 * strip prints every series on it. A mark carries no `<title>`: a native
	 * tooltip needs a hover, and a hover is not a thing a thumb or a key can do.
	 * Where the chart opens something on a day - a list of what the day holds -
	 * a click or Enter picks the day, and the day held open is outlined.
	 *
	 * Two stacked segments of one day are parted by a line of the ground drawn
	 * over where they meet, so two segments of one colour still read as two and
	 * neither loses height to the line.
	 */
	import { AXIS_LABEL_PX } from '$lib/charts/frame';
	import { columnPick, pointerReadout, readoutMarks, type Readout } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import EmptyState from './EmptyState.svelte';
	import type { SeriesGeometry } from './dateSeries';
	import type { EmptyDrawing } from './empty';
	import type { AbsentHatch } from './ordered-colour';

	let {
		geometry,
		empty,
		name,
		label,
		width,
		height,
		readout = null,
		readoutMaxShare = 1,
		restingNote = ', the newest day',
		hint = 'Point at a day to read it. Left and Right step through them, Escape returns to the newest.',
		hintOne = '',
		lede = false,
		hatch = null,
		picked = null,
		onPick
	}: {
		geometry: SeriesGeometry | null;
		/** What to draw where there is no geometry. */
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
		/** The strip under the plot, one column a day in the geometry's order. */
		readout?: Readout | null;
		/** `chart.readout_max_share`. */
		readoutMaxShare?: number;
		restingNote?: string;
		hint?: string;
		/** What the strip's hint line says at one column; see `ChartReadout`. */
		hintOne?: string;
		/** True where the marks are the one thing in the panel meant to land first. */
		lede?: boolean;
		/** The stripes a hatched series is drawn in. */
		hatch?: AbsentHatch | null;
		/** The day a caller holds open, outlined on the plot. */
		picked?: number | null;
		/** Told of a day a click or Enter picked. */
		onPick?: (column: number) => void;
	} = $props();

	/** A tick mark's length, the same as the reserved frame draws. */
	const TICK = 4;
	/** A line is two pixels so it reads over the grid it crosses. */
	const LINE = 2;
	/** A lone reading's dot is as wide as the line it would have been part of,
	 * and a little more, so it is seen as a mark and not a speck. */
	const DOT = 2.5;
	/** The line of ground drawn where two stacked segments meet. */
	const JOIN = 1;
	/** How far the outline of a day held open stands off its bar. */
	const HELD = 2;

	/** The day a pointer or a key has picked, or null for the resting one. */
	let selected = $state<number | null>(null);
	/** A day held open is the strip's resting day until it is closed, so a tap
	 * that opened a list leaves that day's numbers under the plot. */
	const shown = $derived(selected ?? picked);
	const marks = $derived(readout === null ? [] : readoutMarks(geometry?.columns ?? []));
	const showing = $derived(shown ?? readout?.resting ?? null);
	const pattern = $derived(`${name}-hatch`);
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else}
	{@const box = geometry.frame}
	<div class="date-series-plot" data-readout-columns={readout?.columns.length}>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<svg
			class="date-series"
			viewBox="0 0 {box.width} {box.height}"
			width={box.width}
			height={box.height}
			role="img"
			aria-label={label}
			tabindex={readout === null ? undefined : 0}
			data-chart-type="dateSeries"
			data-chart-name={name}
			use:pointerReadout={{ marks, width: box.width, onSelect: (index) => (selected = index) }}
			use:columnPick={{ marks, width: box.width, showing, onPick: (index) => onPick?.(index) }}
		>
			{#if hatch !== null && geometry.bars.some((bar) => bar.hatched)}
				<defs>
					<pattern
						id={pattern}
						width={hatch.tile.size}
						height={hatch.tile.size}
						patternUnits="userSpaceOnUse"
						patternTransform={hatch.tile.transform}
					>
						<rect x="0" y="0" width={hatch.linePx} height={hatch.tile.size} fill={hatch.ink} />
					</pattern>
				</defs>
			{/if}
			{#each geometry.axis.ticks as tick (tick.value)}
				<line x1={box.left} x2={box.right} y1={tick.at} y2={tick.at} stroke="var(--chart-grid)" />
				{#if tick.text}
					<text
						x={box.left - TICK}
						y={tick.at}
						dy="0.32em"
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size={AXIS_LABEL_PX}>{tick.text}</text
					>
				{/if}
			{/each}
			<line x1={box.left} x2={box.right} y1={box.bottom} y2={box.bottom} stroke="var(--chart-axis)" />
			{#each geometry.ticks as tick (tick.index)}
				<line
					x1={geometry.columns[tick.index]}
					x2={geometry.columns[tick.index]}
					y1={box.bottom}
					y2={box.bottom + TICK}
					stroke="var(--chart-axis)"
				/>
				{#if tick.text}
					<text
						x={geometry.columns[tick.index]}
						y={box.bottom + TICK + AXIS_LABEL_PX}
						text-anchor={tick.anchor}
						fill="var(--color-text-tertiary)"
						font-size={AXIS_LABEL_PX}>{tick.text}</text
					>
				{/if}
			{/each}

			<g data-lede={lede ? '' : undefined} data-date-series-marks={name}>
				{#if geometry.stacked}
					{#each geometry.bars as bar (`${bar.label} ${bar.date}`)}
						<rect
							x={bar.x}
							y={bar.y}
							width={bar.width}
							height={bar.height}
							style:fill={bar.hatched && hatch !== null ? `url(#${pattern})` : bar.fill}
							data-series-bar={bar.label}
						/>
					{/each}
					{#each geometry.joins as join, at (at)}
						<line
							x1={join.x}
							x2={join.x + join.width}
							y1={join.y}
							y2={join.y}
							stroke="var(--color-surface)"
							stroke-width={JOIN}
						/>
					{/each}
				{:else}
					{#each geometry.lines as series (series.label)}
						<path d={series.path} fill="none" stroke="var({series.token})" stroke-width={LINE} />
						{#each series.points.filter((point) => point.alone) as point (point.date)}
							<circle cx={point.x} cy={point.y} r={DOT} fill="var({series.token})" />
						{/each}
					{/each}
				{/if}
			</g>

			{#if picked !== null && geometry.columns[picked] !== undefined}
				<rect
					x={geometry.columns[picked] - geometry.bandwidth / 2 - HELD}
					y={box.top - HELD}
					width={geometry.bandwidth + HELD * 2}
					height={box.bottom - box.top + HELD}
					fill="none"
					stroke="var(--color-text)"
					stroke-width="1"
					data-date-series-held={picked}
				/>
			{/if}
			{#if selected !== null && geometry.columns[selected] !== undefined}
				<line
					x1={geometry.columns[selected]}
					x2={geometry.columns[selected]}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--color-text-tertiary)"
					stroke-opacity="0.5"
					data-date-series-guide
				/>
			{/if}
		</svg>
		{#if readout !== null}
			<!-- Below the plot, never over it, and the same strip every chart on this
			     console prints: it is the key as well, so no second key is drawn. -->
			<ChartReadout
				{readout}
				at={shown}
				{name}
				maxShare={readoutMaxShare}
				{restingNote}
				{hint}
				{hintOne}
			/>
		{/if}
	</div>
{/if}

<style>
	/* Drawn at the width its caller measured; until a caller has measured one,
	   the plot shrinks to its column rather than pushing the page sideways. */
	.date-series {
		display: block;
		max-inline-size: 100%;
		block-size: auto;
	}

	.date-series:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}
</style>
