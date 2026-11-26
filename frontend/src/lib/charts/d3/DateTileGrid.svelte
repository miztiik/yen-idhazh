<script lang="ts">
	/** Read categorical evidence by day without giving gaps a value axis. */
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import { daySlots } from '$lib/charts/day-slots';
	import { chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartLabels } from '$lib/charts/label-context';
	import { columnPick, pointerReadout, readoutMarks, readoutOf } from '$lib/charts/readout';
	import { axisLabels, slotCellFor } from '$lib/charts/run-history';
	import { longDate } from '$lib/format';

	let { days, lanes, name, label, chosen, onPick, width, density, maxShare }: {
		days: readonly string[];
		lanes: readonly { name: string; cells: readonly { state: 'written' | 'checked' | 'unavailable'; text: string }[] }[];
		name: string;
		label: string;
		chosen: number;
		onPick: (column: number) => void;
		width: number;
		density: number;
		maxShare: number;
	} = $props();
	const labels = useChartLabels();
	let measured = $state<number | null>(null);
	let pointed = $state<number | null>(null);
	const slots = $derived(daySlots(chartWidth(measured, width), days.length, { left: 0, right: 0 }));
	const square = $derived(slotCellFor(slots.slot));
	const axis = $derived(axisLabels([...days], { density, pitch: slots.slot, labels: labels() }));
	const marks = $derived(readoutMarks(slots.centres));
	const at = $derived(pointed !== null && pointed < days.length ? pointed : chosen);
	const reading = $derived(readoutOf({
		type: 'tileStrip', columns: days.map((date) => `${longDate(date)} UTC`),
		series: lanes.map(({ name, cells }) => ({
			label: name, swatch: null, values: cells.map(({ text }) => text), format: String
		})),
		notMeasured: 'Evidence unavailable', resting: 'last'
	}));
</script>

<div class="tile-grid" class:fits={square !== null} style:--date-columns={days.length}>
	<div class="lanes" aria-hidden="true">
		{#each lanes as lane (lane.name)}<span>{lane.name}</span>{/each}
	</div>
	<div use:observeWidth={(next) => measured = next} class="plot">
		{#if square !== null}
			<!-- svelte-ignore a11y_no_noninteractive_tabindex (One stop for the shared day readout.) -->
			<div class="tracks" role="group" aria-label={label} tabindex="0"
				data-chart-type="tileStrip" data-chart-name={name} data-readout-columns={days.length}
				style:--square-size={`${square.cell}px`}
				use:pointerReadout={{ marks, width: slots.width, selected: at,
					onSelect: (column) => pointed = column, hover: { name, readout: reading } }}
				use:columnPick={{ marks, width: slots.width, showing: at, onPick }}>
				{#each lanes as lane (lane.name)}
					<div class="track" aria-hidden="true">
						{#each lane.cells as cell, index (days[index])}
							<span class="slot" class:chosen={index === chosen}>
								<span data-write-state={cell.state}></span>
							</span>
						{/each}
					</div>
				{/each}
			</div>
			<div class="axis" aria-hidden="true">
				{#each axis as tick (tick.column)}
					<span class={tick.align} style:grid-column={tick.column}>{tick.text}</span>
				{/each}
			</div>
		{/if}
	</div>
</div>
<ChartReadout readout={reading} at={at} {name} {maxShare}
	hint={square === null ? '' : 'Point at a day or use Left and Right. Click, tap or press Enter to select it.'} />

<style>
	.tile-grid { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: var(--space-2); }
	.lanes { display: grid; color: var(--color-text-secondary); font-size: var(--console-small-size); }
	.tile-grid:not(.fits) .lanes { visibility: hidden; block-size: 0; overflow: hidden; }
	.lanes span, .slot { min-block-size: var(--space-6); display: grid; align-items: center; }
	.track, .axis { display: grid; grid-template-columns: repeat(var(--date-columns), minmax(0, 1fr)); }
	.slot { justify-content: center; }
	.slot.chosen { background: var(--color-surface-sunken); }
	[data-write-state] { inline-size: var(--square-size); block-size: var(--square-size); box-sizing: border-box; }
	[data-write-state='written'] { background: var(--chart-measure); }
	[data-write-state='checked'] { border: 1px solid var(--chart-axis); }
	[data-write-state='unavailable'] { border: 1px dashed var(--color-rule-strong); }
	.tracks:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	.axis { color: var(--color-text-secondary); font-size: var(--text-xs); }
	.axis span { white-space: nowrap; justify-self: center; }
	.axis .start { justify-self: start; }
	.axis .end { justify-self: end; }
</style>
