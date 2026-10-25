<script lang="ts">
	import { slowerOnSameWork } from './slower-on-same-work';
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
	let measured = $state<number | null>(null);
	const numberFormat = useNumberFormat();
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const work = $derived(slowerOnSameWork(rows, calendar));
	const geometry = $derived(dateSeries(work.series, {
		frame: frame(width, knobs.chart_height, MARGIN), density: chart.tick_density,
		valueTicks: 5, padding: 0.2, rule,
		rules: work.median === null ? [] : [{ at: work.median, label: 'window median' }],
		number_format: chart.number_format
	}));
</script>
<div use:observeWidth={(next) => measured = next}>
<p data-lede class="lede">{work.newest === null ? 'No comparable reference work on the newest day.' : `${formatNumber(work.newest, numberFormat, { si: false })} seconds for the typical article.`}</p>
<p data-comparison="The newest day's seconds against the window's median.">The newest day's seconds against the window's median, pricing the same article size on the same reference machine.</p>
<DateSeries {geometry} empty={emptyState('quiet', 'No qualifying reference-machine work was measured.')}
	name="slower-on-same-work" label="Seconds for the same typical article, one point a recorded day"
	{width} height={knobs.chart_height} readout={geometry === null ? null : { ...geometry.readout, columns: geometry.dates.map(shortDate) }} readoutMaxShare={chart.readout_max_share} />
<p data-reference-machine>{work.reference.cpuModel === null ? 'No reference machine was recorded.' :
	`Reference: ${work.reference.cpuModel}; typical article: ${work.reference.freshInput} fresh prompt tokens and ${work.reference.output} written tokens.`}</p>
<p>{work.reference.unqualified} rows lack comparable work; {work.reference.unnamedMachine} qualifying rows name no machine.</p>
</div>
<style>.lede { font-size: var(--text-2xl); font-variant-numeric: tabular-nums; }</style>
