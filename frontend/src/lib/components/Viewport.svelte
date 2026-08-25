<script lang="ts">
	import { base } from '$app/paths';
	import {
		datesIn,
		parseTelemetryCsv,
		rowsInWindow,
		type CompressionPoint,
		type SummaryBand,
		type TelemetryRow
	} from '$lib/charts/series';
	import {
		defaultWindow,
		monthsInWindow,
		panWindow,
		zoomWindow,
		type TimeWindow,
		type ViewportConfig
	} from '$lib/charts/viewport';
	import CompressionScatter from './CompressionScatter.svelte';
	import FailureList from './FailureList.svelte';
	import FailurePanels from './FailurePanels.svelte';

	let {
		initialRows,
		availableMonths,
		today,
		config,
		compressionPoints,
		bands
	}: {
		initialRows: TelemetryRow[];
		availableMonths: string[];
		today: string;
		config: ViewportConfig & {
			chart_height: number;
			chart_width: number;
			min_attempts_for_rate: number;
			failure_list_max: number;
		};
		compressionPoints: CompressionPoint[];
		bands: SummaryBand[];
	} = $props();

	// svelte-ignore state_referenced_locally
	let rows = $state<TelemetryRow[]>(initialRows);
	// svelte-ignore state_referenced_locally
	let loadedMonths = $state(datesIn(initialRows).map((date) => date.slice(0, 7)));
	// svelte-ignore state_referenced_locally
	let viewport = $state<TimeWindow>(defaultWindow(datesIn(initialRows), today, config));
	let selectedCode = $state<string | null>(null);
	const visibleRows = $derived(rowsInWindow(rows, viewport));
	const available = $derived(new Set(availableMonths));

	function merge(next: TelemetryRow[]) {
		const byKey = new Map(rows.map((row) => [`${row.run_id}-${row.item_id}`, row]));
		for (const row of next) byKey.set(`${row.run_id}-${row.item_id}`, row);
		rows = [...byKey.values()].sort((a, b) => a.date.localeCompare(b.date));
	}

	async function loadVisibleMonths() {
		for (const month of monthsInWindow(viewport)) {
			if (loadedMonths.includes(month) || !available.has(month)) continue;
			loadedMonths = [...loadedMonths, month];
			try {
				const response = await fetch(`${base}/telemetry/${month}.csv`);
				if (!response.ok) {
					console.warn(`telemetry ${month} unavailable; showing a gap`);
					continue;
				}
				merge(parseTelemetryCsv(await response.text()));
			} catch (error) {
				console.warn(`telemetry ${month} could not be read; showing a gap`, error);
			}
		}
	}

	function pan(days: number) {
		viewport = panWindow(viewport, days);
		void loadVisibleMonths();
	}

	function zoom(factor: number) {
		viewport = zoomWindow(viewport, factor, config);
		void loadVisibleMonths();
	}

	function keydown(event: KeyboardEvent) {
		if (event.key === 'ArrowLeft') {
			event.preventDefault();
			pan(-config.pan_days);
		} else if (event.key === 'ArrowRight') {
			event.preventDefault();
			pan(config.pan_days);
		} else if (event.key === '+' || event.key === '=') {
			event.preventDefault();
			zoom(1 / config.zoom_factor);
		} else if (event.key === '-' || event.key === '_') {
			event.preventDefault();
			zoom(config.zoom_factor);
		}
	}

	$effect(() => {
		void loadVisibleMonths();
	});
</script>

<section class="mt-10" data-viewport-section>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="rounded-md border border-rule p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
		role="region"
		tabindex="0"
		aria-label="Telemetry viewport. Use left and right arrows to pan. Use plus and minus to zoom."
		onkeydown={keydown}
		data-viewport-control
		data-window-start={viewport.start}
		data-window-end={viewport.end}
	>
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<h2 class="text-[1.0625rem] font-semibold text-text">Item telemetry viewport</h2>
				<p class="mt-1 text-[0.8125rem] text-text-tertiary">
					{viewport.start} to {viewport.end}. {visibleRows.length}
					{visibleRows.length === 1 ? ' row' : ' rows'} in view.
				</p>
			</div>
			<div class="flex gap-2" aria-label="Viewport controls">
				<button
					type="button"
					class="min-h-11 rounded-full border border-rule px-3 text-[0.8125rem]"
					onclick={() => pan(-config.pan_days)}
				>
					Back
				</button>
				<button
					type="button"
					class="min-h-11 rounded-full border border-rule px-3 text-[0.8125rem]"
					onclick={() => zoom(1 / config.zoom_factor)}
				>
					Zoom in
				</button>
				<button
					type="button"
					class="min-h-11 rounded-full border border-rule px-3 text-[0.8125rem]"
					onclick={() => zoom(config.zoom_factor)}
				>
					Zoom out
				</button>
				<button
					type="button"
					class="min-h-11 rounded-full border border-rule px-3 text-[0.8125rem]"
					onclick={() => pan(config.pan_days)}
				>
					Forward
				</button>
			</div>
		</div>

		<p class="mt-3 text-[0.75rem] text-text-tertiary" data-viewport-hint>
			Keyboard: Left and Right pan {config.pan_days} days. Plus and Minus zoom.
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
				onSelect={(code) => (selectedCode = code)}
			/>
			<CompressionScatter
				points={compressionPoints}
				viewport={viewport}
				{bands}
				height={config.chart_height}
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
