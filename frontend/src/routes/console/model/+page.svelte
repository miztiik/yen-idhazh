<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { consoleKnobs, routeConsole } from '$lib/console/route-console';
	import { routeReach, retryAsks, tallyAsks, type RouteReach } from '$lib/console/queries/window';
	import type { LedgerReach, SliceResult } from '$lib/data/ledger';
	import * as queries from '$lib/console/queries/model';
	import { settingsRules } from '$lib/console/settings-moved';
	import { windowOfDays } from '$lib/charts/viewport';
	import RecordNotes from '$lib/console/RecordNotes.svelte';
	import RouteStatus from '$lib/components/RouteStatus.svelte';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import Cards from '$lib/console/model/Cards.svelte';
	import Query from '$lib/console/model/Query.svelte';
	import Panels from '$lib/console/model/Panels.svelte';
	import Reasons from '$lib/console/model/Reasons.svelte';
	import { panelQueries, titles, modelRuleFor } from '$lib/console/model/panels';
	let { data } = $props();
	const knobs = consoleKnobs();
	const configured = routeConsole('model');
	const WINDOW_KEY = 'idhazh:console-window';
	let windowDays = $state(knobs.default_window_days);
	let reach = $state<RouteReach | null>(null);
	let ready = $state(false);
	let retry = $state(0);
	let answers = $state<Record<string, SliceResult | LedgerReach | 'pending'>>({});
	const ids = $derived(configured.panel_groups.flatMap((group) => group.panels));
	const doorIds = $derived(ids.filter((id) => id in panelQueries));
	const allAnswers = $derived(doorIds.map((id) => answers[id] ?? 'pending'));
	const tally = $derived(tallyAsks(allAnswers));
	const first = $derived(reach === null ? null : Object.values(reach.ledgers).flatMap((r) => r?.state === 'ok' ? [r.first] : []).sort()[0] ?? null);
	const span = $derived(windowOfDays(data.windowDay, windowDays, knobs.today_anchor));
	const shell = $derived(data);
	const cardRule = $derived(settingsRules(shell, { from: span.start, to: span.end }, 'none'));
	const checkerRule = $derived(settingsRules(shell, { from: span.start, to: span.end }, 'every'));
	const recording = $derived(data.recordingNotes[String(windowDays)]);
	const measurementOff = $derived(data.measurementOff[String(windowDays)]);
	onMount(() => {
		ready = true;
		const saved = Number(localStorage.getItem(WINDOW_KEY));
		if (knobs.window_presets.includes(saved)) windowDays = saved;
		void refresh();
	});
	async function refresh() {
		reach = await routeReach([queries.modelThroughputQuery.ledger, queries.faithfulnessQuery.ledger]);
	}
	function retryFailed() {
		const failed = doorIds.filter((id) => answers[id] !== 'pending' && answers[id]?.state === 'unreachable');
		retryAsks(failed.flatMap((id) => panelQueries[id]));
		for (const id of failed) answers[id] = 'pending';
		void refresh().then(() => { retry += 1; });
	}
	function show(days: number) {
		windowDays = days;
		localStorage.setItem(WINDOW_KEY, String(days));
	}
</script>

<svelte:head>
	<title>Summaries &mdash; Console &mdash; {data.ui.site_title}</title>
</svelte:head>

<WindowControlSource days={windowDays} presets={knobs.window_presets} {ready} busy={tally.state === 'loading'}
	record={{ asked: windowDays, first, through: reach?.through ?? null }} monthsFor={() => 0} onChange={show} />
<p class="console-carry" data-console-carry="machine">
	{data.carries.model}
	<a class="carry-link" href="{base}/console/machine/">Hardware &rarr;</a>
</p>
<RouteStatus route="model" answers={allAnswers} days={windowDays} through={reach?.through ?? null}
	shimmerAfterMs={knobs.shimmer_after_ms} onRetry={retryFailed}>
	<div data-recording-lines>
		{#if measurementOff != null}<p data-recording="off">{measurementOff}</p>{/if}
		{#if recording?.sampled != null}<p data-recording="sampled">{recording.sampled}</p>{/if}
		{#if recording?.startedMidWindow != null}<p data-recording="started">{recording.startedMidWindow}</p>{/if}
		{#if recording?.coveredElsewhere != null}<p data-recording="covered-elsewhere">{recording.coveredElsewhere}</p>{/if}
	</div>
	<RecordNotes notes={data.recordNotes[String(windowDays)] ?? []} />
	<p>A dashed line marks a day a recorded setting changed: the model, its settings, the prompt, the chat template, the runtime or the weights file. A dotted line marks a day the checker changed.</p>
	{#each configured.panel_groups as group (group.id)}
		<div data-console-panel-group={group.id}>
			{#each group.panels as id (id)}
				<Panel {id} title={titles[id]} verdict={id === 'model-cards'}
					note={id === 'model-cards' ? "What the model wrote for the day's own articles, how long it took, and what it got wrong." : null}>
					<div data-panel-question={titles[id]}>
					{#if id === 'model-cards'}
						<Cards days={data.cardDays} instruments={data.instruments} start={span.start} end={span.end}
							rule={cardRule} {checkerRule} chart={data.chart} {windowDays} />
					{:else if id === 'doubt-reasons'}
						<Reasons days={data.reasons} start={span.start} end={span.end} rule={checkerRule} chart={data.chart} {windowDays} />
					{:else if id in panelQueries}
						{#if id === 'faithfulness'}<a href={data.faithfulnessReference}>How each of these measures is scored</a>{/if}
						<Query queries={panelQueries[id]} {reach} preset={windowDays} presets={knobs.window_presets}
							{retry} height={knobs.chart_height} width={knobs.chart_width} name={id}
							onAnswer={(name, answer) => { answers[name] = answer; }}>
							{#snippet children(rows, range)}
								<Panels {id} {rows} {range} rule={modelRuleFor(id, shell, range)} chart={data.chart} {knobs}
									bands={data.summarizeBands} thresholds={data.matchThresholds} throughputReference={data.throughputReference} />
								<p data-door-through>The published record used here reaches {range.to}.</p>
							{/snippet}
						</Query>
					{/if}
					</div>
				</Panel>
			{/each}
		</div>
	{/each}
</RouteStatus>

<style>
	:global([data-console-panels='model'] [data-lede]) { font-size: var(--text-xl); line-height: var(--leading-xl); font-weight: 600; }
	:global([data-console-panels='model'] .kpi-value.lede) { font-size: var(--text-3xl); }
	:global([data-console-panels='model'] table) { font-size: var(--text-xs); border-collapse: collapse; }
	:global([data-console-panels='model'] td), :global([data-console-panels='model'] th) { padding: var(--space-2); }
</style>
