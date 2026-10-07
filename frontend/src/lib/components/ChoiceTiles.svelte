<script lang="ts" generics="T extends string | number">
	/** A row of radio tiles: every choice on the page at once, one of them picked.
	 *
	 * Radio buttons rather than a menu, so a reader compares the choices without
	 * opening anything. The whole tile is the target, not the dot inside it, and
	 * it keeps the 2.75rem touch floor both ways.
	 *
	 * A tile shows a short word and says a whole one: `14D` to the eye and
	 * `14 days` to a screen reader. The shown word is hidden from the reader and
	 * the spoken one from the eye, so the tile is never heard as "14D days".
	 *
	 * The group's name belongs to the caller, who draws the fieldset and its
	 * legend around these tiles and decides whether the legend is seen.
	 */
	import Icon from '$lib/icons/Icon.svelte';
	import type { IconId } from '$lib/icons/generated';

	let {
		name,
		items,
		selected,
		disabled = false,
		tileAttribute,
		onChange
	}: {
		/** The radio group's name, shared by every input in it. */
		name: string;
		items: readonly { value: T; shown: string; spoken: string; icon?: IconId }[];
		selected: T;
		disabled?: boolean;
		/** The data attribute each tile carries its value in, so a page and a test
		 * find one tile by what it means rather than by where it stands. */
		tileAttribute: `data-${string}`;
		onChange: (value: T) => void;
	} = $props();
</script>

<div class="choice-tiles">
	{#each items as item (item.value)}
		<label
			class="choice-tile"
			{...{ [tileAttribute]: item.value }}
			data-selected={item.value === selected}
		>
			<input
				class="choice-input"
				type="radio"
				{name}
				value={item.value}
				checked={item.value === selected}
				{disabled}
				onchange={() => onChange(item.value)}
			/>
			{#if item.icon === 'shape-series'}<Icon id="shape-series" />{/if}
			{#if item.icon === 'shape-ranked'}<Icon id="shape-ranked" />{/if}
			{#if item.icon === 'shape-scatter'}<Icon id="shape-scatter" />{/if}
			{#if item.icon === 'shape-distribution'}<Icon id="shape-distribution" />{/if}
			<span class="choice-word" aria-hidden="true">
				<span class="choice-reserve">{item.shown}</span>
				<span class="choice-shown">{item.shown}</span>
			</span>
			<span class="sr-only">{item.spoken}</span>
		</label>
	{/each}
</div>

<style>
	.choice-tiles {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
	}

	/* The side padding is the small step, so a three-character word still fits
	   inside the 2.75rem floor: the content box is 34px wide, and a word of three
	   characters at the tile's size and weight 600 measured 25.6px in Segoe UI on
	   2026-10-02. */
	.choice-tile {
		position: relative;
		display: flex;
		min-block-size: 2.75rem;
		min-inline-size: 2.75rem;
		align-items: center;
		justify-content: center;
		padding: var(--space-1);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		text-align: center;
		cursor: pointer;
	}

	/* Border, tint and weight: the picked tile says so three ways, and none of
	   them is the tint alone. */
	.choice-tile[data-selected='true'] {
		border-color: var(--color-accent);
		background: var(--color-tint-accent);
	}

	.choice-tile:has(.choice-input:disabled) {
		cursor: default;
		opacity: 0.55;
	}

	/* The ring is on the tile, because the input itself is a 1px square. */
	.choice-tile:has(.choice-input:focus-visible) {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}

	.choice-input {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		overflow: hidden;
		clip-path: inset(50%);
	}

	.choice-word {
		display: grid;
		place-items: center;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
		white-space: nowrap;
	}

	.choice-word > span {
		grid-area: 1 / 1;
	}

	.choice-reserve {
		visibility: hidden;
		font-weight: 600;
	}

	.choice-shown {
		font-weight: 400;
	}

	.choice-tile[data-selected='true'] .choice-shown {
		font-weight: 600;
	}
</style>
