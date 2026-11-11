<script lang="ts">
	/** Compare shard elapsed windows or accumulated work, never a mixture of the two. */
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import ShapeSwitch from '$lib/components/ShapeSwitch.svelte';
	import TimelineDetails from '$lib/console/pipelines/TimelineDetails.svelte';
	import { timelineGeometry, type TimelineMeasure } from '$lib/console/pipelines/run-timeline-geometry';
	import type { RunTimelineView } from '$lib/console/pipelines/run-timeline';
	import { seconds } from '$lib/charts/machine';
	import { observeWidth } from '$lib/charts/frame';
	import { useChartLabels } from '$lib/charts/label-context';
	import { factsOf, markReadout, recordsOf } from '$lib/charts/readout';
	import type { ChartConfig } from '$lib/server/config';
	import { useNumberFormat } from '$lib/number-format-context';
	import { formatNumber } from '$lib/number-format';

	let { view, chart, width }: { view: RunTimelineView; chart: ChartConfig; width: number } = $props();
	const numberFormat = useNumberFormat();
	const labels = useChartLabels();
	const count = (value: number) => formatNumber(value, numberFormat, { exact: true });
	const secs = (ms: number) => seconds(ms / 1000, numberFormat, true);
	const duration = (ms: number | null) => ms === null ? 'Not measured' : secs(ms);
	const utc = (ms: number | null) => ms === null ? null : new Date(ms).toISOString().replace('T', ' ').replace('Z', ' UTC');
	const VIEWS: { value: TimelineMeasure; text: string }[] = [
		{ value: 'elapsed', text: 'Elapsed time' }, { value: 'work', text: 'Item work' }
	];
	let measure = $state<TimelineMeasure>('elapsed');
	let measured = $state<number | null>(null);
	let pickedShard = $state<number | null>(null);
	let inspectedShard = $state<number | null>(null);
	let inspectOpen = $state(false);
	const geometry = $derived(timelineGeometry(view, measure, chart.tick_density, measured ?? width, labels(), secs));
	const picked = $derived(geometry.bars.findIndex((bar) => bar.shard.shard === pickedShard));
	const inspected = $derived(view.shards.find((shard) => shard.shard === inspectedShard) ?? geometry.bars[0]?.shard);
	const records = $derived(recordsOf(geometry.bars.map(({ shard }) => factsOf(`Shard ${count(shard.shard)}`, [
		{ label: 'Items', value: shard.items.length, format: count },
		{ label: 'Recorded window', value: shard.elapsedMs, format: secs },
		{ label: 'First item', value: utc(shard.startMs) },
		{ label: 'Last completion', value: utc(shard.endMs) },
		{ label: 'Item work', value: shard.workMs, format: secs },
		{ label: 'Endpoint pairs', value: `${count(shard.timedCount)} of ${count(shard.items.length)}` },
		{ label: 'Recorded costs', value: `${count(shard.workCount)} of ${count(shard.items.length)}` }
	], 'Not measured'))));
</script>

<div class="timeline" data-run-timeline={view.empty ? 'empty' : view.runId} data-timeline-view={measure}
	data-timeline-items={view.itemCount} data-timeline-shards={view.shards.map((shard) => shard.shard).join(' ')}
	data-timeline-span-ms={view.spanMs} data-timeline-work-ms={view.workMs}
	data-readout-records={geometry.bars.length || undefined}
	data-readout-none={geometry.bars.length ? undefined : 'No recorded shard is available to inspect.'}>
	{#if view.empty}
		<p class="note" data-run-timeline-empty>No item record is available for this run. Elapsed time needs recorded starts and ends; item work needs recorded costs.</p>
	{:else}
		<dl class="headline">
			<div class="primary">
				<dt>Recorded item window</dt>
				<dd class="figure" data-lede data-timeline-figure="span">{duration(view.spanMs)}</dd>
				<dd class="note">{count(view.timedCount)} of {count(view.itemCount)} valid endpoint pairs. Excludes setup and publication.</dd>
			</div>
			<div>
				<dt>Item work</dt>
				<dd class="figure" data-timeline-figure="work">{duration(view.workMs)}</dd>
				<dd class="note">{count(view.workCount)} of {count(view.itemCount)} costs recorded. Parked waits excluded.</dd>
			</div>
			<div>
				<dt>Processed items / minute</dt>
				<dd class="figure" data-timeline-figure="rate" data-timeline-items-per-minute={view.itemsPerMinute}>
					{view.itemsPerMinute === null ? 'Not measured' : formatNumber(view.itemsPerMinute, numberFormat, { si: false })}
				</dd>
				<dd class="note">
					{#if view.itemsPerMinute === null}Requires a complete, positive item window.
					{:else}{count(view.itemCount)} attempts, failures included. Not a publication rate.{/if}
				</dd>
			</div>
		</dl>
		<p class="note">Run <strong>{view.runId}</strong> (UTC): {count(view.itemCount)} items, {count(view.shards.length)} recorded shards.</p>
		<div class="controls">
			<ShapeSwitch bind:shape={measure} name="timeline-view" label="Which timing to compare" options={VIEWS} />
			<span class="note">Longest first</span>
		</div>
		<p class="explanation" data-timeline-explanation>
			{#if measure === 'elapsed'}
				First recorded start to last finish, waits included. A left gap means a later start;
				a right gap means earlier completion - not measured idle time.
			{:else}
				Item costs added up; every bar starts at zero. Parked waits are excluded.
				Open a row for stage averages and article readings.
			{/if}
		</p>
		{#if geometry.bars.length === 0 || geometry.domainMs === null}
			<p class="note" data-timeline-measure-empty>
				{measure === 'elapsed' ? 'No shard has a complete recorded start/end pair.' : 'No shard has a recorded item cost.'}
			</p>
		{/if}
		{#if geometry.bars.length > 0}
			<p class="axis-label">{measure === 'elapsed' ? 'Time since the first recorded item start' : 'Cumulative item work'}</p>
			<div class="plot">
				<div class="axis" aria-hidden="true" use:observeWidth={(next) => measured = next}>
					{#each geometry.ticks as tick (tick.ms)}
						<span class="tick" class:first={tick.ms === 0} class:last={tick.ms === geometry.domainMs}
							style:inset-inline-start={tick.at}>{tick.text}</span>
					{/each}
				</div>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
				<ol class="bars" tabindex="0" aria-label="Shard timings, longest first. Up and Down read a shard; select a row for articles."
					use:markReadout={{
						count: geometry.bars.length, walk: 'list', selected: picked < 0 ? null : picked,
						onSelect: (index) => pickedShard = index === null ? null : geometry.bars[index].shard.shard
					}}>
					{#each geometry.bars as bar, index (bar.shard.shard)}
						<li class="bar" data-readout-at={index} data-timeline-bar={bar.shard.shard}
							data-timeline-shard={bar.shard.shard} data-timeline-value-ms={bar.ms}
							data-timeline-start-ms={bar.offsetMs} data-timeline-item-count={bar.shard.items.length}>
							<button type="button" class="row" data-readout-picked={picked === index ? 'yes' : undefined}
								data-chart="run-timeline" data-chart-name="run-timeline-shard-{bar.shard.shard}"
								aria-expanded={inspectOpen && inspected?.shard === bar.shard.shard}
								aria-controls="timeline-article-details"
								onclick={() => { pickedShard = bar.shard.shard; inspectedShard = bar.shard.shard; inspectOpen = true; }}>
								<span class="gutter">Shard {count(bar.shard.shard)}<small>{count(bar.shard.items.length)} items</small></span>
								<span class="track" aria-hidden="true">
									{#each geometry.ticks as tick (tick.ms)}
										<span class="guide" style:inset-inline-start={tick.at}></span>
									{/each}
									{#if bar.ms !== null}
										<span class="fill" class:zero={bar.ms === 0}
											style:inset-inline-start={bar.offset} style:inline-size={bar.width}></span>
									{/if}
								</span>
								<span class="total">{duration(bar.ms)}
									{#if (measure === 'elapsed' ? bar.shard.timedCount : bar.shard.workCount) < bar.shard.items.length}
										<small>partial record</small>
									{/if}
								</span>
							</button>
						</li>
					{/each}
				</ol>
			</div>
			<ChartReadout readout={records[picked < 0 ? 0 : picked] ?? null} resting={picked < 0}
				name="run-timeline" maxShare={chart.readout_max_share} restingNote=", the longest shard"
				hint="Point at a row to read it. Up and Down step through shards; select a row to inspect its articles." />
		{/if}
		{#if inspected}
			<details id="timeline-article-details" bind:open={inspectOpen} data-timeline-details>
				<summary>Articles in Shard {count(inspected.shard)} ({count(inspected.items.length)})</summary>
				{#key `${view.runId}-${inspected.shard}`}
					<TimelineDetails shard={inspected} limit={view.detailLimit} />
				{/key}
			</details>
		{/if}
	{/if}
</div>

<style>
	.timeline { display: flex; flex-direction: column; gap: var(--space-3); font-variant-numeric: tabular-nums; }
	.note, .axis-label, .explanation { margin: 0; font-size: var(--text-sm); line-height: var(--leading-sm); color: var(--color-text-secondary); }
	.headline { display: flex; flex-wrap: wrap; gap: var(--space-5); margin: 0; padding-block: var(--space-3); border-block-end: 1px solid var(--color-rule); }
	.headline > div { flex: 1; min-inline-size: min-content; }
	dt { font-size: var(--text-xs); color: var(--color-text-secondary); }
	dd { margin: 0; }
	.figure { font-size: var(--text-lg); font-weight: 600; white-space: nowrap; }
	.primary .figure { font-size: var(--text-2xl); }
	.controls { display: flex; align-items: baseline; flex-wrap: wrap; gap: var(--space-3); }
	.plot { display: grid; grid-template-columns: max-content minmax(0, 1fr) max-content; column-gap: var(--space-3); }
	.axis { position: relative; grid-column: 2; block-size: var(--space-6); font-size: var(--text-xs); color: var(--color-text-secondary); }
	.tick { position: absolute; transform: translateX(-50%); white-space: nowrap; }
	.tick.first { transform: none; }
	.tick.last:not(.first) { transform: translateX(-100%); }
	.bars, .bar, .row { display: grid; grid-template-columns: subgrid; grid-column: 1 / -1; }
	.bars { list-style: none; margin: 0; padding: 0; row-gap: var(--space-1); }
	.row { padding-block: var(--space-2); padding-inline: 0; align-items: center; gap: var(--space-3); background: transparent; border: 0; color: var(--color-text); cursor: pointer; border-radius: var(--radius-sm); }
	.row:hover, .row[data-readout-picked='yes'] { background: var(--color-surface-sunken); }
	.row:focus-visible, .bars:focus-visible { outline: 2px solid var(--color-focus); outline-offset: var(--space-1); }
	.gutter { text-align: start; font-size: var(--text-sm); font-weight: 600; white-space: nowrap; }
	small { display: block; font-size: var(--text-xs); font-weight: 400; color: var(--color-text-secondary); }
	.track { position: relative; display: block; block-size: var(--space-5); }
	.fill { position: absolute; block-size: 100%; background: var(--chart-1); border-radius: var(--radius-sm); }
	.fill.zero { border-inline-start: 1px solid var(--chart-1); }
	.guide { position: absolute; inset-block: calc(0px - var(--space-2)); border-inline-start: 1px solid var(--color-rule); }
	.total { text-align: end; font-size: var(--text-sm); white-space: nowrap; }
	summary { font-size: var(--text-sm); cursor: pointer; }
</style>
