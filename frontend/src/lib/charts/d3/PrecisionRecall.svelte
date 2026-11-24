<script lang="ts">
	import { symbol, symbolDiamond, symbolSquare, symbolTriangle } from 'd3-shape';
	import { markReadout, type ReadoutFacts } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import type { CutoffShape, precisionRecall } from './precisionRecall';

	let { drawing, observations, cutoffs, percent, maxShare }: {
		drawing: NonNullable<ReturnType<typeof precisionRecall>>;
		observations: readonly ReadoutFacts[]; cutoffs: readonly ReadoutFacts[];
		percent: (value: number) => string; maxShare: number;
	} = $props();
	const name = 'judge-precision-recall';
	const box = $derived(drawing.box);
	const records = $derived([...observations, ...cutoffs]);
	let pointed = $state<number | null>(null);
	const showing = $derived(pointed ?? drawing.dots[0]?.index ?? 0);
	const shapes = { lower: symbolTriangle, upper: symbolTriangle, reporting: symbolSquare, target: symbolDiamond };
	const pathOf = (shape: CutoffShape) => symbol(shapes[shape], box.labels.fontSize ** 2 / 2)() ?? '';
	const rotation = (shape: CutoffShape) => shape === 'lower' ? 180 : 0;
	const captions: Record<CutoffShape, string> = { lower: 'Lower draw bound', upper: 'Upper draw bound',
		reporting: 'Reporting cutoff', target: 'First point reaching 90% recall' };
</script>

<div data-readout-records={records.length}>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<svg viewBox="0 0 {box.width} {box.height}" width={box.width} height={box.height}
		role="img" aria-label="Precision versus recall for the selected digest" tabindex="0"
		data-chart-type="precisionRecall" data-chart-name={name}
		use:markReadout={{ count: records.length, walk: 'row', selected: showing,
			onSelect: (next) => pointed = next, hover: { name, readout: records } }}>
		{#each drawing.y.ticks as tick (tick)}
			{@const y = drawing.y.scale(tick)}
			<line x1={box.left} x2={box.right} y1={y} y2={y} stroke="var(--chart-grid)" />
			<text x={box.left} y={y} dx="-0.35em" dy="0.35em" text-anchor="end">{percent(tick)}</text>
		{/each}
		{#each drawing.x.ticks as tick (tick)}
			{@const x = drawing.x.scale(tick)}
			<line x1={x} x2={x} y1={box.top} y2={box.bottom} stroke="var(--chart-grid)" />
			<text {x} y={box.bottom + box.labels.leading} text-anchor={tick === 0 ? 'start' : tick === 1 ? 'end' : 'middle'}>{percent(tick)}</text>
		{/each}
		{#each drawing.dots as dot (dot.index)}
			<circle cx={dot.x} cy={dot.y} r={box.labels.fontSize / 4}
				fill="var(--chart-measure)" data-readout-at={dot.index} />
		{/each}
		{#each drawing.markers as marker (marker.index)}
			<path d={pathOf(marker.shape)} transform="translate({marker.x},{marker.y}) rotate({rotation(marker.shape)})"
				fill="var(--chart-2)" stroke="var(--color-surface)" data-cutoff-marker={marker.shape}
				data-readout-at={observations.length + marker.index}>
				<title>{captions[marker.shape]}</title>
			</path>
		{/each}
	</svg>
	<ChartReadout readout={records[showing] ?? null} {name} {maxShare} resting={pointed === null}
		hint="Point at a dot or shape for counts. Left and Right step through the cutoffs." />
</div>

<style>
	svg { display: block; max-inline-size: 100%; font-size: var(--console-small-size); }
	text { fill: var(--color-text-secondary); }
</style>
