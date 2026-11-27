<script lang="ts">
	/** Give Council and Gardener the same UTC dates without joining their evidence. */
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import RouteStatus from '$lib/components/RouteStatus.svelte';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import { windowOfDays } from '$lib/charts/viewport';
	import { consoleKnobs, routeConsole } from '$lib/console/route-console';
	import { utcSpan } from '$lib/console/window-coverage';
	import { useConsoleUtcDay, useWindowChoice } from '$lib/console/window-slot';
	import GardenerActivity from '$lib/console/operations/GardenerActivity.svelte';
	import { useOperationReads } from '$lib/console/operations/operation-reads.svelte';
	import CouncilRunsPanel from './CouncilRunsPanel.svelte';

	let { data } = $props();
	const knobs = consoleKnobs();
	const { panel_groups } = routeConsole('operations');
	const choice = useWindowChoice();
	const utcDay = useConsoleUtcDay();
	const days = $derived(choice.days);
	const viewport = $derived.by(() => {
		const today = utcDay();
		return today === null ? null : windowOfDays(today, days, knobs.today_anchor);
	});
	const chart = __OPERATIONS_CHART__;
	const reads = useOperationReads({
		days: Math.max(...knobs.window_presets), presets: knobs.window_presets,
		maxFiles: __EXPLORER_CONFIG__.max_files, maxBytes: __EXPLORER_CONFIG__.max_fetch_bytes
	});
	const sourceNotes = $derived.by(() => {
		const notes = [];
		const council = reads.council.range;
		const gardener = reads.gardener.range;
		if (council) notes.push(`Council digest files: ${utcSpan({ start: council.from, end: council.to })}. An older digest can be judged later.`);
		if (gardener) notes.push(`Gardener task files: ${utcSpan({ start: gardener.from, end: gardener.to })}.`);
		if (notes.length) notes.push('The widest preset sets the read limit. A monthly pack can start before its first report. Charts show only the selected UTC dates.');
		return notes;
	});
</script>

<svelte:head>
	<title>Operations &mdash; Console &mdash; {data.ui.site_title}</title>
</svelte:head>

<WindowControlSource route="operations" {days} presets={knobs.window_presets} monthsFor={() => 0}
	busy={reads.busy} {sourceNotes}
	ready={viewport !== null} statusLine={viewport === null ? null : `Window: ${utcSpan(viewport)}.`}
	onChange={choice.select} />
{#if viewport}
	<RouteStatus route="operations" answers={reads.answers} {days} shimmerAfterMs={knobs.shimmer_after_ms} onRetry={reads.retry}>
		{#each panel_groups as group (group.id)}
			<PanelGroup id={group.id} title={group.title} panels={group.panels.length}>
				{#each group.panels as id (id)}
					{#if id === 'council-runs'}
						<CouncilRunsPanel {viewport} {knobs} {chart} reading={reads.council} />
					{:else if id === 'gardener-activity'}
						<GardenerActivity {viewport} {days} {knobs} {chart} tracks={reads.tracks} reading={reads.gardener} />
					{/if}
				{/each}
			</PanelGroup>
		{/each}
	</RouteStatus>
{/if}
