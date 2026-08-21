<script lang="ts">
	import { base } from '$app/paths';
	import ThemeToggle from './ThemeToggle.svelte';

	let { title, tagline }: { title: string; tagline: string } = $props();
</script>

<header class="flex items-baseline justify-between gap-4 py-4">
	<div>
		<a href={base || '/'} class="text-[1.0625rem] font-semibold tracking-tight text-text">
			{title}
		</a>
		<p class="mt-0.5 text-[0.8125rem] text-text-tertiary">{tagline}</p>
	</div>
	<ThemeToggle />
</header>
