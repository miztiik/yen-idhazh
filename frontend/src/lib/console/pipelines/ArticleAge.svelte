<script lang="ts">
	import { articleAge } from './article-age';
	import { distribution, distributionShortfall } from '$lib/charts/d3/distribution';
	import Distribution from '$lib/charts/d3/Distribution.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { frame, MARGIN } from '$lib/charts/frame';
	import type { Row } from '$lib/data/ledger';
	import type { ConsoleConfig } from '$lib/server/config';
	let { rows, knobs }: { rows: Row[]; knobs: ConsoleConfig } = $props();
	const age = $derived(articleAge(rows));
	const positive = $derived(age.hours.filter((hour) => hour > 0));
	const options = $derived({
		frame: frame(knobs.chart_width, knobs.chart_height, MARGIN), minValues: knobs.fleet_min_rows,
		valueTicks: 5, scale: 'log' as const,
		rules: [{ at: 24, label: 'one day' }, ...(age.median !== null && age.median > 0 ? [{ at: age.median, label: 'median' }] : [])]
	});
	const geometry = $derived(distribution(positive, options));
</script>
<p data-lede class="lede" data-article-age-inferred={age.inferred}>{age.lede}</p>
<p data-comparison="distribution">Articles over a day old against newer ones, from the source's stated publication to our recorded item start.</p>
<div data-model-rule="no" data-model-rule-name="article-age" data-model-rule-none="one distribution of the window, not a date axis">
	<Distribution {geometry} empty={emptyState('quiet', distributionShortfall(positive, options) ?? 'No positive source-stated age was measured.')}
		name="article-age" label="Article age in hours, on a ten-times axis; inferred times excluded"
		width={knobs.chart_width} height={knobs.chart_height} />
</div>
{#if age.hours.some((hour) => hour === 0)}
	<p data-article-age-zero>{age.hours.filter((hour) => hour === 0).length} items started at their stated publication time: zero hours has no position on a logarithmic axis{age.median === 0 ? '; the median is zero hours' : ''}.</p>
{/if}
<style>.lede { font-size: var(--text-2xl); font-variant-numeric: tabular-nums; }</style>
