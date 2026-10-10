<script lang="ts">
	/** Which record reached this route, with one reserved standing and one shimmer. */
	import { onMount, type Snippet } from 'svelte';
	import type { RouteId } from '$lib/console/band';
	import type { LedgerReach, SliceResult } from '$lib/data/ledger';
	import { tallyAsks } from '$lib/console/query-state';
	import { routeStanding } from '$lib/console/waiting';

	let {
		route,
		answers = ['pending'],
		days,
		through = null,
		shimmerAfterMs,
		onRetry,
		children
	}: {
		route: RouteId;
		answers?: readonly (SliceResult | LedgerReach | 'pending')[];
		days: number;
		through?: string | null;
		shimmerAfterMs: number;
		onRetry: () => void;
		children: Snippet;
	} = $props();

	let mounted = $state(false);
	let shimmer = $state(false);
	onMount(() => { mounted = true; });
	const tally = $derived(mounted ? tallyAsks(answers) : { state: 'loading' as const, missing: 0, unreachable: 0 });
	const loading = $derived(mounted && tally.state === 'loading');
	$effect(() => {
		if (!loading) {
			shimmer = false;
			return;
		}
		if (!Number.isFinite(shimmerAfterMs) || shimmerAfterMs < 0) throw new Error('The route shimmer delay must be a nonnegative duration.');
		const timer = setTimeout(() => { shimmer = true; }, shimmerAfterMs);
		return () => clearTimeout(timer);
	});
	const standing = $derived(routeStanding({ ...tally, days, through, shimmer }));
</script>

<div data-console-panels={route} data-route-state={tally.state} data-shimmer={shimmer ? 'on' : 'off'}>
	<p class="route-standing" data-console-standing>
		{standing}
		{#if tally.state === 'unreachable'}
			<button type="button" data-console-retry onclick={onRetry}>Fetch the record again</button>
		{/if}
	</p>
	{@render children()}
</div>

<style>
	.route-standing {
		min-block-size: calc(var(--route-line-reserve) * var(--leading-sm));
		margin: var(--space-3) 0;
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}

	button {
		margin-inline-start: var(--space-2);
		color: var(--color-text);
		text-decoration: underline;
		text-underline-offset: var(--space-1);
	}
</style>
