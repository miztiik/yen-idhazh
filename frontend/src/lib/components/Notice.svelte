<script lang="ts">
	import { onDestroy } from 'svelte';
	import Icon from '$lib/icons/Icon.svelte';

	let { text, durationMs = 6000, persistent = false, onClose }: {
		text: string;
		durationMs?: number;
		persistent?: boolean;
		onClose?: () => void;
	} = $props();

	let hovered = $state(false);
	let focused = $state(false);
	let timer: ReturnType<typeof setTimeout> | null = null;
	const held = $derived(hovered || focused);

	function clearTimer() {
		if (timer !== null) clearTimeout(timer);
		timer = null;
	}

	$effect(() => {
		clearTimer();
		if (!persistent && text !== '' && !held && durationMs > 0) {
			timer = setTimeout(() => onClose?.(), durationMs);
		}
		return clearTimer;
	});

	onDestroy(clearTimer);
</script>

{#if text}
	<div
		class="notice"
		data-notice
		role="status"
		onpointerenter={() => (hovered = true)}
		onpointerleave={() => (hovered = false)}
		onfocusin={() => (focused = true)}
		onfocusout={() => (focused = false)}
	>
		<p>{text}</p>
		<button type="button" aria-label="Close" onclick={onClose}><Icon id="forget" /></button>
	</div>
{/if}

<style>
	.notice {
		position: fixed;
		inset-block-end: max(var(--space-4), env(safe-area-inset-bottom));
		inset-inline-end: var(--space-4);
		z-index: 50;
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: var(--space-3);
		align-items: start;
		max-inline-size: min(28rem, calc(100vw - 2 * var(--space-4)));
		padding: var(--space-3);
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-md);
		background: var(--color-surface-raised);
		box-shadow: var(--shadow-md);
		color: var(--color-text);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		animation: toastIn var(--dur-base) var(--ease-standard);
	}

	p {
		margin: 0;
	}

	button {
		border: 0;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--color-text-secondary);
		padding: var(--space-1);
	}
</style>
