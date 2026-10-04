<script lang="ts">
	/** Draws a `pairedScatter` geometry: one dot a reading, and no line through them.
	 *
	 * There is no trend line to draw because the geometry holds none. The dots
	 * are hollow, so where many fall together the crowd reads as a crowd rather
	 * than one blot, and each carries its subject and both readings in its
	 * title. Where there is no geometry it draws the empty state it was handed,
	 * which for a floor missed names the floor.
	 */
	import { AXIS_LABEL_PX } from '$lib/charts/frame';
	import EmptyState from './EmptyState.svelte';
	import type { EmptyDrawing } from './empty';
	import type { ScatterGeometry } from './pairedScatter';

	let {
		geometry,
		empty,
		name,
		label,
		width,
		height
	}: {
		geometry: ScatterGeometry | null;
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
	} = $props();

	/** A tick mark's length, the same as the reserved frame draws. */
	const TICK = 4;
	/** A dot big enough to point at, small enough that neighbours stay apart. */
	const DOT = 3;
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else}
	{@const box = geometry.frame}
	<svg
		class="paired-scatter"
		viewBox="0 0 {box.width} {box.height}"
		width={box.width}
		height={box.height}
		role="img"
		aria-label={label}
		data-chart-type="pairedScatter"
		data-chart-name={name}
		data-readout-records={geometry.marks.length}
	>
		{#each geometry.y.ticks as tick (tick.value)}
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
		{#each geometry.x.ticks as tick (tick.value)}
			<line x1={tick.at} x2={tick.at} y1={box.bottom} y2={box.bottom + TICK} stroke="var(--chart-axis)" />
			{#if tick.text}
				<text
					x={tick.at}
					y={box.bottom + TICK + AXIS_LABEL_PX}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size={AXIS_LABEL_PX}>{tick.text}</text
				>
			{/if}
		{/each}
		{#each geometry.marks as mark, index (index)}
			<circle cx={mark.cx} cy={mark.cy} r={DOT} fill="none" stroke="var(--chart-1)" aria-label={`${mark.label}: ${mark.x}, ${mark.y}`} />
		{/each}
	</svg>
{/if}
