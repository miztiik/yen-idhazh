<script lang="ts">
	/** One machine a run drew: what it is called, and what it can do.
	 *
	 * A card on `--color-surface-raised` inside the panel, with a 4px left edge
	 * in that machine's colour and the machine's name in words on the card. The
	 * colour encodes a fact here, so it is semantic and may never be the only
	 * carrier of it (`docs/concepts/design-system.md`).
	 *
	 * **Every watched flag is a chip, present or absent.** A present flag takes a
	 * tinted fill; an absent one takes a hairline outline at the same width. A
	 * list of only the flags a machine has cannot show the one it is missing,
	 * and that missing one is why decode moved.
	 *
	 * **L3 and the copy rate are bars on a track every card of the panel
	 * shares**, so the difference between two machines is a length rather than a
	 * subtraction. The reading stays in words under its own bar: a track is the
	 * comparison and never the carrier of the number. A bar is refused rather
	 * than drawn empty where there is nothing to draw or nothing to draw it
	 * against, and `data-machine-bar-state` says which.
	 *
	 * The disclosure holds where the platform put the machine, and the microcode
	 * revision - the cell that moves without anything else moving, so it is the
	 * only explanation left for a speed change with no other change. A native
	 * `<details>`, which is keyboard-reachable for free and says which state it
	 * is in without a second label.
	 */
	import { bandwidthSentence, cacheWords, type MachineCard } from '$lib/charts/machine-cards';
	import { isUnrecorded, machineColour } from '$lib/charts/machine-colour';

	/** True where this run's day published articles and the record kept no row.
	 *
	 * A card with no flags has two causes and they send an operator to opposite
	 * places: the record had not begun yet, or it ran and what it wrote is gone.
	 */
	let { card, lost = false }: { card: MachineCard; lost?: boolean } = $props();

	/** Why a bar is missing where a neighbour drew one. Said once, because a
	 * reader who has to work out which cards are comparable has lost the
	 * comparison the bars were added for. */
	const ALONE = 'Nothing to draw it against: one reading of this kind on this run.';

	const where = $derived(card.where);
	const placed = $derived(
		where === null
			? []
			: [
					['Machine size', where.vmSize],
					['Region', where.vmLocation],
					['Zone', where.vmZone],
					['Fault domain', where.vmFaultDomain],
					['Microcode', where.microcode],
					['As the host spells it', where.cpuModelRaw]
				].filter((pair): pair is [string, string] => typeof pair[1] === 'string' && pair[1] !== '')
	);
</script>

<article
	class="card"
	data-machine-card={card.identity.key}
	data-machine-name={card.identity.name}
	data-machine-stop={card.identity.colourStop}
	data-machine-source={card.source}
	data-machine-unrecorded={isUnrecorded(card.identity) ? 'yes' : null}
	style="--machine-edge: {machineColour(card.identity.colourStop)}"
>
	<h3 class="name">{card.identity.name}</h3>

	{#if card.identity.folded.length > 0}
		<p class="note" data-machine-folded={card.identity.folded.length}>
			Two or more machines share this row: {card.identity.folded.join(', ')}.
		</p>
	{/if}

	{#if card.part !== null}
		<p class="part tabular-nums" data-machine-part={card.part}>
			Family, model and stepping {card.part}
		</p>
	{/if}

	{#if card.flags.length > 0}
		<ul class="flags" data-machine-flags={card.flags.length}>
			{#each card.flags as flag (flag.name)}
				<li
					class="chip"
					class:present={flag.present}
					data-machine-flag={flag.name}
					data-machine-flag-present={flag.present ? 'yes' : 'no'}
				>
					{flag.name}
				</li>
			{/each}
		</ul>
	{:else}
		<p class="note" data-machine-flags="none" data-machine-flags-why={lost ? 'lost' : 'not-started'}>
			{#if lost}
				Only the processor name survived for this run. The machine record ran on this day and the
				rows it wrote are gone, so the instruction-set flags, the cache and the bandwidth it measured
				cannot be recovered.
			{:else}
				Only the processor name was recorded for this run. Instruction-set flags, cache and bandwidth
				start on the day the machine record ran.
			{/if}
		</p>
	{/if}

	{#if card.source === 'fingerprint'}
		<div class="bar" data-machine-bar="l3" data-machine-bar-state={card.l3Bar.state}>
			{#if card.l3Bar.state === 'drawn'}
				<div
					class="bar-track"
					data-machine-bar-cell="track"
					data-machine-bar-fraction={card.l3Bar.fraction.toFixed(6)}
					role="img"
					aria-label="L3 cache {card.l3Bar.valueWords}, against {card.l3Bar
						.topWords} - the largest of the {card.l3Bar.of} machines this run measured."
				>
					<span
						class="bar-fill"
						data-machine-bar-cell="fill"
						style="inline-size: {card.l3Bar.percent}"
					></span>
				</div>
			{/if}
			<p class="reading" data-machine-cache={card.l3CacheBytes ?? ''}>
				{#if card.l3CacheBytes === null}
					L3 was not recorded on this job.
				{:else}
					{cacheWords(card.l3CacheBytes)} of L3.
				{/if}
			</p>
			{#if card.l3Bar.state === 'alone'}
				<p class="note" data-machine-bar-why="alone">{ALONE}</p>
			{/if}
		</div>

		<div class="bar" data-machine-bar="bandwidth" data-machine-bar-state={card.bandwidthBar.state}>
			{#if card.bandwidthBar.state === 'drawn'}
				<div
					class="bar-track"
					data-machine-bar-cell="track"
					data-machine-bar-fraction={card.bandwidthBar.fraction.toFixed(6)}
					role="img"
					aria-label="Read rate {card.bandwidthBar.valueWords}, against {card.bandwidthBar
						.topWords} - the fastest of the {card.bandwidthBar.of} machines this run measured against memory."
				>
					<span
						class="bar-fill"
						data-machine-bar-cell="fill"
						style="inline-size: {card.bandwidthBar.percent}"
					></span>
				</div>
			{/if}
			<p class="reading" data-machine-bandwidth={card.memcpyGibPerSecond ?? ''}>
				{bandwidthSentence(card)}
			</p>
			{#if card.bandwidthBar.state === 'alone'}
				<p class="note" data-machine-bar-why="alone">{ALONE}</p>
			{:else if card.bandwidthBar.state === 'cache'}
				<p class="note" data-machine-bar-why="cache">
					Not drawn against the others: this reading is cache, not memory.
				</p>
			{/if}
		</div>
	{/if}

	<p class="drawn" data-machine-jobs="{card.jobsDrawn}/{card.jobsTotal}">
		Drawn by {card.jobsDrawn} of this run's {card.jobsTotal}
		{card.jobsTotal === 1 ? 'recorded job' : 'recorded jobs'}.
	</p>

	{#if placed.length > 0}
		<details class="where" data-machine-where={card.identity.key}>
			<summary>Where the platform put this</summary>
			<dl>
				{#each placed as [label, value] (label)}
					<div><dt>{label}</dt><dd>{value}</dd></div>
				{/each}
			</dl>
		</details>
	{/if}
</article>

<style>
	.card {
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-rule);
		border-inline-start: 4px solid var(--machine-edge);
		border-radius: var(--radius-md);
		background: var(--color-surface-raised);
	}

	.name {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		font-weight: 600;
		color: var(--color-text);
	}

	.part {
		margin: var(--space-1) 0 0;
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.flags {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
		margin: var(--space-3) 0 0;
		padding: 0;
		list-style: none;
	}

	/* Same width present or absent, so the row reads as a set with gaps in it
	   rather than as a shorter list. */
	.chip {
		min-inline-size: 6.5rem;
		padding: 2px var(--space-2);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-sm);
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		text-align: center;
		color: var(--color-text-tertiary);
	}

	.chip.present {
		border-color: transparent;
		background: var(--tint-accent);
		color: var(--color-text);
	}

	.reading,
	.drawn,
	.note {
		margin: var(--space-2) 0 0;
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.note {
		color: var(--color-text-tertiary);
	}

	.bar {
		margin-block-start: var(--space-2);
	}

	/* The bar's own margin is on the track, so a row whose bar is refused sits
	   exactly where a row that drew one sits. */
	.bar .reading {
		margin-block-start: var(--space-1);
	}

	.bar-track {
		block-size: 8px;
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	/* The machine's own colour, so a bar and the card's edge say the same thing.
	   The reading is in words underneath, so the colour carries nothing alone. */
	.bar-fill {
		display: block;
		block-size: 100%;
		min-inline-size: 1px;
		border-radius: var(--radius-full);
		background: var(--machine-edge);
	}

	.where {
		margin-top: var(--space-2);
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	.where summary {
		cursor: pointer;
	}

	.where dl {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(9rem, 100%), 1fr));
		gap: var(--space-1) var(--space-3);
		margin: var(--space-2) 0 0;
	}

	.where dt {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.where dd {
		margin: 0;
		color: var(--color-text-secondary);
		overflow-wrap: anywhere;
	}
</style>
