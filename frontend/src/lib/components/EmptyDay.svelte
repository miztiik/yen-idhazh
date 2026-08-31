<script lang="ts">
	/** Nothing published is a legitimate outcome, not an error.
	 *
	 * It is also a state a reader meets often enough that it deserves the same
	 * treatment as everything else. Left plain it reads as a page that broke,
	 * which is the wrong reading of a quiet news day.
	 *
	 * So it is the card an item is: `--color-surface`, the item's hairline and
	 * the item's radius. A quiet day and a busy day are then visibly the same
	 * site. What it does not take is the item's hover lift - the panel is not a
	 * target, and the two links inside it answer the pointer and the keyboard
	 * themselves.
	 */
	import { base } from '$app/paths';
	import { longDate } from '$lib/format';
	import Icon from '$lib/icons/Icon.svelte';

	let { date, latest }: { date: string | null; latest: string | null } = $props();
</script>

<section class="empty" data-empty-day>
	<p class="empty-mark" aria-hidden="true">
		<Icon id="archive" size={20} />
	</p>
	{#if date}
		<p class="empty-headline">Nothing was published for {longDate(date)}.</p>
	{:else}
		<p class="empty-headline">No digest has been published yet.</p>
	{/if}
	<p class="empty-note">That can mean there was no news, or the run did not finish.</p>
	<nav class="empty-nav" aria-label="Other days">
		{#if latest && latest !== date}
			<a href="{base}/{latest}/" class="empty-link">
				Latest day - {longDate(latest)}
			</a>
		{/if}
		<a href="{base}/archive/" class="empty-link">All days</a>
	</nav>
</section>

<style>
	.empty {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--space-2);
		margin-block: var(--space-6);
		padding: var(--space-5);
		/* The item's card, to the token: same surface, same hairline, same radius.
		   A day with nothing on it then reads as the same site as a day with 431
		   stories on it, which is the whole point of the state. */
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		/* Neutral, never a warning tint. A quiet day is not a fault, and colouring
		   it like one tells the reader something untrue about the pipeline. The
		   surface IS the neutral ground here; the wash this used to carry only made
		   one panel a different colour from every other panel on the site. */
		background: var(--color-surface);
	}

	.empty-mark {
		margin: 0;
		color: var(--color-text-tertiary);
	}

	/* The one thing the eye lands on. On a home page whose day published nothing,
	   this line is the whole page. */
	.empty-headline {
		margin: 0;
		font-size: var(--text-xl);
		line-height: var(--leading-xl);
		color: var(--color-text);
	}

	.empty-note {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.empty-nav {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-4);
		margin-block-start: var(--space-2);
	}

	/* A thumb needs a target, and these two links are the only thing on the
	   screen to press. The height is a step on the space scale, not a number
	   chosen here. */
	.empty-link {
		display: inline-flex;
		align-items: center;
		min-height: var(--space-6);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-accent);
	}

	.empty-link:hover {
		text-decoration: underline;
	}
</style>
