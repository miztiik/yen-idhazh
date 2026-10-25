<script lang="ts">
	import { nativeTimeSplit, timeSplitReadout } from './item-time-split';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { frame, MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import { shortDate } from '$lib/format';
	import type { Row } from '$lib/data/ledger';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	import { formatNumber } from '$lib/number-format';
	import { useNumberFormat } from '$lib/number-format-context';
	let { rows, knobs, chart, rule, calendar }: { rows: Row[]; knobs: ConsoleConfig; chart: ChartConfig; rule: ModelRule; calendar?: readonly string[] } = $props();
	const numberFormat = useNumberFormat();
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
<p data-lede class="lede">{split.meanMs === null ? 'No whole item clock was measured.' : `${formatNumber(split.meanMs / 1000, numberFormat, { si: false })} seconds per timed article.`}</p>
<p data-comparison="Summarize against fetching, extracting and checking.">Summarize against fetching, extracting and checking, over the same complete, reconciling clocks. Calls are details, not extra stages.</p>
<p data-duration-cohort>{split.count} of {split.recorded} recorded item clocks supply these means. Positive unclaimed time and overlap are averaged separately; the solid marker is elapsed time.</p>
<DateSeries {geometry} empty={emptyState('quiet', 'No complete reconciling item clock was measured.')}
	name="item-time-split" label="Daily mean stage durations with separate overlap deduction and elapsed marker"
	{width} height={knobs.chart_height} readout={{ ...readout, columns: readout.columns.map(shortDate) }} readoutMaxShare={chart.readout_max_share} />
<details data-time-split-readings><summary>The clocks behind the stacks</summary>
	{#each split.days as day (day.date)}
		<p>{day.date}: {day.count} of {day.recorded} clocks are complete; excluded: {day.missing} missing, {day.invalid} invalid and {day.inconsistent} inconsistent. {day.overlapping} clocks overlap.</p>
		<ul>{#each day.details as part (part.cell)}<li>{part.label}: {part.value === null ? 'not measured for the whole cohort' : `${formatNumber(part.value / 1000, numberFormat, { si: false })} s`}, timed {part.timed} of {day.count}; not added to the stack.</li>{/each}</ul>
	{/each}
</details>
</div>
<style>.lede { font-size: var(--text-2xl); }</style>
