<script lang="ts">
	/** Which stories the day merged, and how close the merge line sits to the pairs a person marked apart. */
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { useWindowChoice } from '$lib/console/window-slot';
	import { windowFromDates, windowOfDays } from '$lib/charts/viewport';
	import { BAND_UNREAD } from '$lib/console/band';
	import { consoleKnobs, holdoutAxisRules, routeConsole } from '$lib/console/route-console';
	import { judgementEvidence } from '$lib/console/judgement-evidence';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import MergedStoriesPanel from './MergedStoriesPanel.svelte';
	import HoldoutMargin from './HoldoutMargin.svelte';

	let { data } = $props();
	const console = consoleKnobs();
	const configured = routeConsole('judgement');
	const axis = holdoutAxisRules(configured.knobs);
	/** Where the judge's own ledgers are read. The address comes from the fixed
	 * route table the rail is built from, never from a literal here. */
	const explorer = BAND_UNREAD.routes.find((route) => route.id === 'data-explorer');

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

	/** Nothing on this route is fetched. Every span it can draw is already
	 * inlined, so no preset costs a month file and none of them is priced. */
	function monthsFor(): number {
		return 0;
	}

	const publishedWindow = $derived(windowFromDates(data.merges.map((day) => day.date), windowDays));
	const viewport = $derived(publishedWindow ?? windowOfDays(data.windowDay, windowDays, 'right'));
	const markNotes = $derived(judgementEvidence(data.holdout.read, data.holdout.reach, data.holdout.reach));
</script>

<svelte:head>
	<title>Judgement &mdash; Console &mdash; {data.ui.site_title}</title>
</svelte:head>

<div data-console-panels="judgement">
	<!-- The route owns its evidence window and hands the control to the shared shell. -->
	<WindowControlSource route="judgement" days={windowDays} {presets} {monthsFor} {ready}
		{publishedWindow} onChange={show} />

	{#if explorer}
		<p class="elsewhere" data-judgement-elsewhere>
			The judge's records are not drawn here: read them in the
			<a href="{base}{explorer.href}">{explorer.label}</a>, in the pair-verdicts and
			threshold-history ledgers. They do not change what the site merges.
		</p>
	{/if}

	{#each configured.panel_groups as group (group.id)}
		<PanelGroup id={group.id} title={group.title} panels={group.panels.length}>
			{#each group.panels as id (id)}
	{#if id === 'merged-stories'}
	<MergedStoriesPanel
		days={data.merges}
		{viewport}
		height={console.chart_height}
		width={console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
	/>

	{:else if id === 'holdout-margin'}
	<HoldoutMargin
		marks={data.holdout.read.state === 'read' ? data.holdout.marks : null}
		agreedScores={data.holdout.read.state === 'read' ? data.holdout.agreedScores : null}
		evidence={markNotes}
		skipped={data.holdout.skipped}
		marked={data.holdout.marked}
		line={data.holdout.line}
		axisBelow={axis.below}
		axisAbove={axis.above}
		weights={data.holdout.weights}
		height={console.chart_height}
		width={console.chart_width}
		readoutMaxShare={data.chart.readout_max_share}
	/>
	{/if}
			{/each}
		</PanelGroup>
	{/each}

</div>

<style>
	.elsewhere {
		margin: 0 0 var(--space-3);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
	.elsewhere a {
		color: var(--color-accent);
		text-decoration: underline;
	}
</style>
