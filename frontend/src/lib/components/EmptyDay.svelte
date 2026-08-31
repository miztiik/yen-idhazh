<script lang="ts">
	/** Nothing published is a legitimate outcome, not an error.
	 *
	 * It is also a state a reader meets often enough that it deserves the same
	 * treatment as everything else. Left plain it reads as a page that broke,
	 * which is the wrong reading of a quiet news day.
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
	<nav class="empty-nav">
		{#if latest && latest !== date}
			<a href="{base}/{latest}/" class="text-accent hover:underline">
				Latest day - {longDate(latest)}
			</a>
		{/if}
		<a href="{base}/archive/" class="text-accent hover:underline">All days</a>
	</nav>
</section>

<style>
	.empty {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--space-2);
		margin-block: var(--space-8);
		padding: var(--space-6);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		/* Neutral, never a warning tint. A quiet day is not a fault, and colouring
		   it like one tells the reader something untrue about the pipeline. */
		background: var(--tint-neutral);
	}

	.empty-mark {
		margin: 0;
		color: var(--color-text-tertiary);
	}

	.empty-headline {
		margin: 0;
		font-size: var(--text-lg);
		line-height: var(--leading-lg);
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
		margin-top: var(--space-3);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}
</style>
