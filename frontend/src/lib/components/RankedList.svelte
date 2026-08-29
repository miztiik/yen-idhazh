<script lang="ts">
	/** A list ranked by how big something is, not by when it happened.
	 *
	 * Five of the console's six tables sorted by date, so the row that cost the
	 * digest the most articles sat wherever it fell. The operator's question is
	 * always "which one is worst", and a date sort answers a different one.
	 *
	 * The bar is markup, not a chart. Four static bars in a row do not need an
	 * engine, a canvas or a lazy chunk, and markup is still readable with
	 * JavaScript off.
	 *
	 * The list prints its own divisor. A bar scaled to a hidden maximum can be
	 * read for order and cannot be read for size, and the reader has no way to
	 * tell which of those they are looking at.
	 */
	import type { Snippet } from 'svelte';
	import type { Ranked, RankedDisplay, RankedRow } from '../charts/rank';

	let {
		caption,
		ranked,
		maxText,
		measured = true,
		unmeasuredNote,
		emptyNote,
		tail = null,
		selectedKey = null,
		onSelect = null,
		glyph = null,
		track = null,
		trend = null
	}: {
		/** What the list is, for anyone who cannot see it. */
		caption: string;
		ranked: Ranked<RankedDisplay>;
		/** The longest bar, as words with its unit - `42 cuts`. */
		maxText: string;
		/** False where the ledger has never held an answer to this question.
		 * Nothing recorded and nothing found are different facts, and the one
		 * nobody checks is the absence read as a zero. */
		measured?: boolean;
		unmeasuredNote: string;
		emptyNote: string;
		/** What the cap left out, in one sentence. */
		tail?: string | null;
		selectedKey?: string | null;
		/** Set to make each row a filter chip. */
		onSelect?: ((key: string) => void) | null;
		glyph?: Snippet<[RankedRow<RankedDisplay>]> | null;
		/** Replaces the plain bar - a target bar where a threshold exists. */
		track?: Snippet<[RankedRow<RankedDisplay>]> | null;
		trend?: Snippet<[RankedRow<RankedDisplay>]> | null;
	} = $props();
</script>

<div class="ranked" data-ranked-list={caption}>
	{#if !measured}
		<p class="ranked-note" data-ranked="unmeasured">{unmeasuredNote}</p>
	{:else if ranked.rows.length === 0}
		<p class="ranked-note" data-ranked="none">{emptyNote}</p>
	{:else}
		<p class="ranked-scale" data-ranked-max={ranked.max}>A full bar is {maxText}.</p>

		<ol class="ranked-rows" data-ranked="rows" aria-label={caption}>
			{#each ranked.rows as row (row.key)}
				<li
					class="ranked-row"
					data-ranked-row={row.key}
					data-ranked-selected={selectedKey === row.key ? 'yes' : null}
				>
					{#if onSelect}
						<button
							type="button"
							class="ranked-name ranked-pick"
							aria-pressed={selectedKey === row.key}
							onclick={() => onSelect?.(row.key)}
						>
							{#if glyph}<span class="ranked-glyph">{@render glyph(row)}</span>{/if}
							<span class="ranked-title">{row.row.label}</span>
							{#if row.row.status}<span class="ranked-status">{row.row.status}</span>{/if}
						</button>
					{:else}
						<span class="ranked-name">
							{#if glyph}<span class="ranked-glyph">{@render glyph(row)}</span>{/if}
							<span class="ranked-title">{row.row.label}</span>
							{#if row.row.status}<span class="ranked-status">{row.row.status}</span>{/if}
						</span>
					{/if}

					{#if row.row.context}
						<span class="ranked-context" data-ranked-cell="context">{row.row.context}</span>
					{/if}

					<span class="ranked-value tabular-nums" data-ranked-cell="value">{row.row.value}</span>

					<span class="ranked-track" data-ranked-cell="track" data-ranked-track={track ? 'own' : 'bar'}>
						{#if track}
							{@render track(row)}
						{:else}
							<span
								class="ranked-bar"
								data-ranked-cell="bar"
								style="inline-size: {row.percent}"
							></span>
						{/if}
					</span>

					{#if trend}
						<span class="ranked-trend" data-ranked-cell="trend">{@render trend(row)}</span>
					{/if}
				</li>
			{/each}
		</ol>

		{#if tail}
			<p class="ranked-note ranked-tail" data-ranked="tail">{tail}</p>
		{/if}
	{/if}
</div>

<style>
	.ranked {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.ranked-note {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.ranked-tail {
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
	}

	.ranked-scale {
		margin: 0;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}

	.ranked-rows {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.ranked-row {
		display: grid;
		grid-template-columns: minmax(9rem, 1.1fr) auto minmax(0, 2fr) auto;
		grid-template-areas: 'name value track trend' 'context value track trend';
		align-items: center;
		column-gap: var(--space-4);
		padding-block: var(--space-2);
		border-block-end: 1px solid var(--color-rule);
	}

	.ranked-row:last-child {
		border-block-end: 0;
	}

	.ranked-name {
		grid-area: name;
		display: flex;
		align-items: center;
		gap: var(--space-2);
		min-inline-size: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text);
	}

	.ranked-title {
		overflow-wrap: anywhere;
	}

	.ranked-glyph {
		display: inline-flex;
		color: var(--color-text-tertiary);
	}

	/* A word beside the name, because colour is one signal and never the only
	   one. Nothing in this list is tinted: the order is the ranking. */
	.ranked-status {
		padding-inline: var(--space-2);
		border-radius: var(--radius-full);
		background: var(--tint-neutral);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-secondary);
		white-space: nowrap;
	}

	.ranked-pick {
		border: 0;
		border-radius: var(--radius-sm);
		background: none;
		padding: var(--space-1) var(--space-2);
		margin-inline-start: calc(var(--space-2) * -1);
		text-align: start;
		cursor: pointer;
		font: inherit;
		color: inherit;
		transition: background var(--dur-fast) var(--ease-standard);
	}

	.ranked-pick:hover {
		background: var(--color-surface-sunken);
	}

	.ranked-pick:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}

	.ranked-row[data-ranked-selected='yes'] .ranked-pick {
		background: var(--tint-accent);
		color: var(--color-accent-strong);
	}

	.ranked-context {
		grid-area: context;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}

	.ranked-value {
		grid-area: value;
		font-size: var(--text-sm);
		font-weight: 600;
		text-align: end;
		color: var(--color-text);
	}

	.ranked-track {
		grid-area: track;
		position: relative;
		display: block;
		min-inline-size: 0;
	}

	/* The rail belongs to the plain bar. A caller that supplies its own track -
	   a target bar with a threshold marker - brings its own ground with it, and a
	   rail behind it would read as a second scale. */
	.ranked-track[data-ranked-track='bar'] {
		block-size: 12px;
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	.ranked-bar {
		display: block;
		block-size: 100%;
		border-radius: var(--radius-full);
		background: var(--chart-1);
	}

	.ranked-trend {
		grid-area: trend;
		display: block;
	}

	/* The console frame is wide, and a row that keeps four columns on a laptop
	   half-window crushes the bar the row exists to show. Below that the bar
	   takes the full width instead of a sliver of it. */
	@media (max-width: 48rem) {
		.ranked-row {
			grid-template-columns: minmax(0, 1fr) auto;
			grid-template-areas: 'name value' 'context value' 'track track' 'trend trend';
			row-gap: var(--space-1);
		}

		.ranked-track {
			margin-block-start: var(--space-1);
		}
	}
</style>
