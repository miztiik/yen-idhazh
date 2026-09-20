<script lang="ts">
	/** One run, one row per shard, ranked by the clock that can kill it.
	 *
	 * A run is not one machine. Measured on the committed ledger, the fastest
	 * shard of run `2026-08-30-5` read the prompt at 41.98 tokens a second and
	 * the slowest at 9.73 - the same run, the same day, 4.31x apart - and the two
	 * slow shards took 62 and 78 percent longer to finish than the two fast ones.
	 * A per-run average reports neither end of that, which is why the shard is a
	 * visible unit here and not a tooltip.
	 *
	 * **This is a break panel and not a verdict one.** It takes the extreme and
	 * the shard that owns it, and it covers every shard of one run. Its question
	 * is what is broken, and the answer it exists to give is work or the host: a
	 * long clock at a normal read rate and a high item count is a lot of
	 * articles, and a long clock at a quarter of its neighbour's read rate, with
	 * load past the cores and swap falling, is the machine. Every host fact that
	 * answer needs is on the row. They used to be spread over four other panels,
	 * so the board's own claim could not be checked without leaving it.
	 *
	 * Reading and writing are never one bar. Read time varies more than 4x on
	 * this ledger and write time barely moves, so a single "model seconds" figure
	 * would average two different machines together.
	 *
	 * At 1280px and under the six columns become one card a shard, and every
	 * cell carries its own label. A column heading that only exists on a desktop
	 * is a value with no name on a phone.
	 */
	import TargetBar from './TargetBar.svelte';
	import { gib, seconds, type RangeMark, type ShardBoardView } from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';

	let {
		board,
		timeoutMinutes
	}: {
		board: ShardBoardView;
		/** `run.shard_timeout_minutes`, for the sentence under each clock. */
		timeoutMinutes: number;
	} = $props();

	/** Shards the plan dispatched that filed nothing. Null where the run's
	 * manifest recorded no plan, because an unknown total subtracts to nothing. */
	const missing = $derived(board.shards === null ? null : board.shards - board.rows.length);

	const rate = (value: number | null) => (value === null ? '-' : value.toFixed(2));
	const percent = (value: number | null) => (value === null ? '-' : `${value.toFixed(1)}%`);

	/** What a range mark says in one sentence, for the hover and for the reader
	 * who has none. Never the only carrier of any of it. */
	function spread(mark: RangeMark, unit: (value: number | null) => string): string {
		if (mark.empty) return 'not recorded on this run';
		return `${unit(mark.median)} on a typical item, ${unit(mark.max)} at its worst`;
	}
</script>

<div
	class="board"
	data-shard-board={board.empty ? 'empty' : board.runId}
	data-shard-board-shards={board.shards ?? ''}
	data-shard-board-reported={board.rows.length}
	data-shard-board-timeout-seconds={board.timeoutSeconds ?? ''}
	data-shard-board-rate-scale={board.rateScale}
	data-shard-board-write-rate-scale={board.writeRateScale}
	data-shard-board-rate-ratio={board.rateRatio === null ? '' : board.rateRatio.toFixed(4)}
	data-shard-board-rates-share-axis={board.ratesShareAxis}
	data-shard-board-memory-scale={board.memoryScaleBytes}
	data-shard-board-swap-known={board.swapKnown}
	data-panel-question="what is broken"
	data-readout-none="one row per shard, and every figure on a row is printed beside its bar"
>
	{#if board.empty}
		<p class="board-note" data-shard-board-empty>
			No run in this span committed a machine row, so there are no shards to rank. That is a
			record that did not happen, not a run that did no work.
		</p>
	{:else}
		<p class="board-note">
			Run <strong>{board.runId}</strong> on {board.date}, {board.rows.length}
			{board.shards === null ? 'shards reporting' : `of ${board.shards} shards reporting`}.
			{#if board.shards === null}
				The run's plan recorded no shard count, so how many filed nothing is unknown rather
				than none.
			{/if}
			{#if missing !== null && missing > 0}
				{missing === 1 ? 'One shard' : `${missing} shards`} committed no row, so
				{missing === 1 ? 'its' : 'their'} time is missing rather than zero.
			{/if}
			{#if board.readSpread !== null}
				The fastest reader ran <strong>{board.readSpread.toFixed(2)}x</strong> the slowest.
			{/if}
		</p>

		<!-- Every domain here comes from the figures drawn, so a 4x spread draws a
		     quarter-length bar instead of being clipped at a round number somebody
		     chose. The memory ceiling joins the memory figures rather than capping
		     them, so a shard past 16 GiB would draw past the line. -->
		<p class="board-note" data-shard-board-domains>
			Clock bars share one scale: the widest stands for {seconds(board.scaleSeconds)}. Rate bars
			share one: the widest stands for {rate(board.rateScale)} tokens a second.
			{#if board.rateRatio === null}
				Only one of the two rates was measured, so there is no ratio to compare them on.
			{:else if board.ratesShareAxis}
				Reading and writing are {board.rateRatio.toFixed(2)}x apart, inside the 20x at which
				the smaller reads as zero, so they share that scale and their lengths compare.
			{:else}
				Reading and writing are {board.rateRatio.toFixed(2)}x apart, past the 20x at which the
				smaller reads as zero, so writing is drawn on its own scale of {rate(
					board.writeRateScale
				)} tokens a second and the two lengths do not compare.
			{/if}
			Memory marks run to {gib(board.memoryScaleBytes)}, which is the runner's own ceiling.
		</p>

		<div class="head" aria-hidden="true">
			<span>Shard</span>
			<span>Reading against writing</span>
			<span>Rate</span>
			<span>Host</span>
			<span>Memory and CPU</span>
			<span>Job clock</span>
		</div>

		{#each board.rows as row (row.shard)}
			<div
				class="row"
				data-shard-row={row.shard}
				data-shard-items={row.items}
				data-shard-read-seconds={row.readSeconds ?? ''}
				data-shard-write-seconds={row.writeSeconds ?? ''}
				data-shard-model-seconds={row.modelSeconds ?? ''}
				data-shard-split-drawn={row.splitDrawn}
				data-shard-read-tps={row.readTokensPerSecond ?? ''}
				data-shard-write-tps={row.writeTokensPerSecond ?? ''}
				data-shard-job-seconds={row.jobSeconds ?? ''}
				data-shard-model-load-ms={row.modelLoadMs ?? ''}
				data-shard-cpu={row.cpuModel ?? ''}
				data-shard-cores={row.cores ?? ''}
				data-shard-load={row.loadMax ?? ''}
				data-shard-mem-median={row.memory.median ?? ''}
				data-shard-mem-max={row.memory.max ?? ''}
				data-shard-cpu-median={row.cpu.median ?? ''}
				data-shard-cpu-max={row.cpu.max ?? ''}
				data-shard-swap-state={row.swapState}
				data-shard-swap-free={row.swapFreeBytes ?? ''}
				data-shard-swap-total={row.swapTotalBytes ?? ''}
			>
				<p class="shard">
					<span class="cell-label" data-shard-name="shard" aria-hidden="true">Shard</span>
					<span data-shard-figure="shard">{row.shard}</span>
					<!-- The work half of work-or-host. A long clock is only a machine
					     problem once the item count says it was not a long queue. It
					     names itself at every width, so it declares no figure of its
					     own: "20 items" is a value and its name in one string. -->
					<span class="unit">
						{row.items === 1 ? '1 item' : `${grouped(row.items)} items`}
					</span>
				</p>

				<div class="split">
					<span class="cell-label" data-shard-name="split" aria-hidden="true">
						Reading against writing
					</span>
					{#if row.modelSeconds === null}
						<p class="absent" data-shard-cell="split" data-shard-figure="split">
							This shard reported no clock of its own, so its reading and writing are unknown.
						</p>
					{:else}
						<div
							class="track"
							role="img"
							title="Shard {row.shard}: {seconds(row.readSeconds)} reading, {seconds(
								row.writeSeconds
							)} writing."
							aria-label="Shard {row.shard} spent {seconds(row.readSeconds)} reading and {seconds(
								row.writeSeconds
							)} writing, {seconds(row.modelSeconds)} in the model altogether."
						>
							{#if row.splitDrawn}
								<span class="seg read" style="inline-size: {row.readWidth}"></span>
								<span class="seg write" style="inline-size: {row.writeWidth}"></span>
							{:else}
								<!-- One of the two would draw under a pixel. A band nobody can
								     see teaches a reader the category is zero, so the track draws
								     whole and both seconds are printed below it. -->
								<span class="seg whole"></span>
							{/if}
						</div>
						<p class="legend" data-shard-figure="split">
							<span class="legend-pair">
								<span class="key read" class:whole={!row.splitDrawn}></span>reading {seconds(
									row.readSeconds
								)}
							</span>
							<span class="legend-pair">
								<span class="key write" class:whole={!row.splitDrawn}></span>writing {seconds(
									row.writeSeconds
								)}
							</span>
						</p>
					{/if}
				</div>

				<div class="rates" data-shard-cell="rate">
					<span class="cell-label" data-shard-name="rate" aria-hidden="true">Rate</span>
					{#if row.readTokensPerSecond === null && row.writeTokensPerSecond === null}
						<p class="absent" data-shard-figure="rate">
							Neither rate was measured on this shard.
						</p>
					{:else}
						<span
							class="rate-line"
							title="Shard {row.shard} read at {rate(
								row.readTokensPerSecond
							)} prompt tokens a second."
						>
							<span
								class="rate-track"
								role="img"
								aria-label="Shard {row.shard} read at {rate(
									row.readTokensPerSecond
								)} prompt tokens a second"
							>
								<span class="seg read" style="inline-size: {row.readRateWidth}"></span>
							</span>
						</span>
						<span
							class="rate-line"
							title="Shard {row.shard} wrote at {rate(row.writeTokensPerSecond)} tokens a second."
						>
							<span
								class="rate-track"
								role="img"
								aria-label="Shard {row.shard} wrote at {rate(
									row.writeTokensPerSecond
								)} tokens a second"
							>
								<span class="seg write" style="inline-size: {row.writeRateWidth}"></span>
							</span>
						</span>
						<p class="legend tabular-nums" data-shard-figure="rate">
							<span class="legend-pair">
								<span class="key read"></span>reading {rate(row.readTokensPerSecond)}
							</span>
							<span class="legend-pair">
								<span class="key write"></span>writing {rate(row.writeTokensPerSecond)}
							</span>
						</p>
						<span class="unit">tokens a second</span>
					{/if}
				</div>

				<!-- Text, never a hue on its own. A colour is one signal and the
				     processor is the one host fact that changes an answer, so it is
				     spelled out even when it makes the row wider. -->
				<div class="host">
					<p class="cpu" data-shard-cell="cpu">
						<span class="cell-label" data-shard-name="cpu" aria-hidden="true">Processor</span>
						<span data-shard-figure="cpu">
							{#if row.cpuModel === null}
								<span class="absent">Not recorded on this run</span>
							{:else}
								{row.cpuModel}
							{/if}
						</span>
					</p>

					<!-- No cell label on the load: the bar prints its own at every
					     width, and the sentence that replaces it when the cores are
					     unknown names itself too. -->
					{#if row.load.empty}
						<span class="unit absent" data-shard-cell="load">
							{row.loadMax === null
								? 'No load reading on this shard.'
								: `Load reached ${row.loadMax.toFixed(2)}, and this run did not record the host's core count - so whether that is a queue cannot be said.`}
						</span>
					{:else}
						<span
							class="load"
							data-shard-cell="load"
							title="Shard {row.shard} reached a one-minute load of {rate(row.loadMax)} on {row.cores} cores."
						>
							<TargetBar
								marks={row.load}
								label="Shard {row.shard} load"
								valueText={rate(row.loadMax)}
								targetText="load, against {row.cores} {row.cores === 1
									? 'core'
									: 'cores'} - past that the work is queueing"
								emptyNote="This shard recorded no load."
							/>
						</span>
					{/if}

					<p class="unit" data-shard-cell="swap">
						<span class="cell-label" data-shard-name="swap" aria-hidden="true">Free swap</span>
						<span data-shard-figure="swap">
							{#if row.swapState === 'unrecorded'}
								<span class="absent">Swap not recorded on this run.</span>
							{:else if row.swapState === 'none'}
								This host has no swap, so it cannot be swapping.
							{:else}
								{gib(row.swapFreeBytes)} free of {gib(row.swapTotalBytes)}
							{/if}
						</span>
					</p>
				</div>

				<div class="ranges" data-shard-cell="ranges">
					<!-- A typical item and the worst one on one track. Two bars each for
					     memory and CPU would be four bars a row, and eighty across a run
					     of twenty shards. -->
					<p class="range-line" title="Shard {row.shard} memory: {spread(row.memory, gib)}.">
						<span class="cell-label" data-shard-name="memory" aria-hidden="true">Memory</span>
						{#if row.memory.empty}
							<span class="absent" data-shard-figure="memory">No memory reading</span>
						{:else}
							<span
								class="range"
								role="img"
								aria-label="Shard {row.shard} memory, {spread(row.memory, gib)}"
							>
								<span class="range-fill" style="inline-size: {row.memory.medianWidth}"></span>
								<span class="range-notch" style="inset-inline-start: {row.memory.notchWidth}"
								></span>
							</span>
							<span class="range-figure tabular-nums" data-shard-figure="memory">
								{gib(row.memory.median)} to {gib(row.memory.max)}
							</span>
						{/if}
					</p>
					<p class="range-line" title="Shard {row.shard} processor: {spread(row.cpu, percent)}.">
						<span class="cell-label" data-shard-name="cpu-range" aria-hidden="true">
							Processor busy
						</span>
						{#if row.cpu.empty}
							<span class="absent" data-shard-figure="cpu-range">No CPU reading</span>
						{:else}
							<span
								class="range"
								role="img"
								aria-label="Shard {row.shard} processor busy, {spread(row.cpu, percent)}"
							>
								<span class="range-fill cpu-fill" style="inline-size: {row.cpu.medianWidth}"
								></span>
								<span class="range-notch" style="inset-inline-start: {row.cpu.notchWidth}"></span>
							</span>
							<span class="range-figure tabular-nums" data-shard-figure="cpu-range">
								{percent(row.cpu.median)} to {percent(row.cpu.max)} busy
							</span>
						{/if}
					</p>
					<span class="unit">fill is a typical item, notch is the worst one</span>
				</div>

				<!-- No cell label here: the bar prints its own, at every width, and so
				     does the sentence under it. -->
				<div class="clock" data-shard-cell="clock">
					<TargetBar
						marks={row.job}
						label="Shard {row.shard} job clock"
						valueText={seconds(row.jobSeconds)}
						targetText="of the {grouped(timeoutMinutes)}-minute timeout{row.jobSeconds !== null &&
						board.timeoutSeconds
							? ` - ${Math.round((row.jobSeconds / board.timeoutSeconds) * 100)} percent`
							: ''}"
						emptyNote="This shard recorded no job clock."
					/>
					<span class="unit">
						{row.modelLoadMs === null
							? 'Weights load not recorded'
							: `${seconds(row.modelLoadMs / 1000)} of it opening the weights, before the first item`}
					</span>
				</div>
			</div>
		{/each}

		<!-- The values as text, for anybody who cannot see the bars and for the
		     oracle, which recomputes every one of them from the ledger. -->
		<ul class="sr-only" data-shard-values>
			{#each board.rows as row (row.shard)}
				<li>
					Shard {row.shard}: {row.items} items, {seconds(row.readSeconds)} reading, {seconds(
						row.writeSeconds
					)} writing, {rate(row.readTokensPerSecond)} prompt tokens a second read and {rate(
						row.writeTokensPerSecond
					)} written, on {row.cpuModel ?? 'a processor this run did not record'}, job clock
					{seconds(row.jobSeconds)}, memory {spread(row.memory, gib)}, processor {spread(
						row.cpu,
						percent
					)}, load {rate(row.loadMax)} on {row.cores ?? 'an unrecorded number of'} cores,
					{row.swapState === 'measured'
						? `${gib(row.swapFreeBytes)} swap free of ${gib(row.swapTotalBytes)}`
						: row.swapState === 'none'
							? 'no swap on this host'
							: 'swap not recorded'}.
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.board {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.board-note {
		margin: 0 0 var(--space-2);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.head,
	.row {
		display: grid;
		grid-template-columns:
			4.5rem minmax(9rem, 1.8fr) minmax(7rem, 1fr) minmax(10rem, 1.5fr)
			minmax(9rem, 1.3fr) minmax(8rem, 1fr);
		gap: var(--space-3);
		align-items: start;
	}

	.head {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
		padding-block-end: var(--space-1);
		border-block-end: 1px solid var(--color-rule);
	}

	/* The same words as the head, one copy a cell, hidden while the head is on
	   screen. Below the breakpoint the head goes and these carry the names. */
	.cell-label {
		display: none;
		font-size: var(--text-xs);
		font-weight: 400;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	/* Thick rows on purpose: the shard is the unit an operator acts on, so it
	   gets the height a unit deserves rather than a table line's. */
	.row {
		padding-block: var(--space-3);
		border-block-end: 1px solid var(--color-rule);
	}

	.row:last-of-type {
		border-block-end: none;
	}

	.shard {
		margin: 0;
		font-size: var(--text-lg);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
	}

	.split,
	.rates,
	.host,
	.ranges {
		display: block;
		min-inline-size: 0;
	}

	.track {
		display: flex;
		block-size: 18px;
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	.seg {
		display: block;
		block-size: 100%;
	}

	.seg.read {
		background: var(--chart-1);
	}

	.seg.write {
		background: var(--chart-4);
	}

	/* The undrawn split. One ground and no bands, because a band under a pixel
	   is the very mark the rule refuses. */
	.seg.whole {
		inline-size: 100%;
		background: var(--color-text-tertiary);
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-3);
		margin: var(--space-1) 0 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	/* One item, not two. A wrap that puts the swatch on one line and the word it
	   names on the next is a colour with nothing to read it by. */
	.legend-pair {
		display: inline-flex;
		align-items: center;
		white-space: nowrap;
	}

	.key {
		display: inline-block;
		inline-size: 10px;
		block-size: 10px;
		border-radius: 2px;
		margin-inline-end: 4px;
	}

	.key.read {
		background: var(--chart-1);
	}

	.key.write {
		background: var(--chart-4);
	}

	/* A key for a band the track did not draw would claim a mark that is not
	   there. The seconds beside it still carry the fact. */
	.key.whole {
		background: var(--color-text-tertiary);
	}

	.rate-line,
	.range-line {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		margin-block-start: var(--space-1);
	}

	.rate-track,
	.range {
		position: relative;
		display: block;
		flex: 1 1 auto;
		min-inline-size: 2.5rem;
		block-size: 10px;
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	.range-figure {
		flex: 0 0 auto;
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}

	.range-fill {
		display: block;
		block-size: 100%;
		background: var(--chart-2);
	}

	.range-fill.cpu-fill {
		background: var(--chart-3);
	}

	/* The worst reading, as a mark across the track rather than a second bar. A
	   bar beside a bar invites the reader to compare two lengths and lose which
	   one is the extreme. */
	.range-notch {
		position: absolute;
		inset-block: 0;
		inline-size: 2px;
		background: var(--chart-marker);
		transform: translateX(-1px);
	}

	.cpu {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.load {
		display: block;
		margin-block-start: var(--space-2);
	}

	.unit {
		display: block;
		font-size: var(--text-xs);
		font-weight: 400;
		color: var(--color-text-tertiary);
	}

	.host .unit,
	.ranges .unit,
	.clock .unit {
		margin-block-start: var(--space-1);
	}

	.absent {
		color: var(--color-text-tertiary);
	}

	.clock {
		min-inline-size: 0;
	}

	/* One card a shard.
	 *
	 * Above this width the row is six columns and the head names them. Below
	 * it the head is gone, and the two-column fallback this replaced pushed the
	 * read rate and the job clock into the 3rem shard column: measured
	 * 2026-09-01 at 360px, `1 h 28 m` was drawn in a 20px box over four lines,
	 * one character to a line, and `of the 150-minute timeout - 59 percent` took
	 * six lines in 41px. A card gives every cell the full width and its own
	 * name.
	 *
	 * The breakpoint moved from 1024px to 1280px when the row went from five
	 * columns to six. Six cells inside the old width leave the two range marks
	 * a track under 60px, and a fill and a notch that close together are one
	 * smudge rather than a span.
	 *
	 * An edge, not a fill. Every quiet line in a row is --color-text-tertiary,
	 * which reads 4.72:1 on --color-surface and 4.26:1 on
	 * --color-surface-raised - so a lifted card would put four strings under
	 * 4.5:1 in the dark theme to buy a tint. The bars need the ground too: both
	 * tracks are --color-surface-sunken, and a sunken card would erase them. */
	@media (max-width: 1280px) {
		.board {
			gap: var(--space-3);
		}

		.head {
			display: none;
		}

		.cell-label {
			display: block;
		}

		.row {
			display: flex;
			flex-direction: column;
			/* The six-column rule aligns its cells to the row's top. In a column
			   that becomes a stretch, which is what the range marks and the two
			   rate tracks need to stay full width. */
			align-items: stretch;
			gap: var(--space-3);
			padding: var(--space-4);
			border: 1px solid var(--color-rule);
			border-radius: var(--radius-lg);
		}

		/* The base rule drops the last row's divider, which on a card is the
		   bottom edge. Stated again because :last-of-type outranks .row. */
		.row:last-of-type {
			border-block-end: 1px solid var(--color-rule);
		}

		.shard {
			display: flex;
			align-items: baseline;
			gap: var(--space-2);
		}

		.shard .cell-label {
			display: inline;
		}

		/* A range line is a flex row, so a label inside it would sit beside the
		   track it names instead of over it. */
		.range-line {
			flex-wrap: wrap;
		}

		.range-line .cell-label {
			flex: 1 0 100%;
		}

		/* The unit is the figure's name and belongs on the figure's line, not
		   under it: three stacked lines for one number is what the label already
		   fixed. */
		.shard .unit {
			display: inline;
		}
	}
</style>
