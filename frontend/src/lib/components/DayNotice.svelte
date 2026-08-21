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
	 */
	import { longDate } from '$lib/format';
	import type { ConfidenceBand, DigestDay } from '$lib/payload/types';
	import BandBar from './BandBar.svelte';

	let { day }: { day: DigestDay } = $props();

	const counts = $derived(
		day.items.reduce(
			(totals, item) => {
				totals[item.band] += 1;
				return totals;
			},
			{ high: 0, medium: 0, low: 0 } as Record<ConfidenceBand, number>
		)
	);
	const laterRuns = $derived(day.runs.filter((run) => run.n > 1 && run.items_added > 0));
</script>

<section class="border-b border-rule py-5" aria-label="About today">
	<h1 class="text-[0.8125rem] tracking-wide text-text-tertiary uppercase">
		{longDate(day.date)}
	</h1>

	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		{day.items.length}
		{day.items.length === 1 ? 'story' : 'stories'}{#if day.partial}, {day.items_failed} did not finish{/if}.
	</p>

	{#each laterRuns as run (run.n)}
		<p class="mt-1 text-[0.9375rem] text-text-secondary">
			{run.items_added}
			{run.items_added === 1 ? 'story' : 'stories'} added later today.
		</p>
	{/each}

	{#if day.items.length > 0}
		<div class="mt-4">
			<BandBar {counts} />
		</div>
	{/if}
</section>
