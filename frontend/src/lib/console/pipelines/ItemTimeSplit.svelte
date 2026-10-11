<script lang="ts">
	import { nativeTimeSplit } from './item-time-split';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { frame, MARGIN } from '$lib/charts/frame';
	import type { Row } from '$lib/data/ledger';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	let { rows, knobs, chart, rule, calendar }: { rows: Row[]; knobs: ConsoleConfig; chart: ChartConfig; rule: ModelRule; calendar?: readonly string[] } = $props();
	const split = $derived(nativeTimeSplit(rows, calendar));
	const geometry = $derived(dateSeries(split.series.map((series) => ({ ...series,
		points: series.points.map((point) => ({ ...point, value: split.signedDates.includes(point.date) ? null : point.value }))
	})), {
		frame: frame(knobs.chart_width, knobs.chart_height, MARGIN), density: chart.tick_density,
		valueTicks: 5, padding: 0.2, rule, stacked: true
	}));
</script>
<p data-lede class="lede">{split.meanMs === null ? 'No whole item clock was measured.' : `${(split.meanMs / 1000).toFixed(2)} seconds per timed article.`}</p>
<p data-comparison="composition">The model's calls against fetching and extracting; each stack uses the same complete, reconciling articles for every mean.</p>
{#if split.signed}
	<p data-contract-blocked="signed-stack">The recorded clocks overlap on {split.signedDates.join(', ')}. The shared stacked drawing cannot place a signed part. Those days have no stack; their readings below retain the signed values.</p>
{/if}
<DateSeries {geometry} empty={emptyState('quiet', 'No complete non-overlapping item clock was measured.')}
	name="item-time-split" label="Daily mean milliseconds in each recorded step, over complete reconciling clocks"
	width={knobs.chart_width} height={knobs.chart_height} readout={geometry?.readout} readoutMaxShare={chart.readout_max_share} />
<details data-time-split-readings><summary>The clocks behind the stacks</summary>
	{#each split.days as day (day.date)}
		<p>{day.date}: total {day.total.value === null ? 'not measured' : `${day.total.value} ms`} over {day.items} timed items; {day.composable} have every part recorded and reconciling.</p>
		<ul>{#each day.readings as part (part.cell)}<li>{part.cell}: {part.value === null ? 'not measured' : `${part.value} ms`}, timed {part.timed} of {day.items}.</li>{/each}</ul>
	{/each}
</details>
<style>.lede { font-size: var(--text-2xl); }</style>
