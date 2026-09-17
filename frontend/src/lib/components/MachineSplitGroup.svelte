<script lang="ts">
	/** One machine's shards, and how their seconds and their tokens split.
	 *
	 * A card on `--color-surface-raised` inside the panel, with a 4px left edge
	 * in that machine's colour. The edge and not a tinted fill: a tint behind
	 * text is the `--tint-*` vocabulary and means something else
	 * (`docs/concepts/design-system.md`).
	 *
	 * **The machine's name is on the card, in words, always.** The colour here
	 * encodes a fact, so it is semantic and may never be the only carrier of it.
	 */
	import { isUnrecorded, machineColour } from '$lib/charts/machine-colour';
	import type { MachineSplit } from '$lib/charts/machine-split';

	let { group }: { group: MachineSplit } = $props();
</script>

<div
	class="group"
	data-machine-group={group.identity.key}
	data-machine-name={group.identity.name}
	data-machine-stop={group.identity.colourStop}
	data-machine-unrecorded={isUnrecorded(group.identity) ? 'yes' : null}
	style="--machine-edge: {machineColour(group.identity.colourStop)}"
>
	<p class="group-head">
		<span class="group-name">{group.identity.name}</span>
		<span class="group-shards">
			{group.shards === 1 ? '1 shard' : `${group.shards} shards`}
		</span>
	</p>

	{#if group.identity.folded.length > 0}
		<p class="folded" data-machine-folded={group.identity.folded.length}>
			Two or more machines share this row: {group.identity.folded.join(', ')}.
		</p>
	{/if}

	{#each group.rows as row (row.label)}
		<div
			class="split-row"
			data-split-row="{group.identity.key}/{row.label}"
			data-split-read-pct={row.readPct}
		>
			<p class="split-head">
				<span>{row.label}</span>
				<span class="tabular-nums">{row.totalText}</span>
			</p>
			<div
				class="track"
				role="img"
				aria-label="{group.identity.name}, {row.label}: {row.readText} reading against {row.writeText} writing, {row.readPct} percent of it reading."
			>
				<span class="seg read" style="inline-size: {row.readWidth}"></span>
				<span class="seg write" style="inline-size: {row.writeWidth}"></span>
			</div>
			<p class="split-legend">
				<span class="key read"></span>reading {row.readText} ({row.readPct}%)
				<span class="key write"></span>writing {row.writeText} ({100 - row.readPct}%)
			</p>
		</div>
	{/each}

	<p class="group-rates" data-machine-rates={group.identity.key}>
		{#if group.readTokensPerSecond === null || group.writeTokensPerSecond === null}
			This machine's shards reported no rate on one side, so there is no ratio to take.
		{:else}
			Reading ran at {group.readTokensPerSecond.toFixed(2)} tokens a second here and writing at
			{group.writeTokensPerSecond.toFixed(2)}, so a written token cost
			{(group.writeCostRatio ?? 0).toFixed(1)}x a read one on this machine.
		{/if}
	</p>
</div>

<style>
	.group {
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-rule);
		border-inline-start: 4px solid var(--machine-edge);
		border-radius: var(--radius-md);
		background: var(--color-surface-raised);
	}

	.group-head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--space-2) var(--space-3);
		margin: 0 0 var(--space-3);
	}

	.group-name {
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text);
	}

	.group-shards,
	.folded {
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	.folded {
		margin: 0 0 var(--space-3);
	}

	.split-row + .split-row {
		margin-top: var(--space-3);
	}

	.split-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--space-3);
		margin: 0 0 var(--space-1);
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
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

	.split-legend {
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

	.group-rates {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
