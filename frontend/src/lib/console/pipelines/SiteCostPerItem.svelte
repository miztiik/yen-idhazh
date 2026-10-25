<script lang="ts">
	import { siteCost, siteCostPoints, publishingHorizon, sizeGain, newestSize } from './site-cost-per-item';
	import { horizonRate, siteCostMeasure } from '$lib/charts/glance';
	import { daysInWindow } from '$lib/charts/viewport';
	import { countDays } from '$lib/console/span-words';
	import { shortDate } from '$lib/format';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { frame, MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import type { RunSummary } from '$lib/server/payload';
	import type { TimeWindow } from '$lib/charts/viewport';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	import { formatNumber } from '$lib/number-format';
	let { manifests, publishedItems, window, knobs, chart, rule, sizeBytes }: {
		manifests: RunSummary[]; publishedItems: Record<string, number>; window: TimeWindow;
		knobs: ConsoleConfig; chart: ChartConfig; rule: ModelRule; sizeBytes?: number | null;
	} = $props();
	let measured = $state<number | null>(null);
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const articles = $derived(new Map(Object.entries(publishedItems)));
	const cost = $derived(siteCost(manifests, articles, window));
	const horizon = $derived(publishingHorizon(sizeBytes === undefined ? newestSize(manifests) : sizeBytes, cost, articles));
	const gain = $derived(sizeGain(manifests.filter((day) => day.date >= window.start && day.date <= window.end)));
	const signed = $derived(cost.days.filter((day) => day.bytesPerItem < 0));
	const windowDays = $derived(daysInWindow(window).length);
	const geometry = $derived(dateSeries([{ label: 'Payload bytes per article', token: '--chart-3', points: siteCostPoints(cost, window) }],
		{ frame: frame(width, knobs.chart_height, MARGIN), density: chart.tick_density, valueTicks: 5, padding: 0.2, stacked: true, rule, number_format: chart.number_format,
			rules: cost.median === null ? [] : [{ at: cost.median, label: 'window median' }] }));
</script>
<div use:observeWidth={(next) => measured = next}>
<p data-lede data-cost-summary class="lede">{cost.median === null ? 'No published article and size were measured together.' : `${formatNumber(Math.round(cost.median), chart.number_format)} B an article.`}</p>
<p data-comparison="Each day's bytes per article against the window's median.">
	Each day's bytes per article against the window's median{cost.spread === null ? '; one day is not a spread' : `; give or take ${Math.round(cost.spread)} B`}.
</p>
<p>How long we can keep publishing under the 1 GB Pages cap. {siteCostMeasure(windowDays)}</p>
{#if manifests.length === 0}<p data-empty="missing">The private manifest record is unavailable.</p>
{:else if cost.empty}<p data-empty="quiet">The manifest window was read; no day both published an article and recorded a size.</p>{/if}
{#if horizon}<p data-cost-horizon>At {formatNumber(Math.round(cost.median!), chart.number_format)} B an article and {horizonRate(horizon.articlesPerDay, windowDays, chart.number_format)}, the cap has room for about {formatNumber(Math.round(horizon.articles), chart.number_format, { exact: true, si: false })} more articles: about {formatNumber(horizon.years, chart.number_format, { si: false })} years at this window's rate. The cap measures the built site, which is larger than the payload tree, so this is the most room we have.</p>{/if}
{#if gain !== null}<p>{gain >= 0 ? 'Up' : 'Down'} {formatNumber(Math.abs(gain) / 1024 / 1024, chart.number_format, { si: false })} MB over {countDays(windowDays)}.</p>
{:else}<p>No second measurement of the private site size is available in this window.</p>{/if}
{#if signed.length > 0}
	<p>The payload shrank on {signed.map((day) => day.date).join(', ')}. A composition bar cannot add negative bytes; the signed readings are listed below, not drawn as zero.</p>
	<ul>{#each signed as day (day.date)}<li>{day.date}: {formatNumber(Math.round(day.bytesPerItem), chart.number_format)} B per article.</li>{/each}</ul>
{/if}
<DateSeries {geometry} empty={emptyState('quiet', 'No day both published an article and recorded a size.')}
	name="site-cost-per-item" label="Payload bytes per published article, one bar a day"
	{width} height={knobs.chart_height} readout={geometry === null ? null : { ...geometry.readout, columns: geometry.dates.map(shortDate) }} readoutMaxShare={chart.readout_max_share} />
<ul class="sr-only" data-cost-days>{#each cost.days as day (day.date)}
	<li data-cost-day={day.date} data-cost-bytes={Math.round(day.bytesPerItem)} data-cost-flagged={String(day.flagged)}>{day.date}: {Math.round(day.bytesPerItem)} B per article{day.flagged ? ', outside the band' : ''}.</li>
{/each}</ul>
</div>
<style>.lede { font-size: var(--text-2xl); font-variant-numeric: tabular-nums; }</style>
