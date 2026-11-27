<script lang="ts">
	/** Compare the judges' UTC activity without pooling their attempts. */
	import DateTileGrid from '$lib/charts/d3/DateTileGrid.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import { daysInWindow, type TimeWindow } from '$lib/charts/viewport';
	import { councilActivity, councilHistory, councilJudges } from '$lib/console/council-runs';
	import type { OperationReading } from '$lib/console/operations/operation-reads.svelte';
	import { evidenceOf, rowsOf, stateOf } from '$lib/console/voices/record';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import CouncilJudgeChart from './CouncilJudgeChart.svelte';

	let { viewport, knobs, chart, reading }: {
		viewport: TimeWindow; knobs: ConsoleConfig; chart: Pick<ChartConfig, 'tick_density' | 'readout_max_share'>;
		reading: OperationReading;
	} = $props();
	let picked = $state<string | null>(null);
	const history = $derived(councilHistory(rowsOf(reading.answer)));
	const judges = $derived(councilJudges(history.attempts, viewport));
	const calendar = $derived(daysInWindow(viewport));
	const lanes = $derived(councilActivity(history.attempts, __OPERATIONS_JUDGE_NAMES__, calendar));
	const chosen = $derived(picked !== null && calendar.includes(picked) ? picked : viewport.end);
	const notes = $derived(evidenceOf(reading.answer, reading.range));
	$effect(() => {
		if (history.ignored) console.warn(`[council] ${history.ignored} invalid step reports were not drawn.`);
	});
</script>

<Panel id="council-runs" title="LLM Council" note="Judge activity by UTC day" wide>
	<div data-readout-fetched data-panel-question="Which judges reported their parts and combined results?"
		data-model-rule-name="council-runs" data-model-rule="no"
		data-model-rule-none="These are reported workflow steps, not changes to model settings.">
		<Reserved panelState={stateOf(reading.answer)} height={knobs.chart_height} width={knobs.chart_width}
			name="council-activity" label="Council judge activity" record={reading.answer !== 'pending' && reading.answer.state === 'unreachable'}>
			{#if lanes.length}
				<DateTileGrid days={calendar} {lanes} name="council-activity" label="Council judge activity by UTC execution day"
					chosen={calendar.indexOf(chosen)} onPick={(at) => { picked = calendar[at] ?? null; }}
					width={knobs.chart_width} density={chart.tick_density} maxShare={chart.readout_max_share} />
				<p class="key">
					<span><i class="reported"></i> Step reported</span>
					<span><i class="checked"></i> No work assigned</span>
					<span><i class="unreported"></i> No report</span>
				</p>
				<p class="note">No report does not mean the judge did not run.</p>
			{:else}
				<p class="note">No judges are configured or present in the packed reports.</p>
			{/if}
			{#if judges.length}
				<details>
					<summary>Parts and combine by judge</summary>
					{#each judges as { judge, days } (judge)}
						<CouncilJudgeChart {judge} {days} {calendar} width={knobs.chart_width}
							density={chart.tick_density} maxShare={chart.readout_max_share} />
					{/each}
				</details>
			{/if}
			{#if history.ignored}<p class="note">Some step reports could not be read.</p>{/if}
			{#each notes as note (note)}<p class="note">{note}</p>{/each}
		</Reserved>
	</div>
</Panel>

<style>
	.note, .key, details { color: var(--color-text-secondary); font-size: var(--console-small-size); margin-block: var(--space-1); }
	.key { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-3); }
	.key span { display: inline-flex; gap: var(--space-1); align-items: center; }
	.key i { inline-size: var(--space-2); block-size: var(--space-2); }
	.reported { background: var(--operation-written); }
	.checked { border: 1px solid var(--chart-axis); }
	.key .unreported { background: var(--color-rule-strong); block-size: var(--console-chart-line-width); }
	summary { cursor: pointer; }
</style>
