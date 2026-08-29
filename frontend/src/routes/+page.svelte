<script lang="ts">
	import DigestList from '$lib/components/DigestList.svelte';
	import EmptyDay from '$lib/components/EmptyDay.svelte';
	import MoreDays from '$lib/components/MoreDays.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>{data.ui.site_title}</title>
	<meta name="description" content={data.ui.tagline} />
</svelte:head>

{#if data.day}
	<DigestList day={data.day} datePrefix="{data.day.date}/" latest={data.latest} ui={data.ui} />
	<MoreDays days={data.recent} current={data.day.date} />
{:else}
	<EmptyDay date={data.today} latest={data.latest} />
	<MoreDays days={data.recent} current={data.today} />
{/if}
