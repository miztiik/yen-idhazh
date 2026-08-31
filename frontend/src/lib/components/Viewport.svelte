<script lang="ts">
	import {
		compressionView,
		rowsInWindow,
		type SummaryBand,
		type TelemetryRow
	} from '$lib/charts/series';
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import BandDistance from './BandDistance.svelte';
	import FailureList from './FailureList.svelte';
	import FailurePanels from './FailurePanels.svelte';

	/** The item-telemetry surfaces, over the window the page is holding.
	 *
	 * The window is not owned here any more. It belongs to the page, because the
	 * source table and the chart arm read the same one, and a window owned by the
	 * widget furthest down the page cannot be read by anything above it.
	 */
	let {
		rows,
		window: viewport,
		config,
		bands,
		tickDensity,
		readoutMaxShare,
		onPan,
		onStep
	}: {
		rows: TelemetryRow[];
		window: TimeWindow;
		config: {
			pan_days: number;
			chart_height: number;
			chart_width: number;
			min_attempts_for_rate: number;
			failure_list_max: number;
			band_outlier_rows: number;
		};
		bands: SummaryBand[];
		/** The most date labels a day axis may carry - `chart.tick_density`. */
		tickDensity: number;
		/** The share of a plot a readout strip may take - `chart.readout_max_share`. */
		readoutMaxShare: number;
		/** Move the window by this many days, keeping its span. */
		onPan: (days: number) => void;
		/** Widen (`1`) or narrow (`-1`) to the next preset. */
		onStep: (direction: 1 | -1) => void;
	} = $props();

	let selectedCode = $state<string | null>(null);
	const visibleRows = $derived(rowsInWindow(rows, viewport));
	const windowDays = $derived(daysBetween(viewport.start, viewport.end));
	// The columns read the rows on the page rather than a list of their own. A
	// month the operator pans to is fetched once and both surfaces gain it
	// together, so the split and the failure panels can never describe different
	// days.
	const compression = $derived(compressionView(rows));

	function keydown(event: KeyboardEvent) {
		if (event.key === 'ArrowLeft') {
			event.preventDefault();
			onPan(-config.pan_days);
		} else if (event.key === 'ArrowRight') {
			event.preventDefault();
			onPan(config.pan_days);
		} else if (event.key === '+' || event.key === '=') {
			event.preventDefault();
			onStep(-1);
		} else if (event.key === '-' || event.key === '_') {
			event.preventDefault();
			onStep(1);
		}
	}
</script>

<section class="mt-10" data-viewport-section>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="rounded-md border border-rule p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
		role="region"
		tabindex="0"
		aria-label="Item telemetry viewport, showing {windowDays} days. Use left and right arrows to pan. Use plus and minus to change the window."
		onkeydown={keydown}
		data-windowed="telemetry-viewport"
		data-viewport-control
		data-window-days={windowDays}
		data-window-start={viewport.start}
		data-window-end={viewport.end}
	>
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<h2 class="text-[1.0625rem] font-semibold text-text">Item telemetry viewport</h2>
				<p class="mt-1 text-[0.8125rem] text-text-tertiary">
					{windowDays} days, {viewport.start} to {viewport.end}. {visibleRows.length}
					{visibleRows.length === 1 ? ' row' : ' rows'} in view.
				</p>
			</div>
			<div class="flex gap-2" aria-label="Viewport controls">
				<button
					type="button"
					class="min-h-11 rounded-full border border-rule px-3 text-[0.8125rem]"
					onclick={() => onPan(-config.pan_days)}
				>
					Back
				</button>
				<button
					type="button"
					class="min-h-11 rounded-full border border-rule px-3 text-[0.8125rem]"
					onclick={() => onPan(config.pan_days)}
				>
					Forward
				</button>
			</div>
		</div>

		<p class="mt-3 text-[0.75rem] text-text-tertiary" data-viewport-hint>
			Keyboard: Left and Right pan {config.pan_days} days. Plus and Minus step the window through
			the presets above.
		</p>

		<!-- Shape first, rows last. The list is the only child that can outgrow
		     the screen, so it cannot sit between two charts. -->
		<div class="mt-6">
			<FailurePanels
				{rows}
				window={viewport}
				minAttempts={config.min_attempts_for_rate}
				height={config.chart_height}
				width={config.chart_width}
				{selectedCode}
				{readoutMaxShare}
				onSelect={(code) => (selectedCode = code)}
			/>
			<BandDistance
				points={compression.points}
				viewport={viewport}
				{bands}
				unplotted={compression.unplotted}
				height={config.chart_height}
				width={config.chart_width}
				{tickDensity}
				{readoutMaxShare}
				outlierRows={config.band_outlier_rows}
			/>
			<FailureList
				{rows}
				window={viewport}
				{selectedCode}
				max={config.failure_list_max}
			/>
		</div>
	</div>
</section>
