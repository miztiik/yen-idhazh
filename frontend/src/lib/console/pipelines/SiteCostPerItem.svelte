<script lang="ts">
	import { siteCost, siteCostPoints, publishingHorizon, sizeGain, newestSize } from './site-cost-per-item';
	import { horizonRate } from '$lib/charts/glance';
	import { daysInWindow } from '$lib/charts/viewport';
	import { countDays } from '$lib/console/span-words';
	import { shortDate } from '$lib/format';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import type { RunSummary } from '$lib/server/payload';
	import type { TimeWindow } from '$lib/charts/viewport';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	import { formatNumber } from '$lib/number-format';
	let { manifests, publishedItems, window, knobs, chart, rule, sizeBytes }: {
		manifests: RunSummary[]; publishedItems: Record<string, number>; window: TimeWindow;
		knobs: ConsoleConfig; chart: ChartConfig; rule: ModelRule; sizeBytes?: number | null;
	} = $props();
	const frame = useChartFrame(() => chart);
	let measured = $state<number | null>(null);
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const articles = $derived(new Map(Object.entries(publishedItems)));
	const cost = $derived(siteCost(manifests, articles, window));
	const horizon = $derived(publishingHorizon(sizeBytes === undefined ? newestSize(manifests) : sizeBytes, cost, articles));
	const gain = $derived(sizeGain(manifests.filter((day) => day.date >= window.start && day.date <= window.end)));
	const signed = $derived(cost.days.filter((day) => day.bytesPerItem < 0));
	const windowDays = $derived(daysInWindow(window).length);
	const whole = (value: number) => formatNumber(Math.round(value), chart.number_format, { exact: true });
	const empty = $derived(
		manifests.length === 0 ? emptyState('missing', 'The private manifest record is unavailable.') :
		cost.empty ? emptyState('quiet', 'No day both published an article and recorded a payload size change.') :
		emptyState('quiet', 'Only decreases were measured; the readings are below.')
	);
	const geometry = $derived(dateSeries([{ label: 'Payload bytes per article', token: '--chart-measure', points: siteCostPoints(cost, window) }],
		{ frame: frame(width, knobs.chart_height, MARGIN), density: chart.tick_density, valueTicks: 5, padding: 0.2, stacked: true, rule, number_format: chart.number_format,
			rules: cost.median === null ? [] : [{ at: cost.median, label: 'window median' }] }));
</script>
<div use:observeWidth={(next) => measured = next}>
	{#if cost.median !== null}
		<p data-lede data-cost-summary class="lede">{whole(cost.median)} B per article</p>
	{/if}
	<p data-comparison="Each day's bytes per article against the window's median.">
		Median of daily payload change per published article{cost.spread === null ? '.' : `; spread ${whole(cost.spread)} B.`}
	</p>
	<DateSeries {geometry} {empty}
		name="site-cost-per-item" label="Payload bytes per published article, one bar a day"
		{width} height={knobs.chart_height} readout={geometry === null ? null : { ...geometry.readout, columns: geometry.dates.map(shortDate) }}
		readoutMaxShare={chart.readout_max_share} hint="Hover, tap or use the arrow keys to read a day." />
	{#if signed.length > 0}
		<p>Payload decreases (not drawn):</p>
		<ul>
			{#each signed as day (day.date)}
				<li><time datetime={day.date}>{day.date}</time>: {whole(day.bytesPerItem)} B per article.</li>
			{/each}
		</ul>
	{/if}
	{#if horizon}
		<p data-cost-horizon>
			1 GB cap estimate: up to {whole(horizon.articles)} more articles, or about
			{formatNumber(horizon.years, chart.number_format, { si: false })} years at
			{horizonRate(horizon.articlesPerDay, windowDays, chart.number_format)}.
			The built site is larger than the payload.
		</p>
	{/if}
	{#if gain !== null}
		<p>Payload {gain >= 0 ? 'up' : 'down'} {formatNumber(Math.abs(gain) / 1024 / 1024, chart.number_format, { si: false })} MB over {countDays(windowDays)}.</p>
	{:else if cost.median !== null}
		<p>Window change needs two size readings.</p>
	{/if}
	<ul class="sr-only" data-cost-days>
		{#each cost.days as day (day.date)}
			<li data-cost-day={day.date} data-cost-bytes={Math.round(day.bytesPerItem)} data-cost-flagged={String(day.flagged)}>{day.date}: {whole(day.bytesPerItem)} B per article{day.flagged ? ', outside the band' : ''}.</li>
		{/each}
	</ul>
</div>
<style>.lede { font-size: var(--text-2xl); font-variant-numeric: tabular-nums; }</style>
