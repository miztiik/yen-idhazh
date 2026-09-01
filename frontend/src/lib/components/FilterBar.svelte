<script lang="ts">
	/** One panel: the topic pills, and the field that narrows the list below them.
	 *
	 * It replaced `TopicPills.svelte` on 2026-09-01 and serves both the day page
	 * and the archive. A field and a pill row each claiming their own band of
	 * vertical space is why the top of a reading page was tall, and the archive
	 * had its search at the very bottom - the control behind the answer.
	 *
	 * **The pills are visible at rest.** Never behind the field, never collapsed
	 * as a set. The only thing the disclosure holds is the topics past
	 * `pillsMax`, and its summary says how many.
	 *
	 * **Sticky at 1024px and up, and nowhere else.** There the pills and the
	 * field share one band. Below it the panel can run to four wrapped lines
	 * plus a field, and a control holding a third of a phone screen for the
	 * whole scroll is screen the reader paid for.
	 *
	 * **Two kinds of pill, and the difference is what happens with no script.**
	 * On a day page each pill is a link to a prerendered route, so it works with
	 * no script at all. On the archive there is no per-topic route, so the pills
	 * are buttons over the list already fetched. Everything that needs a script
	 * carries `data-filter-scripted`, the `<noscript>` rule below hides all of
	 * it, and one sentence takes its place: a dead input that swallows typing is
	 * worse than no input.
	 *
	 * The query is untrusted reader text matched against untrusted payload text.
	 * It is compared as a lowercased substring by the caller and is never
	 * interpolated into a selector, a URL or markup (Rule #11).
	 */
	import { base } from '$app/paths';
	import { splitPills } from '$lib/day-shape';
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
		datePrefix = '',
		linked = true,
		onTopic = null,
		query = $bindable(''),
		fieldId,
		fieldLabel,
		placeholder,
		showField = true,
		submitLabel = null,
		onSubmit = null,
		onType = null,
		matchNote = '',
		noscriptNote
	}: {
		/** The panel's accessible name. It is a landmark, so it needs one. */
		label: string;
		verticals: DigestVerticalRef[];
		active: string | null;
		/** The count on the `All` pill. A fact off the payload, never the length
		 * of whatever list happens to be in hand. */
		total: number;
		pillsMax: number;
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
		onSubmit?: (() => void) | null;
		onType?: (() => void) | null;
		/** What the field has narrowed to, drawn beside it. Never a sentence
		 * shared with a pill count: they count different things. */
		matchNote?: string;
		noscriptNote: string;
	} = $props();

	const root = $derived(dayRoot(base, datePrefix));
	const split = $derived(splitPills(verticals, active, pillsMax));
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
		onSubmit?.();
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
	{vertical.count}
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
					<button type="submit" class="submit">
						<Icon id="search" size={14} />
						{submitLabel}
					</button>
				</form>
			{:else}
				<div class="field-row">{@render box()}</div>
			{/if}
			{#if matchNote}
				<span class="note" data-filter-note>{matchNote}</span>
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

<style>
	.filter-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-3);
		margin-block: var(--space-4);
		padding: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
	}

	/* No `display` on either group that carries `data-filter-scripted`: the
	   `<noscript>` rule above hides them by attribute, and a scoped class rule
	   would outrank it. The flex lives on the row inside each one. */
	.pills {
		flex: 1 1 auto;
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
		padding-inline: 0.875rem;
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
		color: var(--color-accent);
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
		align-items: center;
		gap: var(--space-2);
	}

	.input {
		flex: 1 1 auto;
		min-inline-size: 0;
		min-block-size: 2.75rem;
		padding-inline: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-bg);
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

	.submit:hover {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.note {
		display: block;
		margin-block-start: var(--space-1);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.noscript-note {
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
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

	/* The value matches `frame.breakpoints_px[1]` in `config/appearance.json`; a
	   media query cannot read a custom property, which is the one place this
	   duplication is unavoidable. Above it the panel is one band - pills on the
	   left, field on the right - which is what makes it cheap enough to stick. */
	@media (min-width: 1024px) {
		.filter-bar {
			position: sticky;
			top: 0;
			z-index: 10;
			flex-wrap: nowrap;
		}

		.field {
			flex: 0 0 18rem;
		}
	}
</style>
