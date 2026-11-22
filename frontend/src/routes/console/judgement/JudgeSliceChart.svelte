<script lang="ts">
	/** Show the same drawn-range readings as columns or count rows, depending on available room. */
	import { useChartFrame } from '$lib/charts/label-context';
	import { pointerReadout, readoutMarks } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import type { SliceOutcome } from '$lib/console/judge-observations';
	import type { ChartConfig } from '$lib/server/config';
	import { GAP_LABEL, NOT_DRAWN, judgeSliceColumns, judgeSliceEvidence } from './judge-slice-chart';

	let { slices, name, label, width, height, chart }: {
		slices: readonly SliceOutcome[];
		name: string;
		label: string;
		width: number;
		height: number;
		chart: ChartConfig;
	} = $props();

	const TICK = 4;
	const frame = useChartFrame(() => chart);
	let selected = $state<number | null>(null);
	const evidence = $derived(judgeSliceEvidence(slices, chart.number_format));
	const rowReadings = $derived(evidence.readout.series.filter(({ label }) => label !== 'Drawn'));
	const drawing = $derived(judgeSliceColumns(evidence.ranges, frame(width, height), chart.tick_density, chart.number_format));
	const marks = $derived(readoutMarks(drawing?.columns.map(({ center }) => center) ?? []));
</script>

{#if drawing}
	{@const { plot, columns, width: barWidth, axis } = drawing}
	<div data-readout-columns={columns.length}>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<svg viewBox="0 0 {plot.width} {plot.height}" width={plot.width} height={plot.height} role="img"
			aria-label={label} tabindex="0" data-chart-type="stackedCountColumns" data-chart-name={name}
			use:pointerReadout={{ marks, width: plot.width, hover: { name, readout: evidence.readout }, onSelect: (index) => selected = index }}>
			{#each axis.ticks as tick (tick.value)}
				<line x1={plot.left} x2={plot.right} y1={tick.at} y2={tick.at} stroke="var(--chart-grid)" />
				{#if tick.text}
					<text x={plot.left - TICK} y={tick.at} dy="0.32em" text-anchor="end">{tick.text}</text>
				{/if}
			{/each}
			<line x1={plot.left} x2={plot.right} y1={plot.bottom} y2={plot.bottom} stroke="var(--chart-axis)" />
			{#each columns as column (column.label)}
				{@const left = column.center - barWidth / 2}
				{#each column.segments as part, index (part.token)}
					<rect x={left} y={part.y} width={barWidth} height={part.height} fill="var({part.token})" />
					{#if index > 0}
						<line x1={left} x2={left + barWidth} y1={part.y + part.height} y2={part.y + part.height}
							stroke="var(--color-surface)" />
					{/if}
				{/each}
				{#if column.total === null}
					<text x={column.center} y={plot.bottom - TICK - plot.labels.leading} text-anchor="middle">
						<tspan x={column.center}>{GAP_LABEL[0]}</tspan>
						<tspan x={column.center} dy={plot.labels.leading}>{GAP_LABEL[1]}</tspan>
					</text>
				{:else}
					<text class="drawn-count" x={column.center} y={column.top - TICK} text-anchor="middle">{column.total}</text>
				{/if}
				<text x={column.center} y={plot.bottom + plot.labels.leading} text-anchor="middle">
					<tspan x={column.center}>{column.edges[0]}</tspan>
					<tspan x={column.center} dy={plot.labels.leading}>{column.edges[1]}</tspan>
				</text>
			{/each}
			{#if selected !== null && columns[selected]}
				{@const x = columns[selected].center}
				<line x1={x} x2={x} y1={plot.top} y2={plot.bottom} stroke="var(--chart-marker)" pointer-events="none" />
			{/if}
		</svg>
		<ChartReadout readout={evidence.readout} at={selected} {name} maxShare={chart.readout_max_share}
			hint="Point to or tap a range for exact counts. Left and Right step through ranges, Escape returns to the first." />
	</div>
{:else}
	<ol class="slice-rows" aria-label={label}>
		{#each evidence.ranges as range, index (range.label)}
			<li>
				<div class="range-head">
					<strong>{range.label}</strong>
					<span>{range.total === null ? NOT_DRAWN : `${range.total} drawn`}</span>
				</div>
				{#if range.drawn !== null}
					<dl>
						{#each rowReadings as reading (reading.label)}
							<div><dt>{reading.label}:</dt> <dd>{reading.values[index]}</dd></div>
						{/each}
					</dl>
				{/if}
			</li>
		{/each}
	</ol>
{/if}

<style>
	svg {
		display: block;
		max-inline-size: 100%;
		font-size: var(--console-small-size);
		letter-spacing: var(--console-small-tracking);
	}
	svg:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	svg text { fill: var(--color-text-secondary); }
	.drawn-count { fill: var(--color-text); }
	.slice-rows {
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
	}
	.slice-rows li {
		display: grid;
		gap: var(--space-1);
		padding-block: var(--space-2);
		border-block-start: 1px solid var(--color-rule);
		overflow-wrap: anywhere;
	}
	.range-head, dl {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-3);
	}
	.range-head { justify-content: space-between; }
	dl { color: var(--color-text-secondary); }
	dl, dd { margin: 0; }
	dt, dd { display: inline; }
	dd { color: var(--color-text); font-variant-numeric: tabular-nums; }
</style>
