<script lang="ts">
	/** Whether a bigger prompt cache would save wall clock.
	 *
	 * Prompt tokens the server read, against the ones it reused instead of
	 * reading. The server drew this one stacked, so the first paint matches the
	 * prerendered document; picking `Lines` redraws the identical values with no
	 * transform between them.
	 */
	import Chart from '$lib/charts/Chart.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import ShapeSwitch from '$lib/components/ShapeSwitch.svelte';
	import { cacheChart, cacheColumns, type CacheDay } from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';
	import type { StackShape } from '$lib/charts/stacked';
	import type { ChartConfig } from '$lib/server/config';

	let {
		cacheDays,
		days,
		windowDays,
		svg,
		chart
	}: {
		cacheDays: CacheDay[];
		days: number;
		windowDays: number;
		svg: string | null;
		chart: ChartConfig;
	} = $props();

	let cacheShape = $state<StackShape>('bars');
	const cacheOption = $derived(cacheChart(cacheDays, cacheShape).option);
	const cacheStrip = $derived(cacheColumns(cacheDays));
</script>

<div
	data-windowed="machine-cache"
	data-window-days={windowDays}
	data-model-rule="no"
	data-model-rule-name="machine-cache"
	data-model-rule-none="a change moves this, and an engine-drawn axis carries no rule yet"
>
	<Panel
		heading="h3"
		title="Prompt cache"
		note="Prompt tokens the server read, against the ones it reused instead of reading, over the last {windowDays} days. Read whether a bigger cache would save wall clock."
	>
		{#if cacheDays.length === 0}
			<p class="empty" data-machine-panel-empty="cache">
				No run in these {days} days reported both a read count and a cached count, so there is
				no split to draw.
			</p>
		{:else}
			<Chart
				svg={svg ?? ''}
				option={cacheOption}
				width={chart.width_px}
				height={chart.height_px}
				label="Prompt tokens per day over {days} days, split into the tokens the model server read and the tokens it served from its own cache. One column is one day."
				columns={cacheStrip}
				readoutName="cache"
				readoutMaxShare={chart.readout_max_share}
				restingNote=", the newest day"
				hint="Point at a day to read both halves. Left and Right step through the days, Escape returns to the newest."
			/>
			<!-- Stacked says how many prompt tokens the day needed; lines say whether
			     the read half fell while the cached half rose. One array, two shapes,
			     nothing re-shaped between them. -->
			<ShapeSwitch bind:shape={cacheShape} name="cache" label="How to draw the prompt cache" />
			<!-- No threshold marker and no tint. Nobody has agreed a floor for this,
			     and a tint would invent one and publish it. -->
			<ul class="shares" data-cache-days>
				{#each cacheDays as day (day.date)}
					<li data-cache-day={day.date} data-cache-pct={day.cachedPct ?? ''}>
						<strong>{day.date}</strong>: the cache covered {day.cachedPct}% of the
						{grouped(day.read + day.cached)} prompt tokens
						{day.runs === 1 ? 'that run' : `those ${day.runs} runs`} needed.
					</li>
				{/each}
			</ul>
		{/if}
	</Panel>
</div>

<style>
	.empty {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.shares {
		margin: var(--space-3) 0 0;
		padding-inline-start: var(--space-5);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
