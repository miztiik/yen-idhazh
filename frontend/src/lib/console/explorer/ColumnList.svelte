
<script lang="ts">
	import type { Column } from '$lib/data/ledger';
	import ColumnType from '$lib/console/explorer/ColumnType.svelte';
	import { groupColumns } from '$lib/console/explorer/column-groups';
	import { ICONS } from '$lib/icons/generated';
	let { columns, label }: { columns: readonly Column[]; label: string } = $props();
	const groups = $derived(groupColumns(columns));
</script>

<div class="column-list" data-explorer-columns>
	<h3><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round">{@html ICONS['column-list']}</svg> {label}</h3>
	{#if columns.length === 0}
		<p>No columns are known yet.</p>
	{:else}
		<div class="column-box" data-explorer-column-box>
			<!-- Keyed: a group for another ledger is new elements, not the old ones moved, and a moved element is a layout shift. -->
			{#each groups as group, index (`${index}-${group.ledger}`)}
				<div class="column-group">
					{#if group.ledger !== null}<h4>{group.ledger}</h4>{/if}
					<ul>
						{#each group.columns as column (column.name)}
							<li title={column.name}><code>{#if group.ledger !== null}<span class="sr-only">{group.ledger}.</span>{/if}{#each column.shown.split(/(?<=_)/) as part, index}{#if index > 0}<wbr />{/if}{part}{/each}</code><ColumnType type={column.type} /></li>
						{/each}
					</ul>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.column-list { contain: size; block-size: 100%; min-block-size: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); gap: var(--space-3); overflow: hidden; }
	h3 { margin: 0; display: inline-flex; align-items: center; gap: var(--space-1); color: var(--color-text-tertiary); font-size: var(--text-xs); font-weight: 600; letter-spacing: var(--tracking-label); text-transform: uppercase; }
	p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); }
	/* Positioned, so the hidden screen-reader spans in its rows scroll with the list instead of escaping it and stretching the page. */
	.column-box { position: relative; block-size: 100%; min-block-size: 0; overflow: auto; scrollbar-gutter: stable; scrollbar-width: thin; scrollbar-color: var(--color-rule-strong) transparent; font-size: var(--text-xs); line-height: var(--leading-xs); }
	h4 { position: sticky; inset-block-start: 0; z-index: 1; margin: 0; background: var(--color-surface); font-family: var(--font-data); font-size: inherit; font-weight: 600; }
	ul { list-style: none; margin: 0; padding: 0; }
	li { min-block-size: var(--workbench-row); display: flex; flex-wrap: wrap; align-items: first baseline; column-gap: var(--space-2); padding-inline: var(--space-3); }
	code { min-inline-size: 0; padding-inline-start: 2ch; text-indent: -2ch; font-family: var(--font-data); color: var(--color-text); overflow-wrap: anywhere; }
	li > :global(.column-type) { margin-inline-start: auto; }
</style>
