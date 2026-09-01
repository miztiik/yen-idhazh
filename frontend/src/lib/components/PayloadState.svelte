<script lang="ts">
	/** What a reading page says while the rest of a day is on its way, and when
	 * it never arrives.
	 *
	 * **Unreachable is its own state, and it is the reason this file exists.**
	 * Missing means a day was never published; Unreachable means the fetch
	 * failed. Telling a reader a day was never published when their train went
	 * into a tunnel is a lie they can check, so the two never share a sentence.
	 *
	 * **No spinner, no skeleton, no bar.** The frame a reader already has is
	 * readable, so there is nothing to fill. Past the threshold this says one
	 * sentence - a sentence, never a dot, which is what any machine state a
	 * reader has to act on gets here. A byte readout was weighed and refused: a
	 * compressed response reports its compressed length, so a bar drawn on it
	 * would be making its own precision up.
	 *
	 * **Nothing greys out and nothing is taken away.** The stories already on
	 * screen stay exactly as they were through every failure, and a failure
	 * offers a retry - one flaky connection may not switch the rest of a day off
	 * for the life of the page.
	 *
	 * It imports nothing at run time and formats nothing. Every word it needs
	 * arrives as a prop, which is what lets it be compiled and measured in a
	 * real browser before any route renders it.
	 */
	import type { DayStatus } from '$lib/assist/day';

	let {
		status,
		day,
		onRetry
	}: {
		status: DayStatus;
		/** The day in the reader's own words, already formatted by the caller. */
		day: string;
		onRetry: () => void;
	} = $props();
</script>

<!-- The region is here on every state, empty ones included. A live region has
     to be in the document before its text changes or nothing announces it, so
     rendering it only when there is something to say announces nothing. -->
<div aria-live="polite" data-payload-state={status}>
	{#if status === 'slow'}
		<p class="waiting">The rest of {day} is still loading.</p>
	{:else if status === 'unreachable'}
		<section class="failed">
			<p class="failed-headline">The rest of {day} did not arrive.</p>
			<p class="failed-note">The stories above are all here.</p>
			<button type="button" class="failed-retry" onclick={onRetry}>Try again</button>
		</section>
	{/if}
</div>

<style>
	/* One line of secondary text, and deliberately not a panel. A box drawn
	   around one sentence is a page apologising for a wait that may still turn
	   out to be nothing. */
	.waiting {
		margin-block: var(--space-4);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	/* The item's card, to the token: same surface, same hairline, same radius, so
	   a day that half arrived reads as the same site as a day that arrived.
	   Neutral, never a warning tint - a dropped connection is not our fault and
	   not the reader's, and colouring it like an error says something untrue
	   about the day. */
	.failed {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--space-2);
		margin-block: var(--space-6);
		padding: var(--space-5);
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
	}

	/* The one thing the eye lands on. It names the day, because "something went
	   wrong" is a sentence a reader cannot act on. */
	.failed-headline {
		margin: 0;
		font-size: var(--text-xl);
		line-height: var(--leading-xl);
		color: var(--color-text);
	}

	.failed-note {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	/* The only thing on this panel to press, so it takes a thumb-sized target
	   off the space scale rather than a number chosen here. */
	.failed-retry {
		display: inline-flex;
		align-items: center;
		min-height: var(--space-6);
		margin-block-start: var(--space-2);
		padding-inline: var(--space-4);
		border: 1px solid var(--color-accent);
		border-radius: var(--radius-md);
		background: transparent;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-accent);
		cursor: pointer;
	}

	.failed-retry:hover {
		background: var(--tint-accent);
	}
</style>
