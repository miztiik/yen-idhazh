<script lang="ts">
	import { markReadout } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import type { diagnosticGrid } from './diagnosticGrid';

	let { drawing, name, label, corner, labels = false, tileRows = false, maxShare, onPick = null }: {
		drawing: NonNullable<ReturnType<typeof diagnosticGrid>>;
		name: string; label: string; corner: string; labels?: boolean; tileRows?: boolean; maxShare: number;
		onPick?: ((column: number) => void) | null;
	} = $props();

	let pointed = $state<number | null>(null);
	const at = $derived(pointed ?? drawing.rest);
	const select = (index: number | null) => pointed = index;
</script>

<div data-readout-records={drawing.records.length}>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions (The grid has one keyboard stop and an exact readout.) -->
	<div class="grid-view" class:tileRows role="region" aria-label={label} tabindex="0"
		use:markReadout={{ count: drawing.records.length, walk: drawing.columns.length, selected: at,
			onSelect: select, hover: { name, readout: drawing.records } }}
		onkeydown={(event) => {
			if (event.key === 'Enter' && event.target === event.currentTarget && onPick) {
				event.preventDefault();
				onPick(at % drawing.columns.length);
			}
		}}>
		<table aria-label={label} data-chart-type="diagnosticGrid" data-chart-name={name} class:labels
			style:--grid-columns={drawing.columns.length}>
			<thead>
				<tr>
					<th scope="col">{corner}</th>
					{#each drawing.columns as column, index (index)}
						<th scope="col" title={column.title} class:change={column.change} class:chosen={column.chosen} style:--heading-tone={column.tone}>
							{column.label}{column.change ? ' *' : ''}
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each drawing.rows as row, y (y)}
					<tr>
						<th scope="row" style:--heading-tone={row.tone}>{row.label}</th>
						{#each drawing.cells[y] as cell, x (x)}
							{@const index = y * drawing.columns.length + x}
							{@const chosen = drawing.columns[x].chosen}
							<td data-readout-at={index} data-grid-missing={cell.paint === null ? '' : undefined}
								class:change={drawing.columns[x].change} class:chosen class:diagonal={cell.diagonal}
								class:active={index === at} class:emphasized={cell.emphasized}
								style:--cell-paint={cell.paint} style:--cell-edge={cell.edge}>
								{#if onPick}
									<button type="button" tabindex="-1" aria-label={cell.facts.subject}
										onfocus={() => select(index)} onclick={() => onPick?.(x)}>{cell.text ?? ''}</button>
								{:else}
									{#if tileRows}<span class="tile-label" aria-hidden="true">{drawing.columns[x].label}</span>{/if}
									<span>{cell.text ?? ''}</span>
								{/if}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<ChartReadout readout={drawing.records[at] ?? null} {name} {maxShare} resting={pointed === null}
		hint={onPick ? 'Arrow keys inspect cells. Click, tap or press Enter to select a digest.' : 'Arrow keys inspect cells.'} />
</div>

<style>
	.grid-view { overflow-x: auto; padding: var(--space-1); }
	.grid-view:focus-visible { outline: 2px solid var(--color-focus); outline-offset: -2px; }
	table {
		border-spacing: var(--space-1);
		font-size: var(--console-small-size);
		font-variant-numeric: tabular-nums;
		inline-size: 100%;
		min-inline-size: calc((var(--grid-columns) + 2) * var(--console-control-min-height));
	}
	th { color: var(--heading-tone, var(--color-text-secondary)); font-weight: var(--console-panel-title-weight); }
	tbody th { text-align: start; white-space: nowrap; }
	th, td { padding: var(--space-1); text-align: center; }
	td {
		background: var(--cell-paint, var(--color-surface));
		border: 1px solid var(--color-rule);
		padding: 0;
		min-inline-size: var(--console-control-min-height);
	}
	td[data-grid-missing] {
		background: repeating-linear-gradient(135deg, var(--color-surface) 0 var(--space-1), var(--chart-grid) var(--space-1) var(--space-2));
	}
	td.active { outline: 2px solid var(--color-focus); outline-offset: -2px; }
	td.emphasized { border-color: var(--cell-edge, var(--color-rule-strong)); font-weight: var(--console-panel-title-weight); }
	.change { border-inline-start: 2px dashed var(--chart-change); }
	th.chosen { text-decoration: underline; }
	td.chosen { border-block-color: var(--color-rule-strong); }
	.labels td { padding: var(--space-2); }
	.labels td.diagonal { border-color: var(--color-rule-strong); }
	td button {
		color: inherit;
		background: transparent;
		border: 0;
		display: block;
		inline-size: 100%;
		min-block-size: var(--console-control-min-height);
		cursor: pointer;
	}
	.tileRows { container-type: inline-size; }
	.tileRows table { min-inline-size: 0; }
	.tileRows tbody th { white-space: normal; }
	.tileRows :is(th, td) { overflow-wrap: anywhere; min-inline-size: 0; }
	.tileRows :is(th, td):nth-child(2) { border-inline-end: 1px solid var(--color-rule-strong); }
	.tile-label { display: none; }
	@container (max-width: 32rem) {
		.tileRows thead {
			position: absolute;
			inline-size: 1px;
			block-size: 1px;
			overflow: hidden;
			clip-path: inset(50%);
		}
		.tileRows :is(table, tbody) { display: block; }
		.tileRows tbody tr {
			display: grid;
			grid-template-columns: repeat(calc(var(--grid-columns) - 1), minmax(0, 1fr));
			gap: var(--space-1);
			margin-block-end: var(--space-2);
		}
		.tileRows tbody th { grid-column: 1 / -2; grid-row: 1; align-self: center; }
		.tileRows tbody td:not(:last-child) { grid-row: 2; }
		.tileRows tbody td:last-child { grid-column: -2 / -1; grid-row: 1; }
		.tileRows tbody td:not(:last-child) .tile-label {
			display: block;
			margin-block-end: var(--space-1);
			color: var(--color-text-secondary);
		}
	}
</style>
