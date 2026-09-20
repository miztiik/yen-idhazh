<script lang="ts">
	/** What a run reads against what it writes, in either currency.
	 *
	 * One group a run, a read bar beside a written bar on one axis. The switch
	 * changes the unit and never the row set, so the two grains can never cover
	 * different runs. The server drew the opening unit, so the first paint and
	 * the radio that is already checked agree before a script has run.
	 */
	import Chart from '$lib/charts/Chart.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import ShapeSwitch from '$lib/components/ShapeSwitch.svelte';
	import {
		workChart,
		workValues,
		DEFAULT_WORK_UNIT,
		SHARED_AXIS_LIMIT,
		type ReadWriteSummary,
		type RunWork,
		type WorkUnit
	} from '$lib/charts/machine';
	import { columnStrip } from '$lib/charts/frame';
	import { grouped } from '$lib/charts/series';
	import type { ChartConfig } from '$lib/server/config';

	let {
		runs,
		work,
		totals,
		svg,
		grid,
		chart,
		windowDays,
		days
	}: {
		runs: RunWork[];
		work: ReadWriteSummary;
		totals: { input: number; output: number; items: number };
		svg: string | null;
		grid: { left: number; right: number };
		chart: ChartConfig;
		windowDays: number;
		days: number;
	} = $props();

	let workUnit = $state<WorkUnit>(DEFAULT_WORK_UNIT);
	const WORK_UNITS: { value: WorkUnit; text: string }[] = [
		{ value: 'tokens', text: 'Tokens' },
		{ value: 'seconds', text: 'Seconds' }
	];
	const workOption = $derived(workChart(runs, work, workUnit).option);
	/** Absent where the open unit has nothing to draw. The seconds grain goes
	 * absent on its own while the count grain still draws: a run nobody timed did
	 * not take no time. */
	const workAbsent = $derived(workUnit === 'seconds' && work.timedRuns === 0);
	/** The measured ratio at one precision, so the figure the panel prints and the
	 * figure it stamps can never be two different readings of one measurement. */
	const workRatio = $derived(work.ratio[workUnit]?.toFixed(2) ?? null);

	/** One strip for one panel: the axis carries the run's day and the strip
		* carries the run itself, so the group a pointer is on is the one place a
		* run id and both its figures can be read together. It reads the open span,
		* because the bars do, and the open unit, because 19D7 forbids the tooltip
		* being the only carrier of a fact the panel is about. */
	const tokenRuns = $derived(runs.map((run) => run.runId));
	const workNumber = (value: number | null) =>
		value === null ? '-' : workUnit === 'tokens' ? grouped(value) : `${value.toFixed(1)}s`;
	const workStrip = $derived(
		columnStrip(tokenRuns, [
			{
				label: 'Read',
				colour: 'var(--chart-1)',
				value: (index) =>
					workNumber(runs[index] === undefined ? null : workValues(runs[index], workUnit).read)
			},
			{
				label: 'Written',
				colour: 'var(--chart-4)',
				value: (index) =>
					workNumber(runs[index] === undefined ? null : workValues(runs[index], workUnit).written)
			},
			{
				label: workUnit === 'tokens' ? 'Items counted' : 'Items timed',
				colour: '',
				value: (index) =>
					grouped((workUnit === 'tokens' ? runs[index]?.items : runs[index]?.timed) ?? 0)
			}
		])
	);
</script>

<div
	data-windowed="machine-tokens"
	data-window-days={windowDays}
	data-model-rule="no"
	data-model-rule-name="machine-tokens"
	data-model-rule-none="one bar a run, so there is no day edge to draw between"
>
	<Panel
		heading="h3"
		id="read-against-written"
		title="How much of a run is reading and how much is writing"
		note="Cutting what we send and cutting what we ask for are different edits, and only the split says which one pays - one group a run, over the last {windowDays} days."
	>
		{#if runs.length === 0}
			<p class="empty" data-machine-panel-empty="tokens">
				No run in these {days} days recorded both a prompt count and a written count.
			</p>
		{:else}
			<div
				data-read-write-unit={workUnit}
				data-read-write-runs={runs.length}
				data-read-write-timed-runs={work.timedRuns}
				data-read-write-taller={work.taller[workUnit] ?? ''}
				data-read-write-ratio={workRatio ?? ''}
				data-read-write-split={work.split[workUnit] ? 'yes' : 'no'}
				data-panel-question="is it working"
			>
				<!-- Top right of its own panel, and radio inputs: two named states a
				     reader can see both of beat one state and a verb. -->
				<div class="units">
					<ShapeSwitch
						bind:shape={workUnit}
						name="work-unit"
						label="Which unit to count in"
						options={WORK_UNITS}
					/>
				</div>

				{#if workAbsent}
					<p class="empty" data-work-absent="seconds">
						No run in these {days} days timed the model call, so there are no seconds to draw.
						That is a measurement that did not survive, not a run that took no time. Count the
						tokens instead.
					</p>
				{:else}
					<Chart
						svg={svg ?? ''}
						option={workOption}
						width={chart.width_px}
						height={chart.height_px}
						label="What each run read beside what it wrote, in {workUnit}, over {days} days. One group is one run."
						columns={workStrip}
						readoutName="read-against-written"
						readoutMaxShare={chart.readout_max_share}
						{grid}
						restingNote=", the last run"
						hint="Point at a run to read it. Left and Right step through them, Escape returns to the last."
					/>
				{/if}

				<p class="reads" data-token-totals>
					{grouped(totals.input)} tokens read and {grouped(totals.output)}
					written, over {runs.length}
					{runs.length === 1 ? 'run' : 'runs'} and {grouped(totals.items)} items.
					{#if work.timedRuns < runs.length}
						{work.timedRuns} of those
						{work.timedRuns === 1 ? 'run' : 'runs'} timed the model call.
					{/if}
				</p>
				<!-- 19D4's threshold is a measurement, so the panel prints the one it
				     took rather than asserting the shape was safe. -->
				<p class="reads" data-read-write-measured>
					{#if workRatio === null}
						Nothing in {workUnit} to divide over this span, so the two bars carry no ratio.
					{:else}
						Measured over these runs: {workRatio}
						{workUnit}
						{work.taller[workUnit] === 'read' ? 'read' : 'written'} for every one
						{work.taller[workUnit] === 'read' ? 'written' : 'read'}.
						{#if work.split[workUnit]}
							Past {SHARED_AXIS_LIMIT} to one the smaller side draws under 5 percent of a shared
							axis and reads as zero, so it takes its own row here.
						{/if}
					{/if}
				</p>
			</div>
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

	.reads {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.units {
		display: flex;
		justify-content: flex-end;
	}
</style>
