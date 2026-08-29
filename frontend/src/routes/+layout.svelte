<script lang="ts">
	import '../styles/app.css';
	import SiteFooter from '$lib/components/SiteFooter.svelte';
	import SiteHeader from '$lib/components/SiteHeader.svelte';

	let { data, children } = $props();
</script>

<div class="frame">
	<SiteHeader title={data.ui.site_title} tagline={data.ui.tagline} />
	<main>
		{@render children()}
	</main>
	<SiteFooter facts={data.footer} repoUrl={data.ui.repo_url} />
</div>
