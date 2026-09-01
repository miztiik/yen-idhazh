<script lang="ts">
	/** The day's leading stories: the page's first screen.
	 *
	 * Five at most, chosen across the whole day by the pipeline and published on
	 * the day payload. The block draws what it is handed and decides nothing:
	 * re-ranking here would make a shared link show the recipient a different
	 * page from the one the sender saw.
	 *
	 * No numerals. A number beside a story implies a score we would then owe the
	 * reader an explanation for, and the block already gives its reason in
	 * words. The order is in the DOM, and it is not a claim about a ranking, so
	 * this is an unordered list.
	 *
	 * Every entry is an anchor into the stream below rather than a copy of the
	 * story. The stream still carries all of them, in the published order, so
	 * nothing here removes, hides or re-orders a single story.
	 *
	 * It imports nothing at run time. That is a constraint rather than an
	 * accident: the browser suite compiles this file on its own and renders it
	 * with props, because the canary day has one desk and cannot fill a block
	 * that allows two stories per desk.
	 */
	import type { LeadingStory } from '$lib/day-shape';

	let { stories }: { stories: LeadingStory[] } = $props();
</script>

{#if stories.length > 0}
	<section class="leading" aria-labelledby="leading-heading" data-leading>
		<h2
			id="leading-heading"
			class="mb-3 text-sm font-semibold tracking-wide text-text-tertiary uppercase"
		>
			Leading today
		</h2>
		<ul class="leading-list">
			{#each stories as story (story.item_id)}
				<li class="lead" data-lead={story.item_id}>
					<a class="lead-title measure text-xl font-semibold text-text" href="#{story.item_id}">
						{story.title}
					</a>
					<p class="measure mt-1 text-base text-text-secondary">{story.reason}</p>
				</li>
			{/each}
		</ul>
	</section>
{/if}

<style>
	/* The item's card, to the token: same surface, same hairline, same radius.
	   The block that opens the day and the blocks that fill it then read as one
	   site rather than as two designs. It takes no hover lift - the card is not
	   a target, and the links inside it answer the pointer themselves. */
	.leading {
		margin-block-end: var(--space-5);
		padding: var(--space-4);
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
	}

	.leading-list {
		display: grid;
		gap: var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	/* A rule between the leads and none above the first or below the last. The
	   card's own edge already does that job, and a second line beside it reads
	   as a box inside a box. */
	.lead + .lead {
		padding-block-start: var(--space-4);
		border-block-start: 1px solid var(--color-rule);
	}

	.lead-title {
		display: block;
		text-decoration: none;
		/* An unbroken headline token is the one thing in this block that can force
		   a horizontal scrollbar, and no reader-facing surface carries one. Stated
		   here rather than left to the `measure` utility, so the promise holds
		   wherever this component is drawn. */
		overflow-wrap: anywhere;
	}

	.lead-title:hover,
	.lead-title:focus-visible {
		color: var(--color-accent);
		text-decoration: underline;
	}
</style>
