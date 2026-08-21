<script lang="ts">
	import DigestList from '$lib/components/DigestList.svelte';
	import { longDate } from '$lib/format';

	let { data } = $props();
	const name = $derived(
		data.day.verticals.find((ref) => ref.id === data.vertical)?.display_name ?? data.vertical
	);
</script>

<svelte:head>
	<title>{name} &mdash; {longDate(data.date)} &mdash; {data.ui.site_title}</title>
</svelte:head>

<DigestList
	day={data.day}
	vertical={data.vertical}
	datePrefix="{data.date}/"
	latest={data.latest}
	ui={data.ui}
/>
