<script lang="ts">
	/** Draws a `dateSeries` geometry: lines, or one stacked bar a day, over the days of a window.
	 *
	 * Hand-written SVG from the geometry and nothing else, so the chart is
	 * whole before any script runs and every number on it came out of the one
	 * call that decided it. A reading with no neighbour on either side gets a
	 * dot, because a line cannot draw a single point and a missing mark would
	 * read as a missing day. Where there is no geometry it draws the empty
	 * state it was handed, at the chart's own height.
	 */
	import { AXIS_LABEL_PX } from '$lib/charts/frame';
	import EmptyState from './EmptyState.svelte';
	import type { SeriesGeometry } from './dateSeries';
	import type { EmptyDrawing } from './empty';

	let {
		geometry,
		empty,
		name,
		label,
		width,
		height
	}: {
		geometry: SeriesGeometry | null;
		/** What to draw where there is no geometry. */
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
	} = $props();

	/** A tick mark's length, the same as the reserved frame draws. */
	const TICK = 4;
	/** A line is two pixels so it reads over the grid it crosses. */
	const LINE = 2;
	/** A lone reading's dot is as wide as the line it would have been part of,
	 * and a little more, so it is seen as a mark and not a speck. */
	const DOT = 2.5;
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else}
	{@const box = geometry.frame}
	<svg
		class="date-series"
		viewBox="0 0 {box.width} {box.height}"
		width={box.width}
		height={box.height}
		role="img"
		aria-label={label}
		data-chart-type="dateSeries"
		data-chart-name={name}
	>
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

		{#if geometry.stacked}
			{#each geometry.bars as bar (`${bar.label} ${bar.date}`)}
				<rect x={bar.x} y={bar.y} width={bar.width} height={bar.height} fill="var({bar.token})">
					<title>{bar.label}, {bar.date}: {bar.value}</title>
				</rect>
			{/each}
		{:else}
			{#each geometry.lines as series (series.label)}
				<path d={series.path} fill="none" stroke="var({series.token})" stroke-width={LINE} />
				{#each series.points.filter((point) => point.alone) as point (point.date)}
					<circle cx={point.x} cy={point.y} r={DOT} fill="var({series.token})" />
				{/each}
			{/each}
		{/if}
	</svg>
{/if}
