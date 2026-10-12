<script lang="ts">
	import { nativeFailureMix } from './failure-mix';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import type { PanelState } from '../waiting';
	import FailureList from '$lib/components/FailureList.svelte';
	import { failureRuleRows } from '../failure-rules';
	import type { TimeWindow } from '$lib/charts/viewport';
	import { emptyState } from '$lib/charts/d3/empty';
	import { frame, MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import { shortDate } from '$lib/format';
	import type { Row } from '$lib/data/ledger';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	let { rows, ruleRows, knobs, chart, rule, calendar, nativeState, rulesState, rulesWindow }: {
		rows: Row[]; ruleRows: Row[]; knobs: ConsoleConfig; chart: ChartConfig; rule: ModelRule;
		calendar?: readonly string[];
		nativeState: PanelState; rulesState: PanelState;
		rulesWindow: TimeWindow;
	} = $props();
	let measured = $state<number | null>(null);
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const mix = $derived(nativeFailureMix(rows, calendar));
	const failed = $derived(nativeFailureMix(ruleRows));
	const ranking = $derived(failureRuleRows(ruleRows));
	const geometry = $derived(dateSeries(mix.series, {
		frame: frame(width, knobs.chart_height, MARGIN), density: chart.tick_density,
		valueTicks: 5, padding: 0.2, rule, stacked: true
	}));
</script>
<div use:observeWidth={(next) => measured = next}>
<p data-comparison="Each failed stage against the other stages in the same day's stack.">Each failed stage against the other stages in the same day's stack, not a rate against another day's volume.</p>
<p data-lede class="lede">{nativeState === 'loading' ? 'The failure record is still loading.' : mix.recorded === 0 ? 'No recorded row supplies a failure divisor.' : `${(100 * mix.failures / mix.recorded).toFixed(1)}% of recorded rows failed.`}</p>
<p>The query has no article identity; this counts rows, not distinct articles.</p>
{#if mix.failures === 0 && mix.recorded > 0}<p data-nothing-fired>No recorded row failed at any step in these recorded days.</p>{/if}
<Reserved record panelState={nativeState} height={knobs.chart_height} width={knobs.chart_width} name="failure-mix" label="Native failures by day and stage">
<DateSeries {geometry} empty={emptyState('quiet', 'No failure is recorded in these rows.')}
	name="failure-mix" label="One stack a recorded day, split by failed stage"
	{width} height={knobs.chart_height} readout={geometry === null ? null : { ...geometry.readout, columns: geometry.dates.map(shortDate) }} readoutMaxShare={chart.readout_max_share} />
</Reserved>
<Reserved record panelState={rulesState} height={knobs.chart_height} width={knobs.chart_width} name="failed-rule" label="Native failed-rule readings">
{#if failed.stages.length > 0}
	<FailureList {ranking} stages={{ options: failed.stages, chosen: failed.chosenStage! }}
		window={rulesWindow} selectedCode={null} max={knobs.failure_list_max}
		sourceMax={knobs.source_rows} readoutMaxShare={chart.readout_max_share} />
{:else}
	<p>No recorded row failed at any stage in this window.</p>
{/if}
</Reserved>
</div>
<style>.lede { font-size: var(--text-2xl); font-variant-numeric: tabular-nums; }</style>
