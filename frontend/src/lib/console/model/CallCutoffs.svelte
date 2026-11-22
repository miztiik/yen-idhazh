<script lang="ts">
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import { emptyState } from '$lib/charts/d3/empty';
	import { chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { readoutOf } from '$lib/charts/readout';
	import { daysInWindow } from '$lib/charts/viewport';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { Row } from '$lib/data/ledger';
	import { shortDate } from '$lib/format';
	import { formatNumber } from '$lib/number-format';
	import type { ChartConfig } from '$lib/server/config';
	import { callEnding } from './call-ending';
	import type { Range } from '../queries/window';

	let { rows, range, rule, chart }: {
		rows: readonly Row[]; range: Range; rule: ModelRule; chart: ChartConfig;
	} = $props();
	let width = $state<number | null>(null);
	const frame = useChartFrame(() => chart);
	const box = $derived(frame(chartWidth(width, chart.width_px), chart.height_px));
	const counts = $derived(callEnding(rows, daysInWindow({ start: range.from, end: range.to })));
	const points = $derived(counts.days.map(({ date, endings }) => ({ date, value: endings?.cutoffs ?? null })));
	const count = (value: number) => formatNumber(value, chart.number_format, { exact: true });
	const label = 'Calls cut off at the length limit';
	const token = '--chart-measure';
	// A count axis must not draw fractional calls on quiet days.
	const valueTicks = $derived(Math.min(4, Math.max(1, ...points.map(({ value }) => value ?? 0))));
	const geometry = $derived(dateSeries([{ label, token, points }], {
		frame: box, density: chart.tick_density, padding: 0.2, rule, valueTicks, valueFormat: count,
		number_format: chart.number_format
	}));
	const readout = $derived(geometry === null ? null : readoutOf({
		type: 'dateSeries',
		columns: geometry.dates.map(shortDate),
		series: [{ label: 'Length cutoffs', swatch: `var(${token})`, values: points.map((point) => point.value), format: count }],
		events: { lines: counts.days.map(({ endings }) => endings === null ? [] : [
			{ label: 'Reported endings', value: count(endings.reported), swatch: null },
			{ label: 'Normal stops', value: count(endings.stops), swatch: null },
			...(endings.other > 0 ? [{ label: 'Other reported reasons', value: count(endings.other), swatch: null }] : [])
		]) },
		notMeasured: 'No finish reasons recorded.',
		resting: 'last'
	}));
</script>

{#if counts.total.reported > 0}
	<p data-lede>{count(counts.total.cutoffs)} {counts.total.cutoffs === 1 ? 'cutoff' : 'cutoffs'} in {count(counts.total.reported)} reported endings</p>
{/if}
<p data-comparison="Daily length cutoffs among reported call endings">Only reported finish reasons count. A cutoff can still yield a usable reply; this is not a count of failed attempts.</p>
<div use:observeWidth={(value) => (width = value)}>
	<DateSeries {geometry} {readout} empty={emptyState('quiet', 'No finish reasons were recorded for these calls.')}
		name="call-ending" label="Daily calls cut off at the length limit"
		width={box.width} height={box.height} readoutMaxShare={chart.readout_max_share} />
</div>
