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
	 */
	import { clockUtc, longDate } from '$lib/format';
	import type { DigestDay } from '$lib/payload/types';

	let { day }: { day: DigestDay } = $props();

	const laterAdded = $derived(
		day.runs.filter((run) => run.n > 1).reduce((total, run) => total + run.items_added, 0)
	);
	const lastRun = $derived(day.runs.at(-1) ?? null);
</script>

<section class="border-b border-rule py-5" aria-label="About today">
	<h1 class="text-sm tracking-wide text-text-tertiary uppercase">
		{longDate(day.date)}
	</h1>

	<p class="mt-1 text-base text-text-secondary">
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
		{#if laterAdded > 0}
			{laterAdded} arrived after the first run.
		{/if}
		{#if lastRun}
			This page came from run {lastRun.n}, at {clockUtc(lastRun.at)}.
		{/if}
	</p>
</section>
