<script lang="ts">
	/** Show observed execution days without treating missing steps as missed workflows. */
	import Panel from '$lib/components/Panel.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import { emptyState } from '$lib/charts/d3/empty';
	import { MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { daysInWindow, windowFromDates } from '$lib/charts/viewport';
	import { councilAttemptLink, councilDetails, councilHistory } from '$lib/console/council-runs';
	import { councilRunsQuery } from '$lib/console/queries/judgement';
	import { rangeFor, retryAsks, routeReach, sliceOnce, type Range } from '$lib/console/queries/window';
	import { evidenceOf, rowsOf, stateOf, type Answer } from '$lib/console/voices/record';
	import { readSession } from '$lib/data/read-session';
	import { clockUtc, longDate } from '$lib/format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';

	let { days, knobs, chart, repo }: { days: number; knobs: ConsoleConfig; chart: ChartConfig; repo: string } = $props();
	const name = 'council-runs';
	const title = 'LLM Council runs';
	const countLabel = 'Run attempts with recorded steps';
	const rule = { declined: 'This chart counts reported attempts, not changes to model settings.' };
	const frame = useChartFrame(() => chart);
	let measured = $state<number | null>(null);
	const emptyHistory = councilHistory([]);
	let reading = $state.raw<{ answer: Answer; range: Range | null; history: ReturnType<typeof councilHistory> }>({
		answer: 'pending', range: null, history: emptyHistory
	});
	let retryCount = $state(0);
	let chosenDay = $state<string | null>(null);
	let chosenAttempt = $state<string | null>(null);

	const history = $derived(reading.history);
	const dates = $derived([...history.days.keys()].sort());
	const viewport = $derived(windowFromDates(dates, Math.max(...knobs.window_presets)));
	const calendar = $derived(viewport === null ? [] : daysInWindow(viewport));
	const selection = $derived(chosenDay !== null && (history.days.has(chosenDay) || calendar.includes(chosenDay))
		? chosenDay : dates.at(-1) ?? null);
	const onDay = $derived(selection === null ? [] : history.days.get(selection) ?? []);
	const picked = $derived(onDay.find(({ attempt }) => attempt.key === chosenAttempt) ?? onDay[0]);
	const details = $derived(picked === undefined ? [] : councilDetails(picked.attempt));
	const link = $derived(picked === undefined ? null : councilAttemptLink(picked.attempt, repo));
	const notes = $derived(evidenceOf(reading.answer, reading.range));
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const panelState = $derived(reading.answer !== 'pending' && reading.answer.state === 'ok' && dates.length === 0
		? 'quiet' : stateOf(reading.answer));
	const geometry = $derived(dateSeries([{
		label: countLabel, token: '--chart-measure',
		points: calendar.map((date) => ({ date, value: history.days.get(date)?.length ?? null }))
	}], {
		frame: frame(width, knobs.chart_height, MARGIN), stacked: true, density: chart.tick_density,
		valueTicks: chart.tick_density, padding: 0.25, number_format: chart.number_format, rule,
		valueFormat: (value) => Number.isInteger(value) ? String(value) : ''
	}));
	const dateOptions = $derived([...new Set([...calendar, ...dates])].sort().reverse());
	const column = $derived(selection === null ? -1 : calendar.indexOf(selection));

	function pick(date: string) {
		chosenDay = date;
		chosenAttempt = null;
	}

	$effect(() => {
		const span = days;
		void retryCount;
		let active = true;
		const session = readSession();
		reading = { answer: 'pending', range: null, history: emptyHistory };
		async function load() {
			const reach = await routeReach([councilRunsQuery.ledger]);
			if (!active || session !== readSession()) return;
			const request = rangeFor(councilRunsQuery, span, reach, knobs.window_presets);
			const range = 'from' in request ? request : null;
			const answer = 'from' in request ? await sliceOnce(councilRunsQuery, request) : request;
			if (!active || session !== readSession()) return;
			const next = councilHistory(rowsOf(answer));
			if (next.ignored > 0) console.warn(`[council] ${next.ignored} invalid recorded steps were not drawn.`);
			reading = { answer, range, history: next };
		}
		void load().catch((error: unknown) => {
			if (!active || session !== readSession()) return;
			console.warn('[council] The published run record could not be read.', error);
			reading = { answer: { state: 'unreachable' }, range: null, history: emptyHistory };
		});
		return () => { active = false; };
	});
</script>

<Panel id={name} {title} heading="h3" wide>
	<div use:observeWidth={(next) => measured = next} data-readout-fetched
		data-panel-question="Which Council attempts and judges reported work?"
		data-model-rule-name={name} data-model-rule="no" data-model-rule-none={rule.declined}>
		<noscript><p>JavaScript is needed to read the published Council record.</p></noscript>
		{#if reading.range}
			<p class="note">Judged digests covered: {longDate(reading.range.from)} to {longDate(reading.range.to)} UTC.</p>
		{/if}
		{#each notes as note (note)}<p class="note">{note}</p>{/each}
		{#if history.ignored > 0}<p class="note">Some step reports could not be read. The record is partial.</p>{/if}
		<Reserved record {panelState} {width} height={knobs.chart_height} {name} label={countLabel}>
			{#if geometry !== null}
				<p class="lede" data-lede>Latest recorded step day: <strong>{longDate(dates.at(-1)!)} UTC</strong></p>
				<p class="note">A gap means no step was recorded in the checked digests, not that Council did not run.</p>
				{#if viewport && dates[0] < viewport.start}<p class="note">Earlier reported days are available in the day selector.</p>{/if}
				<DateSeries {geometry} {width} height={knobs.chart_height} {name} label={countLabel}
					empty={emptyState('quiet', 'No Council step was recorded.')} readoutMaxShare={chart.readout_max_share}
					picked={column === -1 ? null : column}
					onPick={(at) => { if (calendar[at]) pick(calendar[at]); }} />
				<div class="selectors">
					<label>Execution day (UTC)
						<select value={selection} onchange={(event) => pick(event.currentTarget.value)}>
							{#each dateOptions as date (date)}<option value={date}>{longDate(date)}</option>{/each}
						</select>
					</label>
					{#if onDay.length > 1}
						<label>Recorded attempt
							<select value={picked?.attempt.key} onchange={(event) => chosenAttempt = event.currentTarget.value}>
								{#each onDay as { attempt } (attempt.key)}
									<option value={attempt.key}>{attempt.runId}, attempt {attempt.attempt}</option>
								{/each}
							</select>
						</label>
					{/if}
				</div>
				{#if picked}
					<p class="note">
						{picked.attempt.runId}, attempt {picked.attempt.attempt}.
						First step that day: <time datetime={picked.first}>{clockUtc(picked.first)}</time>.
						{#if link}<a href={link}>Open recorded attempt</a>{/if}
					</p>
					<ul class="judges" aria-label="Judge and digest reports">
						{#each details as detail (detail.key)}
							<li>
								<strong>{detail.judge}</strong> <span class="note">Judged digest: {longDate(detail.date)} UTC.</span>
								<div>{detail.activity}{detail.incomplete ? ' - missing reports' : ''}.</div>
								<p class="note">Prepare: {detail.prepare}. {#if detail.expected === null}{detail.reported} parts reported; expected parts uncertain.{:else}Parts reported: {detail.reported} of {detail.expected}.{/if} Combine: {detail.combine}.</p>
								{#if detail.parts}<p class="note">{detail.parts}</p>{/if}
							</li>
						{/each}
					</ul>
				{:else}<p class="note">No Council step recorded for this execution day.</p>{/if}
			{/if}
		</Reserved>
		{#if panelState === 'unreachable'}
			<button class="control" type="button" onclick={() => { retryAsks([councilRunsQuery]); retryCount += 1; }}>Retry Council record</button>
		{/if}
	</div>
</Panel>

<style>
	.note { color: var(--color-text-secondary); font-size: var(--console-small-size); margin-block: var(--space-1); }
	.note a { color: var(--color-accent); text-decoration: underline; }
	.lede { margin-block: var(--space-1); }
	.selectors { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); margin-block: var(--space-3); }
	label { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); max-inline-size: 100%; }
	select, .control {
		max-inline-size: 100%; min-block-size: var(--console-control-min-height);
		padding-inline: var(--console-control-padding-inline); border: 1px solid var(--color-rule-strong);
		border-radius: var(--console-control-radius); background: var(--color-surface); color: var(--color-text); font: inherit;
	}
	.judges { margin: 0; padding: 0; list-style: none; overflow-wrap: anywhere; }
	.judges li { border-block-start: 1px solid var(--color-rule); padding-block: var(--space-2); }
</style>
