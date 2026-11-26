<script lang="ts">
	/** Give Council and Gardener the same UTC dates without joining their evidence. */
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import { windowOfDays } from '$lib/charts/viewport';
	import { consoleKnobs, routeConsole } from '$lib/console/route-console';
	import { utcSpan } from '$lib/console/window-coverage';
	import { useConsoleUtcDay, useWindowChoice } from '$lib/console/window-slot';
	import GardenerActivity from '$lib/console/operations/GardenerActivity.svelte';
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
	const limits = { maxFiles: __EXPLORER_CONFIG__.max_files, maxBytes: __EXPLORER_CONFIG__.max_fetch_bytes };
</script>

<svelte:head>
	<title>Operations &mdash; Console &mdash; {data.ui.site_title}</title>
</svelte:head>

<WindowControlSource route="operations" {days} presets={knobs.window_presets} monthsFor={() => 0}
	ready={viewport !== null} statusLine={viewport === null ? null : `Window: ${utcSpan(viewport)}.`}
	onChange={choice.select} />
{#if viewport}
	{#each panel_groups as group (group.id)}
		<PanelGroup id={group.id} title={group.title} panels={group.panels.length}>
			{#each group.panels as id (id)}
				{#if id === 'council-runs'}
					<CouncilRunsPanel {viewport} {knobs} {chart} repoUrl={data.ui.repo_url} />
				{:else if id === 'gardener-activity'}
					<GardenerActivity {viewport} {days} {knobs} {chart} {limits} />
				{/if}
			{/each}
		</PanelGroup>
	{/each}
{/if}
