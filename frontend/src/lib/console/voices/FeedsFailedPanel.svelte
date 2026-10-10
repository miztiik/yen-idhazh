<script lang="ts">
	import type { feedsFailed } from './feeds-failed';
	import type { PanelState } from '../waiting';
	import VoicesPanel from './VoicesPanel.svelte';
	import RecordFrame from './RecordFrame.svelte';
	import FeedTiles from './FeedTiles.svelte';
	let { view, fallback, panelState, articleState, width, height, tileMinPx, readoutMaxShare, minAttempts, notes, feedNotes, days }: {
		view: ReturnType<typeof feedsFailed> | null; fallback: ReturnType<typeof feedsFailed> | null; panelState: PanelState; articleState: PanelState;
		width: number; height: number; tileMinPx: number; readoutMaxShare: number; minAttempts: number; notes: string[]; feedNotes: string[]; days: number;
	} = $props();
</script>
{#snippet scriptless()}
	<noscript>
		<p class="notes">The feed record was included when this page was built. Article-fetch failures need scripts to read their ledger; only feeds are shown here.</p>
		{#if fallback}<FeedTiles view={fallback} {width} {height} {tileMinPx} {readoutMaxShare} {minAttempts} feedOnly={true}/>{:else}<p class="notes">The built feed record is absent or unreadable, so there is no feed-only picture.</p>{/if}
	</noscript>
{/snippet}
<VoicesPanel id="feeds-failed" title="Feeds and articles that failed" question="what happened" {days} {scriptless}
	comparison="feed reads against article fetches" reason="source outcomes, not a model trend">
	<RecordFrame {panelState} {width} {height} name="feeds-failed" label="Feed and article failures" kind="tileStrip">
		{#if view}
			<p data-lede>{view.lede}</p>
			<FeedTiles {view} {width} {height} {tileMinPx} {readoutMaxShare} {minAttempts} feedOnly={articleState === 'missing' || articleState === 'unreachable' || articleState === 'quiet'}/>
			{#if articleState === 'missing'}<p class="notes">Not published yet. The article-fetch record is absent; the feed record alone is shown.</p>
			{:else if articleState === 'unreachable'}<p class="notes">Did not arrive. The article-fetch record is unavailable; the feed record alone is shown.</p>
			{:else if articleState === 'quiet'}<p class="notes">Nothing recorded. No article-fetch rows were recorded in this span; the feed record alone is shown. This does not claim every article fetch answered.</p>{/if}
			{#if view.waiting}<p class="notes">{view.waiting}</p>{/if}
			{#if view.feedWaiting}<p class="notes">{view.feedWaiting}</p>{/if}
			{#each notes as note}<p class="notes">{note}</p>{/each}
		{/if}
	</RecordFrame>
	{#if panelState !== 'loading'}{#each feedNotes as note}<p class="notes">{note}</p>{/each}{/if}
</VoicesPanel>
