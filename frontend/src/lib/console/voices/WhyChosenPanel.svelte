<script lang="ts">
	import type { whyChosen } from './why-chosen';
	import type { PanelState } from '../waiting';
	import VoicesPanel from './VoicesPanel.svelte';
	import RecordFrame from './RecordFrame.svelte';
	import PartsOfOne from '../../charts/d3/PartsOfOne.svelte';
	import { recordEmptyState } from '../../charts/d3/empty';
	let { view, panelState, width, height, readoutMaxShare, notes }: {
		view: ReturnType<typeof whyChosen>; panelState: PanelState; width: number; height: number; readoutMaxShare: number; notes: string[];
	} = $props();
</script>
<VoicesPanel id="why-chosen" title="Why the newest day's articles were chosen" question="what happened"
	comparison="authority against the four bonuses" reason="one day's choice, not a model trend">
	<RecordFrame {panelState} {width} {height} name="why-chosen" label="Parts of selection scores" kind="partsOfOne">
		<p data-lede>{view.lede}</p>
		<div class="evidence" data-chart-type={view.geometry === null ? 'partsOfOne' : undefined} data-chart-name="why-chosen"
			data-readout-none={view.geometry === null ? 'No filled selection part is available for a chart readout; agreed with Susan' : undefined}>
			{#if view.geometry !== null}
				<PartsOfOne geometry={view.geometry} empty={recordEmptyState('quiet')} name="why-chosen" label="Authority and four bonuses" {width} {height} readout={view.records} {readoutMaxShare}/>
			{:else if view.complete > 0}
				<p class="notes">Every recorded selection part is zero, so no filled score bar is drawn.</p>
				{#each view.records as record}<h4>{record.subject}</h4><dl>{#each record.facts as fact}<dt>{fact.label}</dt><dd>{fact.value}</dd>{/each}</dl>{/each}
			{:else}
				<p class="notes">No complete additive selection score was recorded, so no score bar is drawn.</p>
			{/if}
		</div>
		<p class="notes">{view.drawn} of {view.complete} candidates with five parts that add to their selection score are drawn; {view.hidden} more lie below this list. {view.incomplete} of {view.count} identified candidates lack a complete, additive score. {view.unknownIdentity} newest-day rows lack an item identity or numeric run suffix. Authority already contains tier, feed weight and reliability; those factors are not extra parts.</p>
		{#each notes as note}<p class="notes">{note}</p>{/each}
	</RecordFrame>
</VoicesPanel>
