<script lang="ts">
	/** Compare recorded token volume per run without combining same-day runs. */
	import Panel from '$lib/components/Panel.svelte';
	import ChoiceTiles from '$lib/components/ChoiceTiles.svelte';
	import RunSeries from '$lib/charts/d3/RunSeries.svelte';
	import { runSeries } from '$lib/charts/d3/runSeries';
	import { emptyState } from '$lib/charts/d3/empty';
	import { chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { readAgainstWritten } from '$lib/charts/machine';
	import { formatNumber, MAX_SIGNIFICANT_DIGITS } from '$lib/number-format';
	import { settingsRules } from '$lib/console/settings-moved';
	import { nameSpan } from '$lib/console/span-words';
	import { textRows } from '$lib/console/machine/records';
	import { tokenAssessmentKey, tokenDeviationReading } from '$lib/console/machine/token-deviations';
	import type { TokenHistory } from '$lib/console/queries/token-deviations';
	import type { Range } from '$lib/console/queries/window';
	import type { TokenDeviationRules } from '$lib/data/token-deviation-query';
	import type { ReadWriteMetric } from '$lib/console/route-console';
	import type { ConsoleShell } from '$lib/console/band';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';

	let { rows, chart, shell, start, end, windowDays, initialMetric, history, historyRange, deviationRules }: {
		rows: readonly Row[];
		chart: ChartConfig;
		shell: ConsoleShell;
		start: string;
		end: string;
		windowDays: number;
		initialMetric: ReadWriteMetric;
		history: TokenHistory | null;
		historyRange: Range | null;
		deviationRules: TokenDeviationRules;
	} = $props();
	const metrics = [
		{ value: 'total', shown: 'Run total', spoken: 'Run total' },
		{ value: 'median', shown: 'Median per article', spoken: 'Median per article' }
	] as const;
	// svelte-ignore state_referenced_locally
	let metric = $state<ReadWriteMetric>(initialMetric);
	let width = $state<number | null>(null);
	const frame = useChartFrame(() => chart);
	const box = $derived(frame(chartWidth(width, chart.width_px), chart.height_px));
	const answer = $derived(readAgainstWritten(textRows(rows)));
	const runs = $derived(answer.tokenRuns);
	const measured = $derived(runs.filter((run) => run.measured > 0).length);
	const rule = $derived(settingsRules(shell, { from: start, to: end }, 'none'));
	const exact = $derived({ ...chart.number_format, significant_digits: MAX_SIGNIFICANT_DIGITS });
	const precise = (value: number) => formatNumber(value, exact, { si: false });
	const tokens = (value: number) => `${precise(value)} tokens`;
	const count = (value: number) => formatNumber(value, chart.number_format, { exact: true });
	const historyReadings = $derived(new Map((history?.readings ?? []).map((row) =>
		[tokenAssessmentKey(row.date, row.runId, row.metric, row.trace), row])));
	const assessments = $derived(runs.map((run) => ({
		read: tokenDeviationReading(run, metric, 'read', history, historyReadings, deviationRules, tokens, precise),
		written: tokenDeviationReading(run, metric, 'written', history, historyReadings, deviationRules, tokens, precise)
	})));
	const geometry = $derived(runSeries(
		runs.map((run, index) => ({ runId: run.runId, date: run.date, events: [{
			label: 'Measured articles',
			value: `${count(run.measured)} of ${count(run.recorded)} recorded${run.measured < run.recorded ? '; partial coverage' : ''}`,
			swatch: null
		}, assessments[index].read.line, assessments[index].written.line] })),
		[
			{ label: 'Read', token: '--chart-1', dashed: false, values: runs.map((run) => run[metric].read),
				warnings: assessments.map((run) => run.read.warning), format: tokens },
			{ label: 'Written', token: '--chart-2', dashed: true, values: runs.map((run) => run[metric].written),
				warnings: assessments.map((run) => run.written.warning), format: tokens }
		],
		{ frame: box, density: chart.tick_density, valueTicks: chart.tick_density, rule,
			number_format: chart.number_format, notMeasured: 'No paired token reading.' }
	));
</script>

<div data-windowed="machine-tokens" data-window-days={windowDays} data-token-metric={metric}>
	<Panel id="read-against-written" title="What a run reads against what it writes" heading="h3"
		note="Recorded token volume per run, over {nameSpan(windowDays)}.">
		{#snippet actions()}
			<fieldset class="metric">
				<legend class="sr-only">Token measure</legend>
				<ChoiceTiles name="run-token-measure" items={metrics} selected={metric}
					tileAttribute="data-token-measure" onChange={(value) => (metric = value)} />
			</fieldset>
		{/snippet}
		<div data-panel-question="is it working">
			<p class="lede" data-lede>{count(measured)} of {count(runs.length)} recorded runs have paired token readings.</p>
			<p data-comparison="Read against Written, per run">Read includes cached prompts and every recorded model call; only paired readings count.</p>
			<p data-token-unit>{metric === 'total' ? 'Tokens per run' : 'Median tokens per article'}.
				Run sequence, not elapsed time; dates are UTC.</p>
			<p data-token-deviation-rule>Warning diamonds call for investigation, not proof of failure:
				more than {precise(deviationRules.multiplier)} sample standard deviations from up to
				{count(deviationRules.historyRuns)} earlier matching runs, with at least {count(deviationRules.minimumRuns)} required.
				{#if historyRange}Fixed history: {historyRange.from} through {historyRange.to} UTC.{/if}
				Change days are unassessed because settings changes are dated only by UTC day.</p>
			<div class="plot" use:observeWidth={(px) => (width = px)}>
				{#key runs}
					<RunSeries {geometry} empty={emptyState('quiet', 'No run recorded paired token counts.')}
						name="read-against-written"
						label="{metric === 'total' ? 'Total' : 'Median per article'} Read and Written token volume, in run sequence, not elapsed time"
						width={box.width} height={box.height} readoutMaxShare={chart.readout_max_share} />
				{/key}
			</div>
		</div>
	</Panel>
</div>

<style>
	.metric { margin: 0; padding: 0; border: 0; min-inline-size: 0; }
	.plot { margin-block-start: var(--space-2); }
	.lede { font-size: var(--console-page-title-size); line-height: var(--console-page-title-leading); font-weight: var(--console-page-title-weight); }
</style>
