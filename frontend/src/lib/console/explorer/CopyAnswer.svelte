<script lang="ts">
	/** Copies the Records answer as JSON or as a Markdown table. */
	import Icon from '$lib/icons/Icon.svelte';
	import type { Column, Row } from '$lib/data/ledger';
	import { printCell } from './answer';

	let { columns, rows }: { columns: readonly Column[]; rows: readonly Row[] } = $props();
	let message = $state('');

	function fence(text: string): string {
		const longest = Math.max(0, ...[...text.matchAll(/`+/g)].map((match) => match[0].length));
		const ticks = '`'.repeat(longest + 1);
		return `${ticks}${text.replace(/\r?\n/g, ' ').replace(/\|/g, '\\|')}${ticks}`;
	}

	function markdown(): string {
		const header = `| ${columns.map((column) => fence(column.name)).join(' | ')} |`;
		const rule = `| ${columns.map(() => '---').join(' | ')} |`;
		const body = rows.map((row) => `| ${columns.map((column) => fence(printCell(column, row[column.name]).text)).join(' | ')} |`);
		return [header, rule, ...body].join('\n');
	}

	async function copy(text: string, done: string) {
		try {
			await navigator.clipboard.writeText(text);
			message = done;
		} catch {
			message = 'This browser did not let the page write to the clipboard.';
		}
	}
</script>

<div class="copy-answer" aria-live="polite">
	<button type="button" onclick={() => copy(JSON.stringify(rows, null, 2), `Copied ${rows.length} ${rows.length === 1 ? 'row' : 'rows'} as JSON.`)}>
		<Icon id="copy" /> Copy as JSON
	</button>
	<button type="button" onclick={() => copy(markdown(), `Copied ${rows.length} ${rows.length === 1 ? 'row' : 'rows'} as a table.`)}>
		<Icon id="copy" /> Copy as table
	</button>
	{#if message}<span>{message}</span>{/if}
</div>

<style>
	.copy-answer {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: var(--space-2);
	}

	button {
		min-block-size: 2.75rem;
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		color: var(--color-text);
		padding-inline: var(--space-3);
		font-weight: 600;
	}

	span {
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
	}
</style>
