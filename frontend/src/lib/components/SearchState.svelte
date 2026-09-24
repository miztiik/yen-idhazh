<script lang="ts">
	/** What the on-device search is doing, as a sentence a reader reads.
	 *
	 * Both surfaces that search draw this: the archive's control, where it sits
	 * under the panel at all times, and the day page, where it appears the moment
	 * a reader types and names what the extra key costs before the key can spend
	 * it (Susan, 2026-09-24).
	 *
	 * **A stop is offered throughout, and it leaves the page exactly as it was.**
	 * Nothing greys out while the download runs, the list above stays live, and a
	 * failed download offers a retry rather than turning the feature off for the
	 * rest of the page's life.
	 *
	 * The sentences themselves are in `$lib/assist/session`, beside the machine
	 * that moves between them. This file is where they are drawn.
	 */
	import type { SearchPhase } from '$lib/assist/session';

	let {
		phase,
		sentence,
		scope = '',
		surface,
		onStop,
		onRetry
	}: {
		phase: SearchPhase;
		/** The state sentence, already built. */
		sentence: string;
		/** How far back a search reached, or the empty string before it is known. */
		scope?: string;
		/** What this block is, for a test and for nothing else. Two surfaces draw
		 * it and they are never on one page, so the sentence selectors below are
		 * unambiguous wherever a reader is. */
		surface: string;
		onStop: () => void;
		onRetry: () => void;
	} = $props();
</script>

<section class="mt-2 text-sm" data-search-block={surface}>
	<p class="text-sm text-text-tertiary" data-search-state>
		{sentence}
		{#if phase.name === 'working'}
			<button
				type="button"
				onclick={onStop}
				class="ms-1 underline underline-offset-4 hover:text-ink"
				data-search-stop
			>
				Stop
			</button>
		{:else if phase.name === 'failed'}
			<button
				type="button"
				onclick={onRetry}
				class="ms-1 underline underline-offset-4 hover:text-ink"
				data-search-retry
			>
				Try again
			</button>
		{/if}
	</p>

	{#if phase.name !== 'blocked' && scope !== ''}
		<p class="mt-1 text-sm text-text-tertiary" data-search-scope>{scope}</p>
	{/if}
</section>
