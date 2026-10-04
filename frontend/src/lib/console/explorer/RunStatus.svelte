<script lang="ts">
	let { text, lines = 2, tone = 'neutral', href = '', files = 0, bytes = 0, heldBytes = 0 }: {
		text: string;
		lines?: number;
		tone?: 'neutral' | 'warn';
		href?: string;
		files?: number;
		bytes?: number;
		heldBytes?: number;
	} = $props();
</script>

<div
	class="run-status"
	class:warn={tone === 'warn'}
	data-explorer-action-line
	data-workbench-region="status"
	data-files={files}
	data-bytes={bytes}
	data-held-bytes={heldBytes}
	aria-live="polite"
	style={`--readout-lines:${lines}`}
>
	<p class="status-copy">{text}</p>
	{#if href}<a class="status-link" href={href}>See the answer</a>{/if}
</div>

<style>
	.run-status {
		position: relative;
		block-size: calc(var(--readout-lines) * var(--leading-sm) + 2 * var(--space-1));
		overflow: auto;
		scrollbar-width: thin;
		scrollbar-color: var(--color-rule-strong) transparent;
		padding: var(--space-1) var(--space-3);
		border-block-start: 1px solid var(--color-rule);
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		font-variant-numeric: tabular-nums;
	}

	.run-status.warn {
		background: var(--tint-warn);
		color: var(--color-text);
	}

	.status-copy {
		position: absolute;
		inset-block: var(--space-1);
		inset-inline: var(--space-3) 8rem;
		margin: 0;
		white-space: nowrap;
	}

	.status-link {
		position: absolute;
		inset-block-start: var(--space-1);
		inset-inline-end: var(--space-3);
		inline-size: 7rem;
		color: var(--color-text);
		font-weight: 600;
		text-align: end;
	}
</style>
