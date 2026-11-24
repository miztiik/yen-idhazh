<script lang="ts">
	import { symbol, symbolDiamond } from 'd3-shape';
	import { columnPick, pointerReadout, readoutMarks, type ReadoutFacts } from '$lib/charts/readout';
	import type { ChartToken } from '$lib/charts/theme';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import { spaceValueTicks } from './axis';
	import type { scoreIntervals } from './scoreIntervals';

	let { drawing, selected, facts, tokens, format, maxShare, onPick }: {
		drawing: NonNullable<ReturnType<typeof scoreIntervals>>;
		selected: string;
		facts: readonly ReadoutFacts[];
		tokens: readonly ChartToken[];
		format: (n: number) => string;
		maxShare: number;
		onPick: (date: string) => void;
	} = $props();
	const name = 'judge-draw-intervals';
	let pointed = $state<number | null>(null);
	const rest = $derived(Math.max(0, drawing.columns.findIndex(({ date }) => date === selected)));
	const at = $derived(pointed ?? rest);
	const marks = $derived(readoutMarks(drawing.xs));
	const box = $derived(drawing.box);
	const ticks = $derived(spaceValueTicks(drawing.axis.ticks.map((value) => ({
		value, at: drawing.axis.scale(value), text: format(value)
	})), box, 'y'));
	const diamond = $derived(symbol(symbolDiamond, box.labels.fontSize ** 2 / 3)() ?? '');
</script>

<div data-readout-records={facts.length}>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<svg viewBox="0 0 {box.width} {box.height}" width={box.width} height={box.height}
		role="img" aria-label="Score intervals by UTC digest date" tabindex="0"
		data-chart-type="scoreIntervals" data-chart-name={name}
		use:pointerReadout={{ marks, width: box.width, selected: at, onSelect: (next) => pointed = next, hover: { name, readout: facts } }}
		use:columnPick={{ marks, width: box.width, showing: at, onPick: (index) => onPick(drawing.columns[index].date) }}>
		{#each ticks as tick (tick.value)}
			<line x1={box.left} x2={box.right} y1={tick.at} y2={tick.at} stroke="var(--chart-grid)" />
			{#if tick.text}
				<text x={box.left} y={tick.at} dx="-0.35em" dy="0.35em" text-anchor="end">{tick.text}</text>
			{/if}
		{/each}
		{#if drawing.axis.focus !== null}
			{@const join = drawing.axis.scale(drawing.axis.focus)}
			<path d="M{box.left - 4},{join + 3}l8,-3m-8,0l8,-3" stroke="var(--chart-marker)" fill="none" data-score-context />
		{/if}
		{#each drawing.guides as guide, side (side)}
			{#each guide as mark (mark.x)}
				<path d="M{mark.x},{mark.y}H{mark.end}{mark.next === null ? '' : `V${mark.next}`}"
					fill="none" stroke="var(--chart-marker)" stroke-dasharray={side === 0 ? '4 3' : undefined} />
				{#if mark.decision !== null}
					<path d={diamond} transform="translate({(mark.x + mark.end) / 2},{mark.decision})"
						fill="var(--color-surface)" stroke="var(--chart-change)" />
				{/if}
			{/each}
		{/each}
		{#each drawing.columns as column (column.date)}
			{#each column.marks as mark (mark.low)}
				<line x1={column.x} x2={column.x} y1={mark.y0} y2={mark.y1} stroke="var(--chart-marker)" />
				{#each [mark.y0, mark.y1] as endpoint (endpoint)}
					<line x1={column.x - box.labels.fontSize / 4} x2={column.x + box.labels.fontSize / 4}
						y1={endpoint} y2={endpoint} stroke="var(--chart-marker)" />
				{/each}
				{#each mark.segments as part, index (index)}
					{#if part.end > part.start}
						<line x1={part.start} x2={part.end} y1={mark.y} y2={mark.y}
							stroke="var({tokens[index]})" stroke-width="3" />
					{/if}
				{/each}
			{/each}
		{/each}
		{#if drawing.columns[at]}
			<line x1={drawing.columns[at].x} x2={drawing.columns[at].x} y1={box.top} y2={box.bottom}
				stroke="var(--color-focus)" stroke-dasharray="2 4" />
		{/if}
		{#each drawing.dates as tick (tick.date)}
			<text x={drawing.xs[tick.index]} y={box.bottom + box.labels.leading} text-anchor={tick.anchor}>{tick.text}</text>
		{/each}
	</svg>
	<ChartReadout readout={facts[at] ?? null} {name} {maxShare} resting={pointed === null}
		hint="Left and Right inspect dates. Click, tap or press Enter to select a digest."
		hintOne="Click, tap or press Enter to select this digest." />
</div>

<style>
	svg { display: block; max-inline-size: 100%; font-size: var(--console-small-size); }
	text { fill: var(--color-text-secondary); }
</style>
