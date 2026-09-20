<script lang="ts">
	/** What kind of machine the platform has been giving us lately.
	 *
	 * A count of what happened, never a rate: what the next job will draw is the
	 * one thing this cannot say. The shape is a time axis rather than a ranked
	 * list, because the question is about lately.
	 */
	import Chart from '$lib/charts/Chart.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { fleetChart, fleetColumns, type FleetView } from '$lib/charts/fleet';
	import type { RecordingNotes } from '$lib/console/recording';
	import type { ChartConfig } from '$lib/server/config';

	let {
		fleet,
		machineRecord,
		svg,
		grid,
		chart,
		windowDays
	}: {
		fleet: FleetView;
		machineRecord: RecordingNotes;
		svg: string | null;
		grid: { left: number; right: number };
		chart: ChartConfig;
		windowDays: number;
	} = $props();

	/** The fleet trend, redrawn in the browser from the same counts the server
	 * drew, so a span the operator picks gets the same bars as the first paint. */
	const fleetOption = $derived(fleetChart(fleet.trend).option);
	const fleetStrip = $derived(fleetColumns(fleet.trend));
</script>

<div
	data-windowed="machine-fleet"
	data-window-days={windowDays}
	data-readout-none={fleet.drawBars ? undefined : 'a list of counts has no column'}
>
	<Panel
		heading="h3"
		title="What the platform has been giving us"
		note="How often each kind of machine turned up over the last {windowDays} days, day by day. A count of what happened, never a rate: what the next job will draw is the one thing this cannot say."
	>
		{#if fleet.nothing === 'recording-off'}
			<p class="empty" data-machine-panel-empty="fleet-off">
				Which machine a job draws is not being recorded, so there is nothing to count.
			</p>
		{:else if fleet.nothing === 'record-lost'}
			<p class="empty" data-machine-panel-empty="fleet-lost">
				{machineRecord.recordDestroyed}
				There is nothing left in these {fleet.days} days to count.
			</p>
		{:else if fleet.nothing === 'none'}
			<p class="empty" data-machine-panel-empty="fleet-none">
				Nothing has recorded which machine a job drew yet. This starts counting on the first run
				after the record ships.
			</p>
		{:else if fleet.drawBars}
			<!-- The title asks what has been given lately, so the shape is a time
			     axis and not a ranked list. The ordering a list carried is the
			     sentence above the plot: that is the loss, named rather than
			     absorbed. -->
			<div
				data-fleet-days={fleet.trend.days.length}
				data-fleet-series={fleet.trend.series.length}
				data-fleet-folded={fleet.trend.folded}
				data-fleet-top-kinds={fleet.trend.topKinds}
				data-fleet-other={fleet.trend.other}
				data-fleet-outside-top={fleet.trend.outsideTop}
				data-panel-question="is it working"
			>
				<p class="reads" data-fleet-basis={fleet.placements}>
					Over {fleet.placements} job placements in these {fleet.days} days,
					{fleet.trend.days.length}
					{fleet.trend.days.length === 1 ? 'day' : 'days'} of which recorded one. The kind we
					are given most is {fleet.kinds[0].identity.name}, {fleet.kinds[0].placements} of
					them.
					{#if fleet.trend.folded > 0}
						The {fleet.trend.folded} rarest kinds are drawn as one bar:
						{fleet.trend.series.at(-1)?.identity.folded.join(', ')}.
					{/if}
				</p>
				<Chart
					svg={svg ?? ''}
					option={fleetOption}
					width={chart.width_px}
					height={chart.height_px}
					label="Job placements per day over {fleet.days} days, one bar per kind of machine. One group is one day."
					columns={fleetStrip}
					readoutName="machine-fleet"
					readoutMaxShare={chart.readout_max_share}
					{grid}
					restingNote=", the newest day"
					hint="Point at a day to read every kind on it. Left and Right step through them, Escape returns to the newest."
				/>
			</div>
		{:else}
			<ul class="shares" data-fleet-list={fleet.placements}>
				{#each fleet.kinds as kind (kind.identity.key)}
					<li data-fleet-kind={kind.identity.key} data-fleet-count={kind.placements}>
						<strong>{kind.identity.name}</strong>: {kind.placements}
						{kind.placements === 1 ? 'placement' : 'placements'}.
					</li>
				{/each}
			</ul>
			<p class="reads" data-fleet-under={fleet.minRows}>
				{fleet.kinds.length}
				{fleet.kinds.length === 1 ? 'machine' : 'machines'} on record,
				{fleet.placements} placements over these {fleet.days} days. A bar chart of counts
				this small would read as a distribution, and it is not one - this draws one at
				{fleet.minRows}.
			</p>
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

	.reads {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
