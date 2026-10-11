<script lang="ts">
	import DateSeries from '../../charts/d3/DateSeries.svelte';
	import { dateSeries, type SeriesInput } from '../../charts/d3/dateSeries';
	import { emptyState } from '../../charts/d3/empty';
	import { chartWidth, frame, observeWidth } from '../../charts/frame';
	import type { ModelRule } from '../../charts/d3/model-rule';
	import type { ChartConfig } from '../../server/config';
	import { completeModelRule } from './model-rule';
	import { shortDate } from '../../format';

	let { series, rule, chart, name, stacked = false, rules = [], domain, note = 'No reading was recorded in this window.' }: {
		series: readonly SeriesInput[]; rule: ModelRule; chart: ChartConfig; name: string;
		stacked?: boolean; rules?: readonly { at: number; label: string }[];
		domain?: [number, number]; note?: string;
	} = $props();
	let measured = $state<number | null>(null);
	const box = $derived(frame(chartWidth(measured, chart.width_px), chart.height_px));
	const fullRule = $derived(completeModelRule(rule, series.flatMap((one) => one.points.map((point) => point.date))));
	const geometry = $derived(dateSeries(series, {
		frame: box, stacked, density: chart.tick_density, valueTicks: 4, padding: 0.2, rule: fullRule, rules, domain
	}));
	const readout = $derived(geometry === null ? null : {
		...geometry.readout,
		columns: geometry.dates.map(shortDate)
	});
</script>

<div use:observeWidth={(value) => (measured = value)}>
	<DateSeries {geometry} {readout} empty={emptyState('quiet', note)} {name} label={name}
		width={box.width} height={box.height} readoutMaxShare={chart.readout_max_share} />
</div>
{#if geometry === null && 'changes' in fullRule && fullRule.note !== null}
	<p data-model-rule-empty={fullRule.changes.length === 0 ? name : undefined} data-model-rule-note={name}>{fullRule.note}</p>
{/if}
