<script lang="ts">
	/** What the day was, in facts rather than in a paragraph.
	 *
	 * There is deliberately no summary of the summaries. It would be the only
	 * text on the page with nowhere to click - one sourceless assertion above
	 * everything, written by the thing whose accuracy is the open question.
	 *
	 * What does belong here is the partial-run count. If four of five items did
	 * not finish and the page does not say so, a reader who works it out later
	 * has spent the trust the digest was saving.
	 *
	 * The run that made this page belongs here too, and used to sit in the
	 * footer of every page on the site - including the ones that show no day.
	 * It goes last, because a reader came for the stories and not for us.
	 *
	 * One paragraph, one sentence per fact. Every run used to print its own
	 * near-identical paragraph stating one thing.
	 *
	 * It wears the card an item wears - same surface, same hairline, same radius -
	 * so the block that opens the day and the blocks that fill it read as one
	 * site. What it does not take is the item's hover lift: this is a header, not
	 * something to point at.
	 *
	 * Two lines, not one. What the day HELD is the fact a reader came for, and how
	 * many did not finish belongs beside it because it changes that number's
	 * meaning. Which run wrote the page is provenance, and it goes quieter and
	 * last. All four in one paragraph gave the block no order to be read in.
	 */
	import { clockUtc, longDate } from '$lib/format';
	import type { DigestDay } from '$lib/payload/types';

	let { day }: { day: DigestDay } = $props();

	const laterAdded = $derived(
		day.runs.filter((run) => run.n > 1).reduce((total, run) => total + run.items_added, 0)
	);
	const lastRun = $derived(day.runs.at(-1) ?? null);
</script>

<section class="notice" aria-label="About today">
	<h1 class="notice-date">
		{longDate(day.date)}
	</h1>

	<p class="notice-count">
		{#if day.items.length === 0}
			No stories today.
		{:else}
			{day.items.length}
			{day.items.length === 1 ? 'story' : 'stories'}.
		{/if}
		{#if day.partial}
			{day.items_failed} did not finish, because we could not read enough of the page to summarize
			them fairly.
		{/if}
	</p>

	{#if laterAdded > 0 || lastRun}
		<p class="notice-run">
			{#if laterAdded > 0}
				{laterAdded} arrived after the first run.
			{/if}
			{#if lastRun}
				This page came from run {lastRun.n}, at {clockUtc(lastRun.at)}.
			{/if}
		</p>
	{/if}
</section>

<style>
	.notice {
		margin-block-end: var(--space-5);
		padding: var(--space-4);
		/* The item's card, to the token. The rule underneath it used to be the only
		   thing separating the day's facts from the day's stories, and a rule is not
		   a surface: nothing was in front of anything. */
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
	}

	/* Quiet on purpose. It is the page's heading because the page is a day, but a
	   reader came for the stories and not for the date. */
	.notice-date {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.notice-count {
		margin: var(--space-1) 0 0;
		font-size: var(--text-lg);
		line-height: var(--leading-lg);
		color: var(--color-text);
	}

	.notice-run {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	@media (min-width: 1024px) {
		.notice {
			padding: var(--space-5);
		}
	}
</style>
