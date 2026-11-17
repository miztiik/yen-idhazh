<script lang="ts">
	/** Rank above-median article work across every recorded shard of the newest run. */
	import RankedList from '$lib/components/RankedList.svelte';
	import { rankedList } from '$lib/charts/d3/rankedList';
	import { slowestArticles } from './slowest-articles';
	import { formatNumber } from '$lib/number-format';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';

	let { rows, chart, limit }: { rows: readonly Row[]; chart: ChartConfig; limit: number } = $props();
	const slowest = $derived(slowestArticles(rows, chart.number_format));
	const geometry = $derived(rankedList(slowest.rows, {
		max: limit,
		rules: slowest.medianSeconds === null ? [] : [{ at: slowest.medianSeconds, label: 'Run median' }]
	}));
	const shown = $derived(geometry?.rows.length ?? 0);
	const hidden = $derived(slowest.rows.length - shown);
	const emptyNote = $derived(slowest.measured === 0
		? 'No article recorded item work.'
		: slowest.measured === 1
			? 'Only one article has a recorded work time; there is no above-median comparison.'
			: 'No article work time exceeds the run median.');
	const seconds = (value: number) => formatNumber(value, chart.number_format, { si: false });
</script>

<div data-slowest-run={slowest.run ?? ''} data-model-rule-name="slowest-articles"
	data-model-rule="no" data-model-rule-none="This ranks recorded article work within one run, not a change over days."
	data-panel-question="is it working">
	<p>Run {slowest.run ?? 'not recorded'} (UTC), across recorded shards. Parked queue wait is excluded from item work and listed separately.</p>
	<p class="lede" data-lede data-comparison="Article work above the whole-run median">{slowest.medianSeconds === null
		? 'No article recorded item work.'
		: `Run median: ${seconds(slowest.medianSeconds)} s of item work.`}</p>
	<p>Showing {shown} of {slowest.rows.length} articles above the median, from {slowest.measured} measured articles.</p>
	<RankedList {geometry} caption="Above-median article work, longest first"
		maxText={`${geometry === null ? '0' : seconds(geometry.max)} seconds`} fitRuleLabels
		unmeasuredNote="No item work recorded." {emptyNote}
		tail={hidden > 0 ? `${hidden} more above-median articles are not shown (configured row limit: ${limit}).` : null} />
	<p>{slowest.unmeasured} articles did not record item work.</p>
</div>

<style>
	.lede { font-size: var(--console-page-title-size); line-height: var(--console-page-title-leading); font-weight: var(--console-page-title-weight); }
</style>
