<script lang="ts">
	/** How much of the processor the host gave to another tenant while we worked.
	 *
	 * Two rows of tiles and three sentences. The rows are the two grains that
	 * answer different questions: a day tile says whether a slow week was a
	 * shared box, and a shard tile of the newest run says whether the loss
	 * landed on one shard or across all of them - a noisy neighbour on one host
	 * and a busy platform are different faults with different answers.
	 *
	 * The correction is printed rather than kept in a doc. A reader comparing
	 * this month against last month is comparing two different measurements:
	 * before the split landed, the busy figure on this page counted a slice the
	 * host gave elsewhere as our own work.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import { factsOf, markReadout, recordsOf } from '$lib/charts/readout';
	import { grouped } from '$lib/charts/series';
	import {
		BUSY_HELD_BOTH_BEFORE,
		type LostTile,
		type ProcessorLostRun,
		type ProcessorLostSpan
	} from '$lib/console/machine/processor-lost';
	import { nameSpan } from '$lib/console/span-words';

	let {
		span,
		run,
		days,
		windowDays,
		markedAt,
		namedAt,
		readoutMaxShare
	}: {
		span: ProcessorLostSpan;
		/** The newest run's shards. A snapshot: a window is a span and a span
		 * cannot narrow a single run, so this row names its run instead. */
		run: ProcessorLostRun;
		days: number;
		windowDays: number;
		/** `console.processor_lost_pct_marked` - the share at which a tile fills. */
		markedAt: number;
		/** `console.processor_lost_pct_named` - the share at which the headline
		 * names the day. */
		namedAt: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare: number;
	} = $props();

	/** Which of the three sentences the span earns.
	 *
	 * `unrecorded` is bounded to the days drawn and says nothing about any other
	 * run: no committed day carries the reading yet, and "never" would be a
	 * claim about runs this page did not read.
	 */
	const verdict = $derived(
		span.from === 0 ? 'unrecorded' : span.named !== null ? 'named' : 'quiet'
	);

	function title(tile: LostTile): string {
		if (tile.state === 'unrecorded') {
			return `${tile.label}: ${grouped(tile.outOf)} ${tile.outOf === 1 ? 'article' : 'articles'}, none of which recorded what the host gave elsewhere.`;
		}
		if (tile.state === 'marked') {
			return `${tile.label}: at its worst one article was kept off the processor for ${tile.says} of an interval, out of ${grouped(tile.from)} that recorded it.`;
		}
		return `${tile.label}: no article went over ${markedAt}%, out of ${grouped(tile.from)} that recorded it.`;
	}

	/** One record a tile, days first and then the newest run's shards, in the
	 * order a reader meets them. */
	const tiles = $derived([...span.days, ...run.shards]);
	const records = $derived(
		recordsOf(
			tiles.map((tile) =>
				factsOf(
					tile.label,
					tile.state === 'unrecorded'
						? [
								{
									label: tile.outOf === 1 ? 'Article' : 'Articles',
									value: `${grouped(tile.outOf)}, none of which recorded what the host gave elsewhere`
								}
							]
						: [
								{
									label: 'At its worst',
									value:
										tile.state === 'marked'
											? `one article was kept off the processor for ${tile.says} of an interval`
											: `no article went over ${markedAt}%`
								},
								{ label: 'Out of', value: `${grouped(tile.from)} that recorded it` }
							],
					'not recorded'
				)
			)
		)
	);

	/** The tile a pointer, a key or a tap has picked, or null for the resting one:
	 * the day the verdict names, else the newest day. */
	let picked = $state<number | null>(null);
	const resting = $derived.by(() => {
		const named = span.named === null ? -1 : span.days.findIndex((tile) => tile.key === span.named?.key);
		return named >= 0 ? named : Math.max(0, span.days.length - 1);
	});
</script>

<div
	data-windowed="machine-processor-lost"
	data-window-days={windowDays}
	data-readout-records={tiles.length > 0 ? tiles.length : undefined}
	data-readout-none={tiles.length > 0
		? undefined
		: 'no article ran in these days and the newest run left no row, so there is no tile to read; agreed with Susan'}
>
	<Panel
		heading="h3"
		id="processor-lost"
		title="How much of the processor went to somebody else"
		note="A run that loses a share of its processor to another tenant on the same box takes longer for the same work while every other figure on this page reads as normal - {windowDays ===
		1
			? `one tile for ${nameSpan(windowDays)}`
			: `one tile a day over ${nameSpan(windowDays)}`}, and one a shard of the newest run."
	>
		<p class="verdict" data-processor-lost-verdict={verdict}>
			{#if verdict === 'unrecorded'}
				<!-- "Over them" would point at days that are not on screen at one day. -->
				No article in {nameSpan(days)} carries the reading, so this panel says nothing about whether
				the host was shared{days === 1 ? '' : ' over them'} - the split landed on
				{BUSY_HELD_BOTH_BEFORE} and the first run after it is the first one that can answer.
			{:else if span.named !== null && days === 1}
				<!-- One day has no worst day, so the sentence names the day it is about. -->
				On {span.named.label}, one article was kept off the processor for {span.named.says} of an
				interval, at or past the {namedAt}% this panel names a day for.
			{:else if span.named !== null}
				{span.named.label} is the worst day of these {days}: one article was kept off the processor
				for {span.named.says} of an interval, at or past the {namedAt}% this panel names a day for.
			{:else}
				No article in {nameSpan(days)} lost as much as {markedAt}% of an interval to another
				tenant, read over the {grouped(span.daysRecording)}
				{span.daysRecording === 1 ? 'day' : 'days'} that recorded it.
			{/if}
		</p>

		<!-- One tab stop for both rows of tiles. Left and Right step along a row,
		     Up and Down move between the day row and the shard row. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div
			class="grains"
			tabindex="0"
			role="group"
			aria-label="The share of the processor lost, one tile a day and one a shard of the newest run. Arrow keys read a tile, Escape returns to rest."
			use:markReadout={{
				count: tiles.length,
				walk: span.days.length > 0 ? span.days.length : 'row',
				onSelect: (index) => (picked = index),
				selected: picked
			}}
		>
		<div class="grain" data-processor-lost-grain="day">
			<p class="grain-name">
				By day<span class="unit"
					>{grouped(span.from)} of {grouped(span.outOf)} articles recorded it</span
				>
			</p>
			{#if span.days.length === 0}
				<p class="absent" data-processor-lost-empty="day">
					No article ran in {nameSpan(days)}, so there {days === 1
						? 'is nothing'
						: 'are no days'} to draw.
				</p>
			{:else}
				<ul class="tiles">
					{#each span.days as tile, index (tile.key)}
						<li
							data-readout-at={index}
							data-readout-picked={picked === index ? 'yes' : undefined}
							data-processor-lost-tile={tile.key}
							data-processor-lost-state={tile.state}
							data-processor-lost-pct={tile.worstPct ?? ''}
							data-processor-lost-from={tile.from}
							data-processor-lost-outof={tile.outOf}
							class={tile.state}
							aria-label={title(tile)}
						>
							<span class="key">{tile.short}</span>
							<span class="says">{tile.state === 'unrecorded' ? '' : tile.says}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<div class="grain" data-processor-lost-grain="run">
			<p class="grain-name">
				By part of the newest run<span class="unit">
					{#if run.runId === null}
						no run to read
					{:else}
						{run.runId} on {run.date}, {grouped(run.from)} of {grouped(run.outOf)} articles recorded
						it
					{/if}
				</span>
			</p>
			{#if run.shards.length === 0}
				<p class="absent" data-processor-lost-empty="run">
					The newest run committed no article row, so there are no parts of it to draw.
				</p>
			{:else}
				<ul class="tiles">
					{#each run.shards as tile, index (tile.key)}
						<li
							data-readout-at={span.days.length + index}
							data-readout-picked={picked === span.days.length + index ? 'yes' : undefined}
							data-processor-lost-shard={tile.key}
							data-processor-lost-state={tile.state}
							data-processor-lost-pct={tile.worstPct ?? ''}
							data-processor-lost-from={tile.from}
							data-processor-lost-outof={tile.outOf}
							class={tile.state}
							aria-label={title(tile)}
						>
							<span class="key">{tile.short}</span>
							<span class="says">{tile.state === 'unrecorded' ? '' : tile.says}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
		</div>

		{#if tiles.length > 0}
			<ChartReadout
				readout={records[picked ?? resting] ?? null}
				resting={picked === null}
				name="processor-lost"
				maxShare={readoutMaxShare}
				restingNote={span.named === null ? ', the newest day' : ', the day named above'}
				hint="Point at a tile to read it. Left and Right step along a row, Up and Down move between days and shards, Escape returns to rest."
			/>
		{/if}

		<!-- Printed on the panel and not filed in a doc. A reader comparing this
		     month against last month is comparing two different measurements, and
		     the page that shows him both owes him that sentence. -->
		<p class="correction" data-processor-lost-correction={BUSY_HELD_BOTH_BEFORE}>
			Before {BUSY_HELD_BOTH_BEFORE} the busy share on this page counted time the host gave another
			tenant as our own work, so a run older than that reports a machine it had to itself whether or
			not it did. Nothing can split that figure back into two after the fact.
		</p>
		<p class="cannot" data-processor-lost-open="whole-loss">
			What this cannot say is whether the share the kernel calls stolen is the whole of what the
			host took. A hypervisor that slows the clock rather than taking the slice outright leaves no
			mark our kernel can see, and only the platform's own accounting would settle it.
		</p>
	</Panel>
</div>

<style>
	.verdict {
		margin: 0 0 var(--space-3);
		color: var(--color-text);
	}

	.grain + .grain {
		margin-block-start: var(--space-4);
	}

	.grain-name {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2);
		margin: 0 0 var(--space-2);
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text-secondary);
	}

	.unit {
		font-size: var(--text-xs);
		font-weight: 400;
		color: var(--color-text-tertiary);
	}

	.tiles {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	/* Fixed width and height, so a run of tiles reads as a run of equal days and
	   a long label cannot make one day look larger than its neighbour. */
	.tiles > li {
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
		inline-size: 3.25rem;
		block-size: 2.75rem;
		border-radius: var(--radius-sm);
		font-size: var(--text-xs);
		font-variant-numeric: tabular-nums;
		text-align: center;
	}

	.key {
		font-weight: 600;
	}

	.says {
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	/* Three states, three fills, and the empty one is empty on purpose: a day
	   that predates the reading draws a blank cell, because a zero there would
	   promise a quiet host the ledger never measured.

	   Outlined against filled, never a hue on its own: the loud tile is the one
	   that reverses, so it is found by shape at a glance and by its own printed
	   share on a second look. */
	.tiles > li.unrecorded {
		border: 1px dashed var(--color-rule);
		background: none;
		color: var(--color-text-tertiary);
	}

	.tiles > li.quiet {
		border: 1px solid var(--color-rule-strong);
		background: none;
		color: var(--color-text-secondary);
	}

	.tiles > li.marked {
		border: 1px solid var(--color-accent-strong);
		background: var(--color-accent);
		color: var(--color-on-accent);
	}

	.tiles > li.marked .says {
		color: var(--color-on-accent);
		font-weight: 600;
	}

	.absent {
		margin: 0;
		font-size: var(--text-sm);
		color: var(--color-text-tertiary);
	}

	.correction,
	.cannot {
		margin: var(--space-4) 0 0;
		padding-inline-start: var(--space-3);
		border-inline-start: 2px solid var(--color-rule);
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
	}
	/* The tile the strip below is reading. An outline, so it cannot be mistaken
	   for the filled tile that marks a loss. */
	.tiles > li[data-readout-picked] {
		outline: 2px solid var(--color-focus);
		outline-offset: 1px;
	}

	.grains:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 4px;
	}
</style>
