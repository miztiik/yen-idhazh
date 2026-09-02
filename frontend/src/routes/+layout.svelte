<script lang="ts">
	import '../styles/app.css';
	import { afterNavigate } from '$app/navigation';
	import { base } from '$app/paths';
	import { restoreAnchor } from '$lib/assist/day';
	import { startOfflineReader } from '$lib/offline';
	import { OFFLINE_VERSION } from '$lib/offline.generated';
	import SiteFooter from '$lib/components/SiteFooter.svelte';
	import SiteHeader from '$lib/components/SiteHeader.svelte';
	import { onMount } from 'svelte';

	let { data, children } = $props();

	// The one place this site names `serviceWorker`. It starts the offline
	// reader, which is what lets a day already opened be read again with no
	// network - or retires it, when the committed switch says every worker at
	// this version must go. Nothing waits on it: the page is already rendered
	// when this runs, and a browser that refuses leaves the site as it was.
	onMount(() => {
		void startOfflineReader({
			worker: `${base}/service-worker.js`,
			switchFile: `${base}/service-worker-kill.json`,
			version: OFFLINE_VERSION,
			isDev: import.meta.env.DEV
		});
	});

	// A browser honours a fragment once, at load, and a client-side navigation
	// is not a load. Doing it here rather than per page is what makes a deep
	// link behave the same on every route, and it adds the half a browser never
	// does: the story is focused, so a reader arriving by keyboard lands on what
	// the link sent them to read instead of at the top of the document.
	//
	// This is the half that works while every story is still in the document. A
	// page that fetches its stories calls the same function again once they have
	// rendered, because the element does not exist yet when this runs.
	afterNavigate(() => {
		restoreAnchor();
	});
</script>

<div class="frame">
	<!-- The chrome renders when this layout has its own data, and an address the
	     site does not have is the case where it does not. A static host answers
	     an unknown path with the fallback shell, the shell asks for that route's
	     data file, and there is no such file - so this layout is handed an empty
	     object and `data.ui.site_title` threw. Nothing rendered at all: no
	     header, no footer, and not the error screen either, which is a blank
	     page on every wrong address the site has (measured 2026-08-31 over
	     three of them). The guard is on `data.ui` rather than on `data`, because
	     the object arrives and only its contents are missing. -->
	{#if data?.ui}
		<SiteHeader title={data.ui.site_title} tagline={data.ui.tagline} />
	{/if}
	<main>
		{@render children()}
	</main>
	{#if data?.ui}
		<SiteFooter facts={data.footer ?? null} repoUrl={data.ui.repo_url} />
	{/if}
</div>
