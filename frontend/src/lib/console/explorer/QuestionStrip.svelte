<script lang="ts">
	import { onMount, tick } from 'svelte';
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
	let phone = $state(false);
	const available = $derived(examples.filter((example) => example.ledgers.every((ledger) => published.includes(ledger))));
	const savedChips = $derived(saved.map((question) => ({ kind: 'saved' as const, id: question.id, title: question.name, item: question })));
	const exampleChips = $derived(available.map((example) => ({ kind: 'example' as const, id: example.id, title: example.title, item: example })));
	const chips = $derived([...savedChips, ...exampleChips]);
	let visibleCount = $state(0);
	let root = $state<HTMLDivElement | null>(null);
	let measure = $state<HTMLDivElement | null>(null);
	const visibleSaved = $derived(savedChips.slice(0, visibleCount));
	const visibleExamples = $derived(exampleChips.slice(0, Math.max(0, visibleCount - visibleSaved.length)));
	const folded = $derived([...savedChips.slice(visibleSaved.length), ...exampleChips.slice(visibleExamples.length)]);

	async function measureFit() {
		await tick();
		if (phone) {
			visibleCount = shown[0];
			return;
		}
		if (root === null || measure === null) {
			visibleCount = shown[1];
			return;
		}
		const style = getComputedStyle(root);
		const gap = parseFloat(style.columnGap || style.gap || '0');
		const widths = [...measure.querySelectorAll<HTMLElement>('[data-chip-measure]')].map((node) => node.getBoundingClientRect().width);
		const savedLabel = measure.querySelector<HTMLElement>('[data-label-measure="saved"]')?.getBoundingClientRect().width ?? 0;
		const exampleLabel = measure.querySelector<HTMLElement>('[data-label-measure="examples"]')?.getBoundingClientRect().width ?? 0;
		const summary = measure.querySelector<HTMLElement>('[data-summary-measure]')?.getBoundingClientRect().width ?? 0;
		const limit = root.getBoundingClientRect().width;
		for (let count = Math.min(shown[1], chips.length); count >= 0; count -= 1) {
			const savedVisible = Math.min(savedChips.length, count);
			const exampleVisible = Math.min(exampleChips.length, Math.max(0, count - savedVisible));
			const pieces = [
				...(savedVisible > 0 ? [savedLabel] : []),
				...widths.slice(0, savedVisible),
				...(exampleVisible > 0 ? [exampleLabel] : []),
				...widths.slice(savedChips.length, savedChips.length + exampleVisible),
				...(chips.length > count ? [summary] : [])
			];
			const total = pieces.reduce((sum, width) => sum + width, 0) + Math.max(0, pieces.length - 1) * gap;
			if (total <= limit + 0.5) {
				visibleCount = count;
				return;
			}
		}
		visibleCount = 0;
	}

	$effect(() => {
		void measureFit();
	});

	onMount(() => {
		const query = matchMedia('(max-width: 639px)');
		const resize = new ResizeObserver(() => void measureFit());
		if (root !== null) resize.observe(root);
		const sync = () => {
			phone = query.matches;
			void measureFit();
		};
		sync();
		query.addEventListener('change', sync);
		return () => {
			resize.disconnect();
			query.removeEventListener('change', sync);
		};
	});
</script>

<div class="question-strip" aria-label="Example questions" bind:this={root}>
	{#if visibleSaved.length > 0}<span class="run-label">Saved</span>{/if}
	{#each visibleSaved as chip (`${chip.kind}:${chip.id}`)}
		<span class="saved-chip">
			<button type="button" class="example" onclick={() => onPickSaved?.(chip.item)}>
				<Icon id="saved" /> {chip.title}
			</button>
			<button type="button" class="forget" aria-label={`Forget ${chip.title}`} onclick={() => onForget?.(chip.item)}><Icon id="forget" /></button>
		</span>
	{/each}
	{#if visibleExamples.length > 0}<span class="run-label">Examples</span>{/if}
	{#each visibleExamples as chip (`${chip.kind}:${chip.id}`)}
		<button type="button" class="example" onclick={() => onPick(chip.item)}>{chip.title}</button>
	{/each}
	{#if folded.length > 0}
		<details>
			<summary>{phone ? `Questions (${folded.length})` : `${folded.length} more`}</summary>
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
	<div class="measure-strip" aria-hidden="true" bind:this={measure}>
		<span class="run-label" data-label-measure="saved">Saved</span>
		<span class="run-label" data-label-measure="examples">Examples</span>
		{#each chips as chip (`measure:${chip.kind}:${chip.id}`)}
			<button type="button" class="example" data-chip-measure>{chip.title}</button>
		{/each}
		<summary data-summary-measure>99 more</summary>
	</div>
</div>

<style>
	.question-strip { position: relative; display: flex; flex: 1 1 auto; flex-wrap: nowrap; align-items: center; gap: var(--space-2); margin-block: 0; min-inline-size: 0; }
	.run-label { color: var(--color-text-tertiary); font-size: var(--text-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
	.example, summary { min-block-size: var(--workbench-control); border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--tint-neutral); color: var(--color-text); padding: var(--space-1) var(--space-3); font-size: var(--text-sm); display: inline-flex; align-items: center; white-space: nowrap; }
	.saved-chip { display: inline-flex; align-items: center; }
	.saved-chip .example { border-start-end-radius: 0; border-end-end-radius: 0; }
	.forget { min-block-size: var(--workbench-control); border: 1px solid var(--color-rule); border-inline-start: 0; border-radius: 0 var(--radius-md) var(--radius-md) 0; background: var(--color-surface); color: var(--color-text-secondary); padding-inline: var(--space-2); }
	.example:focus-visible, summary:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	details { position: relative; }
	.folded { position: absolute; z-index: 5; display: grid; gap: var(--space-2); min-inline-size: 16rem; padding: var(--space-2); border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-md); }
	.measure-strip { position: absolute; inset: 0 auto auto 0; visibility: hidden; pointer-events: none; display: flex; gap: var(--space-2); inline-size: max-content; }
	@media (max-width: 639px) {
		.question-strip,
		.example,
		summary {
			min-inline-size: 0;
			inline-size: 100%;
			max-inline-size: 100%;
			overflow: hidden;
		}
		.folded {
			inset-inline-start: 0;
			max-inline-size: calc(100vw - 2 * var(--gutter));
		}
	}
</style>
