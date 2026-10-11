<script lang="ts">
	import type { feedsFailed } from './feeds-failed';
	import { FEED_STATE_WORDS, ARTICLE_STATE_WORDS } from './feeds-failed';
	import TileStrip from '../../charts/d3/TileStrip.svelte';
	import { recordEmptyState } from '../../charts/d3/empty';
	let { view, width, height, tileMinPx, readoutMaxShare, minAttempts, feedOnly = false }: {
		view: ReturnType<typeof feedsFailed>; width: number; height: number; tileMinPx: number; readoutMaxShare: number; minAttempts: number; feedOnly?: boolean;
	} = $props();
</script>
<div class="evidence" data-chart-type={view.noCommon || view.sources.length === 0 ? 'tileStrip' : undefined} data-chart-name="feeds-failed"
	data-readout-none={view.noCommon || view.sources.length === 0 ? 'No common failed source-day can be drawn; agreed with Susan' : undefined}>
	<p class="notes" data-feed-reliability={view.feedRecord.runs >= minAttempts ? 'measured' : 'shallow'}
		data-feed-clean={view.feedRecord.clean.length} data-feed-failed={view.feedRecord.failed} data-feed-ineligible={view.feedRecord.ineligible.length} data-feed-checked={view.feedRecord.checked} data-feed-runs={view.feedRecord.runs}>
		In the feed record alone, {view.feedRecord.clean.length} of {view.feedRecord.checked} feeds had no failure over {view.feedRecord.runs} recorded runs.
		{#if view.feedRecord.runs < minAttempts}This is under {minAttempts} runs, so these are counts, not a rate.{/if}
	</p>
	<details><summary>Feed-only answers</summary>
		<ul>{#each view.feedRecord.clean as id}<li data-feed-clean-name={id}>{id}: no feed failure recorded</li>{/each}</ul>
		<ul>{#each view.feedRecord.ineligible as id}<li data-feed-ineligible-name={id}>{id}: no evidence-bearing ask</li>{/each}</ul>
	</details>
	{#if view.noCommon}
		<p class="notes">No common observed feed-and-article span can be drawn. An unobserved day is not a successful fetch.</p>
	{:else if view.sources.length === 0}
		<p class="notes">{view.completeClean ? feedOnly ? 'Every feed answered every day in the recorded feed span. Article fetches are not counted.' : 'Every feed and article fetch answered every day in the common recorded span.' : 'No failure was recorded in the common observed span; unobserved source-days are not claims of successful fetches.'}</p>
	{:else}
		<ol class="sources" data-feeds="table" data-feeds-drawn={view.sources.length} data-feeds-hidden={view.hidden}>
			{#each view.sources as source (source.sourceId)}
				<li data-failed-source={source.sourceId} data-feed={feedOnly ? source.sourceId : undefined}
					data-feed-failures={feedOnly ? source.feedFailures : undefined}
					data-feed-streak={feedOnly ? source.feedStreak : undefined}>
					<p>{source.sourceId}: {source.fired} failed days</p>
					<p class="notes">Feed</p>
					<TileStrip geometry={source.feed} empty={recordEmptyState('quiet')} name="feed-{source.sourceId}" label="{source.sourceId} feed failures" {width} {height} {tileMinPx} showAxis={feedOnly} readout={source.feedRecords} {readoutMaxShare} stateWords={FEED_STATE_WORDS}/>
					<p class="notes">{source.feedEnding}</p>
					{#if feedOnly}<p class="notes" data-feed-result>{source.feedResult}</p>{/if}
					{#if !feedOnly}
						<p class="notes">Articles</p>
						<TileStrip geometry={source.article} empty={recordEmptyState('quiet')} name="articles-{source.sourceId}" label="{source.sourceId} article failures" {width} {height} {tileMinPx} readout={source.articleRecords} {readoutMaxShare} stateWords={ARTICLE_STATE_WORDS}/>
						<p class="notes">{source.ending}</p>
					{/if}
				</li>
			{/each}
		</ol>
	{/if}
	<p class="notes">Filled: a failure. Outlined: recorded with no failure. Dashed: not recorded as asked. Both rows use the same UTC days.</p>
	<p class="notes">{view.tail}</p>
	{#if view.hidden > 0}<p class="notes" data-feeds-more>{view.hidden} more feeds or article sources failed in this span.</p>{/if}
</div>
<style>.sources { padding: 0; list-style: none; } .sources li { margin-block: var(--space-5); }</style>
