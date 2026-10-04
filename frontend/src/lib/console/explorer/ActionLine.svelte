
<script lang="ts">
	import Icon from '$lib/icons/Icon.svelte';
	import { megabytes } from '$lib/assist/session';
	import type { FetchCost } from '$lib/data/ledger';
	let { files = 0, bytes = 0, heldBytes = 0, read = null, busy = false, disabled = false, notice = '', onRun }: {
		files?: number; bytes?: number; heldBytes?: number; read?: FetchCost | null; busy?: boolean; disabled?: boolean; notice?: string; onRun: () => void;
	} = $props();
	const line = $derived(
		notice ||
			(read === null
				? `Run fetches ${files} files, ${megabytes(bytes)} MB.`
				: `Answered in ${read.ms} ms. Fetched ${read.files} files, ${megabytes(read.bytes)} MB; ${read.alreadyHeld} more files were already in this page.`)
	);
	const lineFiles = $derived(read?.files ?? files);
	const lineBytes = $derived(read?.bytes ?? bytes);
</script>

<div class="action-line" data-explorer-action-line data-files={lineFiles} data-bytes={lineBytes} data-held-bytes={heldBytes}>
	<p>{line} This page holds {megabytes(heldBytes)} MB of fetched files; a reload empties it.</p>
	<button type="button" onclick={onRun} disabled={disabled || busy}><Icon id="query-run" /> {busy ? 'Running' : 'Run'}</button>
</div>

<style>
	.action-line { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--tint-neutral); }
	p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); }
	button { min-block-size: 2.75rem; border: 1px solid var(--color-accent); border-radius: var(--radius-md); background: var(--color-accent); color: var(--color-on-accent); padding-inline: var(--space-5); font-weight: 600; }
	button:disabled { opacity: 0.6; }
</style>
