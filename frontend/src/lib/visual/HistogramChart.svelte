<script lang="ts">
	import type { HistogramDrawing } from './histogram';
	import type { StoryChartGeometryConfig } from '$lib/server/config';

	let {
		drawing,
		geometry
	}: {
		drawing: HistogramDrawing;
		geometry: StoryChartGeometryConfig;
	} = $props();
</script>

<svg
	viewBox="0 0 {drawing.width} {drawing.height}"
	width={drawing.width}
	height={drawing.height}
	role="presentation"
>
	<text class="heading" x={drawing.bins[0]?.x ?? 0} y={geometry.axis_label_offset_px}>
		{drawing.valueHeading}
	</text>
	{#each drawing.bins as bin (bin.y)}
		<text
			class="range"
			class:emphasized={bin.emphasized}
			dominant-baseline="middle"
			x="0"
			y={bin.rangeY}
		>{bin.range}</text>
		<rect
			class="histogram-bar"
			class:emphasized={bin.emphasized}
			stroke-width={geometry.mark_outline_width_px}
			x={bin.x}
			y={bin.y}
			width={bin.width}
			height={bin.height}
			rx={geometry.bar_corner_radius_px}
		/>
		<text
			class="count"
			dominant-baseline="middle"
			x={bin.figure}
			y={bin.y + bin.height / 2}
		>{bin.displayed}</text>
	{/each}
</svg>

<style>
	.heading,
	.range,
	.count {
		font-family: inherit;
		font-size: var(--text-xs);
	}

	.heading,
	.count {
		fill: var(--color-text);
	}

	.range {
		fill: var(--color-text-secondary);
	}

	.range.emphasized {
		font-weight: 600;
	}

	.histogram-bar {
		fill: var(--chart-1);
	}

	.histogram-bar.emphasized {
		fill: var(--chart-2);
		stroke: var(--color-text);
		stroke-dasharray: var(--space-1);
	}
</style>
