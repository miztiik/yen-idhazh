<script lang="ts">
	/** What the machine and the server spent outside the model call itself.
	 *
	 * Each figure carries its ceiling, because a counter without one is not a
	 * measurement. A figure with a span is one track: the band is what the window
	 * read, the upright is this run's own mark on it, and that is what says
	 * whether the newest run was unusual.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import HostFigure from './HostFigure.svelte';
	import { grouped } from '$lib/charts/series';
	import { spanTrack, type FigureSpan } from '$lib/charts/span-track';
	import type { Reading } from '$lib/server/machine-counters';

	let {
		cpuBusy,
		modelLoad,
		cpuBusySpan,
		modelLoadSpan,
		parallelSlots,
		chartWidthPx,
		windowDays,
		days
	}: {
		cpuBusy: Reading<number> | null;
		modelLoad: Reading<number> | null;
		cpuBusySpan: FigureSpan;
		modelLoadSpan: FigureSpan;
		parallelSlots: { highest: number | null; from: number; outOf: number };
		chartWidthPx: number;
		windowDays: number;
		days: number;
	} = $props();

	/** The two figures the server records outside the model call that have both a
	 * reading and a window to read it against. One shape for both, so the reader
	 * compares them by looking rather than by converting two sentences.
	 *
	 * A processor share is read against 100 because that is the comparison - a
	 * shard that idled is the gap. Opening the weights has no ceiling, so its
	 * track ends at the slowest thing drawn on it. */
	const cpuBusyTrack = $derived(
		spanTrack(cpuBusy?.value ?? null, cpuBusySpan, {
			ceiling: 100,
			width: chartWidthPx
		})
	);
	const modelLoadTrack = $derived(
		spanTrack(modelLoad?.value ?? null, modelLoadSpan, {
			width: chartWidthPx
		})
	);
</script>

<div data-windowed="machine-host" data-window-days={windowDays}>
	<Panel
		heading="h3"
		title="What the server did outside the model call"
		note="What the machine and the server spent outside the model call itself. Each figure carries its ceiling: a counter without one is not a measurement. A figure with a span is one track - the band is what the last {windowDays} days read, the upright is this run's own mark on it, and that is what says whether the newest run was unusual."
	>
		<dl class="host">
			<!-- Two figures, one shape. Each was a reading and a span written as
			     prose, which a reader can follow but cannot compare: a track puts
			     the run's own mark on the window that measured it. -->
			<HostFigure
				name="cpu-busy"
				label="Least busy shard"
				track={cpuBusyTrack}
				format={(pct) => `${pct.toFixed(2)}%`}
				windowDays={days}
				note="Of every processor second. Near 100 is the expected reading, so the gap is the share of that shard's job spent waiting rather than computing."
			/>

			<!-- The memory row that sat here was the window's span of the same
			     figure the panel above draws, written as prose. It is now that
			     panel's window grain, where it is a track beside the run's own
			     mark rather than a sentence a reader has to hold in their head. -->
			<HostFigure
				name="model-load"
				label="Opening the weights"
				track={modelLoadTrack}
				format={(ms) => `${grouped(Math.round(ms))} ms`}
				windowDays={days}
				note="The run's slowest shard."
			/>

			<!-- One line of text, not a chart. The server serves one request at a
			     time because `models.summarize.inference.n_parallel` is 1, and this
			     earns a chart the day that knob moves. It is the slot count each item
			     recorded its server started with; the slots-per-decode gauge that used
			     to sit here read 1.0 on 382 of 383 rows, so what the reader loses is a
			     number that never moved. -->
			<div data-host="batching" data-batching={parallelSlots.highest ?? ''}>
				<dt>Parallel slots</dt>
				<dd>
					{#if parallelSlots.highest === null}
						<span class="absent">No item in this span recorded how many slots its server had.</span>
					{:else if parallelSlots.highest <= 1}
						One; every decode served one request.
						<span class="unit">
							One slot on all {parallelSlots.from} of {parallelSlots.outOf} items that
							recorded it.
						</span>
					{:else}
						Up to {parallelSlots.highest} slots a server.
						<span class="unit"
							>Over {parallelSlots.from} of {parallelSlots.outOf} items.</span
						>
					{/if}
				</dd>
			</div>
		</dl>
	</Panel>
</div>

<style>
	.host {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
		gap: var(--space-4) var(--space-5);
		margin: 0;
	}

	.host dt {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.host dd {
		margin: var(--space-1) 0 0;
		font-size: var(--text-base);
		color: var(--color-text);
	}

	.unit {
		display: block;
		margin-top: var(--space-1);
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	.absent {
		color: var(--color-text-tertiary);
	}
</style>
