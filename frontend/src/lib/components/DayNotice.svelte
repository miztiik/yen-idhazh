<script lang="ts">
	/** Identify the edition without counting its partially loaded or filtered list. */
	import { clockUtc, longDate } from '$lib/format';
	import type { DayForPage } from '$lib/payload/types';

	let { day, count }: { day: DayForPage; count: number } = $props();

	// The day's own stamp, and never the last run's `at`. `at` is one run's clock,
	// so on a day whose runs land in parallel the last entry is whichever run
	// finished the write, which can be any clock at all - and a reader who once
	// sees a time go backwards stops believing every date on the site.
	const updatedAt = $derived(day.generated_at ?? null);
</script>

<section class="notice" aria-label="About today">
	<h1 class="notice-date"><time datetime={day.date}>{longDate(day.date)}</time></h1>
	<p class="notice-meta">
		<span>
			{#if count === 0}
				No stories today
			{:else}
				{count} {count === 1 ? 'story' : 'stories'}
			{/if}
		</span>
		{#if updatedAt}
			<span aria-hidden="true" class="separator">/</span>
			<time datetime={updatedAt}>Updated {clockUtc(updatedAt)}</time>
		{/if}
	</p>
</section>

<style>
	.notice {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-1) var(--space-3);
		margin-block-end: var(--space-4);
	}

	.notice-date {
		margin: 0;
		font-family: var(--font-display);
		font-size: var(--text-lg);
		line-height: var(--leading-lg);
		font-weight: 600;
		letter-spacing: 0;
		color: var(--color-text);
	}

	.notice-meta {
		display: flex;
		align-items: baseline;
		gap: var(--space-2);
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		font-variant-numeric: tabular-nums;
		color: var(--color-text-secondary);
	}

	.separator {
		color: var(--color-text-tertiary);
	}
</style>
