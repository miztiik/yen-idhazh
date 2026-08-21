<script lang="ts">
	/** Nothing published is a legitimate outcome, not an error. */
	import { base } from '$app/paths';
	import { longDate } from '$lib/format';

	let { date, latest }: { date: string; latest: string | null } = $props();
</script>

<section class="py-12">
	<p class="text-[1.0625rem] text-text">Nothing was published for {longDate(date)}.</p>
	<p class="mt-2 text-[0.9375rem] text-text-secondary">
		A quiet day and a broken pipeline look the same from here, so the run notice above says which
		it was.
	</p>
	<nav class="mt-6 flex flex-wrap gap-4 text-[0.9375rem]">
		{#if latest && latest !== date}
			<a href="{base}/{latest}/" class="text-accent hover:underline">
				Latest day &mdash; {longDate(latest)}
			</a>
		{/if}
		<a href="{base}/archive/" class="text-accent hover:underline">All days</a>
	</nav>
</section>
