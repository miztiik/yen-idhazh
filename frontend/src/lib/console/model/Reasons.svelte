<script lang="ts">
	import { reasonHeadline, neverSeenNote, unexplainedNote, reasonsWithin, reasonTotals, REASONS, type ReasonDay } from '../doubt-reasons';
	import type { ModelRule } from '../../charts/d3/model-rule';
	import type { ChartConfig } from '../../server/config';
	import Series from './Series.svelte';
	import { reasonDrawing } from './doubt-reasons';
	let { days, start, end, rule, chart, windowDays }: {
		days: readonly ReasonDay[] | null; start: string; end: string; rule: ModelRule; chart: ChartConfig; windowDays: number;
	} = $props();
	const selected = $derived(reasonsWithin([...(days ?? [])], { start, end }));
	const series = $derived(reasonDrawing(selected));
	const totals = $derived(reasonTotals(selected));
	const headline = $derived(reasonHeadline(selected, windowDays));
	const unexplained = $derived(unexplainedNote(selected, windowDays));
</script>
<div data-eval-panel="doubt-reasons" data-model-reasons data-model-reasons-from={start}
	data-model-reasons-to={end} data-model-reasons-days={windowDays}>
	<p data-model-reasons-intro>{windowDays === 1 ? 'The single column is this one day' : `The columns run over these ${windowDays} days`}. The reasons stay separate, never added into one doubt count.</p>
	<p data-model-reasons-rule>Each summary carries at most one published reason. The reason comes from its published item, not a second scoring rule.</p>
	{#if !selected.some((day) => day.items > 0)}<p data-model-reasons="empty" data-doubt-reasons-empty={days === null ? 'missing' : 'quiet'} data-lede>{days === null ? 'The published doubt record is unavailable.' : 'No published summary carries a doubt record in this window.'}</p>
		<div data-model-rule="no" data-model-rule-none="There are no published days on which to place a change." data-readout-none="No doubt readings were available."></div>
	{:else}
		<p data-lede data-model-reasons-headline={headline === null ? undefined : ''} data-model-reasons={headline === null ? 'none' : undefined}>{headline ?? 'No summary carried a doubt reason in this window.'}</p>
		<Series {series} {rule} {chart} name="doubt-reasons" stacked />
		<p>{neverSeenNote(selected, windowDays)}</p>{#if unexplained !== null}<p data-model-reasons-unexplained>{unexplained}</p>{/if}
		<p>{REASONS.map((r) => r.label).join('; ')}.</p>
		{#if totals.explained > 0}
			<details><summary>The counts behind the reasons</summary>
				<table data-reason-days><caption>Published reasons by day.</caption>
					<thead><tr><th>Day</th>{#each REASONS as reason}<th>{reason.label}</th>{/each}</tr></thead>
					<tbody>{#each selected as day}<tr data-reason-day={day.date} data-reason-items={day.items}
						data-reason-explained={day.explained} data-reason-unexplained={day.unexplained}>
						<th>{day.date}</th>{#each REASONS as reason}<td data-reason-count={reason.id} data-reason-n={day.counts[reason.id]}>{day.counts[reason.id]}</td>{/each}
					</tr>{/each}</tbody>
				</table>
			</details>
		{/if}
	{/if}
	<p data-comparison="the commonest reason against the rest">The commonest reason against the rest. Each summary carries at most one recorded reason.</p>
</div>
