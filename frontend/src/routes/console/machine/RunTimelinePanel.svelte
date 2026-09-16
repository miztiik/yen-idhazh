<script lang="ts">
	/** Where one run's time went, item by item, on a real clock.
	 *
	 * **A row is one item and the x axis is elapsed time.** An item that waited
	 * forty seconds for a worker sits forty seconds to the right, so the queue is
	 * the first thing a reader sees: a wide staircase is a run that queued, a solid
	 * block is a run that worked in parallel, and the shape is legible before a
	 * single number is. The panel beside this one folds the same seconds per SHARD;
	 * this is the only surface that can say WHICH article was being read.
	 *
	 * **Eight steps, eight ramp stops, fixed by position.** A step keeps its colour
	 * whether or not the run timed it, so two runs drawn a day apart compare by
	 * eye. The ramp deliberately holds none of the confidence hues, so no step is
	 * ever told by its colour that it is the failing one.
	 *
	 * **The residual is drawn hollow and never tinted**, the ruling `SpanPanel`
	 * made for the shard. Nobody has agreed how much overhead is too much, so a
	 * colour would publish an alarm that does not exist. It is signed, and the
	 * sign changes the drawing rather than the colour: positive, it is a hollow
	 * slice extending the bar to the item's full clock; negative, the steps have
	 * already outrun the clock, and the hatched notch covers the stretch that is
	 * counted twice. The known cause is real rather than hypothetical - the visual
	 * plan is decoded inside the summary call, so it is apportioned out of it
	 * rather than timed beside it - and clamping the sign away would delete the
	 * only signal that says so.
	 *
	 * Hand-written markup, not a chart: every mark is in the document before a
	 * script runs and stays there if none ever does.
	 */
	import { seconds } from '$lib/charts/machine';
	import type { RunTimelineView } from '$lib/server/run-timeline';

	let { view }: { view: RunTimelineView } = $props();

	/** Milliseconds as the same seconds string the rest of the route uses. */
	const secs = (ms: number): string => seconds(ms / 1000);

	/** Signed seconds, so an overrun reads as one rather than as a plain figure. */
	const signed = (ms: number): string => (ms < 0 ? `-${secs(-ms)}` : secs(ms));

	/** How many shards were busy on average across the run's span.
	 *
	 * Work divided by span. One means a queue - one item at a time, whatever the
	 * shard count says - and four means four shards were genuinely busy together.
	 * It is the one number that says whether the shape is a staircase or a block.
	 */
	const abreast = $derived(view.spanMs > 0 ? (view.workMs / view.spanMs).toFixed(1) : '0.0');

	/** Few enough bars to carry their own item id, or too many for anything but shape. */
	const labelled = $derived(view.bars.length <= 24);

	/** A step column as the word the panel prints. `summary_ms` is not a word. */
	const plain = (step: string): string => step.replace(/_ms$/, '').replace(/_/g, ' ');

	/** A list of names as a sentence: `a`, `a and b`, `a, b and c`. */
	const listed = (steps: readonly string[]): string => {
		const words = steps.map(plain);
		if (words.length <= 1) return words.join('');
		return `${words.slice(0, -1).join(', ')} and ${words.at(-1)}`;
	};
</script>

<div
	class="timeline"
	class:dense={!labelled}
	data-run-timeline={view.empty ? 'empty' : view.runId}
	data-timeline-items={view.itemCount}
	data-timeline-drawn={view.drawn.join(' ')}
	data-timeline-unproduced={view.unproduced.join(' ')}
	data-timeline-unrecorded={view.unrecorded.join(' ')}
	data-timeline-span-ms={view.spanMs}
	data-timeline-work-ms={view.workMs}
	data-timeline-overruns={view.overrunCount}
	data-timeline-density={labelled ? 'labelled' : 'dense'}
	data-readout-none="one bar an item, placed on the run's own clock"
>
	{#if view.empty}
		<p class="note" data-run-timeline-empty>
			No run has published an item timeline yet. A bar needs the moment an item started and what
			it cost, and a run that recorded neither has nothing to place on a clock - which is a
			record that has not begun, not a run that did no work.
		</p>
	{:else}
		<dl class="headline">
			<div>
				<dt>The run took</dt>
				<dd class="figure tabular-nums" data-timeline-figure="span">{secs(view.spanMs)}</dd>
				<dd class="under">first item picked up to last item finished</dd>
			</div>
			<div>
				<dt>Its items cost</dt>
				<dd class="figure tabular-nums" data-timeline-figure="work">{secs(view.workMs)}</dd>
				<dd class="under">every bar added up, waits excluded</dd>
			</div>
			<div>
				<dt>Items at once</dt>
				<dd class="figure tabular-nums" data-timeline-figure="abreast">{abreast}</dd>
				<dd class="under">
					work over span. Under one means the shards had idle stretches; one is a queue however
					many ran, and {view.shards.length} would be all {view.shards.length} busy throughout
				</dd>
			</div>
		</dl>

		<p class="note">
			Run <strong>{view.runId}</strong> on {view.date}: {view.itemCount}
			{view.itemCount === 1 ? 'item' : 'items'} across {view.shards.length}
			{view.shards.length === 1 ? 'shard' : 'shards'}. Each bar is one item, placed where its own
			work began and split into the steps that timed themselves. Two bars may overlap - that is
			two shards working at once, which is why each bar names its shard.
			{#if view.bars.length < view.itemCount}
				The {view.bars.length} earliest are drawn; the other {view.itemCount - view.bars.length} carry
				the same shape and every figure above counts all {view.itemCount}.
			{/if}
		</p>

		<ul class="legend">
			{#each view.legend as step (step.name)}
				<li><span class="key" style="background: var(--chart-{step.stop})"></span>{step.label}</li>
			{/each}
			<li><span class="key residual"></span>time no step accounts for</li>
			{#if view.overrunCount > 0}
				<li><span class="key overrun"></span>counted twice</li>
			{/if}
		</ul>

		<div class="axis" aria-hidden="true">
			{#each view.ticks as tick (tick.at)}
				<span class="tick tabular-nums" style="inset-inline-start: {tick.at}">{secs(tick.ms)}</span>
			{/each}
		</div>

		<ol class="bars">
			{#each view.bars as bar (bar.itemId)}
				<li
					class="bar"
					data-timeline-bar={bar.itemId}
					data-timeline-shard={bar.shard}
					data-timeline-start-ms={bar.startOffsetMs}
					data-timeline-total-ms={bar.totalMs}
					data-timeline-residual-ms={bar.residualMs}
					data-timeline-residual-sign={bar.residualMs < 0 ? 'negative' : 'positive'}
				>
					<span class="gutter tabular-nums">
						<span class="shard">{bar.shard}</span>
						{#if labelled}<span class="item">{bar.itemId}</span>{/if}
					</span>
					<span
						class="track"
						role="img"
						aria-label="{bar.itemId} on shard {bar.shard} began {secs(
							bar.startOffsetMs
						)} into the run and took {secs(bar.totalMs)}, of which {signed(
							bar.residualMs
						)} is in no named step."
					>
						<span class="lead" style="inline-size: {bar.offset}"></span>
						{#each bar.segments as segment (segment.name)}
							<span
								class="seg"
								data-timeline-seg={segment.name}
								data-timeline-seg-ms={segment.ms}
								style="inline-size: {segment.width}; background: var(--chart-{segment.stop})"
							></span>
						{/each}
						{#if bar.residualWidth}
							<span
								class="seg residual"
								data-timeline-seg="residual"
								data-timeline-seg-ms={bar.residualMs}
								style="inline-size: {bar.residualWidth}"
							></span>
						{/if}
						{#if bar.overrunWidth}
							<span
								class="overrun"
								data-timeline-seg="overrun"
								data-timeline-seg-ms={-bar.residualMs}
								style="inset-inline-start: {bar.overrunOffset}; inline-size: {bar.overrunWidth}"
							></span>
						{/if}
					</span>
					<span class="total tabular-nums">{secs(bar.totalMs)}</span>
				</li>
			{/each}
		</ol>

		<p class="note residual-note" data-timeline-residual-note>
			<strong>{signed(view.residualMs)}</strong> of this run's item time sits in no named step -
			that is the hollow slice at the end of each bar, and it is drawn and never tinted because
			nobody has agreed how much overhead is too much.
			{#if view.unproduced.length > 0}
				Nothing in the pipeline times {listed(view.unproduced)} yet, so whatever those steps cost is
				inside that slice rather than beside it.
			{/if}
			{#if view.unrecorded.length > 0}
				No bar of this run recorded {listed(view.unrecorded)}, which is a gap in what this run wrote
				down rather than a step that took no time.
			{/if}
			{#if view.overrunCount > 0}
				{view.overrunCount}
				{view.overrunCount === 1 ? 'bar overruns its' : 'bars overrun their'} own clock, hatched at
				the end: the visual plan is decoded inside the summary call, so it is apportioned out of it
				rather than timed beside it and the two together count part of one call twice.
			{/if}
		</p>
	{/if}
</div>

<style>
	.timeline {
		--timeline-gutter: 9.5rem;
		--timeline-tail: 3.25rem;
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}
	.timeline.dense {
		--timeline-gutter: 2rem;
	}

	.note {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}
	.note strong {
		color: var(--color-text-secondary);
	}

	/* The three figures that answer the panel's question before any bar is read.
	   One thing lands first, and it is the shape of the run rather than an item. */
	.headline {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
		gap: var(--space-2) var(--space-5);
		margin: 0;
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface-sunken);
	}
	.headline dt {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-tertiary);
	}
	.headline dd {
		margin: 0;
	}
	.headline .figure {
		font-size: var(--text-2xl);
		line-height: var(--leading-2xl);
		font-weight: 600;
		color: var(--color-text);
	}
	.headline .under {
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
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
	.key {
		display: inline-block;
		inline-size: 0.75rem;
		block-size: 0.75rem;
		border-radius: var(--radius-sm);
		flex: none;
	}
	/* Hollow, never tinted: the time nothing filled reads as an outline and not as
	   one more coloured step. */
	.key.residual,
	.seg.residual {
		background: var(--color-surface);
		box-shadow: inset 0 0 0 1.5px var(--color-text-tertiary);
	}
	.key.overrun {
		background: var(--color-surface);
		box-shadow: inset 0 0 0 1.5px var(--color-text-tertiary);
		background-image: repeating-linear-gradient(
			45deg,
			transparent 0 3px,
			var(--color-text-tertiary) 3px 4px
		);
	}

	/* The clock. The label strip spans exactly the tracks under it - the gutter and
	   the trailing figure are taken out on both sides, gaps included - so a bar's
	   position is read against a scale rather than guessed. */
	.axis {
		position: relative;
		margin-inline-start: calc(var(--timeline-gutter) + var(--space-2));
		margin-inline-end: calc(var(--timeline-tail) + var(--space-2));
		block-size: 1.1rem;
		border-block-end: 1px solid var(--color-rule);
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}
	.tick {
		position: absolute;
		inset-block-end: 0.15rem;
		transform: translateX(-50%);
		white-space: nowrap;
	}
	.tick:first-child {
		transform: none;
	}
	.tick:last-child {
		transform: translateX(-100%);
	}

	.bars {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.dense .bars {
		gap: 0.125rem;
	}

	.bar {
		display: grid;
		grid-template-columns: var(--timeline-gutter) 1fr var(--timeline-tail);
		align-items: center;
		gap: var(--space-2);
	}

	.gutter {
		display: flex;
		align-items: baseline;
		gap: var(--space-1);
		min-inline-size: 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}
	.gutter .shard {
		flex: none;
		inline-size: 1rem;
		text-align: end;
		color: var(--color-text-secondary);
	}
	.gutter .item {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.track {
		position: relative;
		display: flex;
		inline-size: 100%;
		block-size: 0.9rem;
		border-radius: var(--radius-sm);
		background: var(--color-surface-sunken);
		box-shadow: inset 0 0 0 1px var(--color-rule);
	}
	.dense .track {
		block-size: 0.55rem;
	}	/* The wait is position, never length: nothing is drawn in front of the bar. */
	.lead {
		flex: none;
		block-size: 100%;
	}
	.seg {
		flex: none;
		block-size: 100%;
	}
	.seg:first-of-type {
		border-start-start-radius: var(--radius-sm);
		border-end-start-radius: var(--radius-sm);
	}
	.seg:last-of-type {
		border-start-end-radius: var(--radius-sm);
		border-end-end-radius: var(--radius-sm);
	}
	/* The overrun sits ON the drawing rather than after it, because the stretch it
	   covers is time already drawn once by the step that claimed it. */
	.overrun {
		position: absolute;
		inset-block: 0;
		border-radius: var(--radius-sm);
		box-shadow: inset 0 0 0 1.5px var(--color-text-tertiary);
		background-image: repeating-linear-gradient(
			45deg,
			transparent 0 3px,
			var(--color-text-tertiary) 3px 4px
		);
	}

	.total {
		font-size: var(--text-xs);
		text-align: end;
		color: var(--color-text-tertiary);
	}

	.residual-note {
		font-size: var(--text-xs);
	}

	/* One column on a phone: the gutter and the trailing figure both cost width a
	   bar needs, and the bar is the point. */
	@media (max-width: 40rem) {
		.timeline,
		.timeline.dense {
			--timeline-gutter: 2rem;
			--timeline-tail: 0rem;
		}
		.bar {
			grid-template-columns: var(--timeline-gutter) 1fr;
		}
		.bar .total {
			display: none;
		}
		.axis {
			margin-inline-end: 0;
		}
		.gutter .item {
			display: none;
		}
	}
</style>
