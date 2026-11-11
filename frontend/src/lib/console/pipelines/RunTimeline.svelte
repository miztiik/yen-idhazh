<script lang="ts">
	/** Draw the newest run from its native item rows, never from the retired projection. */
	import Reserved from '$lib/components/Reserved.svelte';
	import RunTimelinePanel from '../../../routes/console/RunTimelinePanel.svelte';
	import { runTimelineQuery } from '../queries/pipelines';
	import type { LedgerReach, SliceResult } from '$lib/data/ledger';
	import { runTimeline } from './run-timeline';
	import { noRecordSentence, setAsideSentence } from '../recording';
	import type { ConsoleConfig, ChartConfig } from '../../server/config';
	import { formatNumber } from '../../number-format';
	import { useNumberFormat } from '../../number-format-context';

	let { knobs, chart, answer = 'pending' }: {
		knobs: ConsoleConfig;
		chart: ChartConfig;
		answer?: SliceResult | LedgerReach | 'pending';
	} = $props();
	const numberFormat = useNumberFormat();
	const rows = $derived(answer !== 'pending' && 'rows' in answer ? answer.rows : []);
	const native = $derived(runTimeline(rows, knobs.timeline_bars));
	const panelState = $derived(answer === 'pending' ? 'loading' :
		answer.state === 'ok' ? 'ready' : answer.state);
	const lost = $derived(answer !== 'pending' && 'lostDays' in answer && answer.lostDays.length > 0
		? noRecordSentence('article record', answer.lostDays, (days) => `no item clock for ${days} is drawn`) : null);
	const aside = $derived(answer !== 'pending' && 'setAside' in answer
		? setAsideSentence('article record', runTimelineQuery.ledger, answer.setAside, 'this run') : null);
</script>

<Reserved record {panelState} height={knobs.chart_height} width={knobs.chart_width} name="run-timeline" label="The newest run's own clock">
	<p class="comparison" data-comparison="Elapsed windows and cumulative work are separate.">
		Elapsed windows and cumulative work are separate. Longest first, not a measure of efficiency.
	</p>
	<RunTimelinePanel view={native} {chart} width={knobs.chart_width} />
	{#if native.unassigned > 0}
		<p class="note" data-timeline-unassigned={native.unassigned}>
			{formatNumber(native.unassigned, numberFormat, { exact: true })} items have no recorded shard.
			Their recorded costs and endpoints still count in the run totals, but not in a shard's bar.
		</p>
	{/if}
	{#if lost}<p class="note" data-record-note="lost">{lost}</p>{/if}
	{#if aside}<p class="note" data-record-note="set-aside">{aside}</p>{/if}
</Reserved>

<style>
	.comparison, .note { font-size: var(--text-sm); color: var(--color-text-secondary); }
</style>
