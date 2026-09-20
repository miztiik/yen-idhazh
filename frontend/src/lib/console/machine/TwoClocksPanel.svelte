<script lang="ts">
	/** Whether the two instruments that count prompt tokens agree.
	 *
	 * The runtime ledger was created for this check and nothing performed it on a
	 * screen. A day where the two disagree is a day whose rates cannot be
	 * trusted, so this panel is a verdict rather than a trend.
	 */
	import Chart from '$lib/charts/Chart.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { clockColumns, clocksChart, type ClockView } from '$lib/charts/machine';
	import type { ChartConfig } from '$lib/server/config';

	let {
		clocks,
		svg,
		tolerancePct,
		chart
	}: {
		clocks: ClockView;
		svg: string | null;
		tolerancePct: number;
		chart: ChartConfig;
	} = $props();

	const clocksOption = $derived(clocksChart(clocks.pairs).option);
	const clockStrip = $derived(clockColumns(clocks.pairs));
</script>

<Panel
	heading="h3"
	verdict
	id="two-clocks"
	title="Whether the speed numbers can be trusted"
	note="Two instruments count the same speed, and a day where they disagree is a day whose figures cannot be quoted - one bar a shard of the newest run."
>
	{#if svg === null}
		<p class="empty" data-machine-panel-empty="clocks">
			One of the two instruments recorded nothing for the newest run, so there is nothing to
			compare. That is a missing reading, not an agreement.
		</p>
	{:else}
		<Chart
			{svg}
			option={clocksOption}
			width={chart.width_px}
			height={chart.height_px}
			label="Prompt tokens a second as the item ledger counted them, beside the same figure as the model server counted it, per {clocks.grain}."
			columns={clockStrip}
			readoutName="clocks"
			readoutMaxShare={chart.readout_max_share}
			restingNote=", the last one"
			hint="Point at a {clocks.grain} to read both instruments. Left and Right step through them, Escape returns to the last."
		/>
		<ul class="shares" data-clock-pairs={clocks.grain} data-clock-disagreeing={clocks.disagreeing}>
			{#each clocks.pairs as pair (pair.label)}
				<li
					data-clock-pair={pair.label}
					data-clock-gap={pair.gapPct?.toFixed(2) ?? ''}
					data-clock-agrees={pair.agrees === null ? 'unknown' : String(pair.agrees)}
				>
					<strong>{pair.label}</strong>:
					{#if pair.gapPct === null}
						one of the two instruments recorded nothing here.
					{:else}
						the ledger reads {(pair.ledger ?? 0).toFixed(2)} and the server
						{(pair.server ?? 0).toFixed(2)} tokens a second -
						<strong>{pair.gapPct.toFixed(2)}% apart</strong>,
						{pair.agrees ? 'inside' : 'past'} the {tolerancePct}% the reconciliation
						audit allows.
					{/if}
				</li>
			{/each}
		</ul>
		<p class="reads" data-clock-grain={clocks.grain}>
			{#if clocks.grain === 'shard'}
				Compared per shard: all {clocks.itemRows} item rows of this run carry a shard.
			{:else}
				Compared per run, not per shard: {clocks.shardRows} of
				{clocks.itemRows} item rows of this run carry a shard, and a shard the ledger cannot
				name cannot be matched to the server that ran it.
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

	.shares {
		margin: var(--space-3) 0 0;
		padding-inline-start: var(--space-5);
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
