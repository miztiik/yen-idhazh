<script lang="ts">
	import { base } from '$app/paths';
	import ThemeToggle from './ThemeToggle.svelte';

	let { title, tagline }: { title: string; tagline: string } = $props();
</script>

<header class="flex items-baseline justify-between gap-4 py-5">
	<div>
		<a href={base || '/'} class="wordmark text-xl font-semibold tracking-tight">
			{title}
		</a>
		<p class="mt-0.5 text-sm text-text-tertiary">{tagline}</p>
	</div>
	<ThemeToggle />
</header>

<style>
	/* Identity, and the one place on the site a gradient appears above the
	   fold. It encodes nothing, so it is decoration and unconstrained - the
	   colour rule binds a tint that tells a reader something. It never goes
	   near an item: a page that looks confident and expensive while carrying a
	   "may not match the source" mark is a mixed message. */
	.wordmark {
		font-family: var(--font-display);
		background: var(--gradient-brand);
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
		width: fit-content;
	}

	/* A gradient clipped to text is invisible if the clip is unsupported, so the
	   fallback is a real colour rather than nothing. */
	@supports not (background-clip: text) {
		.wordmark {
			background: none;
			color: var(--color-text);
		}
	}
</style>
