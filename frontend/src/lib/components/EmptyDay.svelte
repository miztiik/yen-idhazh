<script lang="ts">
	/** Nothing published is a legitimate outcome, not an error. */
	import { base } from '$app/paths';
	import { longDate } from '$lib/format';

	let { date, latest }: { date: string | null; latest: string | null } = $props();
</script>

<section class="py-12">
	{#if date}
		<p class="text-[1.0625rem] text-text">Nothing was published for {longDate(date)}.</p>
	{:else}
		<p class="text-[1.0625rem] text-text">No digest has been published yet.</p>
	{/if}
	<p class="mt-2 text-[0.9375rem] text-text-secondary">
		That can mean there was no news, or the run did not finish.
	</p>
	<nav class="mt-6 flex flex-wrap gap-4 text-[0.9375rem]">
		{#if latest && latest !== date}
			<a href="{base}/{latest}/" class="text-accent hover:underline">
				Latest day - {longDate(latest)}
			</a>
		{/if}
		<a href="{base}/archive/" class="text-accent hover:underline">All days</a>
	</nav>
</section>
