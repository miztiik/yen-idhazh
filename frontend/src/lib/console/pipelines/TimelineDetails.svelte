<script lang="ts">
	/** Inspect a bounded page of one shard's articles without inventing timing intervals. */
	import type { TimelineShard } from './run-timeline';
	import { timelineItems, type TimelineOrder } from './run-timeline-geometry';
	import { DURATION_STAGES } from '../duration-cohort';
	import { seconds } from '../../charts/machine';
	import { useNumberFormat } from '../../number-format-context';
	import { formatNumber } from '../../number-format';

	let { shard, limit }: { shard: TimelineShard; limit: number } = $props();
	const numberFormat = useNumberFormat();
	const count = (value: number) => formatNumber(value, numberFormat, { exact: true });
	const duration = (ms: number | null): string => ms === null ? 'Not measured'
		: ms < 0 ? `-${seconds(-ms / 1000, numberFormat, true)}` : seconds(ms / 1000, numberFormat, true);
	const utc = (ms: number | null) => ms === null ? 'Not recorded'
		: new Date(ms).toISOString().replace('T', ' ').replace('Z', ' UTC');
	let order = $state<TimelineOrder>('cost');
	let page = $state(0);
	const ordered = $derived(timelineItems(shard.items, order));
	const shown = $derived(ordered.slice(page * limit, (page + 1) * limit));
	const cohort = $derived(shard.breakdown);
</script>

<div class="inspection">
	<p class="note" data-timeline-cohort>
		Stage averages use {count(cohort.count)} complete, consistent clocks out of {count(cohort.recorded)} recorded.
		Excluded: {count(cohort.missing)} missing, {count(cohort.invalid)} invalid and {count(cohort.inconsistent)} inconsistent.
		Every recorded cost still counts in the shard's item work.
	</p>
	<dl class="readings" data-timeline-stage-means>
		{#each cohort.stages as stage, index (stage.cell)}
			<div><dt><span class="swatch" style:background="var({DURATION_STAGES[index][2]})"></span>{stage.label}</dt><dd>{duration(stage.value)}</dd></div>
		{/each}
		<div><dt>Unattributed time</dt><dd>{duration(cohort.unattributed)}</dd></div>
		<div><dt>Overlap deduction</dt><dd>{duration(cohort.overlap)}</dd></div>
	</dl>
	<div class="ordering">
		<label>Article order
			<select bind:value={order} onchange={() => page = 0}>
				<option value="cost">Longest work first</option>
				<option value="start">Start time</option>
			</select>
		</label>
		<p class="note">Showing {count(page * limit + 1)}-{count(Math.min((page + 1) * limit, ordered.length))} of {count(ordered.length)} articles.</p>
	</div>
	<ol class="items" start={page * limit + 1}>
		{#each shown as item (item.itemId)}
			<li data-timeline-item={item.itemId} data-timeline-item-work-ms={item.workMs} data-timeline-item-start-ms={item.startMs}>
				<details>
					<summary><span class="identity">{item.itemId}</span><span class="cost">{duration(item.workMs)} work</span></summary>
					<p class="note">
						{item.sourceId ?? 'Source not recorded'}.
						{item.outcome === null ? 'Outcome not recorded' : item.outcome === 'ok' ? 'Completed' : item.outcome.replaceAll('_', ' ')}
						{#if item.stage && item.outcome !== 'ok'} at {item.stage.replaceAll('_', ' ')}{/if}{#if item.code}: {item.code.replaceAll('_', ' ')}{/if}.
						{#if item.index !== null}Position {count(item.index + 1)} in this shard.{/if}
					</p>
					<dl class="readings">
						<div><dt>Started</dt><dd>{utc(item.startMs)}</dd></div>
						<div><dt>Finished</dt><dd>{utc(item.endMs)}</dd></div>
						<div><dt>Recorded elapsed</dt><dd>{duration(item.elapsedMs)}</dd></div>
						<div><dt>Item work</dt><dd>{duration(item.workMs)}</dd></div>
						<div><dt>Parked queue wait</dt><dd>{duration(item.queueMs)}</dd></div>
						<div><dt>Robots reading</dt><dd>{duration(item.robotsMs)}</dd></div>
						{#each item.stages as stage (stage.cell)}
							<div><dt>{stage.label}</dt><dd>{duration(stage.ms)}</dd></div>
						{/each}
						<div><dt>Signed stage gap</dt><dd>{duration(item.gapMs)}</dd></div>
					</dl>
					<p class="note">Call readings are details within the model stage, not additional durations. Robots time is not added to fetch time.</p>
					<dl class="readings">
						{#each item.calls as call (call.cell)}
							<div><dt>{call.label}</dt><dd>{duration(call.ms)}
								{#if call.cell === 'visual_plan_ms' && call.ms !== null}
									<span class="note">{item.planEstimated === true ? 'estimated' : item.planEstimated === false ? 'timed' : 'attribution not recorded'}</span>
								{/if}
							</dd></div>
						{/each}
					</dl>
				</details>
			</li>
		{/each}
	</ol>
	{#if ordered.length > limit}
		<nav class="pagination" aria-label="Article pages in this shard">
			<button type="button" disabled={page === 0} onclick={() => page -= 1}>Previous articles</button>
			<button type="button" disabled={(page + 1) * limit >= ordered.length} onclick={() => page += 1}>Next articles</button>
		</nav>
	{/if}
</div>

<style>
	.inspection { display: flex; flex-direction: column; gap: var(--space-3); padding-block-start: var(--space-3); }
	.note { margin: 0; font-size: var(--text-xs); line-height: var(--leading-xs); color: var(--color-text-secondary); }
	.readings { display: flex; flex-wrap: wrap; gap: var(--space-3) var(--space-5); margin: 0; padding-block: var(--space-2); }
	dt { display: flex; align-items: center; gap: var(--space-1); font-size: var(--text-xs); color: var(--color-text-secondary); }
	dd { margin: 0; font-size: var(--text-sm); font-variant-numeric: tabular-nums; }
	.swatch { display: inline-block; inline-size: var(--space-2); block-size: var(--space-2); border-radius: var(--radius-sm); }
	.ordering, .pagination { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3); }
	label { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm); }
	select, button { font: inherit; color: var(--color-text); background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: var(--radius-sm); padding: var(--space-2); }
	.items { margin: 0; padding-inline-start: var(--space-5); font-size: var(--text-sm); }
	.items > li { padding-block: var(--space-2); border-block-start: 1px solid var(--color-rule); }
	summary { cursor: pointer; overflow-wrap: anywhere; }
	.identity { font-weight: 600; }
	.cost { display: inline-block; margin-inline-start: var(--space-3); white-space: nowrap; color: var(--color-text-secondary); }
	select:focus-visible, button:focus-visible, summary:focus-visible { outline: 2px solid var(--color-focus); outline-offset: var(--space-1); }
	button:disabled { color: var(--color-text-tertiary); cursor: default; }
</style>
