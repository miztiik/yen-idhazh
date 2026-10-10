<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import RouteStatus from '$lib/components/RouteStatus.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import { tallyAsks } from '$lib/console/query-state';
	import type { SliceResult } from '$lib/data/ledger';

	let { initialAnswers = ['pending'], days, through, shimmerAfterMs, height, width }: {
		initialAnswers?: readonly (SliceResult | 'pending')[];
		days: number;
		through: string;
		shimmerAfterMs: number;
		height: number;
		width: number;
	} = $props();
	let answers = $state<readonly (SliceResult | 'pending')[]>(untrack(() => initialAnswers));
	let mounted = $state(false);
	onMount(() => { mounted = true; });
	const tally = $derived(tallyAsks(answers));
	const panelState = $derived(!mounted || tally.state === 'loading' ? 'loading' : tally.state === 'ok' ? 'ready' : tally.state);
	const empty = (): SliceResult => ({ state: 'quiet', rows: [], first: through, through, lostDays: [], setAside: {} });
	function settle(state: 'ok' | 'quiet' | 'missing' | 'unreachable') {
		if (state === 'missing') answers = Array.from({ length: 4 }, () => ({ state, rows: [], fault: 'not-packed' }));
		else if (state === 'unreachable') answers = Array.from({ length: 6 }, () => ({ state, rows: [], at: through, fault: null }));
		else if (state === 'quiet') answers = [empty()];
		else answers = [{ state, rows: [{ date: through, value: '0' }], first: through, through, lostDays: [], setAside: {} }];
	}
</script>

<RouteStatus route="machine" {answers} {days} {through} {shimmerAfterMs} onRetry={() => { answers = ['pending']; }}>
	<Reserved record panelState={panelState} {height} {width} name="waiting-fixture" label="A recorded count">
		<div data-real-count style="block-size: {height}px">0</div>
	</Reserved>
	<div data-after-box>After the chart</div>
	<button type="button" data-partly-settled onclick={() => { answers = [empty(), 'pending']; }}>One answer arrived</button>
	{#each (['ok', 'quiet', 'missing', 'unreachable'] as const) as state}
		<button type="button" data-settle={state} onclick={() => settle(state)}>{state}</button>
	{/each}
</RouteStatus>
