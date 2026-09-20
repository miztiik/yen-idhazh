<script lang="ts">
	/** How near the runner's ceiling a run got - item, shard, and over the window.
	 *
	 * **One measurement, three grains, one panel.** The run's high-water mark used
	 * to be drawn twice: once as per-shard bars and once again as prose in the
	 * panel about what the server did outside the model call. The item's own
	 * high-water mark was drawn nowhere, and on the committed ledger one item took
	 * the model server to 83.1 percent of the runner's 16 GiB. A per-shard maximum
	 * is the verdict reading and hides the item that owns it, so the two questions
	 * are one panel with a grain switch rather than two panels and a paragraph.
	 *
	 * **This is a break panel.** It takes the extreme and the individual that owns
	 * it, and it covers every item of one run.
	 *
	 * **Machine load is the second series and not a second panel.** A one-minute
	 * load of 5.49 on four cores is a QUEUE, and processor busy runs near 100 on
	 * every row and carries no signal on its own. Busy and queued are different
	 * facts and neither implies the other, so both are drawn, beside the memory
	 * they explain.
	 *
	 * **What it cannot separate, it says.** Nothing here can tell which phase of
	 * the model call owns the peak - reading the prompt or writing the answer.
	 * That split needs an instrument nobody has built, and a memory panel silent
	 * about it invites the reader to assume it was separated.
	 */
	import ShapeSwitch from './ShapeSwitch.svelte';
	import TargetBar from './TargetBar.svelte';
	import {
		gib,
		RUNNER_MEMORY_BYTES,
		type MemoryBoardView,
		type MemoryGrain,
		type RangeMark
	} from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';

	let {
		board,
		span,
		windowDays
	}: {
		board: MemoryBoardView;
		/** The window's own low-to-high peak memory, already derived once per
		 * preset by the loader. The grain switch offers it rather than deriving a
		 * second copy: two derivations of one figure are what the one-builder rule
		 * exists to stop, and this panel makes none. */
		span: { low: number | null; high: number | null; from: number; outOf: number };
		windowDays: number;
	} = $props();

	let grain = $state<MemoryGrain>('item');

	const GRAINS: { value: MemoryGrain; text: string }[] = [
		{ value: 'item', text: 'Item' },
		{ value: 'shard', text: 'Shard' },
		{ value: 'span', text: 'Window' }
	];

	const worstItem = $derived(board.items.find((item) => item.worst) ?? null);

	/** The window grain's own domain. The panel's byte domain, widened where a
	 * run in the window reached further than anything this run drew - the limit
	 * joins the values rather than capping them, so a breach draws past the
	 * line. */
	const spanScale = $derived(Math.max(board.scaleBytes, span.high ?? 0));
	const along = (value: number | null) =>
		spanScale <= 0 || value === null ? 0 : Math.min(value / spanScale, 1) * 100;

	/** A range mark as a sentence, for the reader with no pointer. */
	function busyText(mark: RangeMark): string {
		if (mark.empty) return 'processor busy not recorded on this run';
		if (mark.median === null) return `${mark.max?.toFixed(2)}% busy at its peak, and no trough recorded`;
		if (mark.max === null) return `${mark.median.toFixed(2)}% busy at its trough, and no peak recorded`;
		return `${mark.median.toFixed(2)}% busy at its trough, ${mark.max.toFixed(2)}% at its peak`;
	}
</script>

<div
	class="memory-board"
	data-memory-board={board.empty ? 'empty' : board.runId}
	data-memory-grain={grain}
	data-memory-ceiling={board.ceilingBytes}
	data-memory-total-measured={board.measuredTotalBytes ?? ''}
	data-memory-totals-seen={board.totalsSeen.join(' ')}
	data-memory-total-agrees={board.totalAgrees === null ? '' : String(board.totalAgrees)}
	data-memory-item-high-water={board.itemHighWater ?? ''}
	data-memory-worst-item={board.worstItemId ?? ''}
	data-memory-worker-high-water={board.workerHighWater ?? ''}
	data-memory-both-high-water={board.bothHighWater ?? ''}
	data-memory-co-peak={String(board.coPeak)}
	data-memory-items={board.from}
	data-memory-items-planned={board.outOf ?? ''}
	data-memory-load-high={board.loadHigh ?? ''}
	data-memory-cores={board.cores ?? ''}
	data-memory-busy-low={board.busySpan.median ?? ''}
	data-memory-busy-high={board.busySpan.max ?? ''}
	data-panel-question="what is broken"
	data-readout-none="every figure drawn here is printed beside its own track"
>
	{#if board.empty}
		<p class="note" data-memory-board-empty="all">
			No run in this span recorded what it did to the machine's memory. That is a measurement
			that did not survive, not a run that used none.
		</p>
	{:else}
		<!-- Top right of its own panel, and radio inputs: three named states a
		     reader can see all of beat one state and a verb. The same control the
		     shape switches use, because a second switch shape would be a pile. -->
		<div class="grains">
			<ShapeSwitch
				bind:shape={grain}
				name="memory-grain"
				label="Which grain to draw"
				options={GRAINS}
			/>
		</div>

		<p class="note">
			Run <strong>{board.runId}</strong> on {board.date}.
			{#if board.outOf === null}
				{grouped(board.from)}
				{board.from === 1 ? 'item' : 'items'} carried a memory reading; the run's shards recorded
				no item count, so how many did not is unknown rather than none.
			{:else}
				{grouped(board.from)} of the run's {grouped(board.outOf)} items carried a memory reading.
				{#if board.from < board.outOf}
					The other {grouped(board.outOf - board.from)} recorded nothing, and are left out rather
					than drawn as items that used no memory.
				{/if}
			{/if}
		</p>

		<!-- The denominator, and the one cell that can say the other five are
		     about a different machine. `/proc/meminfo` is not namespaced, so
		     inside a container MemTotal reports the host. -->
		<p class="note" data-memory-denominator>
			{#if board.measuredTotalBytes === null}
				No item recorded what the machine has, so every figure here is drawn against the
				runner's own {gib(board.ceilingBytes)} rather than against a memory total this run
				measured.
			{:else if board.totalAgrees === false}
				<strong
					>The machine reported {gib(board.measuredTotalBytes)} of memory, which is not the
					runner's {gib(RUNNER_MEMORY_BYTES)}.</strong
				>
				`/proc/meminfo` is not namespaced, so inside a container it reports the host. Every
				figure built on those cells is about that machine and not about this job.
			{:else}
				Drawn against {gib(board.ceilingBytes)}, which is what this run's own machine reported
				it has.
			{/if}
			{#if board.totalsSeen.length > 1}
				This run drew {board.totalsSeen.length} machine sizes - {board.totalsSeen
					.map(gib)
					.join(' and ')}. The smaller is the denominator, because the smaller is the one that
				could have run out.
			{/if}
		</p>

		{#if grain === 'item'}
			<div class="grain" data-memory-pane="item">
				{#if board.itemsEmpty}
					<p class="note absent" data-memory-board-empty="item">
						No item of this run recorded what it held or what it left the kernel. The cells
						landed later than this run, so it reports nothing here - which is a missing
						reading and not an item that used no memory.
					</p>
				{:else}
					<!-- Three tracks, one x. The two byte tracks share one domain so
					     their lengths compare; load is not bytes, so it takes its own
					     row on the same x rather than a second axis on the same plot. -->
					<p class="track-name" id="held-name">
						What the model server held, item by item in run order
					</p>
					<div class="strip" role="img" aria-labelledby="held-name">
						{#each board.items as item (item.itemId)}
							<span
								class="mark"
								class:worst={item.worst}
								data-memory-item={item.itemId}
								data-memory-item-shard={item.shard}
								data-memory-item-peak={item.peakBytes ?? ''}
								data-memory-item-worker={item.workerBytes ?? ''}
								data-memory-item-floor={item.headroom.floorBytes ?? ''}
								data-memory-item-end={item.headroom.endBytes ?? ''}
								data-memory-item-recovered={item.headroom.recoveredBytes ?? ''}
								data-memory-item-load={item.load ?? ''}
								data-memory-item-worst={String(item.worst)}
								title="{item.itemId}: {item.peakBytes === null
									? 'no memory reading'
									: `${gib(item.peakBytes)} held by the model server`}{item.headroom.empty
									? ''
									: `, ${gib(item.headroom.floorBytes)} left at its worst and ${gib(
											item.headroom.endBytes
										)} when it ended`}."
							>
								{#if item.peakBytes === null}
									<span class="bar absent-bar"></span>
								{:else}
									<span class="bar held" style="block-size: {item.peakWidth}"></span>
								{/if}
							</span>
						{/each}
					</div>

					<p class="track-name" id="left-name">What the kernel had left: worst, then at the end</p>
					{#if board.headroomFrom === 0}
						<p class="note absent" data-memory-track-empty="headroom">
							No item of this run recorded what the kernel had left. A resident-set mark says
							what a process held; it does not say what was still free, and this run measured
							only the first.
						</p>
					{:else}
						<div class="strip" role="img" aria-labelledby="left-name">
							{#each board.items as item (item.itemId)}
								<span class="mark" class:worst={item.worst}>
									{#if item.headroom.empty}
										<span class="bar absent-bar"></span>
									{:else}
										<span class="bar floor" style="block-size: {item.headroom.floorWidth}"></span>
										{#if item.headroom.endBytes !== null}
											<span class="notch" style="inset-block-end: {item.headroom.endWidth}"></span>
										{/if}
									{/if}
								</span>
							{/each}
						</div>
						<span class="unit">
							The bar is the least the kernel had while the model worked; the notch is what the
							item left when it ended. A bar that falls with a notch that stays down is a leak;
							one that falls with a notch above it was working hard.
						</span>
					{/if}

					<p class="track-name" id="load-name">
						The queue when each item ended{board.cores === null
							? ''
							: `, against ${board.cores} ${board.cores === 1 ? 'core' : 'cores'}`}
					</p>
					{#if board.loadFrom === 0}
						<p class="note absent" data-memory-track-empty="load">
							No item of this run recorded the machine's load, so whether anything was waiting
							for a processor cannot be said here.
						</p>
					{:else}
						<div class="strip" role="img" aria-labelledby="load-name">
							{#each board.items as item (item.itemId)}
								<span class="mark" class:worst={item.worst}>
									{#if item.load === null}
										<span class="bar absent-bar"></span>
									{:else}
										<span class="bar load" style="block-size: {item.loadWidth}"></span>
									{/if}
								</span>
							{/each}
						</div>
					{/if}

					<!-- The figures as text. A hover is never the only carrier of any
					     of this: the dominant reading device has no pointer. -->
					<dl class="readout">
						<div data-memory-figure="item-peak">
							<dt>The worst item held</dt>
							<dd>
								{gib(board.itemHighWater)}
								<span class="unit">
									{board.itemHighWaterPct}% of {gib(board.ceilingBytes)}, on
									<strong>{board.worstItemId ?? 'an item this run did not name'}</strong>{worstItem ===
									null
										? ''
										: `, shard ${worstItem.shard}`}. A per-shard maximum cannot show it, because
									the shard's own figure IS this item and reads as the shard's normal.
								</span>
							</dd>
						</div>
						<div data-memory-figure="both">
							<dt>Both processes together</dt>
							<dd>
								{#if board.bothHighWater === null}
									<span class="absent">The worker process recorded nothing on this run.</span>
								{:else}
									{gib(board.bothHighWater)}
									<span class="unit">
										{board.bothHighWaterPct}% of {gib(board.ceilingBytes)}.
										{#if board.coPeak}
											Both maxima fall on the same item, so this is a reading.
										{:else}
											<strong>An upper bound and not an observed peak</strong> - the two maxima
											fall on different items, so no moment of this run held both.
										{/if}
									</span>
								{/if}
							</dd>
						</div>
						<div data-memory-figure="load">
							<dt>The longest queue</dt>
							<dd>
								{#if board.loadHigh === null}
									<span class="absent">No item of this run recorded the machine's load.</span>
								{:else}
									{board.loadHigh.toFixed(2)}
									<span class="unit">
										{board.cores === null
											? "one-minute load, and this run did not record the host's core count - so whether that is a queue cannot be said"
											: `one-minute load on ${board.cores} ${
													board.cores === 1 ? 'core' : 'cores'
												}${
													board.loadHigh > board.cores
														? ' - past the cores, so work was waiting for a processor'
														: ' - inside the cores, so nothing was waiting'
												}`}. {busyText(board.busySpan)}.
									</span>
								{/if}
							</dd>
						</div>
					</dl>

					<!-- The one thing this panel cannot answer, said on the panel. -->
					<p class="note" data-memory-cannot-separate>
						No figure here can say which half of the model call owns the peak - reading the
						prompt or writing the answer. Nothing samples memory inside the call, so the two
						phases are one reading, and this panel does not separate them.
					</p>
				{/if}
			</div>
		{:else if grain === 'shard'}
			<div class="grain" data-memory-pane="shard">
				{#if board.shard.empty}
					<p class="note absent" data-memory-board-empty="shard">
						No shard of this run recorded a memory high-water mark, which is a missing
						reading and not a run that used no memory.
					</p>
				{:else}
					<div class="bars" data-peak-memory={board.shard.runId}>
						<div data-memory="run" data-memory-high-water={board.shard.highWater ?? ''}>
							<TargetBar
								marks={board.shard.marks}
								label="The run's high-water mark"
								valueText={gib(board.shard.highWater)}
								targetText="of the runner's {gib(RUNNER_MEMORY_BYTES)} - {board.shard
									.pctOfRunner}%, the largest of the {board.shard.from} shards below and never
								their total"
								emptyNote="This run recorded no memory high-water mark."
							/>
						</div>
						{#each board.shard.shards as one (one.shard)}
							<div data-memory-shard={one.shard} data-memory-bytes={one.bytes}>
								<TargetBar
									marks={one.marks}
									label="Shard {one.shard}"
									valueText={gib(one.bytes)}
									targetText="of the runner's {gib(RUNNER_MEMORY_BYTES)} - {Math.round(
										(one.bytes / RUNNER_MEMORY_BYTES) * 100
									)}%"
									emptyNote="This shard recorded no memory high-water mark."
								/>
							</div>
						{/each}
					</div>
					<p class="note" data-memory-basis data-memory-planned={board.shard.outOf ?? ''}>
						The run's figure is the LARGEST of these and never their total: shards are
						separate jobs on separate hosts, so adding them would report a machine that never
						existed.
						{#if board.shard.outOf === null}
							Over {board.shard.from}
							{board.shard.from === 1 ? 'shard' : 'shards'}; this run's manifest recorded no
							shard count, so how many the plan asked for is unknown.
						{:else}
							Over {board.shard.from} of the run's {board.shard.outOf} shards.
						{/if}
					</p>
				{/if}
			</div>
		{:else}
			<div class="grain" data-memory-pane="span">
				{#if span.high === null}
					<p class="note absent" data-memory-board-empty="span">
						No run in these {windowDays} days recorded a memory high-water mark.
					</p>
				{:else}
					<!-- A figure with a span is one track, never two sentences. This
					     was four lines of prose in another panel until this one
					     absorbed it. -->
					<p class="track-name" id="span-name">
						The high-water mark across these {windowDays} days, lowest run to highest
					</p>
					<div
						class="span-track"
						role="img"
						aria-labelledby="span-name"
						data-memory-span-low={span.low ?? ''}
						data-memory-span-high={span.high ?? ''}
						data-memory-span-from={span.from}
						data-memory-span-out-of={span.outOf}
						data-memory-span-scale={spanScale}
					>
						<span
							class="span-fill"
							style="inset-inline-start: {along(span.low)}%; inline-size: {along(span.high) -
								along(span.low)}%"
						></span>
						{#if board.shard.highWater !== null}
							<span class="span-now" style="inset-inline-start: {along(board.shard.highWater)}%"
							></span>
						{/if}
					</div>
					<span class="unit">
						The track runs to {gib(spanScale)}; the bar is the span and the upright is this
						run's own mark on it.
					</span>
					<dl class="readout">
						<div data-memory-figure="span">
							<dt>Over these {windowDays} days</dt>
							<dd>
								{gib(span.low)} to {gib(span.high)}
								<span class="unit">
									on {span.from} of {span.outOf} runs. Each of those is itself the largest of a
									run's shards, so this is a span of maxima and never a total.
								</span>
							</dd>
						</div>
						<div data-memory-figure="span-newest">
							<dt>This run, on that span</dt>
							<dd>
								{#if board.shard.highWater === null}
									<span class="absent">This run recorded no high-water mark.</span>
								{:else}
									{gib(board.shard.highWater)}
									<span class="unit">
										{board.shard.pctOfRunner}% of {gib(board.ceilingBytes)}, marked on the track
										above.
									</span>
								{/if}
							</dd>
						</div>
					</dl>
				{/if}
			</div>
		{/if}

		<!-- Every drawn value as text, for a reader who cannot see the marks and
		     for the oracle, which recomputes each one from the ledger. -->
		<ul class="sr-only" data-memory-values>
			{#each board.items as item (item.itemId)}
				<li>
					{item.itemId}, shard {item.shard}: model server {gib(item.peakBytes)}, worker
					{gib(item.workerBytes)}, kernel headroom {item.headroom.empty
						? 'not recorded'
						: `${gib(item.headroom.floorBytes)} at its worst and ${gib(
								item.headroom.endBytes
							)} when it ended`}, load {item.load === null ? '-' : item.load.toFixed(2)},
					{busyText(item.busy)}.
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.memory-board {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		position: relative;
	}

	.grains {
		display: flex;
		justify-content: flex-end;
	}

	.note {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.absent {
		color: var(--color-text-tertiary);
	}

	.grain {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.track-name {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text-secondary);
	}

	.strip {
		display: flex;
		align-items: flex-end;
		gap: 1px;
		block-size: 5rem;
		padding: 0;
		border-block-end: 1px solid var(--color-border);
	}

	.mark {
		position: relative;
		flex: 1 1 0;
		min-inline-size: 2px;
		block-size: 100%;
		display: flex;
		align-items: flex-end;
	}

	.bar {
		inline-size: 100%;
		border-radius: 1px 1px 0 0;
	}

	.held {
		background: var(--chart-1);
	}

	.floor {
		background: var(--chart-3);
	}

	.load {
		background: var(--chart-4);
	}

	/* An unmeasured item is a gap in the strip and never a bar of no height:
	   a zero-length mark says the reading was taken and came back zero. */
	.absent-bar {
		block-size: 100%;
		background: repeating-linear-gradient(
			45deg,
			transparent,
			transparent 3px,
			var(--color-border) 3px,
			var(--color-border) 4px
		);
	}

	.notch {
		position: absolute;
		inset-inline: 0;
		block-size: 2px;
		background: var(--color-text-primary);
	}

	.mark.worst .bar {
		outline: 1px solid var(--color-text-primary);
		outline-offset: 0;
	}

	/* The run's own mark first, then a bar a shard, every bar on the same
	   ceiling so their lengths compare. One column below the breakpoint: a
	   memory bar squeezed into half a phone cannot be compared with its
	   neighbour. */
	.bars {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
		gap: var(--space-4) var(--space-5);
	}

	.span-track {
		position: relative;
		block-size: 1.5rem;
		border-radius: var(--radius-sm);
		background: var(--color-surface-sunken);
	}

	.span-fill {
		position: absolute;
		inset-block: 0.375rem;
		background: var(--chart-3);
		border-radius: var(--radius-sm);
	}

	.span-now {
		position: absolute;
		inset-block: 0;
		inline-size: 2px;
		background: var(--color-text-primary);
	}

	.readout {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: var(--space-3);
		margin: var(--space-2) 0 0;
	}

	.readout dt {
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
	}

	.readout dd {
		margin: 0;
		font-size: var(--text-lg);
		font-variant-numeric: tabular-nums;
	}

	.unit {
		display: block;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		font-variant-numeric: normal;
		color: var(--color-text-secondary);
	}

	.sr-only {
		position: absolute;
		inline-size: 1px;
		block-size: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
</style>
