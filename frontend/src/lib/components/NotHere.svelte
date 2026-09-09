<script lang="ts">
	/** The plainest screen on the site, and that is the design.
	 *
	 * A reader meets it when the address is wrong, and when the day an address
	 * names was never published. In both cases the site itself is fine, so the
	 * screen wears the same card every other block on the reading surface wears,
	 * sits inside the same header and footer, and always offers two ways on. A
	 * day that went wrong must not look like a site that is gone, and a dead end
	 * is exactly what that looks like.
	 *
	 * No icon and no tint. A mark here would decorate a moment a reader wants to
	 * leave, and a tint would make a wrong address look like a fault.
	 *
	 * **Two callers, one card.** The framework's error page renders it for a
	 * status it was handed, and a dated page renders it when the host answers
	 * that it holds no payload for that date. Until 2026-09-09 only the first
	 * existed, because a date nobody published had no page for a reader to reach.
	 * One shell answers every dated URL now, so the same screen has to be
	 * reachable from inside a page - and one component is what stops the two
	 * saying different things to a reader who cannot tell them apart.
	 */
	import { base } from '$app/paths';

	let {
		headline,
		detail,
		next,
		status
	}: {
		headline: string;
		/** The one sentence that differs between the two callers. */
		detail: string;
		next: string;
		/** What the host answered, for a check that wants to read it. */
		status: number;
	} = $props();
</script>

<section class="failed" data-error-screen data-status={status}>
	<h1 class="failed-headline">{headline}</h1>
	<p class="failed-detail">{detail}</p>
	<p class="failed-next">{next}</p>
	<nav class="failed-nav" aria-label="Where to go next">
		<a href={base || '/'} class="failed-link">Today</a>
		<a href="{base}/archive/" class="failed-link">All days</a>
	</nav>
</section>

<style>
	.failed {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--space-2);
		margin-block: var(--space-6);
		padding: var(--space-5);
		/* The item's card, to the token. Every other block a reader sees here is
		   one, so a bare block of text on the page ground is the one screen that
		   looks like the stylesheet failed to load. */
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
	}

	.failed-headline {
		margin: 0;
		font-size: var(--text-xl);
		line-height: var(--leading-xl);
		font-weight: 600;
		color: var(--color-text);
	}

	.failed-detail {
		margin: 0;
		font-size: var(--text-base);
		line-height: var(--leading-base);
		color: var(--color-text);
	}

	.failed-next {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.failed-nav {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-4);
		margin-block-start: var(--space-2);
	}

	/* The only thing on the screen to press, so it gets a thumb-sized target. */
	.failed-link {
		display: inline-flex;
		align-items: center;
		min-height: var(--space-6);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-accent);
	}

	.failed-link:hover {
		text-decoration: underline;
	}
</style>
