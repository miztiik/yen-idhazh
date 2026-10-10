<script lang="ts">
	import type { Snippet } from 'svelte';
	let { id, title, question, comparison, reason, days = null, scriptless = null, children }: {
		id: string; title: string; question: string; comparison: string; reason: string; days?: number | null; scriptless?: Snippet | null; children: Snippet;
	} = $props();
</script>
<section class="voices-panel" data-console-panel-id={id} data-console-panel={title} data-panel-question={question}
	data-comparison={comparison} data-model-rule="no" data-model-rule-name={id} data-model-rule-none={reason}
	data-windowed={days === null ? undefined : id} data-window-days={days ?? undefined}>
	<h3>{title}</h3>
	<div class="panel-body">{@render children()}</div>
	{#if scriptless}{@render scriptless()}{/if}
</section>
<style>
	.voices-panel { margin-block: var(--space-6); padding: var(--space-5); border: 1px solid var(--color-rule); border-radius: var(--radius-lg); background: var(--color-surface); box-shadow: var(--shadow-sm); min-inline-size: 0; }
	h3 { margin: 0 0 var(--space-3); font-size: var(--text-lg); color: var(--color-text); }
	.panel-body { min-inline-size: 0; }
	.panel-body :global([data-lede]) { margin: 0 0 var(--space-3); font-size: var(--text-xl); line-height: var(--leading-lg); color: var(--color-text); }
	.panel-body :global(.evidence) { padding-block: var(--space-3); min-inline-size: 0; }
	.panel-body :global(.notes) { font-size: var(--text-sm); color: var(--color-text-secondary); margin-block: var(--space-2); overflow-wrap: anywhere; }
	.panel-body :global(table) { inline-size: 100%; font-size: var(--text-sm); border-collapse: collapse; }
	.panel-body :global(th), .panel-body :global(td) { text-align: start; padding: var(--space-2); border-block-end: 1px solid var(--color-rule); overflow-wrap: anywhere; }
	.panel-body :global(th) { color: var(--color-text-secondary); font-weight: normal; }
	.panel-body :global([data-ranked-list]) { inline-size: 100%; }
	@media(max-width: 640px) { .voices-panel { padding: var(--space-3); } }
</style>
