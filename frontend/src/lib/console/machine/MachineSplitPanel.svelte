<script lang="ts">
	/** What a written token cost against a read one, on the machine that paid it.
	 *
	 * One group a machine, never one figure over all of them: 86 of the 90 runs
	 * that name a processor drew more than one kind, so a pooled rate is a number
	 * about neither.
	 */
	import MachineSplitGroup from '$lib/components/MachineSplitGroup.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import type { SplitByMachine } from '$lib/charts/machine-split';

	let { split }: { split: SplitByMachine } = $props();
</script>

<div data-readout-none="one row per machine, no shared column" data-machine-split={split.runId}>
	<Panel
		heading="h3"
		id="reading-against-writing"
		title="Whether some machines do the same work slower"
		note="Where one machine reads or writes far slower than its neighbour, the fix is the draw rather than the prompt - one group a machine of the newest run."
	>
		{#if split.empty}
			<p class="empty" data-machine-panel-empty="reading-writing">
				No shard of the newest run reported all four counters, so there is nothing to split.
			</p>
		{:else}
			<div class="splits">
				{#each split.groups as group (group.identity.key)}
					<MachineSplitGroup {group} />
				{/each}
			</div>

			{#if split.noMachineNamed}
				<p class="reads" data-machine-split-note="pooled">
					No shard of this run recorded what machine it was on, so this is one figure over every
					shard. Where a run drew more than one machine - 86 of the 90 did - a pooled figure
					averages two different machines.
				</p>
			{:else if split.oneMachine}
				<p class="reads" data-machine-split-note="one-machine">
					Every shard of this run drew the same machine, so these figures compare.
				</p>
			{:else if split.spread !== null && split.slowest !== null && split.fastest !== null}
				<p class="reads" data-machine-split-note="spread" data-machine-spread={split.spread.toFixed(2)}>
					Reading ran at {(split.slowest.readTokensPerSecond ?? 0).toFixed(2)} tokens a second
					on {split.slowest.identity.name} and
					{(split.fastest.readTokensPerSecond ?? 0).toFixed(2)} on
					{split.fastest.identity.name} -
					{split.spread.toFixed(1)} times, inside one run.
				</p>
			{/if}

			{#if split.headline !== null && split.headline.writeCostRatio !== null}
				<p class="reads" data-machine-split-headline={split.headline.identity.key}>
					On {split.headline.identity.name}, which read the most tokens of this run, a written
					token cost
					<strong>{split.headline.writeCostRatio.toFixed(1)}x</strong> a read one.
				</p>
			{/if}

			<p class="reads" data-machine-split-basis data-machine-split-planned={split.outOf ?? ''}>
				{#if split.outOf === null}
					Over {split.from}
					{split.from === 1 ? 'shard' : 'shards'}. This run's manifest recorded no shard count.
				{:else}
					Over {split.from} of the run's {split.outOf} shards.
				{/if}
			</p>
		{/if}
	</Panel>
</div>

<style>
	.empty {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.splits {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(var(--auto-grid-min, 20rem), 100%), 1fr));
		gap: var(--space-4);
	}

	.reads {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
