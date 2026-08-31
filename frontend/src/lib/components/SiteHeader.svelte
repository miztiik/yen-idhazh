<script lang="ts">
	import { base } from '$app/paths';
	import ThemeToggle from './ThemeToggle.svelte';

	let { title, tagline }: { title: string; tagline: string } = $props();
</script>

<header class="flex items-center justify-between gap-4 py-5">
	<div>
		<a href={base || '/'} class="wordmark">
			{title}
		</a>
		<p class="mt-1 text-sm text-text-tertiary">{tagline}</p>
	</div>
	<ThemeToggle />
</header>

<style>
	/* Identity, and the one place on the site a gradient appears above the
	   fold. It encodes nothing, so it is decoration and unconstrained - the
	   colour rule binds a tint that tells a reader something. It never goes
	   near an item: a page that looks confident and expensive while carrying a
	   "may not match the source" mark is a mixed message.

	   Weight 300, one weight at every width. The committed face is variable
	   across 100 to 900, so the weight axis costs nothing, and a lighter stem
	   through a clipped gradient shimmers on a low-DPI panel at 28px.

	   No animation. A cycling background-position is a loop rather than a
	   response to anything the reader did, and reduced motion is a hard
	   kill-switch, so the effect would have to be designed twice. What that
	   costs is the moving shimmer; what buys it back is the size, the five
	   stops and the wider angle, and those survive a screenshot, reduced
	   motion and a battery. */
	.wordmark {
		display: block;
		width: fit-content;
		font-family: var(--font-display);
		font-size: var(--wordmark-size);
		font-weight: 300;
		line-height: var(--wordmark-leading);
		letter-spacing: var(--wordmark-tracking);
		background: var(--gradient-wordmark);
		background-size: 100%;
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
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
