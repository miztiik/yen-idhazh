<script lang="ts">
	/** The plainest screen on the site, and that is the design.
	 *
	 * A reader meets this when the address is wrong, and when a day we did
	 * publish could not be read. In both cases the site itself is fine, so the
	 * screen wears the same card every other block on the reading surface wears,
	 * sits inside the same header and footer, and always offers two ways on. A
	 * day that went wrong must not look like a site that is gone, and a dead end
	 * is exactly what that looks like.
	 *
	 * No icon and no tint. A mark here would decorate a moment a reader wants to
	 * leave, and a tint would make a wrong address look like a fault.
	 */
	import { base } from '$app/paths';
	import { page } from '$app/state';

	/** The framework's bare status text is not a sentence, and printing it tells
	 * a reader less than our own words do. A message a load wrote by hand does
	 * say something - "No digest was published for 2026-08-30." - so that one is
	 * printed instead. */
	const BARE = new Set(['Not Found', 'Internal Error', 'Error']);

	const missing = $derived(page.status === 404);
	const said = $derived(page.error?.message ?? '');
	const detail = $derived(said && !BARE.has(said) ? said : null);
</script>

<svelte:head>
	<title>{missing ? 'Not found' : 'This page did not load'}</title>
</svelte:head>

<section class="failed" data-error-screen data-status={page.status}>
	<h1 class="failed-headline">{missing ? 'Not here' : 'This page did not load'}</h1>
	<p class="failed-detail">
		{detail ?? (missing ? 'That address is not on this site.' : 'Something broke on our side.')}
	</p>
	<p class="failed-next">
		{missing
			? 'The address may be wrong, or the day it names was never published.'
			: 'Nothing you did caused it, and the rest of the site still works.'}
	</p>
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
