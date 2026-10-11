<script lang="ts">
	/** Rule counts and their daily trend, over the identity-free query's recorded rows. */
	import { failureRules, type FailureRuleRow } from '$lib/console/failure-rules';
	import type { TimeWindow } from '$lib/charts/viewport';
	import { rank, tailSentence, type RankedDisplay } from '$lib/charts/rank';
	import { rankedGeometry } from '$lib/charts/d3/rankedList';
	import { gridStep, type GridPick } from '$lib/charts/readout';
	import { sparklineMarks, sparklineReadout } from '$lib/charts/sparkline';
	import { grouped } from '$lib/charts/series';
	import { plural } from '$lib/format';
	import RankedList from './RankedList.svelte';
	import Sparkline from './Sparkline.svelte';
	import ChartReadout from './ChartReadout.svelte';

	let { rows, window, stage, max, readoutMaxShare }: {
		rows: readonly FailureRuleRow[];
		window: TimeWindow;
		stage: string;
		max: number;
		readoutMaxShare: number;
	} = $props();

	const counts = $derived(failureRules(rows, window, stage));
	const ranked = $derived(rank(counts.rules.map((rule) => ({
		key: rule.label, value: rule.count, tiebreak: Date.parse(`${rule.last}T00:00:00Z`),
		row: {
			label: rule.label,
			value: `${grouped(rule.count)} of ${plural(counts.failed, 'failure', 'failures')}`,
			context: `at ${stage}; last ${rule.last}`
		} satisfies RankedDisplay
	})), max));
	const tail = $derived(tailSentence(ranked, { one: 'rule', many: 'rules', unitOne: 'failure', unitMany: 'failures' }));
	const trends = $derived(new Map(counts.rules.map((rule) => [
		rule.label, sparklineMarks(rule.daily.map((value, index) => ({ date: counts.dates[index], value })))
	])));
	let picked = $state<GridPick | null>(null);
	const active = $derived(ranked.rows[picked?.row ?? 0]);
	const marks = $derived(active === undefined ? undefined : trends.get(active.key));
	const readout = $derived(marks === undefined || marks.empty ? null : sparklineReadout(
		marks, { label: active.key, format: (value) => plural(value, 'failure', 'failures') }, []
	));
	$effect(() => {
		void window.start;
		void window.end;
		void stage;
		picked = null;
	});
	function step(event: KeyboardEvent) {
		if (event.target !== event.currentTarget) return;
		const next = gridStep(event.key, picked ?? { row: 0, column: 0 }, ranked.rows.length, counts.dates.length);
		if (next === undefined) return;
		event.preventDefault();
		event.stopPropagation();
		picked = next;
	}
</script>

<h2 class="text-[1.0625rem] font-semibold text-text">Which rule refused a reply</h2>
<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-failed-rule-divisor>
	{plural(counts.failed, 'recorded failure', 'recorded failures')} at {stage} in this window.
	These are failure rows, not distinct articles. The query contains no item or source identities.
</p>
<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<div class="mt-3" data-failure-ledger data-failure-ranking="rules"
	role="group" aria-label="Daily failures for each rule" tabindex={ranked.rows.length > 0 ? 0 : undefined}
	onkeydown={step} data-readout-columns={readout === null ? undefined : counts.dates.length}>
	<RankedList geometry={rankedGeometry(ranked)} caption="Rules with most recorded failures at this stage"
		maxText="{grouped(ranked.max)} failures" measured={counts.rows > 0}
		unmeasuredNote="Nothing was recorded for this stage in this window."
		emptyNote={counts.failed > 0 ? 'No failure at this stage names a rule.' : 'No reply failed at this stage in this window.'}
		{tail}>
		{#snippet trend(row)}
			<Sparkline marks={trends.get(row.key) ?? sparklineMarks([])}
				label="Daily failures for {row.key}"
				series={{ label: row.key, format: (value) => plural(value, 'failure', 'failures') }}
				strip={{ selected: picked !== null && ranked.rows[picked.row]?.key === row.key ? picked.column : null,
					onSelect: (column) => picked = column === null ? null : { row: ranked.rows.findIndex((entry) => entry.key === row.key), column } }} />
		{/snippet}
	</RankedList>
	{#if readout !== null}
		<ChartReadout {readout} at={picked?.column ?? null} name="failed-rule-trends"
			maxShare={readoutMaxShare}
			hint="Point at a rule's line to read a day. Up and Down step rules, Left and Right step days, Escape returns to the first rule." />
	{/if}
</div>
<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-failed-rule-unknown>
	{grouped(counts.unknown)} of {plural(counts.failed, 'failure', 'failures')} at {stage}
	{counts.unknown === 1 ? 'has' : 'have'} no recorded failed rule.
</p>
