<script lang="ts">
	import { tick } from 'svelte';
	import Icon from '$lib/icons/Icon.svelte';
	import type { RegistryLedger } from './registry';
	import type { LocalTable } from '$lib/data/local-tables';
	let { ledgers, browsed, imports, filter = '', onBrowse, onFilter, onRefresh, onImport, onRemove, busy = false, refreshing = false }: {
		ledgers: readonly RegistryLedger[];
		browsed: string;
		imports: readonly LocalTable[];
		filter?: string;
		onBrowse: (name: string) => void;
		onFilter: (value: string) => void;
		onRefresh: () => void;
		onImport: (file: File) => void;
		onRemove: (alias: string) => void;
		busy?: boolean;
		refreshing?: boolean;
	} = $props();
	const shown = $derived(ledgers.filter((ledger) => ledger.publish_to_data_explorer && ledger.name.includes(filter.toLowerCase())));
	let options = $state<HTMLDivElement | null>(null);
	$effect(() => {
		browsed;
		imports.length;
		void tick().then(() => {
			const row = options?.querySelector<HTMLElement>('[aria-pressed="true"]');
			if (options === null || row == null) return;
			const list = options.getBoundingClientRect();
			const box = row.getBoundingClientRect();
			if (box.top < list.top) options.scrollTop -= list.top - box.top;
			else if (box.bottom > list.bottom) options.scrollTop += box.bottom - list.bottom;
		});
	});
</script>

<div class="ledger-list">
	<div class="rail-head">
		<h3><Icon id="ledgers" /> Tables</h3>
		<button type="button" onclick={onRefresh} disabled={refreshing || busy}><Icon id="list-refresh" /> {refreshing ? 'Refreshing' : 'Refresh'}</button>
	</div>
	<label class="import-file"><span>Import Parquet</span>
		<input class="sr-only" type="file" accept=".parquet" disabled={busy || refreshing} onchange={(event) => { const file = event.currentTarget.files?.[0]; if (file) onImport(file); event.currentTarget.value = ''; }} />
		<small>No upload. Refresh clears local files.</small>
	</label>
	<label class="filter">Find a ledger <input value={filter} oninput={(event) => onFilter(event.currentTarget.value)} /></label>
	<p>Browse columns here. SQL decides which tables to read.</p>
	<div class="ledger-options" bind:this={options}>
		{#if imports.length > 0}
			<h3>Local files</h3>
			{#each imports as table (table.alias)}
				<div class="local-row">
					<button type="button" class="table-name" aria-pressed={browsed === table.alias} onclick={() => onBrowse(table.alias)}><span>{table.alias}</span><small>{table.filename}</small></button>
					<button type="button" class="remove" aria-label={`Remove ${table.alias}`} disabled={busy} onclick={() => onRemove(table.alias)}>Remove</button>
				</div>
			{/each}
			<h3>Repository ledgers</h3>
		{/if}
		{#each shown as ledger (ledger.name)}
			<button type="button" class="table-name" data-ledger-name={ledger.name} aria-pressed={browsed === ledger.name} onclick={() => onBrowse(ledger.name)}>{ledger.name}</button>
		{/each}
		{#if shown.length === 0}<p>No matching ledgers.</p>{/if}
	</div>
</div>

<style>
	.ledger-list { display: grid; grid-template-rows: auto auto auto auto minmax(0, 1fr); gap: var(--space-2); min-block-size: 0; block-size: 100%; overflow: hidden; }
	.rail-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
	h3 { margin: 0; display: inline-flex; align-items: center; gap: var(--space-1); color: var(--color-text-tertiary); font-size: var(--text-xs); font-weight: 600; letter-spacing: var(--tracking-label); text-transform: uppercase; }
	button { border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text); padding: var(--space-1) var(--space-2); cursor: pointer; }
	button:focus-visible, input:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
	button:disabled { cursor: default; color: var(--color-text-tertiary); }
	.filter, .import-file { display: grid; gap: var(--space-1); font-size: var(--text-xs); color: var(--color-text-secondary); }
	.import-file { cursor: pointer; }
	.import-file span { justify-self: start; padding: var(--space-1) var(--space-2); border: 1px solid var(--color-rule); border-radius: var(--radius-md); color: var(--color-text); }
	.import-file:focus-within span { outline: 2px solid var(--color-accent); outline-offset: 2px; }
	.import-file:has(input:disabled) { cursor: default; }
	.import-file:has(input:disabled) span { color: var(--color-text-tertiary); }
	input { min-inline-size: 0; max-inline-size: 100%; border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-bg); color: var(--color-text); padding: var(--space-2); }
	p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-xs); line-height: var(--leading-xs); }
	.ledger-options { min-block-size: 0; overflow: auto; scrollbar-width: thin; }
	.ledger-options h3 { padding: var(--space-2) var(--space-3); }
	.table-name { inline-size: 100%; min-block-size: var(--workbench-control); display: grid; text-align: start; padding: var(--space-2) var(--space-3); border: 0; border-radius: 0; border-inline-start: 1px solid transparent; font-family: var(--font-data); font-size: var(--text-sm); line-height: var(--leading-sm); overflow-wrap: anywhere; }
	.table-name:hover { background: var(--color-bg); }
	.table-name[aria-pressed='true'] { border-inline-start-color: var(--color-accent); background: var(--tint-accent); font-weight: 600; }
	.local-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; }
	small { color: var(--color-text-secondary); font-size: var(--text-xs); font-weight: 400; font-family: var(--font-reading); }
	.remove { font-size: var(--text-xs); }
</style>
