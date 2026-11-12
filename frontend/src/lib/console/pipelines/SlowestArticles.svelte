<script lang="ts">
	/** Rank recorded article work across every shard of the newest run. */
	import RankedList from '$lib/components/RankedList.svelte';
	import { rankedList } from '$lib/charts/d3/rankedList';
	import { slowestArticles } from './slowest-articles';
	import { formatNumber } from '$lib/number-format';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';

	let { rows, chart, limit }: { rows: readonly Row[]; chart: ChartConfig; limit: number } = $props();
	const slowest = $derived(slowestArticles(rows, chart.number_format));
	const geometry = $derived(rankedList(slowest.rows, { max: limit }));
	const seconds = (value: number) => formatNumber(value, chart.number_format, { si: false });
</script>

<div data-slowest-run={slowest.run ?? ''} data-model-rule-name="slowest-articles"
	data-model-rule="no" data-model-rule-none="This ranks recorded article work within one run, not a change over days."
	data-panel-question="is it working">
	<p>Across all shards of newest run {slowest.run ?? 'not recorded'}. Queue wait is outside recorded item time.</p>
	<p data-comparison="Each article's longest stage against its other stages">Each article's longest stage against its other stages.</p>
	<p class="lede" data-lede>{geometry?.rows.length
		? `${seconds(geometry.rows[0].value)} seconds for the slowest article.`
		: 'No article recorded elapsed time.'}</p>
	<RankedList {geometry} caption="Longest articles" maxText={`${geometry === null ? '0' : seconds(geometry.max)} seconds`}
		unmeasuredNote="No elapsed time recorded." emptyNote="No elapsed time recorded." />
	<p>{slowest.unmeasured} articles did not record elapsed time.</p>
</div>

<style>
	.lede { font-size: var(--console-page-title-size); line-height: var(--console-page-title-leading); font-weight: var(--console-page-title-weight); }
</style>
