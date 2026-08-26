<script lang="ts">
	import { base } from '$app/paths';
	import { longDate, plural } from '$lib/format';
	import AssistSearch from '$lib/components/AssistSearch.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>Archive &mdash; {data.ui.site_title}</title>
</svelte:head>

<section class="py-6">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Archive</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		{plural(data.days.length, 'day', 'days')} published.
	</p>

	{#if data.days.length === 0}
		<p class="mt-8 text-[0.9375rem] text-text-secondary">Nothing has been published yet.</p>
	{:else}
		<ul class="mt-6">
			{#each data.days as entry (entry.date)}
				<li class="border-b border-rule py-4">
					<a href="{base}/{entry.date}/" class="text-[1.0625rem] text-accent hover:underline">
						{longDate(entry.date)}
					</a>
					<span class="ml-3 text-[0.8125rem] text-text-tertiary">
						{plural(entry.items, 'story', 'stories')}{#if entry.partial}, partial{/if}
					</span>
				</li>
			{/each}
		</ul>
	{/if}

	<AssistSearch days={data.payloads} assist={data.assist} />
</section>
