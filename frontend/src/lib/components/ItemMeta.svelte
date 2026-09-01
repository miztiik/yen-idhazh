<script lang="ts">
	/** Where it came from, how sure we are, and the way out.
	 *
	 * Order is deliberate: what it is, then what it says, then where it came
	 * from and how sure we are. The confidence claim is about the summary, so it
	 * sits after it, next to the link that lets you check.
	 *
	 * A search result adds one thing to that line and removes one: the day the
	 * archive found it on, as the link back to it, in place of the day the
	 * publisher put on it. The two are the same day or one apart, and printing
	 * both puts two dates on a line that is already four facts long.
	 *
	 * The source monogram is not here. It moved to the item's leading edge, where
	 * it carries the read state - and this line moves into a 14rem right rail on
	 * a wide screen, so a read mark left in it would sit 14rem from the title it
	 * qualifies.
	 *
	 * The coverage sentence is here rather than beside the title because it is a
	 * fact about where the story came from, which is what this line is for.
	 */
	import { KIND_WORTH_SAYING, SOURCE_KINDS } from '$lib/bands';
	import { shortDate } from '$lib/format';
	import type { DigestItem } from '$lib/payload/types';
	import ConfidenceChip from './ConfidenceChip.svelte';
	import ReadAloud from './ReadAloud.svelte';
	import SourceLink from './SourceLink.svelte';

	let {
		item,
		day,
		onRead
	}: {
		item: DigestItem;
		/** The digest day this item was found on, and the way back to it. */
		day?: { date: string; href: string };
		onRead?: () => void;
	} = $props();
	const kindWorthSaying = $derived(KIND_WORTH_SAYING.includes(item.source_kind));

	/** How many of our sources carried this story, as a sentence.
	 *
	 * Both wordings are the Editor's, from row 9 of the reading-page plan. The
	 * only departure is the singular: the ruling reads `Also covered by N other
	 * sources today.`, and at N of 1 that sentence is not English.
	 *
	 * It is a fact about our feed set and never a claim about the world - we
	 * cannot know who else covered a story, only who we read. Null prints
	 * nothing at all, because a day published before the pass existed recorded
	 * no answer and 0 would be a different claim.
	 */
	function coverage(count: number | null | undefined): string | null {
		if (count === null || count === undefined) return null;
		if (count === 0) return 'Only one of our sources carried this.';
		if (count === 1) return 'Also covered by 1 other source today.';
		return `Also covered by ${count} other sources today.`;
	}
	const coverageLine = $derived(coverage(item.also_covered_by));
</script>

<div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-secondary">
	<span>{item.source_name}</span>

	{#if kindWorthSaying}
		<span class="text-text-tertiary">{SOURCE_KINDS[item.source_kind]}</span>
	{/if}

	{#if coverageLine}
		<span class="text-text-tertiary" data-item-coverage>{coverageLine}</span>
	{/if}

	{#if day}
		<a href={day.href} class="text-text-tertiary hover:underline" data-item-day={day.date}>
			{shortDate(day.date)}
		</a>
	{:else if item.published_at}
		<span class="text-text-tertiary">{shortDate(item.published_at.slice(0, 10))}</span>
	{/if}

	<ConfidenceChip band={item.band} reason={item.band_reason} />

	<ReadAloud title={item.title} summary={item.summary} />

	<SourceLink url={item.source_url} {onRead} />
</div>
