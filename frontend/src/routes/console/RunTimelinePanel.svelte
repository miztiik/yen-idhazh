<script lang="ts">
	/** Where one run's time went, on a real clock, at the grain the reader picks.
	 *
	 * **A row is one item or one shard, and the x axis is elapsed time.** An item
	 * that waited forty seconds for a worker sits forty seconds to the right, so
	 * the queue is the first thing a reader sees: a wide staircase is a run that
	 * queued, a solid block is a run that worked in parallel, and the shape is
	 * legible before a single number is.
	 *
	 * **This panel answers "is it working".** It takes the run's central shape -
	 * how long it took, what its items cost, how many ran at once - and it covers
	 * every item of the run rather than picking the worst one out. The grain
	 * switch changes the row, never the question.
	 *
	 * **One fold, two grains.** A second panel drew the shard grain from a second
	 * ledger until 2026-09-20, and the two could name different runs as the newest
	 * because they read different files. Both grains now come out of one builder
	 * call over one set of rows, so a step's seconds are the same seconds
	 * whichever row a reader is on.
	 *
	 * **Eight steps, eight ramp stops, fixed by position.** A step keeps its colour
	 * whether or not the run timed it, so two runs drawn a day apart compare by
	 * eye. The ramp deliberately holds none of the confidence hues, so no step is
	 * ever told by its colour that it is the failing one.
	 *
	 * **Hollow is unclaimed and hatched is overclaimed**, and both carry a legend
	 * key, because the owner could not name the hatched notch on sight. The
	 * residual is signed and the sign changes the drawing rather than the colour:
	 * positive, a hollow slice extends the bar to its full clock; negative, the
	 * steps have already outrun the clock and the hatched notch covers the stretch
	 * counted twice. Neither is tinted - nobody has agreed how much overhead is
	 * too much, so a colour would publish an alarm that does not exist.
	 *
	 * **The four sub-steps are figures and never bands.** Measured over the
	 * committed rollup they draw far under one pixel of the track, and a band that
	 * small is a legend entry with no mark. They are printed under the bars with
	 * the step each one runs inside, so nobody reads `tag read` as a step beside
	 * taking the article out.
	 *
	 * Hand-written markup, not a chart: every mark is in the document before a
	 * script runs and stays there if none ever does.
	 */
	import ShapeSwitch from '$lib/components/ShapeSwitch.svelte';
	import { seconds } from '$lib/charts/machine';
	import type { RunTimelineView, TimelineBar } from '$lib/server/run-timeline';
	import type { SubStepReadout } from '$lib/server/span-rollup';

	let { view, subSteps }: { view: RunTimelineView; subSteps: SubStepReadout } = $props();

	/** The three rows this panel can draw, out of the one fold that built them. */
	type Grain = 'item' | 'by-shard' | 'shard';

	const GRAINS: { value: Grain; text: string }[] = [
		{ value: 'item', text: 'Item' },
		{ value: 'by-shard', text: 'By shard' },
		{ value: 'shard', text: 'Shard' }
	];

	let grain = $state<Grain>('item');

	/** The bars in the order this grain reads them. The by-shard order is indices
	 * into the same array, never a second copy: the builder decided the order and
	 * the component only follows it. */
	const drawn = $derived<TimelineBar[]>(
		grain === 'shard'
			? view.shardBars
			: grain === 'by-shard'
				? view.shardOrder.map((at) => view.bars[at])
				: view.bars
	);

	/** Milliseconds as the same seconds string the rest of the console uses. */
	const secs = (ms: number): string => seconds(ms / 1000);

	/** Signed seconds, so an overrun reads as one rather than as a plain figure. */
	const signed = (ms: number): string => (ms < 0 ? `-${secs(-ms)}` : secs(ms));

	/** A sub-step figure is milliseconds, and the seconds clock rounds it to zero.
	 * Eleven milliseconds is a measurement; `0.0 s` is a misprint. */
	const small = (ms: number): string => (ms < 1000 ? `${Math.round(ms)} ms` : secs(ms));

	/** How many shards were busy on average across the run's span.
	 *
	 * Work divided by span. One means a queue - one item at a time, whatever the
	 * shard count says - and four means four shards were genuinely busy together.
	 * It is the one number that says whether the shape is a staircase or a block.
	 */
	const abreast = $derived(view.spanMs > 0 ? (view.workMs / view.spanMs).toFixed(1) : '0.0');

	/** Few enough bars to carry their own id, or too many for anything but shape.
	 * A shard grain is never dense - there are four of them. */
	const labelled = $derived(grain === 'shard' || drawn.length <= 24);

	/** The residual this grain adds up to. Both totals are the builder's, because
	 * the drawn item bars are capped and a sum over them would under-report. */
	const residualTotal = $derived(grain === 'shard' ? view.shardResidualMs : view.residualMs);

	/** A step column as the word the panel prints. `summary_ms` is not a word. */
	const plain = (step: string): string => step.replace(/_ms$/, '').replace(/_/g, ' ');

	/** A list of names as a sentence: `a`, `a and b`, `a, b and c`. */
	const listed = (steps: readonly string[]): string => {
		const words = steps.map(plain);
		if (words.length <= 1) return words.join('');
		return `${words.slice(0, -1).join(', ')} and ${words.at(-1)}`;
	};

	/** What a bar says to a pointer. Never the only carrier of any of it: every
	 * figure here is printed beside the bar or in the readout under it. */
	const hovered = (bar: TimelineBar): string =>
		grain === 'shard'
			? `${bar.label}: ${bar.itemCount} ${bar.itemCount === 1 ? 'item' : 'items'}, held a worker ${secs(bar.totalMs)} from ${secs(bar.startOffsetMs)} into the run, ${secs(bar.workMs)} of it inside items, ${signed(bar.residualMs)} in no named step.`
			: `${bar.label} on shard ${bar.shard}: began ${secs(bar.startOffsetMs)} into the run, took ${secs(bar.totalMs)}, ${signed(bar.residualMs)} of it in no named step.`;
</script>

<div
	class="timeline"
	class:dense={!labelled}
	data-run-timeline={view.empty ? 'empty' : view.runId}
	data-timeline-grain={grain}
	data-timeline-items={view.itemCount}
	data-timeline-shards={view.shards.join(' ')}
	data-timeline-drawn={view.drawn.join(' ')}
	data-timeline-unproduced={view.unproduced.join(' ')}
	data-timeline-unrecorded={view.unrecorded.join(' ')}
	data-timeline-span-ms={view.spanMs}
	data-timeline-work-ms={view.workMs}
	data-timeline-residual-ms={view.residualMs}
	data-timeline-shard-residual-ms={view.shardResidualMs}
	data-timeline-overruns={view.overrunCount}
	data-timeline-density={labelled ? 'labelled' : 'dense'}
	data-panel-question="is it working"
	data-readout-none="one bar a row, placed on the run's own clock, with every figure printed beside it"
>
	{#if view.empty}
		<p class="note" data-run-timeline-empty>
			No run has published an item timeline yet. A bar needs the moment an item started and what
			it cost, and a run that recorded neither has nothing to place on a clock - which is a
			record that has not begun, not a run that did no work.
		</p>
	{:else}
		<!-- Top right of its own panel, and radio inputs: three named states a
		     reader can see all of beat one state and a verb. The control belongs
		     to the panel rather than to the page. -->
		<div class="grains">
			<ShapeSwitch
				bind:shape={grain}
				name="timeline-grain"
				label="Which grain to draw"
				options={GRAINS}
			/>
		</div>

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
			{view.shards.length === 1 ? 'shard' : 'shards'}.
			{#if grain === 'shard'}
				One bar a shard, from its first item's start to its last item's end - the stretch it held
				a worker for. Its steps are that shard's items added up, so the same seconds are drawn
				here and at the item grain.
			{:else if grain === 'by-shard'}
				One bar an item, grouped by the shard that ran it and then by start, so one worker's
				stretch reads contiguously instead of being picked out of the run's queue.
			{:else}
				One bar an item, in start order, placed where its own work began and split into the steps
				that timed themselves. Two bars may overlap - that is two shards working at once, which
				is why each bar names its shard.
			{/if}
			{#if grain !== 'shard' && view.bars.length < view.itemCount}
				The {view.bars.length} earliest are drawn; the other {view.itemCount - view.bars.length} carry
				the same shape and every figure above counts all {view.itemCount}.
			{/if}
		</p>

		<ul class="legend">
			{#each view.legend as step (step.name)}
				<li><span class="key" style="background: var(--chart-{step.stop})"></span>{step.label}</li>
			{/each}
			<li><span class="key residual"></span>unclaimed - no named step accounts for it</li>
			{#if view.overrunCount > 0}
				<li><span class="key overrun"></span>overclaimed - two steps counted over it</li>
			{/if}
		</ul>

		<div class="axis" aria-hidden="true">
			{#each view.ticks as tick (tick.at)}
				<span class="tick tabular-nums" style="inset-inline-start: {tick.at}">{secs(tick.ms)}</span>
			{/each}
		</div>

		<ol class="bars">
			{#each drawn as bar (bar.id)}
				<li
					class="bar"
					data-timeline-bar={bar.id}
					data-timeline-shard={bar.shard}
					data-timeline-start-ms={bar.startOffsetMs}
					data-timeline-total-ms={bar.totalMs}
					data-timeline-bar-work-ms={bar.workMs}
					data-timeline-bar-items={bar.itemCount}
					data-timeline-residual-ms={bar.residualMs}
					data-timeline-residual-sign={bar.residualMs < 0 ? 'negative' : 'positive'}
				>
					<span class="gutter tabular-nums">
						<span class="shard">{bar.shard}</span>
						{#if labelled && grain !== 'shard'}<span class="item">{bar.label}</span>{/if}
					</span>
					<span class="track" role="img" title={hovered(bar)} aria-label={hovered(bar)}>
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
			<strong>{signed(residualTotal)}</strong>
			{#if grain === 'shard'}
				of the shards' stretches sits in no named step - that is the hollow slice at the end of
				each bar, and at this grain it holds the time between items as well as the time inside
				one that nothing timed.
			{:else}
				of this run's item time sits in no named step - that is the hollow slice at the end of
				each bar, and it is drawn and never tinted because nobody has agreed how much overhead is
				too much.
			{/if}
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

	<!-- The four steps inside those steps, printed. They read their own ledger, so
	     they are often a different run from the bars above and they say which. -->
	<div
		class="substeps"
		data-substeps={subSteps.empty ? 'empty' : subSteps.runId}
		data-substep-printed={String(subSteps.printed)}
		data-substep-smallest-px={subSteps.smallestPx.toFixed(3)}
		data-substep-track-px={subSteps.trackPx}
		data-substep-named-ms={subSteps.namedMs}
		data-substep-item-ms={subSteps.itemMs}
		data-substep-residual-ms={subSteps.residualMs ?? ''}
		data-substep-wall-ms={subSteps.wallMs}
	>
		{#if subSteps.empty}
			<p class="note" data-substeps-empty>
				No traced run has folded its spans yet, so the four steps inside the steps are unmeasured.
				The span record starts <strong>{subSteps.recordStarts}</strong>: before it a run timed its
				stages but never committed them. That is a record that has not begun, not a run that did
				no work.
			</p>
		{:else}
			<p class="substep-head">
				Steps inside those steps - run <strong>{subSteps.runId}</strong> on {subSteps.date},
				{subSteps.shardCount}
				{subSteps.shardCount === 1 ? 'shard' : 'shards'}
			</p>
			<ul class="figures">
				{#each subSteps.steps as step (step.name)}
					<li
						data-substep={step.name}
						data-substep-ms={step.ms}
						data-substep-px={step.px.toFixed(3)}
					>
						<span class="figure tabular-nums">{small(step.ms)}</span>
						<span class="what">{step.label}</span>
						<span class="inside">{step.inside}</span>
					</li>
				{/each}
			</ul>
			<p class="note" data-substep-note>
				{#if subSteps.printed}
					These are printed rather than drawn. Together they are {small(subSteps.namedMs)} of the
					run's {secs(subSteps.itemMs)} of item time, and the narrowest would paint
					{subSteps.smallestPx.toFixed(3)} px of a {subSteps.trackPx} px track - which a browser
					does not paint at all. A band that small is a legend entry with no mark, and it teaches
					a reader the step is zero when it is only unmeasurable at this scale.
				{:else}
					Together they are {small(subSteps.namedMs)} of the run's {secs(subSteps.itemMs)} of item
					time, and the narrowest would paint {subSteps.smallestPx.toFixed(3)} px of a
					{subSteps.trackPx} px track. They are printed rather than drawn anyway, because each is
					already inside a band the bars draw and a second mark for the same seconds is the same
					seconds counted twice.
				{/if}
				Each runs inside a step already drawn above, so adding one to that step counts it twice.
				{#if subSteps.residualMs === null}
					No shard of this run recorded what fell outside its items, so the overhead is a missing
					reading rather than an overhead of nothing.
				{:else}
					{small(subSteps.residualMs)} fell outside every item - model load, file writes,
					scheduling - which with the item time is the shards' whole clock, {secs(
						subSteps.wallMs
					)}.
				{/if}
			</p>
		{/if}
	</div>
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

	/* The control belongs to the panel, so it sits in the panel's own top right
	   rather than anywhere on the page. */
	.grains {
		display: flex;
		justify-content: flex-end;
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
	}
	/* The wait is position, never length: nothing is drawn in front of the bar. */
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

	/* The sub-steps are a readout, not a plot: they sit under the bars, ruled off,
	   because they are the same seconds at a grain no track can paint. */
	.substeps {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		padding-block-start: var(--space-3);
		border-block-start: 1px solid var(--color-rule);
	}
	.substep-head {
		margin: 0;
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-tertiary);
	}
	.substep-head strong {
		text-transform: none;
		letter-spacing: normal;
		color: var(--color-text-secondary);
	}
	.figures {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
		gap: var(--space-2) var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.figures li {
		display: flex;
		flex-direction: column;
	}
	.figures .figure {
		font-size: var(--text-lg);
		line-height: var(--leading-lg);
		font-weight: 600;
		color: var(--color-text);
	}
	.figures .what {
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}
	.figures .inside {
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
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
