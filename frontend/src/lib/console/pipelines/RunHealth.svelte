<script lang="ts">
	/** Do the day's articles and runs agree about what published? */
	import Panel from '$lib/components/Panel.svelte';
	import RunHealthPanel from '../../../routes/console/RunHealthPanel.svelte';
	import type { RunYieldSource } from '$lib/charts/run-yield';
	import type { TimeWindow } from '$lib/charts/viewport';
	import type { DayColumn } from '$lib/console/run-square';
	import { countDays } from '$lib/console/span-words';

	let { yieldDays, grid, window, days, floorPct, height, width, tickDensity, readoutMaxShare }: {
		yieldDays: RunYieldSource[];
		grid: DayColumn[];
		window: TimeWindow;
		days: number;
		floorPct: number;
		height: number;
		width: number;
		tickDensity: number;
		readoutMaxShare: number;
	} = $props();
	let selected = $state<number | null>(null);
</script>

<section data-windowed="run-health" data-window-days={days} aria-label="Run health, over {countDays(days)}">
	<Panel id="run-health" verdict title="Run health">
		<p data-lede style="font-size: var(--text-2xl)">The published day beside the runs that tried it.</p>
		<p data-comparison="planned">Planned against published articles, and each run's own recorded outcome.</p>
		{#if yieldDays.length === 0 && grid.length === 0}
			<p data-empty="missing">The private run and published-day records are unavailable in this window.</p>
		{:else}
			<RunHealthPanel {yieldDays} {grid} {window} {floorPct} {height} {width} {tickDensity} {readoutMaxShare} bind:selected />
		{/if}
	</Panel>
</section>
