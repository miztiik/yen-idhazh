<script lang="ts">
	import { reasonHeadline, neverSeenNote, unexplainedNote, reasonsWithin, REASONS, type ReasonDay } from '../doubt-reasons';
	import type { ModelRule } from '../../charts/d3/model-rule';
	import type { ChartConfig } from '../../server/config';
	import Series from './Series.svelte';
	import { reasonDrawing } from './doubt-reasons';
	let { days, start, end, rule, chart, windowDays }: {
		days: readonly ReasonDay[]; start: string; end: string; rule: ModelRule; chart: ChartConfig; windowDays: number;
	} = $props();
	const selected = $derived(reasonsWithin([...days], { start, end }));
	const series = $derived(reasonDrawing(selected));
</script>
<div data-eval-panel="doubt-reasons" data-windowed="doubt-reasons" data-window-days={windowDays}>
	{#if selected.length === 0}<p data-doubt-reasons-empty="quiet">No published summary carries a doubt record in this window.</p>
	{:else}
		<p data-lede>{reasonHeadline(selected, windowDays) ?? 'No summary carried a doubt reason in this window.'}</p>
		<p data-comparison="composition">The commonest reason against the rest. Each summary carries at most one recorded reason.</p>
		<Series {series} {rule} {chart} name="doubt-reasons" stacked />
		<p>{neverSeenNote(selected, windowDays)}</p><p>{unexplainedNote(selected, windowDays)}</p>
		<p>{REASONS.map((r) => r.label).join('; ')}.</p>
	{/if}
</div>
