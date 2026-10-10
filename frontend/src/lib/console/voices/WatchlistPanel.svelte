<script lang="ts">
	import type { watchlist } from './watchlist';
	import type { PanelState } from '../waiting';
	import VoicesPanel from './VoicesPanel.svelte';
	import RecordFrame from './RecordFrame.svelte';
	import TileStrip from '../../charts/d3/TileStrip.svelte';
	import { recordEmptyState } from '../../charts/d3/empty';
	let { view, panelState, width, height, readoutMaxShare, tileMinPx, notes, days }: {
		view: ReturnType<typeof watchlist> | null; panelState: PanelState; width: number; height: number; readoutMaxShare: number; tileMinPx: number; notes: string[]; days: number;
	} = $props();
</script>
<VoicesPanel id="watchlist" title="What the watchlist caught" question="what happened" {days}
	comparison="catch days against days with no recorded catch" reason="hit counts, not a model trend">
	<RecordFrame {panelState} {width} {height} name="watchlist" label="Watchlist catch days" kind="tileStrip">
		{#if view}
			<p data-lede>{view.lede}</p>
			<div class="evidence watchlist" data-chart-type={view.geometry === null ? 'tileStrip' : undefined} data-chart-name="watchlist"
				data-readout-none={view.geometry === null ? 'No complete hit column was recorded, so there is no tile reading' : undefined}>
				<TileStrip geometry={view.geometry} empty={recordEmptyState('quiet')} name="watchlist" label="Watchlist catch days" {width} {height} {tileMinPx} readout={view.records} {readoutMaxShare} stateWords={{ absent: 'hit column not recorded completely', quiet: 'no catch recorded', fired: 'caught' }}/>
			</div>
			<p class="notes">{view.quiet ? 'The watchlist caught nothing in this window.' : view.finding}</p>
			<p class="notes">A filled day: the watchlist caught at least one article. This window marks a day at {view.marked} and names it at {view.named} distinct catches.</p>
			{#if view.stale}<p class="notes">{view.stale}</p>{/if}
			{#if view.unknown || view.unknownFront}<p class="notes">{view.unknown} address readings lack a watchlist answer; {view.unknownFront} caught address-days lack a front-page answer. Neither is a recorded false.</p>{/if}
			{#each notes as note}<p class="notes">{note}</p>{/each}
		{/if}
	</RecordFrame>
</VoicesPanel>
<style>
	.watchlist :global(.tile.fired) { background: var(--chart-5); }
	.watchlist :global(.tile.quiet) { border-color: var(--chart-5); }
</style>
