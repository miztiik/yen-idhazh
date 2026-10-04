
<script lang="ts">
	import type { Column } from '$lib/data/ledger';
	let { columns, label }: { columns: readonly Column[]; label: string } = $props();
</script>

<div class="column-list" data-explorer-columns>
	<h3>{label}</h3>
	{#if columns.length === 0}
		<p>No columns are known yet.</p>
	{:else}
		<ul>
			{#each columns as column (column.name)}
				<li><code>{column.name}</code><span>{column.type.toLowerCase()}</span></li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.column-list { display: grid; gap: var(--space-3); align-content: start; }
	h3 { margin: 0; font-size: var(--text-sm); }
	p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); }
	ul { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); max-block-size: 28rem; overflow: auto; }
	li { display: grid; gap: var(--space-1); padding: var(--space-2); border: 1px solid var(--color-rule); border-radius: var(--radius-md); }
	code { font-family: var(--font-data); color: var(--code-keyword); overflow-wrap: anywhere; }
	span { color: var(--color-text-tertiary); font-size: var(--text-xs); }
</style>
