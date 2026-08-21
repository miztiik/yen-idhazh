<script lang="ts">
	import DigestList from '$lib/components/DigestList.svelte';
	import EmptyDay from '$lib/components/EmptyDay.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>{data.ui.site_title}</title>
	<meta name="description" content={data.ui.tagline} />
</svelte:head>

{#if data.day}
	<DigestList day={data.day} latest={data.latest} ui={data.ui} />
{:else}
	<EmptyDay date={data.today} latest={null} />
{/if}
