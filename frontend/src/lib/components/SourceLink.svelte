<script lang="ts">
	/** The reader's exit and their means of verification. Never buried.
	 *
	 * Activating it is also the only thing that marks an item read. Not scroll
	 * dwell: a wrong guess there silently hides something unread, and the reader
	 * cannot tell it happened.
	 */
	let {
		url,
		label = 'Read the original',
		onRead
	}: { url: string; label?: string; onRead?: () => void } = $props();
</script>

<a
	href={url}
	target="_blank"
	rel="noopener noreferrer"
	onclick={() => onRead?.()}
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
