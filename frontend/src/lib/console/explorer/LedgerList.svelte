
<script lang="ts">
	import { tick } from 'svelte';
	import Icon from '$lib/icons/Icon.svelte';
	import type { LedgerName } from '$lib/data/ledger';
	import type { RegistryLedger } from './registry';
	import { shortDate } from '$lib/format';
	let { ledgers, selected, published, through = {}, spanFrom = '', filter = '', onToggle, onFilter, onRefresh, refreshing = false }: {
		ledgers: RegistryLedger[];
		selected: LedgerName[];
		published: string[];
		through?: Record<string, string>;
		spanFrom?: string;
		filter?: string;
		onToggle: (name: LedgerName) => void;
		onFilter: (value: string) => void;
		onRefresh: () => void;
		refreshing?: boolean;
	} = $props();
	const shown = $derived(ledgers.filter((ledger) => ledger.name.includes(filter.toLowerCase())));
	let options = $state<HTMLDivElement | null>(null);
	let initialSelectionShown = $state(false);

	$effect(() => {
		selected;
		shown;
		if (initialSelectionShown || selected.length === 0) return;
		void tick().then(() => {
			if (options === null || initialSelectionShown) return;
			const chosen = options.querySelector<HTMLElement>('[data-chosen="yes"]');
			if (chosen === null) return;
			const box = options.getBoundingClientRect();
			const rect = chosen.getBoundingClientRect();
			if (rect.top < box.top) options.scrollTop -= box.top - rect.top;
			else if (rect.bottom > box.bottom) options.scrollTop += rect.bottom - box.bottom;
			initialSelectionShown = true;
		});
	});
</script>

<div class="ledger-list">
	<div class="rail-head">
		<h3><Icon id="ledgers" /> Ledgers</h3>
		<button type="button" onclick={onRefresh} disabled={refreshing}><Icon id="list-refresh" /> {refreshing ? 'Refreshing' : 'Refresh'}</button>
	</div>
	<label class="filter">Filter <input value={filter} oninput={(event) => onFilter(event.currentTarget.value)} /></label>
	<div class="ledger-options" bind:this={options}>
		{#each shown as ledger (ledger.name)}
			<label class="ledger" data-ledger-name={ledger.name} data-published={published.includes(ledger.name) ? 'yes' : 'no'} data-chosen={selected.includes(ledger.name) ? 'yes' : 'no'}>
				<input type="checkbox" checked={selected.includes(ledger.name)} onchange={() => onToggle(ledger.name)} />
				<span>{ledger.name}</span>
				<small class:late={through[ledger.name] !== undefined && spanFrom !== '' && through[ledger.name] < spanFrom}>{published.includes(ledger.name) ? `${ledger.grain}${through[ledger.name] ? ` - through ${shortDate(through[ledger.name])}` : ''}` : `not on this site - ${ledger.grain}`}</small>
			</label>
		{/each}
	</div>
</div>

<style>
	.ledger-list { display: grid; gap: var(--space-3); align-content: start; }
	.rail-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
	h3 { margin: 0; display: inline-flex; align-items: center; gap: var(--space-1); color: var(--color-text-tertiary); font-size: var(--text-xs); font-weight: 600; letter-spacing: var(--tracking-label); text-transform: uppercase; }
	button { border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text); padding: var(--space-1) var(--space-2); }
	.filter { display: grid; gap: var(--space-1); font-size: var(--text-xs); color: var(--color-text-secondary); }
	.filter input { border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-bg); color: var(--color-text); padding: var(--space-2); }
	.ledger-options { display: grid; align-content: start; max-block-size: 100%; overflow: auto; scrollbar-gutter: stable; scrollbar-width: thin; scrollbar-color: var(--color-rule-strong) transparent; padding-inline-end: var(--space-1); }
	.ledger { min-block-size: var(--workbench-control); display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 0 var(--space-2); align-items: center; padding-inline: var(--space-3); border-inline-start: 3px solid transparent; background: var(--color-surface); cursor: pointer; font-family: var(--font-data); font-size: var(--text-xs); line-height: var(--leading-xs); }
	.ledger input { margin: 0; }
	.ledger small { grid-column: 2; color: var(--color-text-tertiary); }
	.ledger[data-published='no'] span { color: var(--color-text-secondary); }
	.ledger[data-chosen='yes'] { border-inline-start-color: var(--color-accent); background: var(--tint-accent); }
	.ledger[data-chosen='yes'] span { font-weight: 600; }
	.ledger[data-chosen='yes'] small { color: var(--color-text-secondary); }
	/* Last, at the same weight as the rule above: a late date warns about a ledger you are about to query. */
	.ledger small.late { color: var(--color-text); }
</style>
