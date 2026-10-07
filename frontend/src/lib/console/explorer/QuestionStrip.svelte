<script lang="ts">
	/** The Data explorer's strip of question chips: this browser's saved questions, then the
	 * examples. From 640 px it is one line, so saving a question never makes it taller: the
	 * chips that do not fit fold into `{n} more`. */
	import { onMount, tick } from 'svelte';
	import type { ExplorerExample } from '$lib/server/config';
	import Icon from '$lib/icons/Icon.svelte';
	import type { KeptQuestion } from './keep';
	import { closeAfterPick, closesWhenLeft } from './floating-list';
	import { chipsThatFit, type StripWidths } from './strip-fit';
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
	let line = $state(0);
	let strip = $state<HTMLElement | null>(null);
	let ruler = $state<HTMLElement | null>(null);
	let widths = $state<StripWidths | null>(null);
	let rulerWidth = $state(0);
	let fold = $state<HTMLDetailsElement | null>(null);
	const available = $derived(examples.filter((example) => example.ledgers.every((ledger) => published.includes(ledger))));
	const savedChips = $derived(saved.map((question) => ({ kind: 'saved' as const, id: question.id, title: question.name, item: question })));
	const exampleChips = $derived(available.map((example) => ({ kind: 'example' as const, id: example.id, title: example.title, item: example })));
	const limit = $derived(phone ? shown[0] : shown[1]);
	const measured = $derived(widths !== null && widths.chips.length === savedChips.length + exampleChips.length && line > 0);
	const visibleCount = $derived(phone || widths === null || !measured ? limit : chipsThatFit(widths, line, savedChips.length, limit));
	const visibleSaved = $derived(savedChips.slice(0, visibleCount));
	const visibleExamples = $derived(exampleChips.slice(0, Math.max(0, visibleCount - visibleSaved.length)));
	const folded = $derived([...savedChips.slice(visibleSaved.length), ...exampleChips.slice(visibleExamples.length)]);

	onMount(() => {
		const query = matchMedia('(max-width: 639px)');
		const sync = () => (phone = query.matches);
		sync();
		query.addEventListener('change', sync);
		return () => query.removeEventListener('change', sync);
	});

	// The ruler draws every chip, hidden and on one line, so each one's width is known
	// before the strip decides which of them to show. Its own width changes when the
	// site's face replaces the fallback, and that is when the chips are measured again.
	$effect(() => {
		void savedChips;
		void exampleChips;
		void rulerWidth;
		if (ruler === null || strip === null) return;
		const [savedLabel, examplesLabel, more, ...chips] = [...ruler.children].map((child) => child.getBoundingClientRect().width);
		widths = { savedLabel, examplesLabel, more, chips, gap: parseFloat(getComputedStyle(strip).columnGap) || 0 };
	});

	async function pickFolded(pick: () => void) {
		pick();
		await closeAfterPick(fold);
	}

	// Forget moves focus to the nearest x left where it was pressed - on the line, or in the
	// list, which stays open so several can go in turn - then to the summary, then to the last
	// chip on the line, so focus never falls to the page.
	async function forget(question: KeptQuestion, index: number, place: 'line' | 'fold') {
		onForget?.(question);
		await tick();
		const forgets = place === 'fold' ? fold?.querySelectorAll<HTMLButtonElement>('.folded .forget') : strip?.querySelectorAll<HTMLButtonElement>(':scope > .saved-chip > .forget');
		const left = [...(forgets ?? [])];
		const chips = [...(strip?.querySelectorAll<HTMLButtonElement>(':scope > .example, :scope > .saved-chip > .example') ?? [])];
		(left[Math.min(index, left.length - 1)] ?? fold?.querySelector('summary') ?? chips.at(-1))?.focus();
	}
</script>

<div class="question-strip" aria-label="Example questions" bind:this={strip} bind:clientWidth={line}>
	{#if visibleSaved.length > 0}<span class="run-label">Saved</span>{/if}
	{#each visibleSaved as chip, index (`${chip.kind}:${chip.id}`)}
		<span class="saved-chip">
			<button type="button" class="example" onclick={() => onPickSaved?.(chip.item)}>
				<Icon id="saved" /> {chip.title}
			</button>
			<button type="button" class="forget" aria-label={`Forget ${chip.title}`} onclick={() => forget(chip.item, index, 'line')}><Icon id="forget" /></button>
		</span>
	{/each}
	{#if visibleExamples.length > 0}<span class="run-label">Examples</span>{/if}
	{#each visibleExamples as chip (`${chip.kind}:${chip.id}`)}
		<button type="button" class="example" onclick={() => onPick(chip.item)}>{chip.title}</button>
	{/each}
	{#if folded.length > 0}
		<details bind:this={fold} use:closesWhenLeft>
			<summary>{folded.length} more</summary>
			<div class="folded">
				{#each folded as chip, index (`folded:${chip.kind}:${chip.id}`)}
					{#if chip.kind === 'saved'}
						<span class="saved-chip">
							<button type="button" class="example" onclick={() => pickFolded(() => onPickSaved?.(chip.item))}>
								<Icon id="saved" /> {chip.title}
							</button>
							<button type="button" class="forget" aria-label={`Forget ${chip.title}`} onclick={() => forget(chip.item, index, 'fold')}><Icon id="forget" /></button>
						</span>
					{:else}
						<button type="button" class="example" onclick={() => pickFolded(() => onPick(chip.item))}>{chip.title}</button>
					{/if}
				{/each}
			</div>
		</details>
	{/if}
	<div class="ruler" aria-hidden="true" bind:this={ruler} bind:clientWidth={rulerWidth}>
		<span class="run-label">Saved</span>
		<span class="run-label">Examples</span>
		<span class="ruler-chip">{savedChips.length + exampleChips.length} more</span>
		{#each savedChips as chip (`ruler:saved:${chip.id}`)}
			<span class="ruler-saved"><span class="ruler-chip"><Icon id="saved" /> {chip.title}</span><span class="ruler-forget"><Icon id="forget" /></span></span>
		{/each}
		{#each exampleChips as chip (`ruler:example:${chip.id}`)}
			<span class="ruler-chip">{chip.title}</span>
		{/each}
	</div>
</div>

<style>
	.question-strip { position: relative; display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin-block: var(--space-3); overflow-x: clip; }
	.run-label { color: var(--color-text-tertiary); font-size: var(--text-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
	.example, summary, .ruler-chip { min-block-size: 2.75rem; border: 1px solid var(--color-rule); border-radius: var(--radius-full); background: var(--tint-neutral); color: var(--color-text); padding: var(--space-1) var(--space-3); font-size: var(--text-sm); display: inline-flex; align-items: center; }
	.saved-chip, .ruler-saved { display: inline-flex; align-items: center; }
	.saved-chip .example, .ruler-saved .ruler-chip { border-start-end-radius: 0; border-end-end-radius: 0; }
	.forget, .ruler-forget { min-block-size: 2.75rem; border: 1px solid var(--color-rule); border-inline-start: 0; border-radius: 0 var(--radius-full) var(--radius-full) 0; background: var(--color-surface); color: var(--color-text-secondary); padding-inline: var(--space-2); }
	.ruler-forget { display: inline-flex; align-items: center; }
	.example:focus-visible, summary:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	/* Hung from the strip rather than from its summary, so the list opens inside the strip's width. */
	.folded { position: absolute; inset-block-start: 100%; inset-inline-end: 0; z-index: 5; display: grid; gap: var(--space-2); min-inline-size: min(16rem, 100%); max-inline-size: 100%; padding: var(--space-2); border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-md); }
	.ruler { position: absolute; inset-block-start: 0; inset-inline-start: 0; display: flex; gap: var(--space-2); visibility: hidden; pointer-events: none; white-space: nowrap; }
	.ruler > * { flex: none; }
	@media (min-width: 640px) {
		.question-strip { flex-wrap: nowrap; }
		.question-strip > :global(*) { flex: none; }
		.question-strip > .example,
		.question-strip > .saved-chip .example,
		.question-strip > details > summary { white-space: nowrap; }
	}
	@media (max-width: 639px) {
		.example,
		summary {
			min-inline-size: 0;
			inline-size: 100%;
			max-inline-size: 100%;
			overflow: hidden;
		}
	}
</style>
