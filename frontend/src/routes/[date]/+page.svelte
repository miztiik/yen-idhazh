<script lang="ts">
	import DigestList from '$lib/components/DigestList.svelte';
	import { longDate } from '$lib/format';

	let { data } = $props();
</script>

<svelte:head>
	<title>{longDate(data.date)} &mdash; {data.ui.site_title}</title>
</svelte:head>

<DigestList day={data.day} datePrefix="{data.date}/" latest={data.latest} ui={data.ui} />
