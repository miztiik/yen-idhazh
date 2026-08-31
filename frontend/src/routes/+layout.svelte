<script lang="ts">
	import '../styles/app.css';
	import SiteFooter from '$lib/components/SiteFooter.svelte';
	import SiteHeader from '$lib/components/SiteHeader.svelte';

	let { data, children } = $props();
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
