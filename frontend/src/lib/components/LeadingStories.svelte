<script lang="ts">
	/** A compact index of the day's leading stories.
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
		<h2 id="leading-heading" class="leading-heading">Top stories</h2>
		<ul class="leading-list">
			{#each stories as story (story.item_id)}
				<li class="lead" data-lead={story.item_id}>
					<div class="lead-prose">
						<a class="lead-title" href="#{story.item_id}">
							{story.title}
						</a>
						<p class="lead-reason">{story.reason}</p>
					</div>
				</li>
			{/each}
		</ul>
	</section>
{/if}

<style>
	.leading {
		margin-block-end: var(--space-5);
		padding-block: var(--space-4);
		border-block: 1px solid var(--color-rule);
	}

	.leading-heading {
		margin: 0 0 var(--space-3);
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		font-weight: 600;
		letter-spacing: 0;
	}

	.leading-list {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(var(--zone-aside), 100%), 1fr));
		gap: var(--space-4) var(--space-5);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.lead {
		min-width: 0;
	}

	.lead-prose {
		max-width: var(--measure);
		font-size: var(--text-base);
		overflow-wrap: anywhere;
		text-wrap: pretty;
	}

	.lead-title {
		display: block;
		color: var(--color-text);
		font-family: var(--font-display);
		font-size: var(--text-base);
		line-height: var(--leading-base);
		font-weight: 600;
		letter-spacing: 0;
		text-decoration: none;
	}

	.lead-reason {
		margin: var(--space-1) 0 0;
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}

	.lead-title:hover,
	.lead-title:focus-visible {
		color: var(--color-accent);
		text-decoration: underline;
	}
</style>
