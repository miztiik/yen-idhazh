<script lang="ts">
	import type { PieDrawing } from './bar';

	let { drawing }: { drawing: PieDrawing } = $props();
</script>

<svg
	viewBox="0 0 {drawing.width} {drawing.height}"
	width={drawing.width}
	height={drawing.height}
	role="presentation"
>
	<g transform={`translate(${drawing.width / 2}, ${drawing.height / 2})`}>
		{#each drawing.geometry.slices as slice (slice.label)}
			<path
				class="pie-slice"
				class:emphasized={slice.emphasized}
				d={slice.path}
				style={`fill: var(${slice.color})`}
			></path>
		{/each}
	</g>
</svg>
<div class="pie-readings px-3 pb-3 text-xs leading-normal text-text-secondary">
	<p class="font-semibold text-text">Declared total: {drawing.whole}</p>
	<ul>
		{#each drawing.parts as part (part.label)}
			<li class:highlighted={part.emphasized}>
				<span class="font-semibold text-text">{part.label}</span>: {part.displayed}%
			</li>
		{/each}
	</ul>
</div>

<style>
	.pie-slice {
		stroke: var(--color-surface);
		stroke-width: 1px;
	}

	.pie-slice.emphasized {
		stroke: var(--color-text);
		stroke-dasharray: var(--space-1);
		stroke-width: 2px;
	}

	.pie-readings ul {
		list-style: none;
		padding: 0;
	}

	.pie-readings .highlighted {
		font-weight: var(--font-weight-semibold);
		color: var(--color-text);
	}
</style>
