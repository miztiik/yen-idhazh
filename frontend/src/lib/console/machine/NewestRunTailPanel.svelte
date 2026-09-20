<script lang="ts">
	/** The whole distribution of one run at once.
	 *
	 * A different question from whether the tail is growing, which is why it
	 * reads the newest run the item ledger timed and holds still while the window
	 * moves.
	 */
	import Chart from '$lib/charts/Chart.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import {
		curveOf,
		percentileChart,
		percentileColumns,
		seconds,
		type LatencyRun
	} from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';
	import type { ChartConfig } from '$lib/server/config';

	let {
		newestTail,
		svg,
		floor,
		shardRows,
		itemRows,
		chart
	}: {
		newestTail: LatencyRun | null;
		svg: string | null;
		floor: number;
		shardRows: number;
		itemRows: number;
		chart: ChartConfig;
	} = $props();

	const newestCurve = $derived(newestTail === null ? [] : [curveOf(newestTail)]);
	const percentileOption = $derived(percentileChart(newestCurve).option);
	const percentileStrip = $derived(percentileColumns(newestCurve));
	/** The insets `percentileChart` draws its grid at. The strip's column centres
	 * are computed from them, so a pointer and the strip agree. */
	const PERCENTILE_GRID = { left: 60, right: 44 };
</script>

<Panel
	heading="h3"
	id="newest-run-tail"
	title="How far the slowest articles ran behind the rest"
	note="A spread this wide means the average is not a time any article actually took - the whole distribution of the newest run."
>
	{#if svg === null || newestTail === null}
		<p class="empty" data-machine-panel-empty="percentiles">
			No run the item ledger holds timed {floor} items, which is the floor below
			which a p99 is just the last item.
		</p>
	{:else}
		<div
			data-window-exempt="newest-run-tail"
			data-model-rule="no"
			data-model-rule-name="machine-tail"
			data-model-rule-none="one run's own distribution, so no day edge falls inside it"
		>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				{newestTail.runId}, on {newestTail.date}. This panel does not follow the window.
			</p>
			<Chart
				{svg}
				option={percentileOption}
				width={chart.width_px}
				height={chart.height_px}
				label="Per-item model time at the 50th, 75th, 90th, 95th and 99th percentile for run {newestTail.runId}."
				columns={percentileStrip}
				readoutName="percentiles"
				readoutMaxShare={chart.readout_max_share}
				grid={PERCENTILE_GRID}
				restingNote=", the slowest one in a hundred"
				hint="Point at a percentile to read it. Left and Right step through them, Escape returns to p99."
			/>
		</div>
		<p class="reads" data-percentile-note>
			<strong>{newestTail.runId}</strong> timed {grouped(newestTail.items)} items. Its
			slowest one in a hundred took
			<strong>{seconds((newestTail.ms.at(-1) ?? 0) / 1000)}</strong>
			against {seconds((newestTail.ms[0] ?? 0) / 1000)} for a normal one.
			{#if shardRows === itemRows && itemRows > 0}
				Every item row the ledger holds carries a shard, so a curve per shard is possible; twenty
				overlaid curves is not a chart, so the shard is the unit of the board above and of the
				clock check.
			{:else}
				{grouped(shardRows)} of {grouped(itemRows)} item rows carry a
				shard, so the curve is per run.
			{/if}
		</p>
	{/if}
</Panel>

<style>
	.empty {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.reads {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
