<script lang="ts">
	import DateSeries from '../../charts/d3/DateSeries.svelte';
	import { dateSeries, type SeriesInput } from '../../charts/d3/dateSeries';
	import { emptyState } from '../../charts/d3/empty';
	import { chartWidth, frame, observeWidth } from '../../charts/frame';
	import type { ModelRule } from '../../charts/d3/model-rule';
	import type { ChartConfig } from '../../server/config';

	let { series, rule, chart, name, stacked = false, rules = [], domain, note = 'No reading was recorded in this window.' }: {
		series: readonly SeriesInput[]; rule: ModelRule; chart: ChartConfig; name: string;
		stacked?: boolean; rules?: readonly { at: number; label: string }[];
		domain?: [number, number]; note?: string;
	} = $props();
	let measured = $state<number | null>(null);
	const box = $derived(frame(chartWidth(measured, chart.width_px), chart.height_px));
	const geometry = $derived(dateSeries(series, {
		frame: box, stacked, density: chart.tick_density, valueTicks: 4, padding: 0.2, rule, rules, domain
	}));
	const readout = $derived(geometry?.readout ?? null);
</script>

<div use:observeWidth={(value) => (measured = value)}>
	<DateSeries {geometry} {readout} empty={emptyState('quiet', note)} {name} label={name}
		width={box.width} height={box.height} readoutMaxShare={chart.readout_max_share} />
</div>
