<script lang="ts">
	let { text, lines = 2, tone = 'neutral', href = '', files = 0, bytes = 0 }: {
		text: string;
		lines?: number;
		tone?: 'neutral' | 'warn';
		href?: string;
		files?: number;
		bytes?: number;
	} = $props();
</script>

<div
	class="run-status"
	class:warn={tone === 'warn'}
	data-explorer-action-line
	data-workbench-region="status"
	data-files={files}
	data-bytes={bytes}
	aria-live="polite"
	style={`--readout-lines:${lines}`}
>
	<p class="status-copy">{text}</p>
	<div class="status-link-box">
		{#if href}<a class="status-link" href={href}>See the answer</a>{/if}
	</div>
</div>

<style>
	.run-status {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 7rem;
		column-gap: var(--space-3);
		block-size: calc(var(--readout-lines) * var(--leading-sm) + 2 * var(--space-1));
		overflow-y: auto;
		overflow-x: hidden;
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
		margin: 0;
		min-inline-size: 0;
	}

	.status-link-box {
		min-inline-size: 0;
		text-align: end;
	}

	.status-link {
		color: var(--color-text);
		font-weight: 600;
		white-space: nowrap;
	}
</style>
