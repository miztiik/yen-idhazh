<script lang="ts">
	import type { rankingDiscount } from './ranking-discount';
	import VoicesPanel from './VoicesPanel.svelte';
	import RankedList from '../../components/RankedList.svelte';
	import RecordFrame from './RecordFrame.svelte';
	let { discount, width, height }: { discount: ReturnType<typeof rankingDiscount>; width: number; height: number } = $props();
</script>
<VoicesPanel id="ranking-discount" title="How far the ranking discounts each feed" question="what happened"
	comparison="discount against the most the ranking takes" reason="one run's ranking setting, not a model trend">
	{#if discount === null}<RecordFrame panelState="missing" {width} {height} name="ranking-discount" label="Ranking discounts" kind="rankedList">{#snippet children()}{/snippet}</RecordFrame>
	{:else if discount.snapshot.counted === 0}<RecordFrame panelState="quiet" {width} {height} name="ranking-discount" label="Ranking discounts" kind="rankedList">{#snippet children()}{/snippet}</RecordFrame>
	{:else}
		<p data-lede>{discount.lede}</p>
		<p class="notes" data-window-exempt="ranking-discount">Run {discount.snapshot.runId} applied these factors over {discount.snapshot.windowDays} days. This fixed source-health reading does not follow the control. A feed no one read keeps full weight, not a measured perfect record.</p>
		<div class="evidence"><RankedList caption="Ranking discounts" geometry={discount.geometry} maxText={discount.maxText} unmeasuredNote="The ranking factor was not recorded." emptyNote="No feed was discounted by this run." tail={discount.tail}/></div>
	{/if}
</VoicesPanel>
