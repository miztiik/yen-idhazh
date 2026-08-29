<script lang="ts">
	/** The reader's exit and their means of verification. Never buried.
	 *
	 * Activating it is also the only thing that marks an item read. Not scroll
	 * dwell: a wrong guess there silently hides something unread, and the reader
	 * cannot tell it happened.
	 */
	import Icon from '$lib/icons/Icon.svelte';

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
	<Icon id="external" size={13} />
</a>
