<script lang="ts">
	import { statedComparisonRow, type BarDrawing, type ComparisonText, type DotDrawing } from './comparison';
	import type { StoryChartGeometryConfig } from '$lib/server/config';

	let { drawing, geometry }: { drawing: BarDrawing | DotDrawing; geometry: StoryChartGeometryConfig } = $props();
</script>

{#snippet plotText(label: ComparisonText, style: string)}
	<text class={style} x={label.x} y={label.y} text-anchor={label.anchor}>
		{#each label.lines as line, index (index)}
			<tspan x={label.x} y={label.y + index * drawing.leading}>{line}</tspan>
		{/each}
	</text>
{/snippet}

{#snippet rowText(row: BarDrawing['bars'][number] | DotDrawing['dots'][number])}
	{@render plotText(row.label, 'name')}
	{@render plotText(row.reading, 'figure')}
{/snippet}

<g data-comparison-orientation={drawing.orientation}>
	{#each drawing.axis.ticks as tick (tick.value)}
		{#each tick.guides as guide, index (index)}
			<line class="guide" class:zero={drawing.type === 'bar' && tick.value === 0}
				stroke-width={geometry.axis_line_width_px} {...guide} />
		{/each}
	{/each}

	{#if drawing.type === 'bar'}
		{#each drawing.bars as bar (bar.id)}
			<g class="comparison-row">
				<rect class="bar" fill={`var(${bar.color})`} x={bar.x} y={bar.y} width={bar.width}
					height={bar.height} rx={geometry.bar_corner_radius_px}>
					<title>{statedComparisonRow(bar)}</title>
				</rect>
				{@render rowText(bar)}
			</g>
		{/each}
	{:else}
		{#each drawing.dots as dot (dot.id)}
			<g class="comparison-row">
				<circle class="dot" fill={`var(${dot.color})`} cx={dot.x} cy={dot.y} r={dot.radius}>
					<title>{statedComparisonRow(dot)}</title>
				</circle>
				{@render rowText(dot)}
			</g>
		{/each}
	{/if}

	<line class="axis" stroke-width={geometry.axis_line_width_px} {...drawing.axis.line} />
	{#each drawing.axis.ticks as tick (tick.value)}
		<line class="axis" stroke-width={geometry.axis_line_width_px} {...tick.line} />
		{#if tick.label}
			{@render plotText(tick.label, 'tick')}
		{/if}
	{/each}
	{#if drawing.axis.note.lines.length}
		{@render plotText(drawing.axis.note, 'unit')}
	{/if}
</g>

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
