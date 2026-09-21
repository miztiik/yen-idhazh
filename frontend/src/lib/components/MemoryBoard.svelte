<script lang="ts">
	/** How close one article came to using up the machine's memory.
	 *
	 * **The lead is the within-item floor of what the kernel had left.** A
	 * per-shard maximum cannot answer this: one item can take the machine to its
	 * floor while the shard it sits in reads as a normal shard. `MemAvailable` is
	 * also the only figure here that answers the question the panel is for -
	 * whether a bigger model fits - because a resident-set mark says what a
	 * process held and not what was still free.
	 *
	 * **The model server's own high-water mark is not drawn here.** It is
	 * `VmHWM`, which covers the server's whole life rather than this item, and it
	 * reads lower than an earlier item's whenever the kernel reclaims a page. The
	 * column stays in the ledger; the panel says why it is off the page rather
	 * than drawing it under a caveat, because a caveat under a mark does not stop
	 * the mark being read.
	 *
	 * **The end-of-item process readings are brackets, never tracks.** They run
	 * to the larger of themselves and they overlap on purpose. A resident-set
	 * figure drawn against the machine's total reads as a budget, and a reader
	 * cannot add two brackets that visibly overlap.
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
	import {
		gib,
		RUNNER_MEMORY_BYTES,
		type MemoryBoardView,
		type RangeMark
	} from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';

	let { board }: { board: MemoryBoardView } = $props();

	const tightestItem = $derived(board.items.find((item) => item.tightest) ?? null);

	/** A bracket's length against the larger of the two brackets, never against
	 * the machine's total. */
	const bracket = (value: number | null) =>
		board.bracketScaleBytes <= 0 || value === null
			? '0%'
			: `${Math.min(value / board.bracketScaleBytes, 1) * 100}%`;

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
	data-memory-ceiling={board.ceilingBytes}
	data-memory-total-measured={board.measuredTotalBytes ?? ''}
	data-memory-totals-seen={board.totalsSeen.join(' ')}
	data-memory-total-agrees={board.totalAgrees === null ? '' : String(board.totalAgrees)}
	data-memory-floor-low={board.floorLowBytes ?? ''}
	data-memory-floor-item={board.floorItemId ?? ''}
	data-memory-server-end-high-water={board.serverEndHighWater ?? ''}
	data-memory-worker-high-water={board.workerHighWater ?? ''}
	data-memory-both-high-water={board.bothHighWater ?? ''}
	data-memory-bracket-scale={board.bracketScaleBytes}
	data-memory-co-peak={String(board.coPeak)}
	data-memory-items={board.from}
	data-memory-items-planned={board.outOf ?? ''}
	data-memory-kernel-from={board.headroomFrom}
	data-memory-kernel-skipped={board.kernelSkipped}
	data-memory-kernel-begins={board.kernelBeginsOn ?? ''}
	data-memory-read-from={board.readFrom ?? ''}
	data-memory-load-high={board.loadHigh ?? ''}
	data-memory-cores={board.cores ?? ''}
	data-memory-busy-low={board.busySpan.median ?? ''}
	data-memory-busy-high={board.busySpan.max ?? ''}
	data-panel-question="what is broken"
	data-readout-none="every figure drawn here is printed beside its own track"
>
	{#if board.empty}
		<p class="note" data-memory-board-empty="all">
			No item of this run recorded what it did to the machine's memory. That is a measurement
			that did not survive, not a run that used none.
		</p>
	{:else}
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
				No item recorded what the machine has, so the kernel figures here are drawn against the
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

		<!-- THE LEAD. The first figure on the panel and the reason it exists: how
		     little the kernel had left at one item's worst moment. -->
		<dl class="readout lead">
			<div data-memory-figure="floor-low">
				<dt>The least the kernel had left</dt>
				<dd>
					{#if board.floorLowBytes === null}
						<span class="absent">
							No item of this run recorded what the kernel had left, so how close it came
							cannot be said here.
						</span>
					{:else}
						{gib(board.floorLowBytes)}
						<span class="unit">
							still free - {board.floorLowPct}% of {gib(board.ceilingBytes)} - at the worst
							moment of
							<strong>{board.floorItemId ?? 'an item this run did not name'}</strong>{tightestItem ===
							null
								? ''
								: `, shard ${tightestItem.shard}`}. A per-shard maximum cannot show this: one
							item can take the machine to its floor while the shard it sits in reads as a
							normal shard.
						</span>
					{/if}
				</dd>
			</div>
		</dl>

		<p class="track-name" id="left-name">What the kernel had left: worst, then at the end</p>
		{#if board.headroomFrom === 0}
			<p class="note absent" data-memory-track-empty="headroom">
				No item of this run recorded what the kernel had left, so nothing is drawn here.
				{#if board.kernelBeginsOn !== null}
					The reading begins on {board.kernelBeginsOn} in the ledger this page read, which
					starts on {board.readFrom}.
				{:else if board.readFrom !== null}
					No item in the ledger this page read, back to {board.readFrom}, carries it.
				{/if}
				A resident-set mark says what a process held; it does not say what was still free.
			</p>
		{:else}
			<div class="strip" role="img" aria-labelledby="left-name">
				{#each board.items as item (item.itemId)}
					<span
						class="mark"
						class:tightest={item.tightest}
						data-memory-item={item.itemId}
						data-memory-item-shard={item.shard}
						data-memory-item-server-end={item.serverEndBytes ?? ''}
						data-memory-item-worker={item.workerBytes ?? ''}
						data-memory-item-floor={item.headroom.floorBytes ?? ''}
						data-memory-item-end={item.headroom.endBytes ?? ''}
						data-memory-item-recovered={item.headroom.recoveredBytes ?? ''}
						data-memory-item-load={item.load ?? ''}
						data-memory-item-tightest={String(item.tightest)}
						title="{item.itemId}: {item.headroom.empty
							? 'no kernel reading'
							: `${gib(item.headroom.floorBytes)} left at its worst and ${gib(
									item.headroom.endBytes
								)} when it ended`}."
					>
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
				The bar is the least the kernel had while the model worked; the notch is what the item
				left when it ended. A bar that falls with a notch that stays down is a leak; one that
				falls with a notch above it was working hard.
			</span>
			{#if board.kernelSkipped > 0}
				<!-- Decision 4: an item older than the kernel columns is a printed
				     count, never a line at zero and never a fall back to a mark the
				     page has just said it does not trust. -->
				<p class="note absent" data-memory-kernel-gap>
					{grouped(board.kernelSkipped)} of the {grouped(board.from)}
					{board.from === 1 ? 'item' : 'items'} drawn carry no kernel reading and are hatched
					rather than drawn at zero.
					{#if board.kernelBeginsOn !== null}
						The reading begins on {board.kernelBeginsOn} in the ledger this page read, which
						starts on {board.readFrom}.
					{/if}
				</p>
			{/if}
		{/if}

		<!-- Decision 3: brackets and never a track. Both run to the larger of
		     themselves, they overlap on purpose, and they are labelled at most -
		     a resident-set figure drawn against the machine's total reads as a
		     budget, which is the figure this project retracted on 2026-09-09. -->
		<p class="track-name" id="held-name">
			What the two processes held when each item ended, at most
		</p>
		{#if board.bracketScaleBytes <= 0}
			<p class="note absent" data-memory-track-empty="held">
				No item of this run recorded what either process held when it ended.
			</p>
		{:else}
			<div class="brackets" role="img" aria-labelledby="held-name">
				<span class="bracket server" style="inline-size: {bracket(board.serverEndHighWater)}">
					<span class="cap"></span>
				</span>
				<span class="bracket worker" style="inline-size: {bracket(board.workerHighWater)}">
					<span class="cap"></span>
				</span>
			</div>
			<span class="unit">
				Each bracket runs to <strong>at most</strong> that many bytes over the run's items, and
				the two are drawn against the larger of themselves rather than against the machine. They
				overlap because they may not be added into a share of it: the weights are read from a
				file, so they sit inside the model server's bracket and inside the page cache at once.
			</span>
			<dl class="readout">
				<div data-memory-figure="server-end">
					<dt>The model server held, at most</dt>
					<dd>
						{#if board.serverEndHighWater === null}
							<span class="absent">The model server recorded nothing on this run.</span>
						{:else}
							{gib(board.serverEndHighWater)}
							<span class="unit">at the end of an item, over the items drawn.</span>
						{/if}
					</dd>
				</div>
				<div data-memory-figure="worker-end">
					<dt>The worker process held, at most</dt>
					<dd>
						{#if board.workerHighWater === null}
							<span class="absent">The worker process recorded nothing on this run.</span>
						{:else}
							{gib(board.workerHighWater)}
							<span class="unit">at the end of an item, over the items drawn.</span>
						{/if}
					</dd>
				</div>
				<div data-memory-figure="both">
					<dt>Both brackets added</dt>
					<dd>
						{#if board.bothHighWater === null}
							<span class="absent">Only one of the two processes recorded anything.</span>
						{:else}
							{gib(board.bothHighWater)}
							<span class="unit">
								{#if board.coPeak}
									Both maxima fall on the same item, so this is a reading.
								{:else}
									<strong>An upper bound and not an observed figure</strong> - the two maxima
									fall on different items, so no moment of this run held both.
								{/if}
							</span>
						{/if}
					</dd>
				</div>
			</dl>
		{/if}

		<p class="track-name" id="load-name">
			The queue when each item ended{board.cores === null
				? ''
				: `, against ${board.cores} ${board.cores === 1 ? 'core' : 'cores'}`}
		</p>
		{#if board.loadFrom === 0}
			<p class="note absent" data-memory-track-empty="load">
				No item of this run recorded the machine's load, so whether anything was waiting for a
				processor cannot be said here.
			</p>
		{:else}
			<div class="strip" role="img" aria-labelledby="load-name">
				{#each board.items as item (item.itemId)}
					<span class="mark" class:tightest={item.tightest}>
						{#if item.load === null}
							<span class="bar absent-bar"></span>
						{:else}
							<span class="bar load" style="block-size: {item.loadWidth}"></span>
						{/if}
					</span>
				{/each}
			</div>
			<dl class="readout">
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
		{/if}

		<!-- Decision 1: the mark comes off the page and stays in the ledger, and
		     the surface that would have drawn it is where that is said. -->
		<p class="note" data-memory-not-drawn>
			<strong>The model server's own high-water mark is not drawn here.</strong> The kernel prints
			the larger of what the process holds now and a stored mark it refreshes only when the
			process gives memory back, so the figure covers the server's whole life rather than this
			item and reads lower than an earlier item's whenever a page is reclaimed. The column is
			still written to the ledger; nothing on this panel is built on it.
		</p>

		<!-- The one thing this panel cannot answer, said on the panel. -->
		<p class="note" data-memory-cannot-separate>
			No figure here can say which half of the model call owns the peak - reading the prompt or
			writing the answer. Nothing samples memory inside the call, so the two phases are one
			reading, and this panel does not separate them.
		</p>

		<!-- Every drawn value as text, for a reader who cannot see the marks and
		     for the oracle, which recomputes each one from the ledger. -->
		<ul class="sr-only" data-memory-values>
			{#each board.items as item (item.itemId)}
				<li>
					{item.itemId}, shard {item.shard}: kernel headroom {item.headroom.empty
						? 'not recorded'
						: `${gib(item.headroom.floorBytes)} at its worst and ${gib(
								item.headroom.endBytes
							)} when it ended`}, model server {gib(item.serverEndBytes)} and worker {gib(
						item.workerBytes
					)} at the end, load {item.load === null ? '-' : item.load.toFixed(2)},
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

	.note {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.absent {
		color: var(--color-text-tertiary);
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
		border-block-end: 1px solid var(--color-rule);
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
			var(--color-rule) 3px,
			var(--color-rule) 4px
		);
	}

	.notch {
		position: absolute;
		inset-inline: 0;
		block-size: 2px;
		background: var(--color-text);
	}

	.mark.tightest .bar {
		outline: 1px solid var(--color-text);
		outline-offset: 0;
	}

	/* Two brackets from one origin, overlapping on purpose. A slice that abuts
	   its neighbour invites a reader to add the two, and these two may not be
	   added - one page can be resident in both processes at once. */
	.brackets {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0;
		block-size: 2.25rem;
		justify-content: center;
	}

	.bracket {
		position: relative;
		block-size: 0.75rem;
		border-block-start: 2px solid currentColor;
		border-block-end: 2px solid currentColor;
		min-inline-size: 2px;
	}

	.bracket .cap {
		position: absolute;
		inset-block: -2px;
		inset-inline-end: 0;
		inline-size: 2px;
		background: currentColor;
	}

	.bracket.server {
		color: var(--chart-1);
	}

	/* Pulled up over the first so the two visibly cross rather than stack. */
	.bracket.worker {
		color: var(--chart-2);
		margin-block-start: -0.375rem;
	}

	.readout {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: var(--space-3);
		margin: var(--space-2) 0 0;
	}

	/* The lead is one figure across the panel's whole width, not one cell of a
	   grid a reader has to pick it out of. */
	.readout.lead {
		grid-template-columns: 1fr;
	}

	.readout.lead dd {
		font-size: var(--text-2xl);
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
