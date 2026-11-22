<script lang="ts">
	import { nativeTimeSplit, timeSplitReadout } from './item-time-split';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { shortDate } from '$lib/format';
	import type { Row } from '$lib/data/ledger';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	import { formatNumber } from '$lib/number-format';
	import { useNumberFormat } from '$lib/number-format-context';
	let { rows, knobs, chart, rule, calendar }: { rows: Row[]; knobs: ConsoleConfig; chart: ChartConfig; rule: ModelRule; calendar?: readonly string[] } = $props();
	const numberFormat = useNumberFormat();
	const frame = useChartFrame(() => chart);
	let measured = $state<number | null>(null);
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const split = $derived(nativeTimeSplit(rows, calendar));
	const geometry = $derived(dateSeries(split.series, {
		frame: frame(width, knobs.chart_height, MARGIN), density: chart.tick_density,
		valueTicks: 5, padding: 0.2, rule, stacked: true, reconciliation: split.reconciliation,
		number_format: chart.number_format
	}));
	const readout = $derived(timeSplitReadout(split, numberFormat));
</script>
<div use:observeWidth={(next) => measured = next}>
<p data-lede class="lede" data-comparison="Time per stage against the other stages in the same complete article clocks.">{split.meanMs === null ? 'No complete article timings.' : `${formatNumber(split.meanMs / 1000, numberFormat, { si: false })} seconds per timed article.`}
	<span data-duration-cohort>{split.count} of {split.recorded} recorded item clocks used.</span>
</p>
<DateSeries {geometry} empty={emptyState('quiet', 'No complete reconciling item clock was measured.')}
	name="item-time-split" label="Daily mean stage durations with separate overlap deduction and elapsed marker"
	{width} height={knobs.chart_height} readout={{ ...readout, columns: readout.columns.map(shortDate) }} readoutMaxShare={chart.readout_max_share} />
{#if split.recorded > 0}
	<details class="console-disclosure" data-time-split-readings>
		<summary class="console-summary">Clock exclusions and calls</summary>
		<p>Calls are part of Summarize. The summary call includes the visual plan.</p>
		{#each split.days.filter((day) => day.recorded > 0) as day (day.date)}
			<p><time datetime={day.date}>{shortDate(day.date)} UTC</time>: {day.count} of {day.recorded} used; {day.missing} missing, {day.invalid} invalid, {day.inconsistent} inconsistent; {day.overlapping} with overlap.</p>
			<dl>
				{#each day.details as part (part.cell)}
					<div><dt>{part.label}</dt><dd>{part.value === null ? 'No mean' : `${formatNumber(part.value / 1000, numberFormat, { si: false })} s`} ({part.timed} of {day.count} timed)</dd></div>
				{/each}
			</dl>
		{/each}
	</details>
{/if}
</div>

<style>
	.lede { font-size: var(--text-2xl); }
	[data-duration-cohort], details p, dl { font-size: var(--text-sm); line-height: var(--leading-sm); color: var(--color-text-secondary); }
	time, dt { font-weight: 600; }
	dl { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); margin: 0 0 var(--space-3); }
</style>
