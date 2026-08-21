<script lang="ts">
	import { base } from '$app/paths';
	import { page } from '$app/state';
</script>

<svelte:head>
	<title>Not found</title>
</svelte:head>

<section class="py-12">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">
		{page.status === 404 ? 'Not here' : 'Something went wrong'}
	</h1>
	<p class="mt-2 text-[0.9375rem] text-text-secondary">
		{page.error?.message ?? 'That page does not exist.'}
	</p>
	<nav class="mt-6 flex flex-wrap gap-4 text-[0.9375rem]">
		<a href={base || '/'} class="text-accent hover:underline">Today</a>
		<a href="{base}/archive/" class="text-accent hover:underline">All days</a>
	</nav>
</section>
