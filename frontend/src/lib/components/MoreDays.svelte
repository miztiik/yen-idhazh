<script lang="ts">
	/** A way into the days before this one, without leaving the day.
	 *
	 * The archive was a separate destination, which meant "what did I miss on
	 * Tuesday" cost a page load and a scan of a list. A handful of recent days at
	 * the foot of the digest answers the common version of that question in
	 * place, and the full archive stays one link away for the rest.
	 *
	 * `/archive/` is not deleted. It is a bookmarkable URL that works, and
	 * removing it to tidy the route list would spend a reader's bookmark to buy
	 * nothing they can see.
	 */
	import { base } from '$app/paths';
	import { longDate, shortDate } from '$lib/format';
	import Icon from '$lib/icons/Icon.svelte';

	let {
		days,
		current
	}: {
		days: { date: string; items: number }[];
		current: string | null;
	} = $props();

	// The day being read is not a place to go.
	const others = $derived(days.filter((d) => d.date !== current).slice(0, 6));
</script>

{#if others.length > 0}
	<nav class="more-days" aria-label="Previous days" data-more-days>
		<h2 class="more-title">Earlier days</h2>
		<ul class="more-list">
			{#each others as day (day.date)}
				<li>
					<a class="more-day" href="{base}/{day.date}/" data-more-day={day.date}>
						<span class="more-date">{shortDate(day.date)}</span>
						<span class="more-count">
							{day.items}
							{day.items === 1 ? 'story' : 'stories'}
						</span>
						<span class="sr-only">{longDate(day.date)}</span>
					</a>
				</li>
			{/each}
		</ul>
		<a class="more-all" href="{base}/archive/">
			<Icon id="archive" size={14} />
			Every day, and search
		</a>
	</nav>
{/if}

<style>
	.more-days {
		margin-top: var(--space-8);
		padding-top: var(--space-6);
		border-top: 1px solid var(--color-rule);
	}

	.more-title {
		margin: 0 0 var(--space-3);
		font-size: var(--text-xs);
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	/* A row of days is a scan surface, not a ranked list, so it may go
	   multi-column where the archive's browse list does. The ranked order this
	   page protects is the order of the STORIES, and none of them are here. */
	.more-list {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.more-day {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-height: 2.75rem;
		padding: var(--space-2) var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--tint-neutral);
		text-decoration: none;
	}

	.more-day:hover {
		border-color: var(--color-accent);
	}

	.more-date {
		font-size: var(--text-sm);
		color: var(--color-text);
	}

	.more-count {
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	.more-all {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		min-height: 2.75rem;
		margin-top: var(--space-3);
		font-size: var(--text-sm);
		color: var(--color-accent);
	}

	.more-all:hover {
		text-decoration: underline;
	}
</style>
