<script lang="ts">
	/** Keep a record's four nothings in its chart's room without inventing a reading. */
	import type { Snippet } from 'svelte';
	import type { PanelState } from '../waiting';
	import Reserved from '../../components/Reserved.svelte';
	import EmptyState from '../../charts/d3/EmptyState.svelte';
	import { recordEmptyState } from '../../charts/d3/empty';
	let { panelState, width, height, name, label, kind, children }: {
		panelState: PanelState; width: number; height: number; name: string; label: string; kind: string; children: Snippet;
	} = $props();
</script>
{#if panelState === 'ready'}
	{@render children()}
{:else if panelState === 'loading'}
	<Reserved {panelState} {width} {height} {name} {label} record={true}>{#snippet children()}{/snippet}</Reserved>
{:else}
	<div class="record-frame" data-chart-type={kind} data-chart-name={name} data-readout-none="No recorded mark is available to read; agreed with Susan" data-lede>
		<EmptyState drawing={panelState === 'refused' ? recordEmptyState('refused', 'The record refused this question.') : recordEmptyState(panelState)} {width} {height} {name} {label}/>
	</div>
{/if}
<style>.record-frame :global(.empty-sentence) { font-size: var(--text-xl); line-height: var(--leading-lg); }</style>
