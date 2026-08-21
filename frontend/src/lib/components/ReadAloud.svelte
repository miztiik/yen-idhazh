<script lang="ts">
	/** Read the summary aloud, on the device, when the reader asks.
	 *
	 * The browser's own speech synthesis: no model, no download, no network, and
	 * nothing on the digest's critical path. If the browser has no voice the
	 * control does not render - a button that does nothing is worse than none.
	 */
	import { onMount } from 'svelte';

	let { title, summary }: { title: string; summary: string } = $props();

	let supported = $state(false);
	let speaking = $state(false);

	onMount(() => {
		supported = typeof window !== 'undefined' && 'speechSynthesis' in window;
		return () => {
			if (supported) window.speechSynthesis.cancel();
		};
	});

	function toggle() {
		if (!supported) return;
		if (speaking) {
			window.speechSynthesis.cancel();
			speaking = false;
			return;
		}
		window.speechSynthesis.cancel();
		const utterance = new SpeechSynthesisUtterance(`${title}. ${summary}`);
		utterance.onend = () => (speaking = false);
		utterance.onerror = () => (speaking = false);
		speaking = true;
		window.speechSynthesis.speak(utterance);
	}
</script>

{#if supported}
	<button
		type="button"
		onclick={toggle}
		class="inline-flex min-h-11 items-center gap-1 text-text-tertiary hover:text-accent"
		aria-label={speaking ? 'Stop reading aloud' : 'Read this summary aloud'}
	>
		{speaking ? 'Stop' : 'Listen'}
	</button>
{/if}
