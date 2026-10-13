<script lang="ts">
	import WindowControl from '$lib/components/WindowControl.svelte';
	import WindowStatus from '$lib/components/WindowStatus.svelte';
	import StageTimings from '$lib/console/pipelines/StageTimings.svelte';
	import FailureMix from '$lib/console/pipelines/FailureMix.svelte';
	import ItemTimeSplit from '$lib/console/pipelines/ItemTimeSplit.svelte';
	import ItemCost from '$lib/console/pipelines/ItemCost.svelte';
	import { daysInWindow, monthsToFetch, windowOfDays } from '$lib/charts/viewport';
	import { nameSpan } from '$lib/console/span-words';
	import type { TelemetryRow } from '$lib/charts/series';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	import type { PanelState } from '$lib/console/waiting';
	let { rows, config, chart, pinned, initialDays, panelState, months = [], held = [] }: {
		rows: (TelemetryRow & { failed_rule?: string | null })[];
		config: ConsoleConfig; chart: ChartConfig;
		pinned: string; initialDays: number; panelState: PanelState;
		months?: string[]; held?: string[];
	} = $props();
	const initial = (() => ({ days: initialDays, window: windowOfDays(pinned, initialDays, config.today_anchor) }))();
	let days = $state(initial.days);
	let window = $state(initial.window);
	const visible = $derived(rows.filter((row) => row.date >= window.start && row.date <= window.end));
	const calendar = $derived(daysInWindow(window));
	const nativeState = $derived(panelState === 'ready' && visible.length === 0 ? 'quiet' : panelState);
	const failures = $derived(visible.map(({ date, stage, outcome, code, failed_rule }) =>
		({ date, stage, outcome, code, failed_rule: failed_rule ?? null })));
	const clocks = $derived(visible.map(({ date, fetch_ms, extract_ms, summarize_ms, label_ms,
		summary_ms, visual_plan_ms, faithfulness_ms, item_total_ms, stage_gap_ms }) =>
		({ date, fetch_ms, extract_ms, summarize_ms, label_ms, summary_ms, visual_plan_ms,
			faithfulness_ms, item_total_ms, stage_gap_ms })));
	const costRows = $derived(visible.map(({ date, prefill_ms, decode_ms, input_tokens, output_tokens, cached_tokens }) =>
		({ date, prefill_ms, decode_ms, input_tokens, output_tokens, cached_tokens })));
	const rule = { changes: [], note: null };
	function show(next: number) {
		days = next;
		window = windowOfDays(pinned, next, config.today_anchor);
	}
</script>
<div data-telemetry-rows={rows.length} data-telemetry-fetching="no">
	<WindowControl {days} presets={config.window_presets} ready onChange={show} />
	<WindowStatus {days} presets={config.window_presets} ready
		monthsFor={(next) => monthsToFetch(windowOfDays(pinned, next, config.today_anchor), months, held).length} />
	<div data-windowed="stage-timings" data-window-days={days}>
		<p>{nameSpan(days)}</p>
		<StageTimings rows={clocks} knobs={config} {chart} {window} {rule} />
	</div>
	<div data-windowed="failure-mix" data-window-days={days}>
		<p>{nameSpan(days)}</p>
		<FailureMix rows={failures} ruleRows={failures} knobs={config} {chart} {rule} {calendar}
			{nativeState} rulesState={nativeState} rulesWindow={window} />
	</div>
	<div data-windowed="item-time-split" data-window-days={days}>
		<p>{nameSpan(days)}</p>
		<ItemTimeSplit rows={clocks} knobs={config} {chart} {rule} {calendar} />
	</div>
	<div data-windowed="item-cost" data-window-days={days}>
		<ItemCost rows={costRows} knobs={config} {chart} />
	</div>
</div>
