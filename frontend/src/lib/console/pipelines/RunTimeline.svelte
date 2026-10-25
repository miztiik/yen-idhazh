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
	{#if native.itemsPerMinute !== null}
		<p class="lede" data-lede data-timeline-items-per-minute={native.itemsPerMinute}>
			{formatNumber(native.itemsPerMinute, numberFormat, { si: false })} items a minute
		</p>
	{/if}
	<p class="comparison" data-comparison="The shards' work against the time the run took.">
		The shards' work against the time the run took.
	</p>
	<RunTimelinePanel view={native.view} readoutMaxShare={chart.readout_max_share} />
	{#if native.queue.some((row) => row.milliseconds !== null) || native.robots.some((row) => row.milliseconds !== null)}
		<details data-timeline-item-clocks>
			<summary>Recorded queue and robots readings</summary>
			<p class="note">These are separate readings, not additional parts subtracted from the item's total.</p>
			<ul>
				{#each native.queue as row, index (row.itemId)}
					<li data-timeline-clock={row.itemId} data-queue-wait-ms={row.milliseconds} data-robots-ms={native.robots[index].milliseconds}>
						{row.itemId}: queue {row.milliseconds === null ? 'not measured' : `${formatNumber(row.milliseconds, numberFormat, { exact: true })} ms`};
						robots {native.robots[index].milliseconds === null ? 'not measured' : `${formatNumber(native.robots[index].milliseconds, numberFormat, { exact: true })} ms`}.
					</li>
				{/each}
			</ul>
		</details>
	{/if}
	{#if native.unplaced > 0}
		<p class="note" data-timeline-unplaced={native.unplaced}>
			{formatNumber(native.unplaced, numberFormat, { exact: true })} items in this run have no recorded start, total or machine shard, so they are not placed on its clock.
		</p>
	{/if}
	{#if lost}<p class="note" data-record-note="lost">{lost}</p>{/if}
	{#if aside}<p class="note" data-record-note="set-aside">{aside}</p>{/if}
</Reserved>

<style>
	.lede { font-size: var(--text-2xl); margin: var(--space-2) 0; font-variant-numeric: tabular-nums; }
	.comparison, .note { font-size: var(--text-sm); color: var(--color-text-secondary); }
</style>
