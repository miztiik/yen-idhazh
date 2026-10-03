
<script lang="ts">
	import Icon from '$lib/icons/Icon.svelte';
	import type { LedgerName } from '$lib/data/ledger';
	import type { RegistryLedger } from './registry';
	let { ledgers, selected, published, filter = '', onToggle, onFilter, onRefresh, refreshing = false }: {
		ledgers: RegistryLedger[];
		selected: LedgerName[];
		published: string[];
		filter?: string;
		onToggle: (name: LedgerName) => void;
		onFilter: (value: string) => void;
		onRefresh: () => void;
		refreshing?: boolean;
	} = $props();
	const shown = $derived(ledgers.filter((ledger) => ledger.name.includes(filter.toLowerCase())));
</script>

<div class="ledger-list">
	<div class="rail-head">
		<h3>Ledgers</h3>
		<button type="button" onclick={onRefresh} disabled={refreshing}><Icon id="list-refresh" /> {refreshing ? 'Refreshing' : 'Refresh'}</button>
	</div>
	<label class="filter">Filter <input value={filter} oninput={(event) => onFilter(event.currentTarget.value)} /></label>
	<div class="ledger-options">
		{#each shown as ledger (ledger.name)}
			<label class="ledger" data-published={published.includes(ledger.name) ? 'yes' : 'no'}>
				<input type="checkbox" checked={selected.includes(ledger.name)} onchange={() => onToggle(ledger.name)} />
				<span>{ledger.name}</span>
				<small>{published.includes(ledger.name) ? ledger.grain : `not on this site - ${ledger.grain}`}</small>
			</label>
		{/each}
	</div>
</div>

<style>
	.ledger-list { display: grid; gap: var(--space-3); align-content: start; }
	.rail-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
	h3 { margin: 0; font-size: var(--text-sm); }
	button { border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text); padding: var(--space-1) var(--space-2); }
	.filter { display: grid; gap: var(--space-1); font-size: var(--text-xs); color: var(--color-text-secondary); }
	.filter input { border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-bg); color: var(--color-text); padding: var(--space-2); }
	.ledger-options { display: grid; gap: var(--space-2); max-block-size: 28rem; overflow: auto; padding-inline-end: var(--space-1); }
	.ledger { display: grid; grid-template-columns: auto 1fr; gap: 0 var(--space-2); padding: var(--space-2); border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); }
	.ledger small { grid-column: 2; color: var(--color-text-tertiary); }
	.ledger[data-published='no'] { opacity: 0.72; }
</style>
