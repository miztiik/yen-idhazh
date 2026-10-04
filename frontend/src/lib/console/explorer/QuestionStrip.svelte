<script lang="ts">
	import type { ExplorerExample } from '$lib/server/config';
	let { examples, published, shown, onPick }: { examples: ExplorerExample[]; published: string[]; shown: [number, number]; onPick: (example: ExplorerExample) => void } = $props();
	const available = $derived(examples.filter((example) => example.ledgers.every((ledger) => published.includes(ledger))));
	const visibleCount = $derived(shown[1]);
	const visible = $derived(available.slice(0, visibleCount));
	const folded = $derived(available.slice(visibleCount));
</script>

<div class="question-strip" aria-label="Example questions">
	{#if available.length > 0}<span class="run-label">Examples</span>{/if}
	{#each visible as example (example.id)}
		<button type="button" class="example" onclick={() => onPick(example)}>{example.title}</button>
	{/each}
	{#if folded.length > 0}
		<details>
			<summary>{folded.length} more</summary>
			<div class="folded">
				{#each folded as example (example.id)}<button type="button" class="example" onclick={() => onPick(example)}>{example.title}</button>{/each}
			</div>
		</details>
	{/if}
</div>

<style>
	.question-strip { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin-block: var(--space-3); }
	.run-label { color: var(--color-text-tertiary); font-size: var(--text-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
	.example, summary { min-block-size: 2.75rem; border: 1px solid var(--color-rule); border-radius: var(--radius-full); background: var(--tint-neutral); color: var(--color-text); padding: var(--space-1) var(--space-3); font-size: var(--text-sm); display: inline-flex; align-items: center; }
	.example:focus-visible, summary:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	details { position: relative; }
	.folded { position: absolute; z-index: 5; display: grid; gap: var(--space-2); min-inline-size: 16rem; padding: var(--space-2); border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-md); }
	@media (max-width: 639px) { .question-strip .example:nth-of-type(n + 4) { display: none; } }
</style>
