
<script lang="ts">
	import Icon from '$lib/icons/Icon.svelte';
	import { megabytes } from '$lib/assist/session';
	import type { FetchCost } from '$lib/data/ledger';
	let {
		files = 0,
		bytes = 0,
		heldBytes = 0,
		read = null,
		busy = false,
		disabled = false,
		notice = '',
		from,
		to,
		minDay,
		maxDay,
		saveName = '',
		saveNameMaxChars,
		canSave = true,
		canCopyQuestion = false,
		onRun,
		onSave,
		onCopyQuestion,
		onDates
	}: {
		files?: number; bytes?: number; heldBytes?: number; read?: FetchCost | null; busy?: boolean; disabled?: boolean; notice?: string; from: string; to: string; minDay: string; maxDay: string; saveName?: string; saveNameMaxChars: number; canSave?: boolean; canCopyQuestion?: boolean; onRun: () => void; onSave?: (name: string) => void; onCopyQuestion?: () => void; onDates?: (from: string, to: string) => void;
	} = $props();
	let saving = $state(false);
	let draftName = $state('');
	const line = $derived(
		notice ||
			(read === null
				? `Run fetches ${files} files, ${megabytes(bytes)} MB.`
				: `Answered in ${read.ms} ms. Fetched ${read.files} files, ${megabytes(read.bytes)} MB; ${read.alreadyHeld} more files were already in this page.`)
	);
	const lineFiles = $derived(read?.files ?? files);
	const lineBytes = $derived(read?.bytes ?? bytes);
	function changeFrom(value: string) {
		onDates?.(value > to ? to : value, to);
	}
	function changeTo(value: string) {
		onDates?.(from, value < from ? from : value);
	}
</script>

<div class="action-line" data-explorer-action-line data-files={lineFiles} data-bytes={lineBytes} data-held-bytes={heldBytes}>
	<p>{line} This page holds {megabytes(heldBytes)} MB of fetched files; a reload empties it.</p>
	<div class="actions">
		<label>From (UTC)<input type="date" value={from} min={minDay} max={to < maxDay ? to : maxDay} onchange={(event) => changeFrom(event.currentTarget.value)} /></label>
		<label>To (UTC)<input type="date" value={to} min={from > minDay ? from : minDay} max={maxDay} onchange={(event) => changeTo(event.currentTarget.value)} /></label>
		{#if saving}
			<label>Name <input bind:value={draftName} maxlength={saveNameMaxChars} /></label>
			<button type="button" class="secondary" onclick={() => { onSave?.(draftName); saving = false; }} disabled={!draftName.trim()}>
				<Icon id="saved" /> Keep
			</button>
			<button type="button" class="secondary" onclick={() => (saving = false)}>Cancel</button>
		{:else}
			<button type="button" class="secondary" onclick={() => { draftName = saveName; saving = true; }} disabled={!canSave || busy}>
				<Icon id="saved" /> Save
			</button>
			{#if canCopyQuestion}
				<button type="button" class="secondary" onclick={onCopyQuestion}><Icon id="copy" /> Copy question</button>
			{/if}
			<button type="button" onclick={onRun} disabled={disabled || busy}><Icon id="query-run" /> {busy ? 'Running' : 'Run'}</button>
		{/if}
	</div>
</div>

<style>
	.action-line { display: grid; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--tint-neutral); }
	p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); }
	.actions { display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: end; gap: var(--space-2); }
	label { display: grid; gap: var(--space-1); color: var(--color-text-secondary); font-size: var(--text-xs); }
	input { min-block-size: 2.75rem; border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text); padding-inline: var(--space-3); font: inherit; }
	button { min-block-size: 2.75rem; border: 1px solid var(--color-accent); border-radius: var(--radius-md); background: var(--color-accent); color: var(--color-on-accent); padding-inline: var(--space-5); font-weight: 600; }
	button.secondary { border-color: var(--color-rule); background: var(--color-surface); color: var(--color-text); }
	button:disabled { opacity: 0.6; }
</style>
