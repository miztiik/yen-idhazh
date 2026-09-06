<script lang="ts">
	/** Where one run's shards spent their seconds, and how many nobody could name.
	 *
	 * The pipeline commits, per shard, the time inside its items and four
	 * sub-steps that no ledger column separates - `robots`, `tag`, `render_prompt`
	 * and `parse_reply` - plus one figure that is the whole reason this panel
	 * exists: `unattributed_ms`, the shard's wall clock minus the time inside its
	 * items. That residual is the overhead between and around items - model load,
	 * file writes, scheduling - that no span covers, and until it was drawn nothing
	 * on this site could say a slow shard was slow because it did a lot or because
	 * it spent its clock waiting.
	 *
	 * **The residual is drawn beside the work, never inside it.** Each shard is one
	 * bar of its whole clock: the coloured slices are time inside items, and the
	 * hollow slice on the right is the overhead outside them. The two together are
	 * the shard's wall clock exactly - `item.total_ms + unattributed_ms` - so a
	 * reader can see at a glance how much of a shard's time went to work nobody
	 * asked for.
	 *
	 * **No band and no threshold.** Nobody has agreed how much overhead is too
	 * much, so the residual is drawn and named and never tinted. A colour would
	 * publish an alarm that does not exist.
	 *
	 * Hand-written markup, not a chart: every mark is in the document before a
	 * script runs and stays there if none ever does, and the numbers are printed
	 * beside the bars so the panel reads with no colour at all.
	 */
	import { seconds } from '$lib/charts/machine';
	import type { SpanBreakdown } from '$lib/server/span-rollup';

	let { breakdown }: { breakdown: SpanBreakdown } = $props();

	/** Milliseconds as the same seconds string the rest of the route uses. */
	const secs = (ms: number | null): string => (ms === null ? '-' : seconds(ms / 1000));
</script>

<div
	class="spans"
	data-span-board={breakdown.empty ? 'empty' : breakdown.runId}
	data-span-record-starts={breakdown.recordStarts}
	data-readout-none="one bar a shard, and every slice's time is printed beside it"
>
	{#if breakdown.empty}
		<p class="span-note" data-span-board-empty>
			No traced run has folded its spans yet. The span record starts
			<strong>{breakdown.recordStarts}</strong>: before it a run timed its stages but never
			committed them, so there is nothing to draw for an earlier day. This is a record that has not
			begun, not a run that did no work.
		</p>
	{:else}
		<p class="span-note">
			Run <strong>{breakdown.runId}</strong> on {breakdown.date},
			{breakdown.shards.length}
			{breakdown.shards.length === 1 ? 'shard' : 'shards'}. Each bar is one shard's whole clock: the
			sub-steps no ledger column times, the rest of the item work, and the overhead between items on
			the right. Bars share one scale - the widest stands for {secs(breakdown.scaleMs)}. The span
			record starts {breakdown.recordStarts}.
		</p>

		<ul class="legend" aria-hidden="true">
			<li><span class="key robots"></span>robots check</li>
			<li><span class="key tag"></span>tag read</li>
			<li><span class="key render_prompt"></span>prompt build</li>
			<li><span class="key parse_reply"></span>reply parse</li>
			<li><span class="key other"></span>the rest of the item time</li>
			<li><span class="key residual"></span>overhead between items</li>
		</ul>

		{#each breakdown.shards as shard (shard.shard)}
			<div
				class="row"
				data-span-shard={shard.shard}
				data-span-wall-ms={shard.wallMs}
				data-span-item-ms={shard.itemMs}
				data-span-residual-ms={shard.residualMs ?? ''}
			>
				<p class="shard-label">
					<span class="name">Shard {shard.shard}</span>
					<span class="wall tabular-nums"
						>{secs(shard.wallMs)} over {shard.itemCount}
						{shard.itemCount === 1 ? 'item' : 'items'}</span
					>
				</p>

				<div
					class="track"
					role="img"
					aria-label={shard.residualMs === null
						? `Shard ${shard.shard} timed ${secs(shard.itemMs)} inside its items; its overhead was not recorded.`
						: `Shard ${shard.shard} ran ${secs(shard.wallMs)}, of which ${secs(
								shard.residualMs
							)}, ${shard.residualPct} percent, was overhead outside every item.`}
				>
					{#each shard.segments as segment (segment.kind)}
						<span
							class="seg {segment.kind}"
							data-span-seg={segment.kind}
							data-span-seg-ms={segment.ms}
							style="inline-size: {segment.width}"
						></span>
					{/each}
				</div>

				<p class="figures tabular-nums">
					{#each shard.segments as segment (segment.kind)}
						<span class="figure" data-span-figure={segment.kind}>
							<span class="swatch {segment.kind}" aria-hidden="true"></span>{segment.label}
							{secs(segment.ms)}
						</span>
					{/each}
				</p>

				{#if shard.residualMs === null}
					<p class="residual-note" data-span-residual-note="absent">
						This shard committed its stages before the overhead column existed, so its wall clock is
						unknown and no overhead is drawn - which is a missing reading, not a shard that wasted no
						time.
					</p>
				{:else}
					<p class="residual-note" data-span-residual-note>
						<strong>{shard.residualPct}%</strong> of this shard's clock - {secs(shard.residualMs)} -
						fell outside every item: model load, file writes, scheduling. Item time plus that
						overhead is the whole clock.
					</p>
				{/if}
			</div>
		{/each}
	{/if}
</div>

<style>
	.spans {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.span-note {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}
	.legend li {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
	}

	.key,
	.swatch {
		display: inline-block;
		inline-size: 0.75rem;
		block-size: 0.75rem;
		border-radius: var(--radius-sm);
		flex: none;
	}

	/* Coloured slices are time inside items. The four sub-steps carry the chart
	   hues, and the rest of the item time is one more hue beside them. */
	.robots {
		background: var(--chart-1);
	}
	.tag {
		background: var(--chart-2);
	}
	.render_prompt {
		background: var(--chart-3);
	}
	.parse_reply {
		background: var(--chart-4);
	}
	.other {
		background: var(--chart-5);
	}
	/* The overhead is drawn hollow: it is the time nothing filled, so it reads as
	   an outline and not as one more coloured stage. No tint - there is no agreed
	   threshold to colour it against. */
	.residual {
		background: var(--color-surface);
		box-shadow: inset 0 0 0 1.5px var(--color-text-tertiary);
	}

	.row {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.shard-label {
		display: flex;
		justify-content: space-between;
		gap: var(--space-2);
		margin: 0;
		font-size: var(--text-sm);
	}
	.shard-label .name {
		font-weight: 600;
		color: var(--color-text);
	}
	.shard-label .wall {
		color: var(--color-text-tertiary);
	}

	.track {
		display: flex;
		inline-size: 100%;
		block-size: 1.25rem;
		border-radius: var(--radius-sm);
		overflow: hidden;
		background: var(--color-surface-raised);
	}
	.seg {
		block-size: 100%;
	}
	.seg:first-child {
		border-start-start-radius: var(--radius-sm);
		border-end-start-radius: var(--radius-sm);
	}
	.seg:last-child {
		border-start-end-radius: var(--radius-sm);
		border-end-end-radius: var(--radius-sm);
	}

	.figures {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-3);
		margin: 0;
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}
	.figure {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
	}

	.residual-note {
		margin: 0;
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}
	.residual-note strong {
		color: var(--color-text-secondary);
	}
</style>
