<script lang="ts">
	import type { ExplorerExample } from '$lib/server/config';
	import Icon from '$lib/icons/Icon.svelte';
	import type { KeptQuestion } from './keep';
	let {
		examples,
		published,
		saved = [],
		shown,
		onPick,
		onPickSaved,
		onForget
	}: {
		examples: ExplorerExample[];
		published: string[];
		saved?: readonly KeptQuestion[];
		shown: [number, number];
		onPick: (example: ExplorerExample) => void;
		onPickSaved?: (question: KeptQuestion) => void;
		onForget?: (question: KeptQuestion) => void;
	} = $props();
	const available = $derived(examples.filter((example) => example.ledgers.every((ledger) => published.includes(ledger))));
	const visibleCount = $derived(shown[1]);
	const chips = $derived([
		...saved.map((question) => ({ kind: 'saved' as const, id: question.id, title: question.name, item: question })),
		...available.map((example) => ({ kind: 'example' as const, id: example.id, title: example.title, item: example }))
	]);
	const visible = $derived(chips.slice(0, visibleCount));
	const folded = $derived(chips.slice(visibleCount));
</script>

<div class="question-strip" aria-label="Example questions">
	{#if saved.length > 0}<span class="run-label">Saved</span>{/if}
	{#each visible as chip (`${chip.kind}:${chip.id}`)}
		{#if chip.kind === 'saved'}
			<span class="saved-chip">
				<button type="button" class="example" onclick={() => onPickSaved?.(chip.item)}>
					<Icon id="saved" /> {chip.title}
				</button>
				<button type="button" class="forget" aria-label={`Forget ${chip.title}`} onclick={() => onForget?.(chip.item)}><Icon id="forget" /></button>
			</span>
		{:else}
			<button type="button" class="example" onclick={() => onPick(chip.item)}>{chip.title}</button>
		{/if}
	{/each}
	{#if available.length > 0}<span class="run-label">Examples</span>{/if}
	{#if folded.length > 0}
		<details>
			<summary>{folded.length} more</summary>
			<div class="folded">
				{#each folded as chip (`folded:${chip.kind}:${chip.id}`)}
					{#if chip.kind === 'saved'}
						<span class="saved-chip">
							<button type="button" class="example" onclick={() => onPickSaved?.(chip.item)}>
								<Icon id="saved" /> {chip.title}
							</button>
							<button type="button" class="forget" aria-label={`Forget ${chip.title}`} onclick={() => onForget?.(chip.item)}><Icon id="forget" /></button>
						</span>
					{:else}
						<button type="button" class="example" onclick={() => onPick(chip.item)}>{chip.title}</button>
					{/if}
				{/each}
			</div>
		</details>
	{/if}
</div>

<style>
	.question-strip { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin-block: var(--space-3); }
	.run-label { color: var(--color-text-tertiary); font-size: var(--text-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
	.example, summary { min-block-size: 2.75rem; border: 1px solid var(--color-rule); border-radius: var(--radius-full); background: var(--tint-neutral); color: var(--color-text); padding: var(--space-1) var(--space-3); font-size: var(--text-sm); display: inline-flex; align-items: center; }
	.saved-chip { display: inline-flex; align-items: center; }
	.saved-chip .example { border-start-end-radius: 0; border-end-end-radius: 0; }
	.forget { min-block-size: 2.75rem; border: 1px solid var(--color-rule); border-inline-start: 0; border-radius: 0 var(--radius-full) var(--radius-full) 0; background: var(--color-surface); color: var(--color-text-secondary); padding-inline: var(--space-2); }
	.example:focus-visible, summary:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	details { position: relative; }
	.folded { position: absolute; z-index: 5; display: grid; gap: var(--space-2); min-inline-size: 16rem; padding: var(--space-2); border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-md); }
	@media (max-width: 639px) { .question-strip .example:nth-of-type(n + 4) { display: none; } }
</style>
