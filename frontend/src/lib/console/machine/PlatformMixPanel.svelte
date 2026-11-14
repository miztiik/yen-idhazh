<script lang="ts">
	/** Show historical job placements by reported L3 capacity, with exact day details. */
	import Panel from '$lib/components/Panel.svelte';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import { emptyState } from '$lib/charts/d3/empty';
	import {
		fleetDots,
		fleetHover,
		fleetJobs,
		fleetReadout,
		fleetSummary,
		fleetSeries
	} from '$lib/charts/fleet';
	import { fleetCacheView } from '$lib/charts/fleet-cache';
	import { chartWidth, labelWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame, useChartLabels } from '$lib/charts/label-context';
	import { rateWords, type MachineRamp } from '$lib/charts/machine-colour';
	import FleetDots from '$lib/console/machine/FleetDots.svelte';
	import type { LostDay } from '$lib/console/recording';
	import { nameSpan } from '$lib/console/span-words';
	import type { Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import { tick } from 'svelte';

	let {
		ramp,
		start,
		end,
		windowDays,
		lost,
		recording,
		gradients,
		chart,
		knobs,
		recordRows
	}: {
		/** The widest host universe keeps ordering and identity stable across presets. */
		ramp: MachineRamp;
		/** The open span, inclusive UTC days, and how many days it covers. */
		start: string;
		end: string;
		windowDays: number;
		/** Days with article records and no machine row. */
		lost: LostDay[];
		/** False where the machine record is switched off. */
		recording: boolean;
		gradients: boolean;
		chart: ChartConfig;
		recordRows: readonly Row[];
		knobs: Pick<
			ConsoleConfig,
			'fleet_min_rows' | 'fleet_top_kinds' | 'fleet_dot_max_px' | 'machine_colour_floor_share'
		>;
	} = $props();

	/** How many value ticks the count axis aims for. */
	const VALUE_TICKS = 4;
	const frame = useChartFrame(() => chart);
	const labels = useChartLabels();
	/** The share of a day's column left empty beside its bar. */
	const PADDING = 0.2;
	/** One CSS pixel separates counted job squares without changing their count. */
	const SQUARE_GAP = 1;

	const span = $derived({ start, end });
	$effect(() => {
		void start;
		void end;
		openDay = null;
	});
	const jobs = $derived(fleetJobs(recordRows));
	const view = $derived(
		fleetCacheView(jobs, {
			ramp,
			appearance: { gradients, floor: knobs.machine_colour_floor_share, palette: chart.palette },
			start: span?.start ?? start,
			end: span?.end ?? end,
			windowDays,
			minRows: knobs.fleet_min_rows,
			topKinds: knobs.fleet_top_kinds,
			numberFormat: chart.number_format,
			recording,
			lost
		})
	);
	let measured = $state<number | null>(null);
	const legendColumns = $derived.by(() => {
		const style = labels();
		const widest = Math.max(style.fontSize, ...view.rows.map((row) =>
			labelWidth(`  ${row.label}`, style) + style.fontSize));
		return Math.max(1, Math.min(Math.ceil(Math.sqrt(view.rows.length)),
			Math.floor(chartWidth(measured, chart.width_px) / widest)));
	});
	const legendRows = $derived(Math.ceil(view.rows.length / legendColumns));
	const box = $derived(frame(chartWidth(measured, chart.width_px), chart.height_px));
	const bars = $derived(
		view.shape === 'bars'
			? dateSeries(fleetSeries(view), {
					frame: box,
					stacked: true,
					stackOrder: 'descending',
					density: chart.tick_density,
					valueTicks: VALUE_TICKS,
					padding: PADDING,
					rule: { declined: 'which machine the platform hands a job does not depend on any model setting' },
					number_format: chart.number_format
				})
			: null
	);
	const squares = $derived(
		view.shape === 'dots'
			? fleetDots(view, {
					frame: box,
					density: chart.tick_density,
					padding: PADDING,
					maxPx: knobs.fleet_dot_max_px,
					gapPx: SQUARE_GAP
				})
			: null
	);
	const readout = $derived(fleetSummary(view));
	const details = $derived(fleetReadout(view));
	const hover = $derived(fleetHover(view));
	const note = $derived(`Recorded jobs per UTC day, grouped by reported L3 across CPU vendors. Larger caches are darker.${view.shape === 'dots' ? ' One square per job.' : ''}`);
	const barsLabel = 'Recorded jobs per UTC day by reported L3 capacity, largest job count at the bottom of each stack.';
	const dotsLabel = 'One square per recorded job, grouped by UTC day and reported L3 capacity.';
	const hint = '';

	/** The day whose jobs are listed under the plot, by date, so a new span
	 * cannot leave the list on a column that now means another day. */
	let openDay = $state<string | null>(null);
	const open = $derived(openDay === null ? -1 : view.days.indexOf(openDay));
	let list = $state<HTMLElement | null>(null);
	let plot = $state<HTMLElement | null>(null);

	async function pick(column: number): Promise<void> {
		const day = view.days[column] ?? null;
		openDay = day === openDay ? null : day;
		await tick();
		if (openDay === null) plot?.querySelector('svg')?.focus();
		else list?.focus();
	}

	async function close(): Promise<void> {
		openDay = null;
		await tick();
		plot?.querySelector('svg')?.focus();
	}

</script>

<div data-windowed="machine-fleet" data-readout-fetched="host-fingerprint" data-window-days={windowDays} data-fleet-state="ready" data-fleet-from={span.start} data-fleet-through={span.end}>
	<Panel heading="h3" id="platform-mix" title={windowDays === 1
		? 'Which machines ran our jobs for this one day'
		: 'Which machines ran our jobs, day by day'} {note}>
		{#if view.nothing === 'recording-off'}
			<p class="empty" data-machine-panel-empty="fleet-off">
				Which machine a job draws is not being recorded, so there is nothing to count.
			</p>
		{:else if view.nothing === 'record-lost'}
			<p class="empty" data-machine-panel-empty="fleet-lost">
				There is nothing left in {nameSpan(windowDays)} to count.
			</p>
		{:else if view.nothing === 'none'}
			<p class="empty" data-machine-panel-empty="fleet-none">
				Nothing has recorded which machine a job drew yet. This starts counting on the first run
				after the record ships.
			</p>
		{:else}
			<div
				class="body"
				data-comparison="composition"
				data-panel-question="is it working"
				data-fleet-shape={view.shape}
				data-fleet-days={view.days.length}
				data-fleet-rows={view.rows.length}
				data-fleet-placements={view.placements}
				data-fleet-min-rows={view.minRows}
			>
				<div
					class="plot"
					bind:this={plot}
					use:observeWidth={(width) => (measured = width > 0 ? width : null)}
					data-model-rule="no"
					data-model-rule-name="platform-mix"
					data-model-rule-none="which machine the platform hands a job does not depend on any model setting"
				>
					{#if bars !== null}
						<DateSeries
							geometry={bars}
							empty={emptyState('quiet', 'No job was placed in this span.')}
							name="machine-fleet"
							label={barsLabel}
							width={box.width}
							height={box.height}
							{readout}
							{hover}
							readoutMaxShare={chart.readout_max_share}
							{hint}
							hintOne={hint}
							restingNote=""
							lede
							picked={open < 0 ? null : open}
							onPick={pick}
						/>
					{:else if squares !== null}
						<FleetDots
							geometry={squares}
							{readout}
							{hover}
							name="machine-fleet"
							label={dotsLabel}
							readoutMaxShare={chart.readout_max_share}
							{hint}
							hintOne={hint}
							restingNote=""
							picked={open < 0 ? null : open}
							onPick={pick}
						/>
					{/if}
				</div>
				<ul class="machine-key" data-fleet-identity-key aria-label="Reported L3 capacity, largest first"
					style:grid-template-columns={`repeat(${legendColumns}, minmax(0, 1fr))`}
					style:grid-template-rows={`repeat(${legendRows}, auto)`}>
					{#each view.rows as row (row.key)}
						<li class="key-kind" data-fleet-kind={row.key}>
							<span class="chip" style:background={row.parts[0].swatch}></span>{row.label}
						</li>
					{/each}
				</ul>
				<p class="count-note">Counts are recorded jobs, not unique physical machines. L2 capacity is not recorded.</p>
				{#if open >= 0}
					<!-- One tab stop for the whole list, where a pick moves focus, and
					     Escape inside it closes it. -->
					<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
					<div
						class="jobs"
						bind:this={list}
						role="region"
						aria-label="Jobs on {longDate(view.days[open])} UTC"
						tabindex="0"
						data-fleet-jobs={view.days[open]}
						onkeydown={(event) => {
							if (event.key === 'Escape') {
								event.preventDefault();
								void close();
							}
						}}
					>
						<ChartReadout readout={details} at={open} name="machine-fleet-details" maxShare={chart.readout_max_share} hint="" />
						<table>
							<caption>
								{view.lines[open].length}
								{view.lines[open].length === 1 ? 'job' : 'jobs'} on {longDate(view.days[open])} UTC
							</caption>
							<thead>
								<tr>
									<th scope="col">Run</th>
									<th scope="col">Job or pipeline/task</th>
									<th scope="col" class="number">Shard</th>
									<th scope="col">Machine and L3</th>
									<th scope="col" class="number">Seconds</th>
									<th scope="col" class="number">Speed</th>
								</tr>
							</thead>
							<tbody>
								{#each view.lines[open] as line, at (at)}
									<!-- Below the console's stacking width a job takes two lines, run, job
									     and shard over machine, seconds and speed, and the two numbers
									     carry their own words because the heading row is not shown. -->
									<tr data-fleet-job={line.row}>
										<td class="run">{line.runId}</td>
										<td class="job">{line.pipelineName !== null && line.taskName !== null
											? `${line.pipelineName}/${line.taskName}`
											: line.job ?? 'not recorded'}</td>
										<td class="number shard"><span class="narrow-word" aria-hidden="true">{'shard '}</span>{line.shard ?? 'not recorded'}</td>
										<td class="machine"><span class="chip" style:background={line.swatch}></span> {line.machine}; {line.l3Cache}</td>
										{#if line.seconds === null}
											<td class="number seconds"><span class="narrow-word" aria-hidden="true">{'seconds '}</span>not recorded</td>
										{:else}
											<td class="number seconds">{Math.round(line.seconds)}<span class="narrow-word" aria-hidden="true">{' seconds'}</span></td>
										{/if}
										<td class="number speed">{line.rate === null ? 'Speed not recorded' : rateWords(line.rate, chart.number_format)}</td>
									</tr>
								{/each}
							</tbody>
						</table>
						<button type="button" class="close" onclick={() => void close()}>Close the list</button>
					</div>
				{/if}
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

	.machine-key {
		display: grid;
		grid-auto-flow: column;
		list-style: none;
		padding: 0;
		margin-block: var(--space-3);
		gap: var(--console-control-gap) var(--console-panel-gap);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		color: var(--color-text-secondary);
	}
	.key-kind {
		overflow-wrap: anywhere;
	}
	.count-note {
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		color: var(--color-text-tertiary);
	}

	.chip {
		display: inline-block;
		inline-size: var(--console-small-size);
		block-size: var(--console-small-size);
		border-radius: var(--radius-sm);
		margin-inline-end: var(--space-1);
		vertical-align: middle;
		border: 1px solid var(--color-rule-strong);
		box-sizing: border-box;
	}
	.plot :global([data-series-bar]) {
		stroke: var(--chart-axis);
		stroke-width: var(--console-chart-axis-width);
	}

	.plot {
		margin-top: var(--space-3);
	}

	.jobs {
		margin-top: var(--space-3);
		padding: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		overflow-x: auto;
	}

	.jobs:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}

	table {
		inline-size: 100%;
		border-collapse: collapse;
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}

	caption {
		text-align: start;
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text);
		padding-block-end: var(--space-2);
	}

	th,
	td {
		padding: var(--space-1) var(--space-2);
		border-block-end: 1px solid var(--color-rule);
		text-align: start;
		white-space: nowrap;
	}

	.number {
		text-align: end;
		font-variant-numeric: tabular-nums;
	}

	/* The words a number carries when the heading row is not shown. */
	.narrow-word {
		display: none;
	}

	/* The console's stacking width. Six columns do not fit a phone, and a list
	   that scrolls sideways hides the speed that ties a job to its colour, so a
	   job takes two lines: run, job and shard, then machine, seconds and speed.
	   The heading row stays for a screen reader and leaves the page. */
	@media (max-width: 48rem) {
		.jobs {
			overflow-x: visible;
		}

		thead {
			position: absolute;
			inline-size: 1px;
			block-size: 1px;
			overflow: hidden;
			clip-path: inset(50%);
			white-space: nowrap;
		}

		tbody tr {
			display: flex;
			flex-wrap: wrap;
			align-items: baseline;
			column-gap: var(--space-3);
			padding-block: var(--space-1);
			border-block-end: 1px solid var(--color-rule);
		}

		/* The break between the two lines, so each line keeps its own widths. */
		tbody tr::before {
			content: '';
			flex-basis: 100%;
			order: 4;
		}

		td,
		.number {
			padding: 0;
			border: 0;
			text-align: start;
			white-space: normal;
		}

		.run {
			order: 1;
			overflow-wrap: anywhere;
		}

		.job {
			order: 2;
		}

		.shard {
			order: 3;
		}

		.machine {
			order: 5;
		}

		.seconds {
			order: 6;
		}

		.speed {
			order: 7;
		}

		.narrow-word {
			display: inline;
		}
	}

	.close {
		margin-top: var(--space-2);
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
		background: none;
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-sm);
		padding: var(--space-1) var(--space-2);
		cursor: pointer;
	}

	.close:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}
</style>
