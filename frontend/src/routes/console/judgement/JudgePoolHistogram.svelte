<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import Distribution from '$lib/charts/d3/Distribution.svelte';
	import { binnedDistribution } from '$lib/charts/d3/distribution';
	import { emptyState } from '$lib/charts/d3/empty';
	import { chartWidth, labelWidth, MARGIN, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import type { TimeWindow } from '$lib/charts/viewport';
	import { exactJudgeDay, judgeDayAbsence, judgeStatus, DRIFT_STATUS, type JudgeIdentity } from '$lib/console/judge-observations';
	import { judgePool, savedPoolBaseline, type JudgePool } from '$lib/console/judge-score-pool';
	import { inTrialRange, judgeTrialRange, revealJudgeTrial, useJudgeTrialAnswer } from '$lib/console/judge-trial-read.svelte';
	import { judgePoolTrialQuery } from '$lib/console/queries/judgement';
	import { sliceOnce } from '$lib/console/queries/window';
	import { rowsOf } from '$lib/console/voices/record';
	import type { LedgerReach, Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';

	let { viewport, reach, selected, identity, detail, knobs, chart }: {
		viewport: TimeWindow; reach: LedgerReach; selected: string; identity: JudgeIdentity | null;
		detail: Row | null; knobs: ConsoleConfig; chart: ChartConfig;
	} = $props();
	let near = $state(false);
	let measured = $state<number | null>(null);
	let reference = $state.raw<{ pool: JudgePool; compared: JudgePool | null } | null>(null);
	const name = 'judge-full-pool';
	const frame = useChartFrame(() => chart);
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const scope = $derived(near ? judgeTrialRange(viewport, knobs.default_window_days, reach) : null);
	const inWindow = $derived(inTrialRange(scope, selected));
	const history = useJudgeTrialAnswer(judgePoolTrialQuery, () => scope, (range) => sliceOnce(judgePoolTrialQuery, range));
	const day = useJudgeTrialAnswer(judgePoolTrialQuery, () => near && !inWindow && identity
		? judgeTrialRange({ start: selected, end: selected }, knobs.default_window_days, reach) : null,
		(range) => sliceOnce(judgePoolTrialQuery, range));
	const answer = $derived(inWindow || identity === null ? history.answer : day.answer);
	const row = $derived(identity ? exactJudgeDay(rowsOf(answer), identity) : null);
	const pool = $derived(judgePool(row?.score_pool_histogram));
	const baseline = $derived(reference?.pool === pool ? reference?.compared ?? null : null);
	const showReference = $derived(detail?.score_drift_status === 'measured');
	const number = $derived(numberFormatter(chart.number_format));
	const box = $derived.by(() => {
		const probe = frame(width, knobs.chart_height);
		return frame(width, knobs.chart_height, { ...MARGIN, left: labelWidth('100%', probe.labels) + probe.labels.fontSize });
	});
	const plot = $derived(pool === null ? null : binnedDistribution(pool.edges, pool.counts, baseline?.counts ?? null,
		{ frame: box, minValues: 1, valueTicks: chart.tick_density, number_format: chart.number_format }));
	const note = $derived(pool?.total === 0 ? 'Not measured: the eligible score pool was empty.'
		: row?.score_pool_histogram != null && pool === null ? 'Did not arrive as a recognized score histogram.'
			: judgeDayAbsence(selected, answer, reach));
	$effect(() => {
		const current = pool, evidence = detail?.score_drift_baseline;
		const rows = rowsOf(history.answer);
		if (!showReference || current === null || !rows.length) return;
		let active = true;
		void savedPoolBaseline(current, evidence, rows).then((compared) => {
			if (active) reference = { pool: current, compared };
		}, (error: unknown) => {
			if (!active) return;
			console.warn('[judgement] The saved score baseline could not be checked.', error);
			reference = { pool: current, compared: null };
		});
		return () => { active = false; };
	});
</script>

<Panel title="All eligible pairs score pool" heading="h3" wide>
	<div use:revealJudgeTrial={() => near = true} use:observeWidth={(next) => measured = next}
		data-judge-digest={selected} data-panel-question="Where did scores fall before sampling?"
		data-model-rule="no" data-model-rule-name={name} data-model-rule-none="The eligible pairs score pool uses the saved scorer and pair rule.">
		<p data-lede>{longDate(selected)} UTC. Shares of all eligible cross-outlet pairs for this digest before sampling (same-day pairs plus target-to-prior-day pairs inside the configured cross-day window, deduplicated by canonical URL pair).</p>
		{#if pool && pool.total > 0}
			<p data-comparison="Current eligible pairs score pool against its saved comparable baseline when available.">
				{number(pool.total, { exact: true })} eligible pairs across {number(pool.counts.length, { exact: true })} saved score bins.
				{#if baseline}
					Filled: this digest. Outline: {number(baseline.total, { exact: true })} reference pairs pooled before taking shares.
				{/if}
			</p>
		{/if}
		{#if near && answer !== 'pending'}
			<Distribution geometry={plot} empty={emptyState('quiet', note)} {name} label="Score histogram of all eligible cross-outlet pairs"
				{width} height={knobs.chart_height} binLabel="Eligible pairs" readoutMaxShare={chart.readout_max_share} />
		{:else}
			<p>{note}</p>
		{/if}
		{#if showReference && pool}
			{#if !rowsOf(history.answer).length || (reference?.pool === pool && !baseline)}
				<p>The saved PSI reading is available below. Its reference histogram could not be verified in this window.</p>
			{/if}
		{:else if detail}
			<p>PSI: {judgeStatus(detail.score_drift_status, DRIFT_STATUS)}</p>
		{/if}
		{#if answer !== 'pending' && answer.state === 'unreachable'}
			<button type="button" onclick={inWindow ? history.retry : day.retry}>Retry eligible pairs score pool</button>
		{/if}
	</div>
</Panel>

<style>
	p { margin: 0 0 var(--space-2); }
</style>
