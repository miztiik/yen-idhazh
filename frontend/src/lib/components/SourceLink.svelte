<script lang="ts">
	/** The reader's exit and their means of verification. Never buried. */
	let { url, label = 'Read the original' }: { url: string; label?: string } = $props();
</script>

<a
	href={url}
	target="_blank"
	rel="noopener noreferrer"
	class="inline-flex min-h-11 items-center gap-1 text-accent hover:underline"
>
	{label}
	<svg
		width="12"
		height="12"
		viewBox="0 0 16 16"
		fill="none"
		stroke="currentColor"
		stroke-width="1.6"
		stroke-linecap="round"
		stroke-linejoin="round"
		aria-hidden="true"
	>
		<path d="M6 3h7v7" />
		<path d="M13 3 6.5 9.5" />
		<path d="M11 10.5V13H3V5h2.5" />
	</svg>
</a>
