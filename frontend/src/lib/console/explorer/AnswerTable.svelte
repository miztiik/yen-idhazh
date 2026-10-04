
<script lang="ts">
	import Icon from '$lib/icons/Icon.svelte';
	import type { Column, Row } from '$lib/data/ledger';
	import { nextSort, numericBarShare, printCell, sortedRows, type SortSpec } from './answer';
	let { columns, rows, capped = false, maxRows, pageSize, tableMaxVh, cellMaxCh, barSpreadShare, onOrderChange }: {
		columns: readonly Column[]; rows: readonly Row[]; capped?: boolean; maxRows: number; pageSize: number; tableMaxVh: number; cellMaxCh: number; barSpreadShare: number; onOrderChange?: (rows: Row[]) => void;
	} = $props();
	let sort = $state<SortSpec>({ column: '', direction: null });
	// svelte-ignore state_referenced_locally
	let shown = $state(pageSize);
	const ordered = $derived(sortedRows(rows, columns, sort));
	const visible = $derived(ordered.slice(0, shown));
	const bars = $derived(new Map(columns.map((column) => [column.name, numericBarShare(column, rows, barSpreadShare)])));
	$effect(() => onOrderChange?.(ordered));
</script>

<div class="answer-summary">
	<p data-lede>{capped ? `The first ${rows.length} rows` : `${rows.length} ${rows.length === 1 ? 'row' : 'rows'}`}</p>
	<p data-comparison="each row against the others, in the order of the column you sort by">Press a column's name to sort the rows by it.</p>
	{#if capped}<p>The answer stopped at {maxRows} rows, the most one answer holds here. Narrow the days or the question to see the rest.</p>{/if}
</div>
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="table-box" role="region" tabindex="0" aria-label={`Answer, ${rows.length} rows by ${columns.length} columns`} data-chart="answer-table" data-readout-none="every value is printed in its own cell; agreed with Susan" style={`--table-max:${tableMaxVh}svh;--cell-max:${cellMaxCh}ch`}>
	<table data-explorer-answer>
		<thead>
			<tr>
				<th class="row-number">#</th>
				{#each columns as column (column.name)}
					<th aria-sort={sort.column === column.name ? (sort.direction === 'asc' ? 'ascending' : sort.direction === 'desc' ? 'descending' : 'none') : 'none'}>
						<button type="button" onclick={() => (sort = nextSort(sort, column))}>
							<span>{column.name}{#if sort.column === column.name && sort.direction === 'asc'} <Icon id="sort-ascending" />{:else if sort.column === column.name && sort.direction === 'desc'} <Icon id="sort-descending" />{/if}</span>
							<small>{column.type.toLowerCase()}{#if bars.get(column.name) !== null}, full bar {printCell(column, bars.get(column.name) as never).text}{/if}</small>
						</button>
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each visible as row, index (index)}
				<tr>
					<th class="row-number">{index + 1}</th>
					{#each columns as column (column.name)}
						{@const printed = printCell(column, row[column.name])}
						<td data-kind={printed.kind}>
							<span>{printed.text}</span>
							{#if bars.get(column.name) !== null && printed.kind === 'number'}<i style={`inline-size:${Math.max(0, Math.min(100, Number(String(row[column.name]).replace(/,/g, '')) / (bars.get(column.name) || 1) * 100))}%`}></i>{/if}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>
<div class="show-more">
	{#if shown < rows.length}<button type="button" onclick={() => (shown = Math.min(rows.length, shown + pageSize))}>Show {Math.min(pageSize, rows.length - shown)} more rows</button>{/if}
	<p>{shown < rows.length ? `${shown} of ${rows.length} rows shown.` : `All ${rows.length} rows are shown.`}</p>
</div>

<style>
	.answer-summary { display: grid; gap: var(--space-1); padding-block: var(--space-2); }
	.answer-summary p { margin: 0; color: var(--color-text-secondary); }
	.answer-summary [data-lede] { color: var(--color-text); font-size: var(--text-xl); font-weight: 700; }
	.table-box { max-block-size: var(--table-max); overflow: auto; scrollbar-width: thin; padding-inline: 0 !important; border-block: 1px solid var(--color-rule); background: var(--color-surface); }
	table { border-collapse: separate; border-spacing: 0; min-inline-size: 100%; font-size: var(--text-sm); }
	th, td { border-block-end: 1px solid var(--color-rule); padding: var(--space-2) var(--space-3); text-align: start; vertical-align: top; background: var(--color-surface); }
	thead th { position: sticky; inset-block-start: 0; z-index: 2; }
	.row-number { position: sticky; inset-inline-start: 0; z-index: 3; inline-size: calc(4ch + var(--space-3) + var(--space-5)); color: var(--color-text-tertiary); font-family: var(--font-data); border-inline-end: 1px solid var(--color-rule-strong); }
	th button { display: grid; gap: var(--space-1); border: 0; background: transparent; color: inherit; padding: 0; text-align: start; font: inherit; }
	th span { font-family: var(--font-data); overflow-wrap: anywhere; }
	th small { color: var(--color-text-tertiary); font-weight: 400; }
	td { max-inline-size: var(--cell-max); overflow-wrap: anywhere; }
	td[data-kind='number'] { text-align: end; font-variant-numeric: tabular-nums; }
	td[data-kind='null'] span { color: var(--color-text-tertiary); font-style: italic; }
	td[data-kind='json'], td[data-kind='blob'] { font-family: var(--font-data); }
	td i { display: block; block-size: 3px; margin-block-start: var(--space-1); border-radius: var(--radius-full); background: var(--chart-1); }
	.show-more { display: flex; justify-content: space-between; gap: var(--space-3); align-items: center; padding-block: var(--space-3); }
	.show-more p { margin: 0; color: var(--color-text-secondary); }
	.show-more button { border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text); padding: var(--space-2) var(--space-3); }
	@media (min-width: 640px) { tbody td:first-of-type, thead th:nth-child(2) { position: sticky; inset-inline-start: calc(4ch + var(--space-3) + var(--space-5)); z-index: 2; border-inline-end: 1px solid var(--color-rule-strong); } }
</style>
