<script lang="ts">
	let { value, maxChars, lines, counterFromShare, onInput, onRun }: { value: string; maxChars: number; lines: number; counterFromShare: number; onInput: (value: string) => void; onRun?: () => void } = $props();
	const count = $derived(value.length);
	const showCounter = $derived(count >= maxChars * counterFromShare);
	const rows = $derived((value || ' ').split('\n'));
	function highlighted(line: string): { text: string; kind: string }[] {
		return line.split(/(\bSELECT\b|\bFROM\b|\bWHERE\b|\bGROUP\b|\bORDER\b|\bBY\b|\bWITH\b|\bDESCRIBE\b|\bSUMMARIZE\b|\bEXPLAIN\b|'[^']*'|\b\d+(?:\.\d+)?\b|--.*$)/gi).filter(Boolean).map((text) => {
			const upper = text.toUpperCase();
			if (/^--/.test(text)) return { text, kind: 'comment' };
			if (/^'/.test(text)) return { text, kind: 'string' };
			if (/^\d/.test(text)) return { text, kind: 'number' };
			if (['SELECT','FROM','WHERE','GROUP','ORDER','BY','WITH','DESCRIBE','SUMMARIZE','EXPLAIN'].includes(upper)) return { text, kind: 'keyword' };
			return { text, kind: 'text' };
		});
	}
	function keydown(event: KeyboardEvent) {
		if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && onRun) {
			event.preventDefault();
			onRun();
		}
	}
</script>

<div class="editor" style={`--lines:${lines}`}>
	<div class="frame">
		<div class="numbers" aria-hidden="true">
			{#each rows as _, index}<span>{index + 1}</span>{/each}
		</div>
		<pre class="highlight" aria-hidden="true">{#each rows as line}<span class="line">{#each highlighted(line) as part}<span data-code={part.kind}>{part.text}</span>{/each}</span>{/each}</pre>
		<textarea id="explorer-sql" spellcheck="false" autocapitalize="off" autocomplete="off" value={value} maxlength={maxChars} oninput={(event) => onInput(event.currentTarget.value)} onkeydown={keydown} placeholder="Write one DuckDB question, or pick an example above."></textarea>
	</div>
	<p class="hint">Ctrl+Enter or Cmd+Enter runs it. Tab moves to the next control.{#if showCounter} {count} of {maxChars} characters.{/if}</p>
</div>

<style>
	.editor { display: grid; gap: var(--space-2); }
	.frame { position: relative; display: grid; grid-template-columns: calc(3ch + var(--space-3)) 1fr; block-size: calc(var(--lines) * var(--workbench-field-leading) + 2 * var(--space-3)); overflow: auto; scrollbar-width: thin; scrollbar-color: var(--color-rule-strong) transparent; border: 1px solid var(--color-rule-strong); border-radius: var(--radius-md); background: var(--code-ground); font-family: var(--font-data); font-size: var(--workbench-field-text); line-height: var(--workbench-field-leading); }
	.frame:focus-within { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	.numbers { display: grid; align-content: start; padding: var(--space-3) var(--space-2); color: var(--color-text-tertiary); font-variant-numeric: tabular-nums; text-align: end; user-select: none; }
	.numbers { border-inline-end: 1px solid var(--color-rule); }
	.numbers span, .line { min-block-size: var(--workbench-field-leading); }
	.highlight { grid-column: 2; grid-row: 1; margin: 0; padding: var(--space-3); color: var(--code-text); white-space: pre-wrap; overflow-wrap: anywhere; pointer-events: none; }
	.line { display: block; }
	textarea { grid-column: 2; grid-row: 1; min-block-size: 100%; overflow: hidden; resize: none; border: 0; background: transparent; color: transparent; caret-color: var(--code-text); padding: var(--space-3); font: inherit; line-height: inherit; white-space: pre-wrap; overflow-wrap: anywhere; tab-size: 2; }
	textarea:focus { outline: 0; }
	[data-code='keyword'] { color: var(--code-keyword); }
	[data-code='string'] { color: var(--code-string); }
	[data-code='number'] { color: var(--code-number); }
	[data-code='comment'] { color: var(--code-comment); }
	.hint { margin: 0; color: var(--color-text-tertiary); font-size: var(--text-xs); text-align: end; }
</style>
