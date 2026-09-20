<script lang="ts">
	/** Which machines one run was actually given.
	 *
	 * A run is not a machine: over the committed record, 86 of the 90 runs that
	 * name a processor drew more than one kind, so one card a machine is the only
	 * honest grain.
	 */
	import MachineCard from '$lib/components/MachineCard.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import type { MachineCards } from '$lib/charts/machine-cards';

	let { machines }: { machines: MachineCards } = $props();
</script>

<div
	data-readout-none="one card per machine, nothing shared"
	data-machine-cards={machines.runId}
	data-machine-record={machines.record}
>
	<Panel
		heading="h3"
		id="machine-cards"
		title="Which machines this run was given"
		note="A run is not a machine and most runs draw more than one kind, so a rate quoted for the whole run belongs to none of them - one card a machine of the newest run."
	>
		{#if machines.nothing === 'recording-off'}
			<p class="empty" data-machine-panel-empty="machines-off">
				What machine this job drew is not being recorded. The processor name below comes from the
				model server's own counters.
			</p>
		{:else if machines.nothing === 'record-lost'}
			<p class="empty" data-machine-panel-empty="machines-lost">
				{machines.lostNote}
				{#if machines.runId !== ''}
					The run was {machines.runId}.
				{/if}
			</p>
		{:else if machines.nothing === 'no-machine'}
			<p class="empty" data-machine-panel-empty="machines-none">
				No shard of this run recorded what machine it was on.
				{#if machines.runId !== ''}
					The run was {machines.runId}.
				{/if}
			</p>
		{:else}
			{#if !machines.recording}
				<p class="empty" data-machine-panel-note="machines-off">
					What machine this job drew is not being recorded. The processor name below comes from the
					model server's own counters.
				</p>
			{:else if machines.lostNote}
				<p class="empty" data-machine-panel-note="machines-lost">
					{machines.lostNote}
				</p>
			{/if}
			<div class="machines">
				{#each machines.cards as card (card.identity.key)}
					<MachineCard {card} lost={machines.lost !== null} />
				{/each}
			</div>
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

	.machines {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(var(--auto-grid-min, 20rem), 100%), 1fr));
		gap: var(--space-4);
	}
</style>
