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
		lanes: readonly { name: string; cells: readonly {
			state: 'written' | 'checked' | 'unavailable' | 'failed' | 'deferred' | 'recovered';
			text: string; draw?: boolean; links?: { before: boolean; after: boolean }; caption?: string
		}[] }[];
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
	let pointed = $state<string | null>(null);
	const slots = $derived(daySlots(chartWidth(measured, width), days.length, { left: 0, right: 0 }));
	const square = $derived(slotCellFor(slots.slot));
	const axis = $derived(axisLabels([...days], { density, pitch: slots.slot, labels: labels() }));
	const marks = $derived(readoutMarks(slots.centres));
	const pointedIndex = $derived(pointed === null ? -1 : days.indexOf(pointed));
	const at = $derived(pointedIndex < 0 ? chosen : pointedIndex);
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
					onSelect: (column) => pointed = column === null ? null : days[column] ?? null,
					hover: { name, readout: reading } }}
				use:columnPick={{ marks, width: slots.width, showing: at, onPick }}>
				{#each lanes as lane (lane.name)}
					<div class="track" aria-hidden="true">
						{#each lane.cells as cell, index (days[index])}
							<span class="slot" class:chosen={index === chosen}>
								{#if cell.draw !== false}
									<span data-write-state={cell.state}>
										{#if cell.state === 'written'}<span class="check"></span>
										{:else if cell.state === 'failed'}<span class="cross"></span>{/if}
									</span>
									{#if cell.links?.before}<span class="connector before"></span>{/if}
									{#if cell.links?.after}<span class="connector after"></span>{/if}
									{#if cell.caption && index < days.length / 2}<span class="caption">{cell.caption}</span>{/if}
								{/if}
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
		{:else}
			<label class="compact-days">Inspect UTC day
				<input type="range" min="0" max={days.length - 1} step="1" value={chosen}
					aria-valuetext={days[chosen] ? longDate(days[chosen]) : undefined}
					oninput={(event) => { pointed = null; onPick(event.currentTarget.valueAsNumber); }} />
			</label>
		{/if}
	</div>
</div>
<ChartReadout readout={reading} at={at} {name} {maxShare}
	hint={square === null ? '' : 'Point at a day or use Left and Right. Click, tap or press Enter to select it.'} />

<style>
	.tile-grid { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: var(--space-2); }
	.lanes { display: grid; color: var(--color-text-secondary); font-size: var(--console-small-size); }
	.tile-grid:not(.fits) .lanes { visibility: hidden; block-size: 0; overflow: hidden; }
	.lanes span, .slot { min-block-size: var(--space-5); display: grid; align-items: center; }
	.caption { position: absolute; inset-block-end: 50%; inset-inline-start: 50%; white-space: nowrap;
		color: var(--color-text-secondary); font-size: var(--console-small-size); text-transform: capitalize; }
	@container (max-width: 42rem) { .caption { display: none; } }
	.plot { container-type: inline-size; }
	.track, .axis { display: grid; grid-template-columns: repeat(var(--date-columns), minmax(0, 1fr)); }
	.slot { position: relative; justify-content: center; }
	.slot.chosen { background: var(--color-surface-sunken); }
	[data-write-state] { position: relative; inline-size: var(--square-size); block-size: var(--square-size); box-sizing: border-box; }
	[data-write-state='written'] { background: var(--operation-written); color: var(--color-surface); }
	[data-write-state='checked'] { border: 1px solid var(--chart-axis); }
	[data-write-state='unavailable'] {
		border: 1px solid var(--chart-grid);
		background: repeating-linear-gradient(135deg, transparent 0 2px, var(--color-rule-strong) 2px 3px);
	}
	[data-write-state='failed'] { background: var(--operation-failed); color: var(--color-surface); }
	[data-write-state='deferred'] { background: var(--operation-deferred); block-size: var(--console-chart-line-width); }
	.connector { position: absolute; inset-block-start: 50%; inline-size: 50%; translate: 0 -50%;
		block-size: var(--console-chart-line-width); background: var(--operation-deferred); }
	.connector.before { inset-inline-start: 0; }
	.connector.after { inset-inline-end: 0; }
	[data-write-state='recovered'] { background: var(--chart-1); scale: .65; rotate: 45deg; }
	.check, .cross { position: absolute; inset: 20%; }
	.check { border: solid currentColor; border-width: 0 1px 1px 0; transform: rotate(40deg) scaleX(.55); }
	.cross::before, .cross::after { content: ''; position: absolute; inset: 45% 0; background: currentColor; rotate: 45deg; }
	.cross::after { rotate: -45deg; }
	.compact-days { display: grid; gap: var(--space-1); color: var(--color-text-secondary); }
	.compact-days input { accent-color: var(--color-accent); }
	.tracks:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	.axis { color: var(--color-text-secondary); font-size: var(--text-xs); }
	.axis span { white-space: nowrap; justify-self: center; }
	.axis .start { justify-self: start; }
	.axis .end { justify-self: end; }
</style>
