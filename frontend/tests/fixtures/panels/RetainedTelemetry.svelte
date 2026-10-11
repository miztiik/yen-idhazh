<script lang="ts">
	import Viewport from '$lib/components/Viewport.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import StageTimings from '$lib/components/StageTimings.svelte';
	import ItemCost from '$lib/console/pipelines/ItemCost.svelte';
	import { panWindow, stepPreset, windowOfDays } from '$lib/charts/viewport';
	import { nativeStageTimings } from '$lib/console/pipelines/stage-timings';
	import type { TelemetryRow, SummaryBand } from '$lib/charts/series';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	let { rows, bands, config, chart, pinned, initialDays }: {
		rows: TelemetryRow[]; bands: SummaryBand[]; config: ConsoleConfig; chart: ChartConfig;
		pinned: string; initialDays: number;
	} = $props();
	const initial = (() => ({ days: initialDays, window: windowOfDays(pinned, initialDays, config.today_anchor) }))();
	let days = $state(initial.days);
	let window = $state(initial.window);
	const timings = $derived(nativeStageTimings(rows.map(({ date, fetch_ms, extract_ms, summarize_ms }) =>
		({ date, fetch_ms, extract_ms, summarize_ms }))));
	const costRows = $derived(rows.filter((row) => row.date >= window.start && row.date <= window.end).map(
		({ date, prefill_ms, decode_ms, input_tokens, output_tokens, cached_tokens }) =>
			({ date, prefill_ms, decode_ms, input_tokens, output_tokens, cached_tokens })));
	function show(next: number) {
		days = next;
		window = windowOfDays(pinned, next, config.today_anchor);
	}
</script>
<div data-telemetry-rows={rows.length} data-telemetry-fetching="no">
	<WindowControl {days} presets={config.window_presets} ready onChange={show} />
	<StageTimings days={timings} span={window} height={config.chart_height} width={config.chart_width}
		tickDensity={chart.tick_density} readoutMaxShare={chart.readout_max_share} />
	<Viewport {rows} {window} panelState="ready" {config} {bands}
		tickDensity={chart.tick_density} readoutMaxShare={chart.readout_max_share}
		onPan={(offset) => window = panWindow(window, offset)}
		onStep={(direction) => show(stepPreset(days, config.window_presets, direction))} />
	<div data-windowed="item-cost" data-window-days={days}>
		<ItemCost rows={costRows} knobs={config} {chart} />
	</div>
</div>
