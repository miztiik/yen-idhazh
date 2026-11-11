<script lang="ts">
	/** Choose a topic or narrow the list, retaining topic links without JavaScript. */
	import { base } from '$app/paths';
	import { deskCount, deskShortfall, splitPills } from '$lib/day-shape';
	import Icon from '$lib/icons/Icon.svelte';
	import { ICONS, type IconId } from '$lib/icons/generated';
	import { dayRoot, verticalHref } from '$lib/links';
	import type { DigestVerticalRef } from '$lib/payload/types';

	let {
		label,
		verticals,
		active,
		total,
		pillsMax,
		pillMoveMin,
		datePrefix = '',
		linked = true,
		onTopic = null,
		query = $bindable(''),
		fieldId,
		fieldLabel,
		placeholder,
		showField = true,
		submitLabel = null,
		submitVisible = true,
		submitDisabled = false,
		onSubmit = null,
		onType = null,
		matchNote = '',
		noscriptNote,
		deskThinMax = null
	}: {
		/** The panel's accessible name. It is a landmark, so it needs one. */
		label: string;
		verticals: DigestVerticalRef[];
		active: string | null;
		/** The count on the `All` pill. A fact off the payload, never the length
		 * of whatever list happens to be in hand. */
		total: number;
		pillsMax: number;
		/** How many stories ahead a desk must be before it passes another on the
		 * row. `digest.pill_move_min`, never a literal here. */
		pillMoveMin: number;
		datePrefix?: string;
		/** Pills are links to prerendered routes. False makes them buttons. */
		linked?: boolean;
		onTopic?: ((id: string | null) => void) | null;
		query?: string;
		fieldId: string;
		fieldLabel: string;
		placeholder: string;
		showField?: boolean;
		/** Set it and the field becomes a form with that button. The archive's
		 * search costs a 43 MB download, so it is named before it is paid for. */
		submitLabel?: string | null;
		/** A hidden submit remains keyboard reachable and preserves native Enter submission. */
		submitVisible?: boolean;
		/** Broader search may be unavailable while local filtering still works. */
		submitDisabled?: boolean;
		onSubmit?: (() => void) | null;
		onType?: (() => void) | null;
		/** Result feedback follows the controls; topic totals describe a different scope. */
		matchNote?: string;
		noscriptNote: string;
		/** The story count at or under which the topic being read explains itself.
		 * Null is a surface with no shortfall line at all, which is what the archive
		 * is: its counts are sums over every published day, so a shortfall taken
		 * from one day's run would be a number about nothing on the page. */
		deskThinMax?: number | null;
	} = $props();

	const root = $derived(dayRoot(base, datePrefix));
	const split = $derived(splitPills(verticals, active, pillsMax, pillMoveMin));
	// The desk the reader is on, and only that one. On the all-topics view there
	// is no desk being read, and one sentence per desk would be five.
	const shortfall = $derived(
		deskThinMax === null || active === null
			? null
			: deskShortfall(
					verticals.find((vertical) => vertical.id === active),
					deskThinMax
				)
	);
	/** True when something in the panel dies with no script, so the sentence that
	 * replaces it is worth rendering. Button pills are one of those things. */
	const scripted = $derived(showField || !linked);

	// A vertical is declared in config and can be added without an icon. A pill
	// with no mark is fine; a pill that throws is not.
	function mark(id: string): IconId | null {
		const candidate = `topic-${id}`;
		return candidate in ICONS ? (candidate as IconId) : null;
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!submitDisabled) onSubmit?.();
	}
</script>

{#snippet box()}
	<label class="sr-only" for={fieldId}>{fieldLabel}</label>
	<input
		id={fieldId}
		type="search"
		bind:value={query}
		oninput={() => onType?.()}
		{placeholder}
		autocomplete="off"
		class="input"
	/>
{/snippet}

{#snippet body(vertical: DigestVerticalRef)}
	{#if mark(vertical.id)}
		<Icon id={mark(vertical.id) as IconId} size={14} />
	{/if}
	{vertical.display_name}
	{deskCount(vertical)}
{/snippet}

{#snippet pill(vertical: DigestVerticalRef)}
	{@const on = active === vertical.id}
	{#if linked}
		<a
			href={verticalHref(base, datePrefix, vertical.id)}
			class="pill"
			class:on
			aria-current={on ? 'page' : undefined}
		>
			{@render body(vertical)}
		</a>
	{:else}
		<button
			type="button"
			class="pill"
			class:on
			aria-pressed={on}
			onclick={() => onTopic?.(on ? null : vertical.id)}
		>
			{@render body(vertical)}
		</button>
	{/if}
{/snippet}

<section class="filter-bar" aria-label={label} data-filter-bar>
	<div class="pills" data-filter-scripted={linked ? undefined : ''}>
		<div class="pill-row" data-topic-row>
			{#if linked}
				<a
					href={root}
					class="pill"
					class:on={active === null}
					aria-current={active === null ? 'page' : undefined}
				>
					All {total}
				</a>
			{:else}
				<button
					type="button"
					class="pill"
					class:on={active === null}
					aria-pressed={active === null}
					onclick={() => onTopic?.(null)}
				>
					All {total}
				</button>
			{/if}

			{#each split.shown as vertical (vertical.id)}
				{@render pill(vertical)}
			{/each}

			{#if split.folded.length > 0}
				<details class="more" data-topic-more={split.folded.length}>
					<summary class="pill">+{split.folded.length} more</summary>
					<div class="folded">
						{#each split.folded as vertical (vertical.id)}
							{@render pill(vertical)}
						{/each}
					</div>
				</details>
			{/if}
		</div>
	</div>

	{#if showField}
		<div class="field" data-filter-scripted>
			{#if submitLabel}
				<form class="field-row" onsubmit={submit}>
					{@render box()}
					<button
						type="submit"
						disabled={submitDisabled}
						class={submitVisible ? 'submit' : 'submit sr-only focus:not-sr-only'}
					>
						<Icon id="search" size={14} />
						{submitLabel}
					</button>
				</form>
			{:else}
				<div class="field-row">{@render box()}</div>
			{/if}
		</div>
	{/if}

	{#if scripted}
		<noscript>
			<style>
				[data-filter-scripted] {
					display: none;
				}
				[data-filter-noscript][data-filter-noscript] {
					display: block;
					inline-size: 100%;
				}
			</style>
		</noscript>
		<p class="noscript-note" data-filter-noscript>{noscriptNote}</p>
	{/if}
</section>

{#if matchNote}
	<p class="note" data-filter-note>{matchNote}</p>
{/if}

{#if shortfall}
	<p class="shortfall" data-desk-shortfall>
		Today our sources offered {shortfall.offered}
		{shortfall.offered === 1 ? 'story' : 'stories'} on this topic. {shortfall.tooOld}
		{shortfall.tooOld === 1 ? 'was' : 'were'} too old for today's page.
	</p>
{/if}

<style>
	.filter-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		gap: var(--space-3);
		margin-block-end: var(--space-5);
		padding-block-start: var(--space-3);
		border-block-start: 1px solid var(--color-rule);
	}

	/* No `display` on either group that carries `data-filter-scripted`: the
	   `<noscript>` rule above hides them by attribute, and a scoped class rule
	   would outrank it. The flex lives on the row inside each one. */
	.pills {
		flex: 1 1 100%;
		min-inline-size: 0;
	}

	.pill-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
	}

	.pill {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		min-block-size: 2.75rem;
		padding-inline: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-full);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
		white-space: nowrap;
		transition:
			color var(--dur-fast) ease,
			border-color var(--dur-fast) ease;
	}

	.pill:hover {
		border-color: var(--color-rule-strong);
		color: var(--color-text);
	}

	.pill.on {
		border-color: var(--color-accent);
		background: var(--tint-accent);
		color: var(--color-accent);
		font-weight: 600;
	}

	.more {
		max-inline-size: 100%;
	}

	/* The default disclosure triangle is dropped by `inline-flex` in Chrome and
	   Safari and kept in Firefox, where it would sit inside the pill's own
	   outline. The open row of topics below is the state indicator. */
	summary {
		cursor: pointer;
		list-style: none;
	}

	summary::-webkit-details-marker {
		display: none;
	}

	.folded {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
		margin-block-start: var(--space-2);
	}

	/* No `display` here: the `<noscript>` rule above sets `display: none` on this
	   element by attribute, and a scoped class rule would outrank it. */
	.field {
		flex: 1 1 100%;
		min-inline-size: 0;
	}
	.field-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
	}

	.input {
		flex: 1 1 100%;
		min-inline-size: 0;
		min-block-size: 2.75rem;
		padding-inline: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		font-size: var(--text-base);
		color: var(--color-text);
	}

	.input::placeholder {
		color: var(--color-text-tertiary);
	}

	.submit {
		display: inline-flex;
		flex-shrink: 0;
		align-items: center;
		gap: var(--space-1);
		margin-inline-start: auto;
		min-block-size: 2.75rem;
		padding-inline: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
		transition:
			color var(--dur-fast) ease,
			border-color var(--dur-fast) ease;
	}

	.submit:hover:not(:disabled) {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.submit:disabled {
		color: var(--color-text-tertiary);
		cursor: not-allowed;
	}

	.note {
		margin-block-end: var(--space-4);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.noscript-note {
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	.shortfall {
		margin-block-end: var(--space-4);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	/* Unscoped on purpose, and it is the whole reason this rule is not the
	   `hidden` attribute. Chrome's user-agent sheet declares `[hidden]` as
	   `display: none !important`, which no ordinary author rule can beat - so
	   the `<noscript>` block above could hide the field and never reveal the
	   sentence replacing it. A scoped rule would not work either: Svelte would
	   compile it to `.noscript-note.svelte-<hash>`, and that outranks the
	   attribute selector the block has to use. */
	:global([data-filter-noscript]) {
		display: none;
	}

	/* Matches frame.breakpoints_px[1]; custom properties cannot set media queries. */
	@media (min-width: 1024px) {
		.pills {
			flex: 2 1 0;
		}

		.field {
			flex: 1 1 0;
		}
	}
</style>
