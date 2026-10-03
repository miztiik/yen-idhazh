
<script lang="ts">
	import type { ExplorerExample } from '$lib/server/config';
	let { examples, onPick }: { examples: ExplorerExample[]; onPick: (example: ExplorerExample) => void } = $props();
</script>

<div class="question-strip" aria-label="Example questions">
	{#each examples as example (example.id)}
		<button type="button" class="example" onclick={() => onPick(example)}>{example.title}</button>
	{/each}
</div>

<style>
	.question-strip { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-block: var(--space-3); }
	.example { border: 1px solid var(--color-rule); border-radius: var(--radius-full); background: var(--tint-neutral); color: var(--color-text); padding: var(--space-1) var(--space-3); font-size: var(--text-sm); }
	.example:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
</style>
