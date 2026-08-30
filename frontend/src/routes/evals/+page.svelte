<script lang="ts">
	import { base } from '$app/paths';

	const consoleHref = `${base}/console/`;
</script>

<svelte:head>
	<title>Scores moved to console</title>
	<meta http-equiv="refresh" content={`0; url=${consoleHref}`} />
	<link rel="canonical" href={consoleHref} />
</svelte:head>

<section class="py-6">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Scores moved</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		The score view now lives on the console. If your browser does not move you there,
		use this link.
	</p>
	<p class="mt-4">
		<a href={consoleHref} class="text-accent hover:underline">Open the console</a>
	</p>
</section>
