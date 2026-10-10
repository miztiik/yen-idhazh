<script lang="ts">
	import type { sourceCuts } from './source-cuts';
	import type { PanelState } from '../waiting';
	import VoicesPanel from './VoicesPanel.svelte';
	import RecordFrame from './RecordFrame.svelte';
	import SourceCutRange from '../../components/SourceCutRange.svelte';
	let { view, panelState, width, height, readoutMaxShare, notes, days }: {
		view: ReturnType<typeof sourceCuts> | null; panelState: PanelState; width: number; height: number; readoutMaxShare: number; notes: string[]; days: number;
	} = $props();
</script>
<VoicesPanel id="source-cuts" title="Sources cut short most often" question="what happened" {days}
	comparison="typical cut against the source's length range" reason="ranking of cuts, not a model trend">
	<RecordFrame {panelState} {width} {height} name="source-cuts" label="Source cuts and original lengths" kind="rankedList">
		{#if view}
			<p data-lede>{#if view.rows[0]}{view.rows[0].sourceId} lost text on {Math.round(100 * view.rows[0].cut / view.rows[0].articles)}% of articles with both lengths recorded: {view.rows[0].cut} of {view.rows[0].articles}.{:else if view.measured}No source's articles were cut short.{:else}No article has both lengths recorded yet.{/if}</p>
			<p class="notes" data-source-cuts-intro>The {view.days}-day span held {view.articles} articles with both lengths recorded.</p>
			<div class="evidence"><SourceCutRange rows={view.rows} caps={view.caps} width={width} {readoutMaxShare}/></div>
			{#if view.cost}<p class="notes" data-source-cuts-cost data-source-cut-n={view.cost.n} data-source-cut-median={view.cost.median} data-source-cut-max={view.cost.max}>{view.cost.n} articles were cut short. The typical cut removed {view.cost.median} words; the largest removed {view.cost.max}. The range shows original lengths on a log axis.</p>{/if}
			<p class="notes" data-source-cuts-more data-source-more-sources={view.moreSources} data-source-more-cuts={view.moreCuts}>{view.moreSources} more sources hold {view.moreCuts} cuts. {view.unknown} distinct articles lack a before or after length, so they are not in the cut-share denominator.</p>
			{#if view.zeroLengths || view.zeroCaps}<p class="notes">{view.zeroLengths} recorded zero-length originals remain in the counts but cannot sit on a log axis. {view.zeroCaps} cuts ended at zero words, which has no rule position on that axis.</p>{/if}
			{#each notes as note}<p class="notes">{note}</p>{/each}
		{/if}
	</RecordFrame>
</VoicesPanel>
