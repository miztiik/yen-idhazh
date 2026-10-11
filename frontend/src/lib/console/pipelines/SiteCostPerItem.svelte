<script lang="ts">
	import { siteCost, siteCostPoints, publishingHorizon, sizeGain, newestSize } from './site-cost-per-item';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { frame, MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import type { RunSummary } from '$lib/server/payload';
	import type { TimeWindow } from '$lib/charts/viewport';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
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
	const geometry = $derived(dateSeries([{ label: 'Payload bytes per article', token: '--chart-3', points: siteCostPoints(cost, window) }],
		{ frame: frame(width, knobs.chart_height, MARGIN), density: chart.tick_density, valueTicks: 5, padding: 0.2, stacked: true, rule,
			rules: cost.median === null ? [] : [{ at: cost.median, label: 'window median' }] }));
</script>
<div use:observeWidth={(next) => measured = next}>
<p data-lede class="lede">{cost.median === null ? 'No published article and size were measured together.' : `${Math.round(cost.median).toLocaleString('en-GB')} B per article.`}</p>
<p data-comparison="Each day's bytes per article against the window's median." data-cost-summary>
	Each day's bytes per article against the window's median{cost.spread === null ? '; one day is not a spread' : `; give or take ${Math.round(cost.spread)} B`}.
</p>
{#if manifests.length === 0}<p data-empty="missing">The private manifest record is unavailable.</p>
{:else if cost.empty}<p data-empty="quiet">The manifest window was read; no day both published an article and recorded a size.</p>{/if}
{#if horizon}<p data-cost-horizon>The cap has room for about {Math.round(horizon.articles).toLocaleString('en-GB')} more articles: about {horizon.years.toFixed(1)} years at this window's rate. The cap measures the built site, which is larger than the payload tree, so this is the most room we have.</p>{/if}
{#if gain !== null}<p>{gain >= 0 ? 'Up' : 'Down'} {(Math.abs(gain) / 1024 / 1024).toFixed(1)} MB in this window.</p>{/if}
{#if signed.length > 0}
	<p>The payload shrank on {signed.map((day) => day.date).join(', ')}. A composition bar cannot add negative bytes; the signed readings are listed below, not drawn as zero.</p>
	<ul>{#each signed as day (day.date)}<li>{day.date}: {Math.round(day.bytesPerItem)} B per article.</li>{/each}</ul>
{/if}
<DateSeries {geometry} empty={emptyState('quiet', 'No day both published an article and recorded a size.')}
	name="site-cost-per-item" label="Payload bytes per published article, one bar a day"
	{width} height={knobs.chart_height} readout={geometry?.readout} readoutMaxShare={chart.readout_max_share} />
<ul class="sr-only" data-cost-days>{#each cost.days as day (day.date)}
	<li data-cost-day={day.date} data-cost-bytes={Math.round(day.bytesPerItem)} data-cost-flagged={String(day.flagged)}>{day.date}: {Math.round(day.bytesPerItem)} B per article{day.flagged ? ', outside the band' : ''}.</li>
{/each}</ul>
</div>
<style>.lede { font-size: var(--text-2xl); font-variant-numeric: tabular-nums; }</style>
