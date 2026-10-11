<script lang="ts">
	import { nativeFailureMix } from './failure-mix';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import type { PanelState } from '../waiting';
	import RankedList from '$lib/components/RankedList.svelte';
	import { rankedList } from '$lib/charts/d3/rankedList';
	import { emptyState } from '$lib/charts/d3/empty';
	import { frame, MARGIN } from '$lib/charts/frame';
	import type { Row } from '$lib/data/ledger';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	let { rows, ruleRows, knobs, chart, rule, calendar, nativeState, rulesState }: {
		rows: Row[]; ruleRows: Row[]; knobs: ConsoleConfig; chart: ChartConfig; rule: ModelRule;
		calendar?: readonly string[];
		nativeState: PanelState; rulesState: PanelState;
	} = $props();
	const mix = $derived(nativeFailureMix(rows, calendar));
	const failed = $derived(nativeFailureMix(ruleRows));
	let chosen = $state<string | null>(null);
	const stage = $derived(chosen !== null && failed.stages.includes(chosen) ? chosen : failed.chosenStage);
	const rules = $derived(failed.rules.find((entry) => entry.stage === stage));
	const ranked = $derived(rankedList((rules?.rules ?? []).map((entry) => ({
		label: entry.rule, value: entry.count, context: `${entry.count} of ${rules?.failures} failures at ${stage}`
	})), { max: knobs.failure_list_max }));
	const geometry = $derived(dateSeries(mix.series, {
		frame: frame(knobs.chart_width, knobs.chart_height, MARGIN), density: chart.tick_density,
		valueTicks: 5, padding: 0.2, rule, stacked: true
	}));
</script>
{#if nativeState === 'loading' && rulesState === 'loading'}
	<Reserved record panelState="loading" height={knobs.chart_height} width={knobs.chart_width} name="failure-mix" label="Native failures and rules">
		{#snippet children()}{/snippet}
	</Reserved>
{:else}
<p data-comparison="composition">Each failed stage against the other stages in the same day's stack, not a rate against another day's volume.</p>
<Reserved record panelState={nativeState} height={knobs.chart_height} width={knobs.chart_width} name="failure-mix" label="Native failures by day and stage">
<p data-lede class="lede">{mix.articles === 0 ? 'No recorded article supplies a failure divisor.' : `${(100 * mix.failures / mix.articles).toFixed(1)}% of recorded articles failed.`}</p>
{#if mix.failures === 0 && mix.articles > 0}<p data-nothing-fired>No article failed at any step in these recorded days.</p>{/if}
<DateSeries {geometry} empty={emptyState('quiet', 'No failure is recorded in these rows.')}
	name="failure-mix" label="One stack a recorded day, split by failed stage"
	width={knobs.chart_width} height={knobs.chart_height} readout={geometry?.readout} readoutMaxShare={chart.readout_max_share} />
</Reserved>
<Reserved record panelState={rulesState} height={knobs.chart_height} width={knobs.chart_width} name="failed-rule" label="Native failed-rule readings">
{#if failed.stages.length > 0}
	<label>Failed stage <select value={stage ?? ''} onchange={(event) => chosen = event.currentTarget.value} data-failure-stage>
		{#each failed.stages as option (option)}<option value={option}>{option}</option>{/each}
	</select></label>
	<RankedList geometry={ranked} caption="Rules that refused an item at the chosen stage" maxText={ranked === null ? 'not measured' : `${ranked.max} failures`}
		unmeasuredNote="No failed rule was measured." emptyNote="No failure at this stage names a failed rule." />
	<p data-failed-rule-unknown>{rules?.unknown ?? 0} failures at this stage have no recorded failed rule.</p>
{/if}
<p data-contract-blocked="failure-list">The declared rule query has no article or source identities. The rule counts above remain useful; the shared failure-detail list needs its identity contract settled before this panel is ready.</p>
</Reserved>
{/if}
<style>.lede { font-size: var(--text-2xl); font-variant-numeric: tabular-nums; }</style>
