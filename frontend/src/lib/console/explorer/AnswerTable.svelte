
<script lang="ts">
	import Icon from '$lib/icons/Icon.svelte';
	import type { Column, Row } from '$lib/data/ledger';
	import ColumnType from '$lib/console/explorer/ColumnType.svelte';
	import { nextSort, numericBarShare, printCell, sortedRows, type SortSpec } from './answer';
	type GapLine = { ledger: string; kind: string; text: string };
	let { columns, rows, capped = false, maxRows, pageSize, cellMaxCh, barSpreadShare, spanText = '', siteFromText = '', gapLines = [], onOrderChange }: {
		columns: readonly Column[]; rows: readonly Row[]; capped?: boolean; maxRows: number; pageSize: number; cellMaxCh: number; barSpreadShare: number; spanText?: string; siteFromText?: string; gapLines?: readonly GapLine[]; onOrderChange?: (rows: Row[]) => void;
	} = $props();
	let sort = $state<SortSpec>({ column: '', direction: null });
	// svelte-ignore state_referenced_locally
	let shown = $state(pageSize);
	const ordered = $derived(sortedRows(rows, columns, sort));
	const visible = $derived(ordered.slice(0, shown));
	const bars = $derived(new Map(columns.map((column) => [column.name, numericBarShare(column, rows, barSpreadShare)])));
	const rowStatus = $derived(shown < rows.length ? `${shown} of ${rows.length} rows shown.` : `All ${rows.length} rows shown.`);
	$effect(() => onOrderChange?.(ordered));
</script>

<div class="answer-table-region">
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<div class="table-box" role="region" tabindex="0" aria-label={`Answer, ${rows.length} rows by ${columns.length} columns`} data-chart="answer-table" data-readout-none="every value is printed in its own cell; agreed with Susan" style={`--cell-max:${cellMaxCh}ch`}>
		<table data-explorer-answer>
		<thead>
			<tr>
				<th class="row-number">#</th>
				{#each columns as column (column.name)}
					<th aria-sort={sort.column === column.name ? (sort.direction === 'asc' ? 'ascending' : sort.direction === 'desc' ? 'descending' : 'none') : 'none'}>
						<button type="button" onclick={() => (sort = nextSort(sort, column))}>
							<span>{column.name}<i class="sort-mark" data-sorted={sort.column === column.name ? sort.direction ?? 'none' : 'none'} aria-hidden="true"></i></span>
							<small><ColumnType type={column.type} />{#if bars.get(column.name) !== null}, full bar {printCell(column, bars.get(column.name) as never).text}{/if}</small>
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
		<p class="answer-note">{spanText} {rowStatus}{#if capped} The answer stops at {maxRows} rows; narrow the days or the question to see the rest.{/if}{#if siteFromText} {siteFromText}{/if}{#each gapLines as line} <span data-explorer-gap={line.kind} data-ledger={line.ledger}>{line.text}</span>{/each}</p>
	</div>
</div>

<style>
	.answer-table-region { min-block-size: 0; display: grid; grid-template-rows: minmax(0, 1fr) var(--workbench-control); overflow: hidden; }
	.table-box { block-size: 100%; min-block-size: 0; overflow: auto; scrollbar-width: thin; scrollbar-color: var(--color-rule-strong) transparent; padding-inline: 0 !important; border-block: 1px solid var(--color-rule); background: var(--color-surface); }
	table { border-collapse: separate; border-spacing: 0; inline-size: max-content; min-inline-size: 100%; font-size: var(--text-xs); line-height: var(--leading-xs); }
	th, td { padding: var(--space-1) var(--space-2); text-align: start; vertical-align: top; background: var(--color-surface); }
	tbody th, tbody td { block-size: var(--workbench-row); }
	tbody tr:nth-child(even) td,
	tbody tr:nth-child(even) th { background: var(--tint-neutral); }
	thead th { position: sticky; inset-block-start: 0; z-index: 2; }
	thead th { background: var(--color-surface-raised); border-block-end: 1px solid var(--color-rule-strong); }
	.row-number { position: sticky; inset-inline-start: 0; z-index: 3; inline-size: calc(4ch + 2 * var(--space-2)); color: var(--color-text-tertiary); font-family: var(--font-data); font-variant-numeric: tabular-nums; text-align: end; border-inline-end: 1px solid var(--color-rule-strong); }
	th button { display: grid; gap: var(--space-1); border: 0; background: transparent; color: inherit; padding: 0; text-align: start; font: inherit; }
	th span { display: inline-flex; align-items: center; gap: var(--space-1); font-family: var(--font-data); white-space: nowrap; }
	th small { color: var(--color-text-tertiary); font-size: var(--text-xs); font-weight: 400; white-space: nowrap; }
	.sort-mark { inline-size: 0; block-size: 0; border-inline: 0.28rem solid transparent; border-block-start: 0.36rem solid var(--color-text-tertiary); opacity: 0.55; }
	.sort-mark[data-sorted='asc'] { border-block-start: 0; border-block-end: 0.36rem solid var(--color-text); opacity: 1; }
	.sort-mark[data-sorted='desc'] { border-block-start-color: var(--color-text); opacity: 1; }
	td { max-inline-size: var(--cell-max); overflow-wrap: anywhere; }
	td[data-kind='number'] { text-align: end; font-variant-numeric: tabular-nums; }
	td[data-kind='null'] span { color: var(--color-text-tertiary); font-style: italic; }
	td[data-kind='json'], td[data-kind='blob'] { font-family: var(--font-data); }
	td i { display: block; block-size: 3px; margin-block-start: var(--space-1); border-radius: var(--radius-full); background: var(--chart-1); }
	.show-more { min-block-size: var(--workbench-control); display: flex; justify-content: space-between; gap: var(--space-3); align-items: center; padding-inline: var(--space-3); }
	.show-more p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-xs); line-height: var(--leading-xs); }
	.show-more button { border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text); padding: var(--space-2) var(--space-3); }
	@media (min-width: 640px) { tbody td:first-of-type, thead th:nth-child(2) { position: sticky; inset-inline-start: calc(4ch + 2 * var(--space-2)); z-index: 2; border-inline-end: 1px solid var(--color-rule-strong); } }
</style>
