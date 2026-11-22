<script lang="ts">
	/** Which stories the day merged, and where the merge line sits against pairs marked as separate stories. */
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { useWindowChoice } from '$lib/console/window-slot';
	import { windowFromDates, windowOfDays } from '$lib/charts/viewport';
	import { BAND_UNREAD } from '$lib/console/band';
	import { consoleKnobs, holdoutAxisRules, judgeObservationRules, routeConsole } from '$lib/console/route-console';
	import { judgementEvidence } from '$lib/console/judgement-evidence';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import JudgeObservations from './JudgeObservations.svelte';
	import MergedStoriesPanel from './MergedStoriesPanel.svelte';
	import HoldoutMargin from './HoldoutMargin.svelte';

	let { data } = $props();
	const console = consoleKnobs();
	const configured = routeConsole('judgement');
	const axis = holdoutAxisRules(configured.knobs);
	const rules = judgeObservationRules(configured.knobs);
	const [grouping, observations] = configured.panel_groups;
	/** Where the judge's own ledgers are read. The address comes from the fixed
	 * route table the rail is built from, never from a literal here. */
	const explorerRoute = BAND_UNREAD.routes.find((route) => route.id === 'data-explorer');

	const presets = console.window_presets;
	const choice = useWindowChoice();
	const windowDays = $derived(choice.days);
	/** False until a browser has run this page. The control cannot do anything
	 * before that, so it says so rather than pretending. */
	let ready = $state(false);

	onMount(() => {
		ready = true;
	});

	function show(days: number) {
		choice.select(days);
	}

	/** The built-in grouping evidence has no month-file cost. Judge reads use
	 * the ledger's existing bounded query door, not priced month shards. */
	function monthsFor(): number {
		return 0;
	}

	const publishedWindow = $derived(windowFromDates(data.merges.map((day) => day.date), windowDays));
	const viewport = $derived(publishedWindow ?? windowOfDays(data.windowDay, windowDays, 'right'));
	const markNotes = $derived(judgementEvidence(data.holdout.read, data.holdout.reach, data.holdout.reach));
	const markSpan = $derived.by(() => {
		const { read, reach } = data.holdout;
		if (read.state !== 'read') return null;
		const start = read.first > reach.start ? read.first : reach.start;
		const end = read.through < reach.end ? read.through : reach.end;
		return start <= end ? { start, end } : null;
	});
</script>

<svelte:head>
	<title>Judgement &mdash; Console &mdash; {data.ui.site_title}</title>
</svelte:head>

<JudgeObservations {viewport} {windowDays} group={observations} {rules} knobs={console} chart={data.chart}>
	{#snippet published()}
		<WindowControlSource route="judgement" days={windowDays} {presets} {monthsFor} {ready}
			{publishedWindow} onChange={show} />
		<PanelGroup id={grouping.id} title={grouping.title} panels={grouping.panels.length}>
			{#each grouping.panels as id (id)}
				{#if id === 'merged-stories'}
					<MergedStoriesPanel days={data.merges} {viewport}
						height={console.chart_height} width={console.chart_width}
						tickDensity={data.chart.tick_density} readoutMaxShare={data.chart.readout_max_share} />
				{:else if id === 'holdout-margin'}
					<HoldoutMargin coverage={markSpan} commonCoverage={publishedWindow}
						marks={data.holdout.read.state === 'read' ? data.holdout.marks : null}
						agreedScores={data.holdout.read.state === 'read' ? data.holdout.agreedScores : null}
						evidence={markNotes} skipped={data.holdout.skipped} marked={data.holdout.marked}
						line={data.holdout.line} axisBelow={axis.below} axisAbove={axis.above} weights={data.holdout.weights}
						height={console.chart_height} width={console.chart_width} readoutMaxShare={data.chart.readout_max_share} />
				{/if}
			{/each}
		</PanelGroup>
	{/snippet}
	{#snippet explorer()}
		{#if explorerRoute}
			Read the raw pair-verdicts and threshold-history records in
			<a href="{base}{explorerRoute.href}" data-judgement-elsewhere>{explorerRoute.label}</a>.
		{/if}
	{/snippet}
</JudgeObservations>

<style>
	[data-judgement-elsewhere] {
		color: var(--color-accent);
		text-decoration: underline;
	}
</style>
