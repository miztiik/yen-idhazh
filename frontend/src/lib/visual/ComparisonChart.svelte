<script lang="ts">
	import { statedComparisonRow, type BarDrawing, type DotDrawing } from './comparison';
	import type { StoryChartGeometryConfig } from '$lib/server/config';

	let { drawing, geometry }: { drawing: BarDrawing | DotDrawing; geometry: StoryChartGeometryConfig } = $props();
	const tickEnd = $derived(drawing.baseline + geometry.axis_label_offset_px / 4);
</script>

{#snippet rowText(row: BarDrawing['bars'][number] | DotDrawing['dots'][number])}
	<text class="name" x={drawing.inset} y={row.label}>
		{#each row.lines as line, index (index)}
			<tspan x={drawing.inset} y={row.label + index * drawing.leading}>{line}</tspan>
		{/each}
	</text>
	<text class="figure" text-anchor="end" x={drawing.valueX} y={row.center}>{row.displayed}</text>
{/snippet}

{#snippet guides(top: number, bottom: number)}
	{#each drawing.axis.ticks as tick (tick.value)}
		<line class="guide" class:zero={drawing.type === 'bar' && tick.value === 0}
			stroke-width={geometry.axis_line_width_px} x1={tick.x} x2={tick.x} y1={top} y2={bottom} />
	{/each}
{/snippet}

{#if drawing.type === 'bar'}
	{#each drawing.bars as bar (bar.center)}
		<g>
			{@render guides(bar.plotTop, bar.plotBottom)}
			<rect class="bar" fill={`var(${bar.color})`} x={bar.x} y={bar.y} width={bar.width}
				height={bar.height} rx={geometry.bar_corner_radius_px}>
				<title>{statedComparisonRow(bar, drawing.unit)}</title>
			</rect>
			{@render rowText(bar)}
		</g>
	{/each}
{:else}
	{#each drawing.dots as dot (dot.center)}
		<g>
			{@render guides(dot.plotTop, dot.plotBottom)}
			<circle class="dot" fill={`var(${dot.color})`} cx={dot.x} cy={dot.y} r={dot.radius}>
				<title>{statedComparisonRow(dot, drawing.unit)}</title>
			</circle>
			{@render rowText(dot)}
		</g>
	{/each}
{/if}

<line class="axis" stroke-width={geometry.axis_line_width_px}
	x1={drawing.axis.left} x2={drawing.axis.right} y1={drawing.baseline} y2={drawing.baseline} />
{#each drawing.axis.ticks as tick (tick.value)}
	<line class="axis" stroke-width={geometry.axis_line_width_px}
		x1={tick.x} x2={tick.x} y1={drawing.baseline} y2={tickEnd} />
	{#if tick.text}
		<text class="tick" text-anchor={tick.anchor} x={tick.x} y={drawing.axis.tickY}>{tick.text}</text>
	{/if}
{/each}
{#each drawing.axis.label as line, index (index)}
	<text class="unit" x={drawing.inset} y={drawing.axis.labelY + index * drawing.leading}>{line}</text>
{/each}

<style>
	text {
		dominant-baseline: middle;
		fill: var(--color-text-secondary);
	}

	.name,
	.figure {
		fill: var(--color-text);
	}

	.figure,
	.tick {
		font-variant-numeric: tabular-nums;
	}

	.axis,
	.guide.zero {
		stroke: var(--chart-axis);
	}

	.guide {
		stroke: var(--chart-grid);
	}
</style>
