<script lang="ts">
	import { markReadout } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import type { diagnosticGrid } from './diagnosticGrid';

	let { drawing, name, label, corner, labels = false, maxShare, onPick = null }: {
		drawing: NonNullable<ReturnType<typeof diagnosticGrid>>;
		name: string; label: string; corner: string; labels?: boolean; maxShare: number;
		onPick?: ((column: number) => void) | null;
	} = $props();

	let pointed = $state<number | null>(null);
	const at = $derived(pointed ?? drawing.rest);
	const select = (index: number | null) => pointed = index;
</script>

<div data-readout-records={drawing.records.length}>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions (The grid has one keyboard stop and an exact readout.) -->
	<div class="grid-view" role="region" aria-label={label} tabindex="0"
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
								class:active={index === at} style:--cell-paint={cell.paint}>
								{#if onPick}
									<button type="button" tabindex="-1" aria-label={cell.facts.subject}
										onfocus={() => select(index)} onclick={() => onPick?.(x)}>{cell.text ?? ''}</button>
								{:else}
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
</style>
