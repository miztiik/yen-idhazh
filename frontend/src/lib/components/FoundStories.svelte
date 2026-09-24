<script lang="ts">
	/** What a meaning-based search found, drawn where the day's stream was.
	 *
	 * **One list, and the answer replaces it.** The archive settled this and the
	 * reason holds harder here: two lists leave a reader working out which one
	 * answered them, and on a reading page the day's leading block, its zone note
	 * and its hide-read control would all sit under a cross-day answer and read
	 * as part of it. What the reader loses is the day they came to read, while an
	 * answer is up - which is paid back by making the return free. The next
	 * keystroke in the field brings the day back, narrowed, and the control at the
	 * head of this list is the second way for a reader who does not type again
	 * (Susan, 2026-09-24).
	 *
	 * **A result names a day, and the day is fetched only for the results on
	 * screen.** The month index carries a title, a date and a topic and no
	 * summary - it would be over six times the entry - so a story is rendered from
	 * the day it names, through the same card the stream uses. A day that cannot
	 * be read is the designed null `assist/day.ts` returns: the result keeps its
	 * title, its date and its topic and loses the summary. The page never waits on
	 * that and never breaks on it.
	 */
	import { base } from '$app/paths';
	import DigestItemView from '$lib/components/DigestItem.svelte';
	import { itemOf } from '$lib/assist/day';
	import { shortDate } from '$lib/format';
	import type { SearchOutcome } from '$lib/assist/search';
	import type { DayForPage } from '$lib/payload/types';

	let {
		found,
		days,
		verticalNames,
		onClear
	}: {
		found: SearchOutcome;
		/** One entry per result day, so a re-render draws a day the moment it
		 * lands. A date with no entry yet is a result still waiting for its day. */
		days: Record<string, DayForPage | null>;
		verticalNames: Record<string, string>;
		/** Put the day back. The field's next keystroke does this too. */
		onClear: () => void;
	} = $props();
</script>

<section aria-label="Search results" data-day-found>
	<div class="head">
		<h2 class="text-lg font-semibold text-text">Found on other days</h2>
		<button type="button" onclick={onClear} class="text-sm text-accent hover:underline" data-day-found-clear>
			Show this day again
		</button>
	</div>

	<ul data-day-found-rows>
		{#each found.hits as hit (`${hit.entry.date}-${hit.entry.item_id}`)}
			{@const item = itemOf(days[hit.entry.date] ?? null, hit.entry.item_id)}
			{@const href = `${base}/${hit.entry.date}/#${hit.entry.item_id}`}
			<li data-day-found-date={hit.entry.date}>
				{#if item}
					<DigestItemView
						{item}
						verticalName={verticalNames[item.vertical] ?? item.vertical}
						level={3}
						showVertical={false}
						showMark={false}
						day={{ date: hit.entry.date, href }}
					/>
				{:else}
					<p class="border-b border-rule py-3">
						<a {href} class="text-lg text-accent hover:underline">{hit.entry.title}</a>
						<span class="mt-1 block text-sm text-text-tertiary">
							{shortDate(hit.entry.date)} &mdash; {verticalNames[hit.entry.vertical] ??
								hit.entry.vertical}
						</span>
					</p>
				{/if}
			</li>
		{/each}
	</ul>
</section>

<style>
	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--space-2) var(--space-4);
		margin-block: var(--space-5) var(--space-3);
	}
</style>
