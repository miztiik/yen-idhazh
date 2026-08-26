<script lang="ts">
	import '../styles/app.css';
	import SiteFooter from '$lib/components/SiteFooter.svelte';
	import SiteHeader from '$lib/components/SiteHeader.svelte';

	let { data, children } = $props();
</script>

<div class="mx-auto w-full max-w-2xl px-5 sm:px-6">
	<SiteHeader title={data.ui.site_title} tagline={data.ui.tagline} />
	<main>
		{@render children()}
	</main>
	<SiteFooter facts={data.footer} repoUrl={data.ui.repo_url} />
</div>
