<script lang="ts">
	import type { fetchTime } from './fetch-time';
	import type { PanelState } from '../waiting';
	import VoicesPanel from './VoicesPanel.svelte';
	import RecordFrame from './RecordFrame.svelte';
	import RankedList from '../../components/RankedList.svelte';
	import ChartReadout from '../../components/ChartReadout.svelte';
	import { markReadout } from '../../charts/readout';
	import type { RankedRow, RankedDisplay } from '../../charts/rank';
	import { formatNumber } from '../../number-format';
	import { useNumberFormat } from '../../number-format-context';
	let { view, panelState, width, height, readoutMaxShare, notes, days }: {
		view: ReturnType<typeof fetchTime>; panelState: PanelState; width: number; height: number; readoutMaxShare: number; notes: string[]; days: number;
	} = $props();
	const numberFormat = useNumberFormat();
	let selected = $state<number | null>(null);
</script>
{#snippet timingTrack(row: RankedRow<RankedDisplay>)}
	{@const entry = view.geometry?.rows.find((candidate) => candidate.key === row.key)}
	<span class="timing-track" data-readout-at={view.geometry?.rows.findIndex((candidate) => candidate.key === row.key)}>
		{#if entry?.segments.length}
			{#each entry.segments as part (part.label)}<span class="timing-part" style="inset-inline-start: {part.start}; inline-size: {part.size}; background: var({part.token})" aria-label="{part.label}: {formatNumber(part.value, numberFormat, { si: false })} ms"></span>{/each}
		{:else}<span class="timing-whole" style="inline-size: {row.percent}"></span>{/if}
	</span>
{/snippet}
<VoicesPanel id="fetch-time" title="Where a fetch spent its time" question="what happened" {days}
	comparison="largest recorded part against the other parts" reason="ranking of recorded fetch clocks, not a model trend">
	<RecordFrame {panelState} {width} {height} name="fetch-time" label="Fetch timing" kind="rankedList">
		<p data-lede>{view.lede}</p>
		<div class="evidence">
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<div tabindex={view.records.length ? 0 : undefined} role="group" aria-label="Fetch time by source" data-readout-records={view.records.length || undefined}
				use:markReadout={{ count: view.records.length, walk: 'list', selected, onSelect: (index) => selected = index }}>
				<RankedList caption="Mean fetch time" geometry={view.geometry} maxText={view.maxText} unmeasuredNote="The fetch clocks were not recorded." emptyNote="No fetch has the whole and robots clocks this comparison needs." tail={view.tail}
					track={timingTrack}
					selectedKey={selected === null ? null : view.summaries[selected]?.id ?? null}
					onSelect={(key) => selected = view.summaries.findIndex((row) => row.id === key)}/>
			{#if view.records.length}<ChartReadout readout={view.records[selected ?? 0] ?? null} resting={selected === null} name="fetch-time" maxShare={readoutMaxShare} restingNote=", the slowest source" hint="Point at a bar or pick its source name. Up and Down move between sources; Escape returns to the slowest."/>{/if}
			</div>
		</div>
		<p class="notes">{view.finding}</p>
		{#if view.noRetries}<p class="notes">No fetch was retried.</p>{/if}
		{#each notes as note}<p class="notes">{note}</p>{/each}
	</RecordFrame>
</VoicesPanel>
<style>
	.timing-track { display: block; position: relative; block-size: var(--space-3); }
	.timing-part { position: absolute; inset-block: 0; }
	.timing-whole { display: block; block-size: 100%; background: var(--chart-1); }
</style>
