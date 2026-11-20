<script lang="ts">
	import { articleAge, HOURS_PER_DAY } from './article-age';
	import { distribution, distributionShortfall } from '$lib/charts/d3/distribution';
	import Distribution from '$lib/charts/d3/Distribution.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import type { Row } from '$lib/data/ledger';
	import type { ConsoleConfig } from '$lib/server/config';
	import { useNumberFormat } from '$lib/number-format-context';
	import { formatNumber } from '$lib/number-format';
	let { rows, knobs }: { rows: Row[]; knobs: ConsoleConfig } = $props();
	const numberFormat = useNumberFormat();
	const frame = useChartFrame();
	let measured = $state<number | null>(null);
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const age = $derived(articleAge(rows));
	const positive = $derived(age.hours.filter((hour) => hour > 0));
	const zero = $derived(age.hours.length - positive.length);
	const options = $derived({
		frame: frame(width, knobs.chart_height, MARGIN), minValues: knobs.fleet_min_rows,
		valueTicks: 5, scale: 'log' as const,
		rules: [
			{ at: HOURS_PER_DAY, label: age.median === HOURS_PER_DAY ? 'Median: 1 day' : '1 day' },
			...(age.median !== null && age.median > 0 && age.median !== HOURS_PER_DAY ? [{ at: age.median, label: 'Median' }] : [])
		],
		number_format: numberFormat
	});
	const geometry = $derived(distribution(positive, options));
</script>
<div use:observeWidth={(next) => measured = next}>
<p data-lede class="lede" data-article-age-inferred={age.inferred}
	data-comparison="Articles older than one day against articles started no more than one day after publication.">
	{#if age.hours.length > 0}
		{formatNumber(100 * age.overDay / age.hours.length, numberFormat, { si: false })}% ({age.overDay} of {age.hours.length} measured) were older than one day.
	{:else}
		No article ages measured.
	{/if}
</p>
{#if geometry}<p class="note">Bars: article count; line: share of plotted articles at or below.</p>{/if}
<div data-model-rule="no" data-model-rule-name="article-age" data-model-rule-none="one distribution of the window, not a date axis">
	<Distribution {geometry} empty={emptyState('quiet', distributionShortfall(positive, options) ?? 'No positive source-stated age was measured.')}
		name="article-age" label="Article age at processing start in hours, logarithmic scale; inferred and future times excluded"
		{width} height={knobs.chart_height} binLabel="Articles" />
</div>
{#if zero > 0}
	<p class="note" data-article-age-zero>{zero} at 0 h, counted in the headline but not plotted{age.median === 0 ? '; median: 0 h' : ''}.</p>
{/if}
<details class="console-disclosure">
	<summary class="console-summary">Age coverage</summary>
	<p class="note">From the feed's publication time to processing start. Of {age.published} successful articles, {age.inferred} had inferred times, {age.unknown} had no usable time and {age.future} had future publication times. These are excluded.</p>
</details>
</div>
<style>
	.lede { font-size: var(--text-2xl); line-height: var(--leading-2xl); font-variant-numeric: tabular-nums; }
	.note { color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-sm); }
</style>
