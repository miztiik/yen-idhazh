<script lang="ts">
	/** The screen for a status the framework handed us.
	 *
	 * The card, the words and the two ways on live in
	 * [NotHere.svelte](../lib/components/NotHere.svelte), because a dated page
	 * renders the same screen from inside itself since 2026-09-09: one shell
	 * answers every dated URL, so a date nobody published is decided in the
	 * browser rather than by a page a build did not write.
	 */
	import NotHere from '$lib/components/NotHere.svelte';
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

<NotHere
	status={page.status}
	headline={missing ? 'Not here' : 'This page did not load'}
	detail={detail ?? (missing ? 'That address is not on this site.' : 'Something broke on our side.')}
	next={missing
		? 'The address may be wrong, or the day it names was never published.'
		: 'Nothing you did caused it, and the rest of the site still works.'}
/>
