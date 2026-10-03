
<script lang="ts">
	let { value, maxChars, minLines, maxLines, onInput }: { value: string; maxChars: number; minLines: number; maxLines: number; onInput: (value: string) => void } = $props();
	const lines = $derived(Math.min(maxLines, Math.max(minLines, value.split('\n').length)));
	const count = $derived(value.length);
</script>

<div class="editor" style={`--lines:${lines}`}>
	<label for="explorer-sql">Question</label>
	<textarea id="explorer-sql" spellcheck="false" value={value} maxlength={maxChars} oninput={(event) => onInput(event.currentTarget.value)}></textarea>
	<p data-counter>{count} of {maxChars} characters</p>
</div>

<style>
	.editor { display: grid; gap: var(--space-2); }
	label { font-weight: 600; }
	textarea { min-block-size: calc(var(--lines) * 1.35em + var(--space-4)); max-block-size: calc(var(--lines) * 1.35em + var(--space-4)); overflow: auto; resize: vertical; border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface-sunken); color: var(--code-text); padding: var(--space-3); font-family: var(--font-data); line-height: 1.35; tab-size: 2; }
	p { margin: 0; color: var(--color-text-tertiary); font-size: var(--text-xs); text-align: end; }
</style>
