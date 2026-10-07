<script lang="ts">
	/** Whether each day's runs delivered: what they published against what they
	 * planned, and every run, on one day axis.
	 *
	 * Two figures answer the one question and they share everything a reader
	 * compares across them. The chart hands the squares its own day slots, so a
	 * day's runs stand under that day's bars. One day is picked for both, so the
	 * guide line on the chart and the tint on the squares are always the same day.
	 * And one readout prints that day for both - its three counts and share, then
	 * one row per run - because two readouts for one day are two places for the
	 * same fact to disagree.
	 *
	 * They were two panels until 2026-09-27, and on the committed ledger they
	 * disagreed with nothing on the page saying why: a day that published 86
	 * percent of its plan drew an ordinary bar over one red run, and a day that
	 * published 66 percent drew four amber squares. Why they are one panel, and
	 * what each alternative cost, is in
	 * `docs/architecture/publishing/what-the-pipelines-route-draws.md`.
	 */
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import RunSquares from '$lib/components/RunSquares.svelte';
	import RunYield from '$lib/components/RunYield.svelte';
	import { coverage, coverageSentence } from '$lib/charts/frame';
	import { readoutOf, type ReadoutLine } from '$lib/charts/readout';
	import { plannedDays, runYield, yieldSeries, type RunYieldSource } from '$lib/charts/run-yield';
	import type { TimeWindow } from '$lib/charts/viewport';
	import { HEALTH_FILL, type DayColumn } from '$lib/console/run-square';
	import { nameSpan } from '$lib/console/span-words';
	import { shortDate } from '$lib/format';

	let {
		yieldDays,
		grid,
		window,
		floorPct,
		height,
		width,
		tickDensity,
		readoutMaxShare,
		selected = $bindable(null)
	}: {
		/** The three counts a day, from the committed day records. */
		yieldDays: RunYieldSource[];
		/** Every day a run wrote a manifest on, over the widest window the control offers. */
		grid: DayColumn[];
		window: TimeWindow;
		/** `run.success_floor_pct`, the line under which a run is red. */
		floorPct: number;
		/** The chart's height, margins included. */
		height: number;
		/** The column, until the figure has been measured. */
		width: number;
		/** `chart.tick_density`. */
		tickDensity: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare: number;
		/** The day both figures are showing, or null for the newest. */
		selected?: number | null;
	} = $props();

	const load = $derived(runYield(yieldDays, window));
	const windowDays = $derived(load.columns.length);

	// Built once from the committed grid, not per pan. `grid` holds every day the
	// widest window can reach and never changes in the browser, so rebuilding this
	// index on every window move re-read the whole history to answer a windowed
	// question. The window walk below is output-sized: one lookup a day in view.
	const byDate = $derived(new Map(grid.map((day) => [day.date, day.squares])));
	/** One column a day of the window, on the chart's own days. */
	const days = $derived<DayColumn[]>(
		load.columns.map((column) => ({ date: column.date, squares: byDate.get(column.date) ?? [] }))
	);
	const runs = $derived(days.reduce((count, day) => count + day.squares.length, 0));

	// The window is not narrowed to the days that ran: a day nothing was planned
	// on is a fact about the record, and hiding it would report a fuller one than
	// exists. Where the empty part is the larger part, the caption says how much.
	const covered = $derived(coverage(plannedDays(load.columns)));
	const coverageNote = $derived(coverageSentence(covered, 'Runs planned articles on'));

	const NO_RUN = 'No run is on record for this day.';
	const NOTHING_PLANNED = 'No article was planned on this day.';

	/** One day for both figures: the chart's counts first, then every run.
	 *
	 * The readout prints no position of its own: each figure keeps its own marks,
	 * from its own geometry, and reports only which day it landed on. It rests on
	 * the newest day, which is the one an operator came for, until one is picked. */
	const readout = $derived(
		readoutOf({
			type: 'dateSeries',
			columns: load.columns.map((column) => shortDate(column.date)),
			series: yieldSeries(load.columns),
			events: {
				lines: days.map((day) =>
					day.squares.map(
						(square): ReadoutLine => ({
							label: `Run ${square.n}`,
							value: square.outcome,
							swatch: HEALTH_FILL[square.health]
						})
					)
				),
				none: NO_RUN
			},
			notMeasured: NOTHING_PLANNED,
			resting: 'last'
		})
	);

	let squares = $state<{ reveal: (index: number) => void } | undefined>();
</script>

<h3 class="run-health-heading">Articles published against planned</h3>
<p class="run-health-caption">
	Planned and failed are totals across the day's runs. Published counts each article once, and
	only if it reached readers. So the line can be lower than the run squares suggest.
	{#if coverageNote}
		<span
			data-coverage-note="run-yield"
			data-coverage-days={covered.days}
			data-coverage-measured={covered.measured}>{coverageNote}</span
		>
	{/if}
</p>

<div data-readout-columns={readout.columns.length} data-run-health-figures>
	<RunYield
		{load}
		{height}
		{width}
		{tickDensity}
		bind:selected
		onPick={(index) => squares?.reveal(index)}
	>
		{#snippet below(slots, narrow)}
			{#if grid.length === 0}
				<!-- A different fact from the one below, so a different sentence: the
				     record holds no run at all, rather than none in this span. -->
				<p class="run-health-empty" data-grid="empty">
					No run is on record yet. This panel fills in as runs publish.
				</p>
			{:else if runs === 0}
				<p class="run-health-empty" data-grid="outside-window">
					No run is on record in {nameSpan(windowDays)}. Widen the window to look further back.
				</p>
			{:else}
				<RunSquares bind:this={squares} {days} {slots} {narrow} {tickDensity} bind:selected />
			{/if}
		{/snippet}
	</RunYield>

	{#if !load.empty || runs > 0}
		<!-- Below both figures, never over either, and the same strip every chart on
		     this console prints - see `ChartReadout.svelte` for the rules. It is also
		     the key: every count and every run carries the colour it is drawn in. -->
		<ChartReadout
			{readout}
			at={selected}
			name="run-health"
			maxShare={readoutMaxShare}
			restingNote=", the newest day"
			hint="Point at a day to read its counts and every run on it. Left and Right step through the days, Escape returns to the newest."
		/>
	{/if}
</div>

<p class="run-health-caption run-health-rule">
	Each square is one run, with run 1 at the bottom. A run is judged only on the articles it tried.
	Red: fewer than {floorPct}% of them succeeded, or the run failed. Amber: at least one of them
	failed, the run had nothing new to try, it reused yesterday's list of sources, or another run's
	failed article was still missing. Green: none of these. A skipped article, already published or
	repeated by a feed, never counts.
</p>

<style>
	.run-health-heading {
		margin: 0;
		font-size: var(--text-base);
		line-height: var(--leading-base);
		font-weight: 600;
		color: var(--color-text);
	}

	.run-health-caption {
		margin-block-start: var(--space-1);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	/* The reading rule closes the panel, after the readout it explains. */
	.run-health-rule {
		margin-block-start: var(--space-4);
	}

	.run-health-empty {
		margin-block-start: var(--space-2);
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
	}
</style>
