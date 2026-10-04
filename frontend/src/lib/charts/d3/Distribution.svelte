<script lang="ts">
	/** Draws a `distribution` geometry: counts in bins, with the running share on a second axis.
	 *
	 * The count axis is on the left and the share axis, nought to a hundred, on
	 * the right, and the curve is drawn over the bars in the text colour rather
	 * than a series hue, because it is a reading of the bars and not a second
	 * quantity. A named rule is a dashed upright at its own value with its name
	 * above it. Where there is no geometry it draws the empty state it was
	 * handed, which for a floor missed names the floor.
	 */
	import { AXIS_LABEL_PX } from '$lib/charts/frame';
	import type { BinGeometry } from './distribution';
	import EmptyState from './EmptyState.svelte';
	import type { EmptyDrawing } from './empty';

	let {
		geometry,
		empty,
		name,
		label,
		width,
		height
	}: {
		geometry: BinGeometry | null;
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
	} = $props();

	/** A tick mark's length, the same as the reserved frame draws. */
	const TICK = 4;
	/** The curve is a reading drawn over marks, so it is thinner than a series
	 * line and still clear of the bars' edges. */
	const CURVE = 1.5;
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else}
	{@const box = geometry.frame}
	<svg
		class="distribution"
		viewBox="0 0 {box.width} {box.height}"
		width={box.width}
		height={box.height}
		role="img"
		aria-label={label}
		data-chart-type="distribution"
		data-chart-name={name}
		data-readout-records={geometry.bins.length}
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
		{#each geometry.share.ticks as tick (tick.value)}
			{#if tick.text}
				<text
					x={box.right + TICK}
					y={tick.at}
					dy="0.32em"
					text-anchor="start"
					fill="var(--color-text-tertiary)"
					font-size={AXIS_LABEL_PX}>{tick.text}%</text
				>
			{/if}
		{/each}

		{#each geometry.bins as bin (bin.x0)}
			<rect x={bin.left} y={bin.top} width={bin.width} height={bin.height} fill="var(--chart-1)" aria-label={`${bin.x0} to ${bin.x1}: ${bin.count} rows, ${bin.share.toFixed(1)}% at or below`} />
		{/each}
		<path d={geometry.cumulative} fill="none" stroke="var(--color-text)" stroke-width={CURVE} />

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

		{#each geometry.rules as rule (rule.label)}
			<line
				x1={rule.x}
				x2={rule.x}
				y1={box.top}
				y2={box.bottom}
				stroke="var(--chart-marker)"
				stroke-dasharray="3 3"
			/>
			<text
				x={rule.x}
				y={box.top}
				dy="-0.3em"
				text-anchor="middle"
				fill="var(--color-text-secondary)"
				font-size={AXIS_LABEL_PX}>{rule.label}</text
			>
		{/each}
	</svg>
	{@const resting = geometry.bins.reduce((best, bin) => (bin.count > best.count ? bin : best), geometry.bins[0])}
	{#if resting}
		<dl class="record-readout" data-readout={name} data-readout-shape="record">
			<dt data-readout-subject>{resting.x0} to {resting.x1}</dt>
			<div data-readout-row="rows"><dd>Rows</dd><dd>{resting.count}</dd></div>
			<div data-readout-row="share"><dd>At or below</dd><dd>{resting.share.toFixed(1)}%</dd></div>
		</dl>
	{/if}
{/if}

<style>
	.record-readout {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-4);
		margin: var(--space-3) 0 0;
		color: var(--color-text-secondary);
		font-size: var(--text-xs);
	}

	.record-readout dt {
		flex-basis: 100%;
		font-weight: 600;
	}

	.record-readout div {
		display: flex;
		gap: var(--space-1);
	}

	.record-readout dd {
		margin: 0;
	}
</style>
