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
	import type { DigestCoverage, DigestItem } from '$lib/payload/types';
	import ConfidenceChip from './ConfidenceChip.svelte';
	import ReadAloud from './ReadAloud.svelte';
	import SourceLink from './SourceLink.svelte';

	let {
		item,
		stack = [],
		onRead
	}: {
		item: DigestItem;
		/** The other newsrooms that ran this story, as links this page can reach.
		 * Empty where a card stands alone, and then the count below prints instead. */
		stack?: DigestCoverage[];
		onRead?: () => void;
	} = $props();

	/** How many of our sources carried this story, as a sentence.
	 *
	 * The wording is the Editor's, from row 9 of the reading-page plan. The only
	 * departure is the singular: the ruling reads `Also covered by N other
	 * sources today.`, and at N of 1 that sentence is not English.
	 *
	 * It is a fact about our feed set and never a claim about the world - we
	 * cannot know who else covered a story, only who we read. Null prints
	 * nothing at all, because a day published before the pass existed recorded
	 * no answer and 0 would be a different claim.
	 *
	 * **Zero also prints nothing, and that is a ruling rather than an oversight.**
	 * It used to print `Only one of our sources carried this.` The Editor read
	 * 2026-09-12 by hand on 2026-09-14 and counted about 95 of 356 items in a
	 * cross-source cluster - 27 percent - where the pass had found 8. So roughly
	 * a quarter of the items carrying that sentence were on the page more than
	 * once and the sentence was false. 2026-09-03 printed it on five cards about
	 * one acquisition while another card on the same page said the story was
	 * covered twice. What the reader loses is the genuine signal that a story is
	 * an exclusive; that is a real loss, and a signal wrong a quarter of the time
	 * is not one. It comes back when recall is measured.
	 */
	function coverage(count: number | null | undefined): string | null {
		if (count === null || count === undefined || count === 0) return null;
		if (count === 1) return 'Also covered by 1 other source today.';
		return `Also covered by ${count} other sources today.`;
	}
	const coverageLine = $derived(coverage(item.also_covered_by));
	/** How many other outlets the stack does not name.
	 *
	 * The stack is capped and it drops a name this page cannot reach, so the count
	 * and the names part company and the difference is owed to the reader - a card
	 * saying two newsrooms on a story five carried is a wrong number, which is the
	 * one thing this whole block exists to avoid. `also_covered_by` is the count and
	 * it is whole, so the subtraction is the honest remainder. Never below zero: on
	 * a day published before the count existed it is null, and a stack of two would
	 * otherwise print "and -2 more".
	 */
	const more = $derived(Math.max((item.also_covered_by ?? stack.length) - stack.length, 0));
</script>

<div
	class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-secondary"
	data-item-foot
>
	<!-- Two sentences, then the two controls. The coverage line comes first
	     because it is about the story and the confidence line is about what we
	     wrote, and that is the order a reader needs them in.

	     Names where the page has them, and the bare count where it does not. They
	     answer different questions - who ran it, and how many did - and the names
	     are the more useful answer, so the count only prints where no name can be
	     linked. Every name is a link to OUR page for that newsroom's piece: our
	     summary of it, and its own way out to the original. A reader who wanted the
	     publisher's version is one more click away and a reader who wanted ours has
	     not lost it. -->
	{#if stack.length > 0}
		<span class="stack" data-item-stack={stack.length}>
			<span class="stack-label">Also covered by</span>
			{#each stack as other (other.item_id)}
				<a class="pill" href="#{other.item_id}" data-coverage-pill={other.item_id}>
					{other.source_name}
				</a>
			{/each}
			{#if more > 0}
				<span class="stack-more" data-coverage-more={more}>and {more} more</span>
			{/if}
		</span>
	{:else if coverageLine}
		<span class="text-text-tertiary" data-item-coverage>{coverageLine}</span>
	{/if}

	<ConfidenceChip band={item.band} reason={item.band_reason} />

	<ReadAloud title={item.title} summary={item.summary} />

	<span class="out"><SourceLink url={item.source_url} {onRead} /></span>
</div>

<style>
	/* The stack reads as one sentence with the mastheads set in it, so it wraps as
	   one thing and keeps its own rhythm inside the footer's flex row. */
	.stack {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
		color: var(--color-text-tertiary);
	}

	.stack-label,
	.stack-more {
		color: var(--color-text-tertiary);
	}

	/* A masthead, not a button. The hairline is what says it is a thing you can
	   press; the surface is the card's own, so a row of them does not become a row
	   of blocks under a summary. The tap target is the footer's line height plus
	   this padding, which is what a name beside a name can afford - the two
	   controls at the trailing edge are where the 44px targets are. */
	.pill {
		display: inline-flex;
		align-items: center;
		padding: var(--space-1) var(--space-2);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-full);
		color: var(--color-text-secondary);
		line-height: var(--leading-xs);
	}

	.pill:hover,
	.pill:focus-visible {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	/* Pinned rather than merely last: on an item whose two sentences are short
	   the link would otherwise float in the middle of the line, and a reader
	   scanning a page of items is looking for it in one place. */
	.out {
		margin-inline-start: auto;
	}
</style>
