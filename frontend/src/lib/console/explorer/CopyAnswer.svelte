<script lang="ts">
	/** Copies the Data explorer answer as JSON or as a Markdown table, and hands
	 * the page the sentence that says what happened, for its floating notice. */
	import Icon from '$lib/icons/Icon.svelte';
	import type { Column, Row } from '$lib/data/ledger';
	import { printCell } from './answer';

	let { columns, rows, onMessage }: { columns: readonly Column[]; rows: readonly Row[]; onMessage: (text: string) => void } = $props();

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
			onMessage(done);
		} catch {
			onMessage('This browser did not let the page write to the clipboard.');
		}
	}
</script>

<div class="copy-answer">
	<button type="button" onclick={() => copy(JSON.stringify(rows, null, 2), `Copied ${rows.length} ${rows.length === 1 ? 'row' : 'rows'} as JSON.`)}>
		<Icon id="copy" /> Copy as JSON
	</button>
	<button type="button" onclick={() => copy(markdown(), `Copied ${rows.length} ${rows.length === 1 ? 'row' : 'rows'} as a table.`)}>
		<Icon id="copy" /> Copy as table
	</button>
</div>

<style>
	/* One line, never wrapping: the buttons stand on the answer's heading line,
	   which is one control tall. */
	.copy-answer {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	button {
		flex: none;
		min-block-size: var(--workbench-control);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		color: var(--color-text);
		padding-inline: var(--space-3);
		font-weight: 600;
		white-space: nowrap;
	}
</style>
