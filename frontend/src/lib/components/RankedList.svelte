<script module lang="ts">
	import type { RangeMark } from '../charts/d3/rankedList';
	export { rangeTrack, endsTrack };
</script>

{#snippet rangeTrack(mark: RangeMark, token = '--chart-2', classes = '')}
	<span class="range-fill {classes}" style="inline-size: {mark.medianWidth}; background: var({token})"></span>
	{#if mark.max !== null}
		<span class="range-notch" style="inset-inline-start: {mark.notchWidth}"></span>
	{/if}
{/snippet}

{#snippet endsTrack(valuePercent: string, endPercent: string | null, vertical = false, outlined = false, token = '--chart-3')}
	<span class:vertical class:outlined class="ends-fill bar floor" style="{vertical ? `block-size: ${valuePercent}` : `inline-size: ${valuePercent}`}; background: var({token})"></span>
	{#if endPercent !== null}
		<span class:vertical class="ends-notch notch" style={vertical ? `inset-block-end: ${endPercent}` : `inset-inline-start: ${endPercent}`}></span>
	{/if}
{/snippet}

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
	import type { RankedDisplay, RankedRow } from '../charts/rank';
	import type { RankedGeometry } from '../charts/d3/rankedList';

	let {
		caption,
		geometry,
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
		geometry: RankedGeometry | null;
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
	const ranked = $derived(geometry ?? { rows: [], max: 0, rules: [] });
</script>

<div class="ranked" data-ranked-list={caption} data-chart-type="rankedList" data-readout-none="Each ranked row prints its name and value; agreed with Susan">
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

					<span class="ranked-track" data-ranked-cell="track" data-ranked-track={track || row.range || row.ends || row.refused ? 'own' : 'bar'}>
						{#if row.refused}
							<span class="ranked-context" data-ranked-too-few>{row.refused}</span>
						{:else if track}
							{@render track(row)}
						{:else if row.range}
							<span class="ranked-range">{@render rangeTrack(row.range, '--chart-1')}</span>
						{:else if row.ends}
							<span class="ranked-range">{@render endsTrack(row.ends.valuePercent, row.ends.endPercent, false, false, '--chart-1')}</span>
						{:else if row.segments.length > 0}
							{#each row.segments as part (part.label)}
								<span class="ranked-part" style="inset-inline-start: {part.start}; inline-size: {part.size}; background: var({part.token})" aria-label="{part.label}: {part.value}"></span>
							{/each}
						{:else}
							<span
								class="ranked-bar"
								data-ranked-cell="bar"
								style="inline-size: {row.percent}"
							></span>
						{/if}
						{#if !row.refused}
							{#each ranked.rules as rule (rule.label)}
								<span class="ranked-rule" style="inset-inline-start: {rule.percent}" aria-label="{rule.label}: {rule.at}"><span>{rule.label}</span></span>
							{/each}
						{/if}
					</span>

					{#if trend}
						<span class="ranked-trend" data-ranked-cell="trend">{@render trend(row)}</span>
					{/if}
				</li>
			{/each}
		</ol>

		{#if tail || geometry?.tail}
			<p class="ranked-note ranked-tail" data-ranked="tail">{tail ?? geometry?.tail}</p>
		{/if}
	{/if}
</div>

<style>
	.range-fill { display: block; block-size: 100%; }
	.range-notch { position: absolute; inset-block: 0; inline-size: 2px; background: var(--chart-marker); transform: translateX(-1px); }
	.ends-fill { display: block; block-size: 100%; background: var(--chart-3); }
	.ends-fill.vertical { inline-size: 100%; border-radius: 1px 1px 0 0; }
	.ends-fill.outlined { outline: 1px solid var(--color-text); outline-offset: 0; }
	.ends-notch { position: absolute; inset-block: 0; inline-size: 2px; background: var(--color-text); }
	.ends-notch.vertical { inset-inline: 0; inset-block-start: auto; inline-size: auto; block-size: 2px; }
	.ranked-range { display: block; position: relative; block-size: 12px; background: var(--color-surface-sunken); }
	.ranked-part { position: absolute; inset-block: 0; }
	.ranked-rule { position: absolute; inset-block: -4px; border-inline-start: 1px dashed var(--chart-marker); }
	.ranked-rule span { position: absolute; inset-block-end: 100%; font-size: var(--text-xs); color: var(--color-text-secondary); white-space: nowrap; }
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

	/* One column set for the whole list, borrowed by every row. A row that sized
	   its own columns gave a two-digit value a narrower track than a one-digit
	   one - measured 587.34px against 591.86px - so two bars of the same fraction
	   came out different lengths. The fractions were right and the picture lied. */
	.ranked-rows {
		display: grid;
		grid-template-columns: minmax(9rem, 1.1fr) auto minmax(0, 2fr) auto;
		column-gap: var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.ranked-row {
		grid-column: 1 / -1;
		display: grid;
		grid-template-columns: subgrid;
		grid-template-areas: 'name value track trend' 'context value track trend';
		align-items: center;
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
		overflow: visible;
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
		.ranked-rows {
			grid-template-columns: minmax(0, 1fr) auto;
		}

		.ranked-row {
			grid-template-areas: 'name value' 'context value' 'track track' 'trend trend';
			row-gap: var(--space-1);
		}

		.ranked-track {
			margin-block-start: var(--space-1);
		}
	}
</style>
