<script lang="ts">
	/** The item's footer: how sure we are, and the two things you can do next.
	 *
	 * It used to be the whole meta line and it carried four more facts. Those
	 * moved above the title on 2026-09-01, because who is speaking, which desk it
	 * is on and when it happened are what a reader uses to decide whether to read
	 * the title - and they were printed under the summary, where that decision
	 * has already been made.
	 *
	 * What stays is everything that is a claim about our summary rather than
	 * about the story. The confidence sentence is the reason for the split:
	 * printing "our summary leaves out figures from the opening" above a headline
	 * the reader has not read is a disclaimer on nothing.
	 *
	 * The way out sits at the trailing edge, so it lands in the same place on
	 * every item however long the sentences beside it run.
	 */
	import type { DigestItem } from '$lib/payload/types';
	import ConfidenceChip from './ConfidenceChip.svelte';
	import ReadAloud from './ReadAloud.svelte';
	import SourceLink from './SourceLink.svelte';

	let {
		item,
		onRead
	}: {
		item: DigestItem;
		onRead?: () => void;
	} = $props();

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

<div
	class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-secondary"
	data-item-foot
>
	<!-- Two sentences, then the two controls. The coverage line comes first
	     because it is about the story and the confidence line is about what we
	     wrote, and that is the order a reader needs them in. -->
	{#if coverageLine}
		<span class="text-text-tertiary" data-item-coverage>{coverageLine}</span>
	{/if}

	<ConfidenceChip band={item.band} reason={item.band_reason} />

	<ReadAloud title={item.title} summary={item.summary} />

	<span class="out"><SourceLink url={item.source_url} {onRead} /></span>
</div>

<style>
	/* Pinned rather than merely last: on an item whose two sentences are short
	   the link would otherwise float in the middle of the line, and a reader
	   scanning a page of items is looking for it in one place. */
	.out {
		margin-inline-start: auto;
	}
</style>
