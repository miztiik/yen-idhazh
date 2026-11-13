<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { Range } from '../queries/window';
	import { countDays } from '../span-words';
	import Panel from '$lib/components/Panel.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	let { id, title, state, height, width, children, retry, heading = 'h3', range, windowed }: {
		id: string; title: string; state: 'loading' | 'ok' | 'quiet' | 'missing' | 'unreachable';
		height: number; width: number; children: Snippet; retry: () => void;
		heading?: 'h2' | 'h3';
		range?: Range;
		windowed?: { name: string; days: number };
	} = $props();
</script>

<div data-machine-panel-state={state} data-readout-fetched data-panel-query={id}
	data-windowed={windowed?.name} data-window-days={windowed?.days}
	aria-label={windowed === undefined ? undefined : `${title}, selected window ${countDays(windowed.days)}`}
	data-window-exempt={['two-clocks', 'memory-held'].includes(id) ? 'newest-run' : undefined}>
	{#if state === 'ok'}
		{@render children()}
	{:else}
		<Panel {id} {title} {heading} verdict={id === 'two-clocks'} note="The published record has not answered this comparison yet.">
			<div data-readout-none="The requested record has no drawing yet; agreed with Susan"
				data-empty-state={state === 'loading' ? undefined : state}
				data-model-rule-name={`machine-${id}`}
				data-model-rule="no" data-model-rule-none="No record is available for this comparison yet.">
				<Reserved panelState={state} {height} {width} name={id} label={title} record>
					{#snippet children()}{/snippet}
				</Reserved>
				{#if state === 'unreachable'}<button type="button" onclick={retry}>Try this record again</button>{/if}
			</div>
			{#if range !== undefined}
				<p data-native-window data-range-from={range.from} data-range-to={range.to}>Native record: {range.from} through {range.to} UTC.</p>
			{/if}
		</Panel>
	{/if}
</div>
