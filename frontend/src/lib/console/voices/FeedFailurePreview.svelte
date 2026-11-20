<script lang="ts">
	import { plural, shortDate } from '../../format';
	import type { feedFailurePreview } from './feed-failure-preview';

	type Preview = ReturnType<typeof feedFailurePreview>;
	type Failure = Extract<Preview, { state: 'read' }>['preview'][number];
	let { view }: { view: Preview } = $props();
</script>

{#snippet failures(rows: readonly Failure[])}
	<ol class="failure-list" role="list">
		{#each rows as row (row.id)}
			<li data-feed-row={row.id}>
				<p class="failure-heading">
					<strong>{row.id}</strong>
					<span>{row.failedDays} of {plural(row.observedDays, 'day', 'days')} checked had failures</span>
				</p>
				<p class="detail">
					{row.failedReads} of {plural(row.reads, 'recorded read', 'recorded reads')} failed.
					Last failing day: <time datetime={row.last}>{shortDate(row.last)}</time> UTC ({row.reasons.join('; ')}).
				</p>
			</li>
		{/each}
	</ol>
{/snippet}

<div class="feed-preview" data-feed-preview={view.state}>
	{#if view.state === 'read'}
		{#if view.checked === 0}
			<p class="finding" data-lede>No feed reads were recorded in this window.</p>
		{:else if view.failed === 0}
			<p class="finding" data-lede>No failures recorded among {plural(view.checked, 'checked feed', 'checked feeds')}.</p>
		{:else}
			<p class="finding" data-lede>{view.failed} of {plural(view.checked, 'checked feed', 'checked feeds')} failed at least once.</p>
		{/if}
		<p class="detail">
			{#if view.start !== view.end}<time datetime={view.start}>{shortDate(view.start)}</time>{' to '}{/if}<time datetime={view.end}>{shortDate(view.end)}</time> UTC,
			{plural(view.runs, 'recorded run', 'recorded runs')}.
		</p>
		{#if view.partial}
			<p class="detail" data-feed-preview-coverage>
				Partial feed evidence: results were recorded on {view.recordedDays} of {plural(view.days, 'day', 'days')} in this window.
				{#if view.end < view.publishedOn}Newer published days through <time datetime={view.publishedOn}>{shortDate(view.publishedOn)}</time> UTC are not counted.{/if}
				{#if view.lost.length > 0}Feed records were lost for {view.lost.map(shortDate).join(', ')} UTC.{/if}
				{#if view.setAside > 0}{plural(view.setAside, 'feed record file was', 'feed record files were')} set aside unread.{/if}
			</p>
		{/if}
		<p class="detail">
			Only days with a recorded read count as checked. Robots refusals and rests are not reads.
		</p>
		{#if view.preview.length > 0}{@render failures(view.preview)}{/if}
		{#if view.more.length > 0}
			<details data-feed-preview-more>
				<summary>
					{plural(view.more.length, 'more failing feed', 'more failing feeds')} ({plural(view.moreFailedReads, 'failed read', 'failed reads')})
					{#if view.tied > 0 && view.cutoff !== null} - {view.tied} also failed on {plural(view.cutoff, 'day', 'days')}{/if}
				</summary>
				{@render failures(view.more)}
			</details>
		{/if}
	{:else if view.state === 'not-packed'}
		<p class="finding" data-lede>Not published yet. No packed feed record was included in this build.</p>
	{:else}
		<p class="finding" data-lede>Did not arrive. The build could not read the packed feed record.</p>
	{/if}
</div>

<style>
	.feed-preview {
		min-inline-size: 0;
		overflow-wrap: anywhere;
	}
	.finding { margin: 0 0 var(--space-3); font-size: var(--text-xl); line-height: var(--leading-lg); }
	.detail { margin: var(--space-2) 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-sm); }
	.failure-list { margin: var(--space-3) 0; padding: 0; list-style: none; }
	.failure-list li { border-block-start: 1px solid var(--color-rule); padding-block: var(--space-3); }
	.failure-heading {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		column-gap: var(--space-3);
		margin: 0;
		font-variant-numeric: tabular-nums;
	}
	.failure-heading + .detail { margin-block-end: 0; }
	summary {
		min-block-size: var(--console-control-min-height);
		padding-block: var(--space-3);
		cursor: pointer;
		color: var(--color-text);
		font-weight: var(--console-control-weight);
	}
</style>
