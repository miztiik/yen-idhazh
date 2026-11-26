<script lang="ts">
	/** Compare judging completion without pooling dates, retries or judges. */
	import Panel from '$lib/components/Panel.svelte';
	import { daysInWindow, type TimeWindow } from '$lib/charts/viewport';
	import { councilHistory, councilJudges } from '$lib/console/council-runs';
	import { councilRunsQuery } from '$lib/console/queries/operations';
	import { rangeFor, retryAsks, routeReach, sliceOnce, type Range } from '$lib/console/queries/window';
	import { evidenceOf, rowsOf, type Answer } from '$lib/console/voices/record';
	import { readSession } from '$lib/data/read-session';
	import { longDate } from '$lib/format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import CouncilJudgeChart from './CouncilJudgeChart.svelte';

	let { viewport, knobs, chart, repoUrl }: {
		viewport: TimeWindow; knobs: ConsoleConfig; chart: Pick<ChartConfig, 'tick_density' | 'readout_max_share'>; repoUrl: string;
	} = $props();
	const empty = councilHistory([]);
	let reading = $state.raw<{ answer: Answer; range: Range | null; history: typeof empty }>({
		answer: 'pending', range: null, history: empty
	});
	let retry = $state(0);
	const history = $derived(reading.history);
	const judges = $derived(councilJudges(history.attempts, viewport));
	const calendar = $derived(daysInWindow(viewport));
	const notes = $derived(evidenceOf(reading.answer, reading.range));

	$effect(() => {
		const presets = knobs.window_presets;
		void retry;
		let active = true;
		const session = readSession();
		reading = { answer: 'pending', range: null, history: empty };
		async function load() {
			const reach = await routeReach([councilRunsQuery.ledger]);
			if (!active || session !== readSession()) return;
			const request = rangeFor(councilRunsQuery, Math.max(...presets), reach, presets);
			const range = 'from' in request ? request : null;
			const answer = 'from' in request ? await sliceOnce(councilRunsQuery, request) : request;
			if (!active || session !== readSession()) return;
			const next = councilHistory(rowsOf(answer));
			if (next.ignored) console.warn(`[council] ${next.ignored} invalid step reports were not drawn.`);
			reading = { answer, range, history: next };
		}
		void load().catch((error: unknown) => {
			if (!active || session !== readSession()) return;
			console.warn('[council] The published work record could not be read.', error);
			reading = { answer: { state: 'unreachable' }, range: null, history: empty };
		});
		return () => { active = false; };
	});
</script>

<Panel id="council-runs" title="LLM Council" note="Judging parts and result combination" wide>
	<div data-readout-fetched data-panel-question="Which judges reported their parts and combined results?"
		data-model-rule-name="council-runs" data-model-rule="no"
		data-model-rule-none="These are reported workflow steps, not changes to model settings.">
		{#if reading.answer === 'pending'}
			<p class="note pending" role="status">Checking packed Council reports.</p>
		{:else if reading.answer.state === 'unreachable'}
			<p class="note">Council reports could not be read.</p>
			<button type="button" onclick={() => { retryAsks([councilRunsQuery]); retry += 1; }}>Retry Council reports</button>
		{:else if judges.length === 0}
			<p class="note">No Council work was recorded in this execution window. That does not establish that no judge ran.</p>
		{:else}
			{#each judges as { judge, days } (judge)}
				<CouncilJudgeChart {judge} {days} {calendar} repoUrl={repoUrl} width={knobs.chart_width}
					density={chart.tick_density} maxShare={chart.readout_max_share} />
			{/each}
		{/if}
		{#if reading.range}
			<p class="note">Judged digest dates checked: {longDate(reading.range.from)} to {longDate(reading.range.to)} UTC.</p>
		{/if}
		{#if history.ignored}<p class="note">Some step reports could not be read.</p>{/if}
		{#each notes as note (note)}<p class="note">{note}</p>{/each}
	</div>
</Panel>

<style>
	.note { color: var(--color-text-secondary); font-size: var(--console-small-size); margin-block: var(--space-1); }
	.pending { min-block-size: var(--space-8); }
	button { cursor: pointer; }
</style>
