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
	 * **The count arrives as a prop and is never taken off `day.items`.** A
	 * reading document carries a seed of the day and fetches the rest, so a count
	 * of the list in hand states the seed - it ticks up while the reader watches
	 * with script on, and stays wrong for ever with script off, four lines above a
	 * topic row printing the day's real total on the same screen. The caller reads
	 * a bounded fact off the payload instead: the whole day's total, or one desk's,
	 * depending on which page this is.
	 */
	import { clockUtc, longDate } from '$lib/format';
	import type { DayForPage } from '$lib/payload/types';

	let { day, count }: { day: DayForPage; count: number } = $props();

	// A payload written before a served day carried its runs says nothing about
	// them, so this block does not draw. Absent is unknown, and "this page came
	// from run 1" is a claim nothing here can make.
	const runs = $derived(day.runs ?? []);
	const laterAdded = $derived(
		runs.filter((run) => run.n > 1).reduce((total, run) => total + run.items_added, 0)
	);
	// The day's own stamp, and never the last run's `at`. `at` is one run's clock,
	// so on a day whose runs land in parallel the last entry is whichever run
	// finished the write, which can be any clock at all - and a reader who once
	// sees a time go backwards stops believing every date on the site.
	const updatedAt = $derived(day.generated_at ?? null);
</script>

<section class="notice" aria-label="About today">
	<div class="notice-heading">
		<h1 class="notice-date">{longDate(day.date)}</h1>
		<p class="notice-count">
			{#if count === 0}
				No stories today.
			{:else}
				{count} {count === 1 ? 'story' : 'stories'}.
			{/if}
		</p>
	</div>

	{#if day.partial === true && day.items_failed !== null && day.items_failed !== undefined}
		<p class="notice-status">
			{day.items_failed} {day.items_failed === 1 ? 'article' : 'articles'} did not finish.
		</p>
	{/if}

	{#if laterAdded > 0 || updatedAt}
		<p class="notice-run">
			{#if updatedAt}
				<span>Updated {clockUtc(updatedAt)}.</span>
			{/if}
			{#if laterAdded > 0}
				<span>{laterAdded} added after this page first went up.</span>
			{/if}
		</p>
	{/if}
</section>

<style>
	.notice {
		margin-block-end: var(--space-5);
	}

	.notice-heading {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-1) var(--space-4);
	}

	.notice-date {
		margin: 0;
		font-family: var(--font-display);
		font-size: var(--text-xl);
		line-height: var(--leading-xl);
		font-weight: 600;
		letter-spacing: 0;
		color: var(--color-text);
	}

	.notice-count {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.notice-status,
	.notice-run {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.notice-run {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-3);
	}
</style>
