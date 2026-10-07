<script lang="ts">
	/** Which machines ran our jobs, day by day.
	 *
	 * A count of what happened, never a rate: what the next job will draw is the
	 * one thing this cannot say. One bar a day, each split by the kind of machine
	 * that ran its jobs, and a machine's colour is its speed - stronger is faster,
	 * slowest at the bottom where every day shares a baseline. Under
	 * `console.fleet_min_rows` placements the bars become one square a job.
	 *
	 * It draws from the machine record's rows in the query door's own shape and
	 * works everything else out here, so the list a pick opens reuses the rows
	 * already in hand rather than asking for them again.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import EmptyState from '$lib/charts/d3/EmptyState.svelte';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import { emptyState } from '$lib/charts/d3/empty';
	import { absentHatch } from '$lib/charts/d3/ordered-colour';
	import {
		FLEET_COLUMNS,
		fleetDots,
		fleetJobs,
		fleetReadout,
		fleetSentence,
		fleetSeries,
		fleetView,
		foldSentences
	} from '$lib/charts/fleet';
	import { chartWidth, frame, observeWidth } from '$lib/charts/frame';
	import { rateWords, type MachineRamp } from '$lib/charts/machine-colour';
	import type { TimeWindow } from '$lib/charts/viewport';
	import FleetDots from '$lib/console/machine/FleetDots.svelte';
	import type { LostDay, RecordingNotes } from '$lib/console/recording';
	import { nameSpan } from '$lib/console/span-words';
	import type { PanelState } from '$lib/console/waiting';
	import { ledgerReach, slice, type LedgerFault, type Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import { onMount, tick } from 'svelte';

	let {
		ramp,
		start,
		end,
		windowDays,
		lost,
		recording,
		machineRecord,
		chart,
		knobs
	}: {
		/** The page's one ramp, so this panel and the machine cards colour a machine alike. */
		ramp: MachineRamp;
		/** The open span, inclusive UTC days, and how many days it covers. */
		start: string;
		end: string;
		windowDays: number;
		/** Days that published articles and kept no machine row. */
		lost: LostDay[];
		/** False where the machine record is switched off. */
		recording: boolean;
		machineRecord: RecordingNotes;
		chart: ChartConfig;
		knobs: Pick<
			ConsoleConfig,
			'fleet_min_rows' | 'fleet_top_kinds' | 'fleet_dot_max_px' | 'absent_hatch_degrees'
		>;
	} = $props();

	/** How many value ticks the count axis aims for. */
	const VALUE_TICKS = 4;
	/** The share of a day's column left empty beside its bar. */
	const PADDING = 0.2;
	/** The ground between two squares, and a hatch's stripe and gap, in CSS px. */
	const SQUARE_GAP = 1;
	const HATCH_GAP = 3;
	const HATCH_LINE = 1;

	let mounted = $state(false);
	let rows = $state<Row[]>([]);
	let span = $state<TimeWindow | null>(null);
	let panelState = $state<PanelState>('loading');
	let fault = $state<LedgerFault | null>(null);
	onMount(() => { mounted = true; });
	$effect(() => {
		const from = start;
		const to = end;
		const enabled = recording;
		if (!mounted) return;
		let current = true;
		rows = [];
		span = null;
		fault = null;
		openDay = null;
		panelState = enabled ? 'loading' : 'ready';
		if (enabled) {
			void (async () => {
				try {
					const reach = await ledgerReach('host-fingerprint');
					if (!current) return;
					if (reach.state !== 'ok') {
						panelState = reach.state;
						fault = reach.state === 'missing' ? reach.fault : null;
						return;
					}
					// The route's own window, which ends on the site's newest published day,
					// never on this record's newest packed day.
					span = { start: from, end: to };
					const answer = await slice('host-fingerprint', { columns: FLEET_COLUMNS, from, to });
					if (!current) return;
					// The door cuts a window that starts before the record began, and names the day it answered from.
					if (answer.state === 'ok' || answer.state === 'quiet') span = { start: answer.first, end: to };
					rows = answer.rows;
					panelState = answer.state === 'ok' ? 'ready' : answer.state;
					fault = answer.state === 'missing' || answer.state === 'unreachable' ? answer.fault : reach.fault;
				} catch (error) {
					if (!current) return;
					panelState = 'unreachable';
					console.warn('[platform-mix] The machine record could not be read.', error);
				}
			})();
		}
		return () => { current = false; };
	});
	// Every ledger a panel reads is published, so `missing` is a record with no
	// compact folder: one that is not packed yet, never one left unpublished.
	const empty = $derived(
		panelState === 'loading' ? emptyState('loading')
			: panelState === 'missing' ? emptyState('missing', 'The machine record is not packed yet.')
				: panelState === 'unreachable' ? emptyState('unreachable', 'The machine record could not be read. Reload this page to try again.')
					: emptyState('quiet', 'No jobs were recorded in this window.')
	);
	const jobs = $derived(fleetJobs(rows));
	const view = $derived(
		fleetView(jobs, {
			ramp,
			start: span?.start ?? start,
			end: span?.end ?? end,
			windowDays,
			minRows: knobs.fleet_min_rows,
			topKinds: knobs.fleet_top_kinds,
			recording,
			lost
		})
	);
	const hatch = $derived(
		absentHatch({ degrees: knobs.absent_hatch_degrees, gapPx: HATCH_GAP, linePx: HATCH_LINE })
	);
	let measured = $state<number | null>(null);
	const box = $derived(frame(chartWidth(measured, chart.width_px), chart.height_px));
	const bars = $derived(
		view.shape === 'bars'
			? dateSeries(fleetSeries(view), {
					frame: box,
					stacked: true,
					density: chart.tick_density,
					valueTicks: VALUE_TICKS,
					padding: PADDING
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
	const readout = $derived(fleetReadout(view, hatch));
	const sentence = $derived(fleetSentence(view));
	const folds = $derived(foldSentences(view));
	/** The steps at least one kind of machine lands on. A step no kind reaches
	 * names nothing, so the key leaves it out. */
	const landed = $derived(ramp.steps.filter((step) => step.low !== null && step.high !== null));
	const keyed = $derived(landed.length > 0);
	/** One sentence, whose last clause names the span in the words every
	 * Hardware subtitle uses, so the page reads alike from panel to panel. One day
	 * is not "each day", so at one day the clause names the day itself. */
	const note = $derived(
		'The platform picks the machine for every job, so a slow week can be the machine and not the ' +
			(windowDays === 1
				? `code - ${nameSpan(windowDays)} split by the kind that ran its jobs.`
				: `code - each day split by the kind that ran its jobs, over ${nameSpan(windowDays)}.`)
	);
	/** What the two plots are, to a screen reader. "A day" needs a second day, so at
	 * one day each label is for that day. */
	const barsLabel = $derived(
		windowDays === 1
			? `Jobs in ${nameSpan(windowDays)}, stacked by the kind of machine that ran them, slowest at the bottom.`
			: `Jobs a day over ${nameSpan(windowDays)}, stacked by the kind of machine that ran them, slowest at the bottom.`
	);
	const dotsLabel = $derived(
		windowDays === 1
			? `One square a job, one column for ${nameSpan(windowDays)}, coloured by the speed of the machine that ran it.`
			: `One square a job, a column a day over ${nameSpan(windowDays)}, coloured by the speed of the machine that ran it.`
	);
	const hint =
		"Point at a day to read every kind on it. Left and Right step through them, Escape returns to the newest. Click or Enter lists that day's jobs.";

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

	function stepText(low: number, high: number): string {
		return low.toFixed(1) === high.toFixed(1) ? low.toFixed(1) : `${low.toFixed(1)} to ${high.toFixed(1)}`;
	}
</script>

<div data-windowed="machine-fleet" data-readout-fetched="host-fingerprint" data-window-days={windowDays} data-fleet-state={panelState} data-ledger-fault={fault} data-fleet-from={span?.start} data-fleet-through={span?.end}>
	<Panel heading="h3" id="platform-mix" title="Which machines ran our jobs, day by day" {note}>
		{#if panelState !== 'ready'}
			<EmptyState drawing={empty} width={box.width} height={box.height} name="machine-fleet" label="Jobs a day by kind of machine" />
		{:else if view.nothing === 'recording-off'}
			<p class="empty" data-machine-panel-empty="fleet-off">
				Which machine a job draws is not being recorded, so there is nothing to count.
			</p>
		{:else if view.nothing === 'record-lost'}
			<p class="empty" data-machine-panel-empty="fleet-lost">
				{machineRecord.recordDestroyed}
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
				<p class="reads" data-fleet-basis={view.placements}>
					{sentence}
					{#each folds as fold (fold)}
						<span data-fleet-fold>{fold}</span>
					{/each}
					This counts what we were given and predicts nothing about the next job.
				</p>
				{#if keyed}
					<!-- The speed each colour stands for, named by the kinds that land on
					     it over the whole record, so the key holds still when the span
					     moves. The strip under the plot names every row. -->
					<p class="speed-key" data-fleet-speed-key>
						<span class="key-lead">The stronger the colour, the faster the machine.</span>
						<span class="key-end">Slower</span>
						{#each landed as step (step.step)}
							<span class="key-step" data-fleet-speed-step={step.step}>
								<span class="chip" style="background: {step.colour}"></span>
								{stepText(step.low ?? 0, step.high ?? 0)}
							</span>
						{/each}
						<span class="key-end">Faster</span>
						<span class="key-unit">tokens a second, each kind's middle reading</span>
					</p>
				{/if}
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
							readoutMaxShare={chart.readout_max_share}
							{hint}
							lede
							{hatch}
							picked={open < 0 ? null : open}
							onPick={pick}
						/>
					{:else if squares !== null}
						<FleetDots
							geometry={squares}
							{readout}
							name="machine-fleet"
							label={dotsLabel}
							readoutMaxShare={chart.readout_max_share}
							{hint}
							picked={open < 0 ? null : open}
							onPick={pick}
						/>
					{/if}
				</div>
				{#if open >= 0}
					<!-- One tab stop for the whole list, where a pick moves focus, and
					     Escape inside it closes it. -->
					<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
					<div
						class="jobs"
						bind:this={list}
						role="region"
						aria-label="Jobs on {longDate(view.days[open])}"
						tabindex="0"
						data-fleet-jobs={view.days[open]}
						onkeydown={(event) => {
							if (event.key === 'Escape') {
								event.preventDefault();
								void close();
							}
						}}
					>
						<table>
							<caption>
								{view.lines[open].length}
								{view.lines[open].length === 1 ? 'job' : 'jobs'} on {longDate(view.days[open])}
							</caption>
							<thead>
								<tr>
									<th scope="col">Run</th>
									<th scope="col">Job</th>
									<th scope="col" class="number">Shard</th>
									<th scope="col">Machine</th>
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
										<td class="job">{line.job}</td>
										<td class="number shard"><span class="narrow-word" aria-hidden="true">{'shard '}</span>{line.shard ?? 'not recorded'}</td>
										<td class="machine">{line.machine}</td>
										{#if line.seconds === null}
											<td class="number seconds"><span class="narrow-word" aria-hidden="true">{'seconds '}</span>not recorded</td>
										{:else}
											<td class="number seconds">{Math.round(line.seconds)}<span class="narrow-word" aria-hidden="true">{' seconds'}</span></td>
										{/if}
										<td class="number speed">{line.rate === null ? 'no speed reading' : rateWords(line.rate)}</td>
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

	.reads {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.speed-key {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-3);
		margin: var(--space-2) 0 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	.key-step {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		font-variant-numeric: tabular-nums;
	}

	.key-end {
		font-weight: 600;
		color: var(--color-text-secondary);
	}

	/* The key's sentence takes a line of its own, so the steps under it read as
	   one row from slower to faster. */
	.key-lead {
		flex-basis: 100%;
		color: var(--color-text-secondary);
	}

	.chip {
		display: inline-block;
		inline-size: 12px;
		block-size: 12px;
		border-radius: 2px;
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
