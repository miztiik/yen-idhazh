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
	 * What the board is for: deciding whether a slow day was the WORK or the
	 * MACHINE. A long bar with a normal read rate is a lot of articles; a long
	 * bar with a read rate a quarter of its neighbour's is the host lottery, and
	 * nothing else on this site can tell those apart.
	 *
	 * Reading and writing are never one bar. Read time varies more than 4x on
	 * this ledger and write time barely moves, so a single "model seconds" figure
	 * would average two different machines together.
	 */
	import TargetBar from './TargetBar.svelte';
	import { gib, seconds, type ShardBoardView } from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';

	let {
		board,
		timeoutMinutes
	}: {
		board: ShardBoardView;
		/** `run.shard_timeout_minutes`, for the sentence under each clock. */
		timeoutMinutes: number;
	} = $props();

	const missing = $derived(board.shards - board.rows.length);
</script>

<div
	class="board"
	data-shard-board={board.empty ? 'empty' : board.runId}
	data-shard-board-shards={board.shards}
	data-shard-board-reported={board.rows.length}
	data-shard-board-timeout-seconds={board.timeoutSeconds ?? ''}
>
	{#if board.empty}
		<p class="board-note" data-shard-board-empty>
			No run in this span committed a counters row, so there are no shards to rank. That is a
			scrape that did not happen, not a run that did no work.
		</p>
	{:else}
		<p class="board-note">
			Run <strong>{board.runId}</strong> on {board.date}, {board.rows.length} of
			{board.shards} shards reporting.
			{#if missing > 0}
				{missing === 1 ? 'One shard' : `${missing} shards`} committed no row, so
				{missing === 1 ? 'its' : 'their'} time is missing rather than zero.
			{/if}
			{#if board.readSpread !== null}
				The fastest reader ran <strong>{board.readSpread.toFixed(2)}x</strong> the slowest.
			{/if}
			Bars share one scale: the widest stands for {seconds(board.scaleSeconds)}.
		</p>

		<div class="head" aria-hidden="true">
			<span>Shard</span>
			<span>Reading against writing</span>
			<span>Read rate</span>
			<span>Processor</span>
			<span>Job clock</span>
		</div>

		{#each board.rows as row (row.shard)}
			<div
				class="row"
				data-shard-row={row.shard}
				data-shard-read-seconds={row.readSeconds ?? ''}
				data-shard-write-seconds={row.writeSeconds ?? ''}
				data-shard-model-seconds={row.modelSeconds ?? ''}
				data-shard-read-tps={row.readTokensPerSecond ?? ''}
				data-shard-job-seconds={row.jobSeconds ?? ''}
				data-shard-cpu={row.cpuModel ?? ''}
			>
				<p class="shard">{row.shard}</p>

				<div class="split">
					{#if row.modelSeconds === null}
						<p class="absent" data-shard-cell="split">
							This shard reported no clock of its own, so its reading and writing are unknown.
						</p>
					{:else}
						<div
							class="track"
							role="img"
							aria-label="Shard {row.shard} spent {seconds(row.readSeconds)} reading and {seconds(
								row.writeSeconds
							)} writing, {seconds(row.modelSeconds)} in the model altogether."
						>
							<span class="seg read" style="inline-size: {row.readWidth}"></span>
							<span class="seg write" style="inline-size: {row.writeWidth}"></span>
						</div>
						<p class="legend">
							<span class="key read"></span>reading {seconds(row.readSeconds)}
							<span class="key write"></span>writing {seconds(row.writeSeconds)}
						</p>
					{/if}
				</div>

				<p class="figure tabular-nums" data-shard-cell="rate">
					{#if row.readTokensPerSecond === null}
						<span class="absent">-</span>
					{:else}
						{row.readTokensPerSecond.toFixed(2)}
						<span class="unit">prompt tokens a second</span>
					{/if}
				</p>

				<!-- Text, never a hue on its own. A colour is one signal and the
				     processor is the one host fact that changes an answer, so it is
				     spelled out even when it makes the row wider. -->
				<p class="cpu" data-shard-cell="cpu">
					{#if row.cpuModel === null}
						<span class="absent">Not recorded on this run</span>
					{:else}
						{row.cpuModel}
					{/if}
					{#if row.cpuBusyPct !== null}
						<span class="unit">{row.cpuBusyPct.toFixed(1)}% busy</span>
					{/if}
				</p>

				<div class="clock">
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
				</div>
			</div>
		{/each}

		<!-- The values as text, for anybody who cannot see the bars and for the
		     oracle, which recomputes every one of them from the ledger. -->
		<ul class="sr-only" data-shard-values>
			{#each board.rows as row (row.shard)}
				<li>
					Shard {row.shard}: {seconds(row.readSeconds)} reading, {seconds(row.writeSeconds)}
					writing, {row.readTokensPerSecond === null
						? 'no read rate'
						: `${row.readTokensPerSecond.toFixed(2)} prompt tokens a second`}, on
					{row.cpuModel ?? 'a processor this run did not record'}, job clock {seconds(
						row.jobSeconds
					)}{row.cpuBusyPct === null ? '' : `, ${row.cpuBusyPct.toFixed(1)} percent busy`}.
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
		grid-template-columns: 3rem minmax(12rem, 2.2fr) 7rem minmax(10rem, 1.4fr) minmax(9rem, 1fr);
		gap: var(--space-4);
		align-items: center;
	}

	.head {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
		padding-block-end: var(--space-1);
		border-block-end: 1px solid var(--color-rule);
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

	.split {
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

	.legend {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-3);
		margin: var(--space-1) 0 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
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

	.figure {
		margin: 0;
		font-size: var(--text-base);
		font-weight: 600;
		color: var(--color-text);
	}

	.cpu {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.unit {
		display: block;
		font-size: var(--text-xs);
		font-weight: 400;
		color: var(--color-text-tertiary);
	}

	.absent {
		color: var(--color-text-tertiary);
	}

	.clock {
		min-inline-size: 0;
	}

	@media (max-width: 1024px) {
		.head {
			display: none;
		}

		.row {
			grid-template-columns: 3rem 1fr;
			row-gap: var(--space-2);
		}
	}
</style>
