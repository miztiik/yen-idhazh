
<script lang="ts">
	import Icon from '$lib/icons/Icon.svelte';
	import type { Column } from '$lib/data/ledger';
	let { columns, label }: { columns: readonly Column[]; label: string } = $props();
</script>

<div class="column-list" data-explorer-columns>
	<h3><Icon id="column-list" /> {label}</h3>
	{#if columns.length === 0}
		<p>No columns are known yet.</p>
	{:else}
		<ul data-explorer-column-box>
			{#each columns as column (column.name)}
				<li><code>{column.name}</code><span>{column.type.toLowerCase()}</span></li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.column-list { block-size: 100%; min-block-size: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); gap: var(--space-3); overflow: hidden; }
	h3 { margin: 0; display: inline-flex; align-items: center; gap: var(--space-1); color: var(--color-text-tertiary); font-size: var(--text-xs); font-weight: 600; letter-spacing: var(--tracking-label); text-transform: uppercase; }
	p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); }
	ul { list-style: none; margin: 0; padding: 0; display: grid; align-content: start; block-size: 100%; min-block-size: 0; overflow: auto; scrollbar-gutter: stable; scrollbar-width: thin; scrollbar-color: var(--color-rule-strong) transparent; }
	li { min-block-size: var(--workbench-row); display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-2); align-items: center; padding-inline: var(--space-3); }
	code { font-family: var(--font-data); color: var(--color-text); overflow-wrap: anywhere; font-size: var(--text-xs); line-height: var(--leading-xs); }
	span { color: var(--color-text-tertiary); font-size: var(--text-xs); }
</style>
