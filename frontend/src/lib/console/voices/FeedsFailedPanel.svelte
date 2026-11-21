<script lang="ts">
	import type { feedsFailed } from './feeds-failed';
	import type { feedFailurePreview } from './feed-failure-preview';
	import type { stateOf } from './record';
	import type { PanelState } from '../waiting';
	import VoicesPanel from './VoicesPanel.svelte';
	import RecordFrame from './RecordFrame.svelte';
	import FeedTiles from './FeedTiles.svelte';
	import FeedFailurePreview from './FeedFailurePreview.svelte';
	let { view, fallback, panelState, articleState, width, height, tileMinPx, readoutMaxShare, minAttempts, notes, feedNotes, days }: {
		view: ReturnType<typeof feedsFailed> | null; fallback: ReturnType<typeof feedFailurePreview>; panelState: PanelState; articleState: ReturnType<typeof stateOf>;
		width: number; height: number; tileMinPx: number; readoutMaxShare: number; minAttempts: number; notes: string[]; feedNotes: string[]; days: number;
	} = $props();

	const articleNote = $derived(
		articleState === 'missing' ? 'Article fetches are not published yet; showing feed reads only.' :
		articleState === 'unreachable' ? 'Article fetches did not arrive; showing feed reads only.' :
		articleState === 'quiet' ? 'No article fetches were recorded in this span; showing feed reads only.' : null
	);
	const feedOnly = $derived(articleNote !== null);
</script>
{#snippet scriptless()}
	<noscript>
		<h4>Feed failures</h4>
		<p>Article fetches need JavaScript; showing feed reads only.</p>
		<FeedFailurePreview view={fallback}/>
	</noscript>
{/snippet}
<VoicesPanel id="feeds-failed" title={feedOnly ? 'Feed failures' : 'Feeds and articles that failed'} question="what happened" {days} {scriptless}
	comparison={feedOnly ? 'feeds by days with a failure' : 'feed reads against article fetches'} reason="source outcomes, not a model trend">
	{#if feedOnly}
		<p class="notes">{articleNote}</p>
		<FeedFailurePreview view={fallback}/>
		{#each notes as note}<p class="notes">{note}</p>{/each}
	{:else}
		<RecordFrame {panelState} {width} {height} name="feeds-failed" label="Feed and article failures" kind="tileStrip">
			{#if view}
				<p data-lede>{view.lede}</p>
				<FeedTiles {view} {width} {height} {tileMinPx} {readoutMaxShare} {minAttempts}/>
				{#if view.waiting}<p class="notes">{view.waiting}</p>{/if}
				{#if view.feedWaiting}<p class="notes">{view.feedWaiting}</p>{/if}
				{#each notes as note}<p class="notes">{note}</p>{/each}
			{/if}
		</RecordFrame>
		{#if panelState !== 'loading'}{#each feedNotes as note}<p class="notes">{note}</p>{/each}{/if}
	{/if}
</VoicesPanel>
