<script lang="ts">
	/** How many days the console is showing, and what a wider window costs.
	 *
	 * One control for the whole page. Six controls would invite six windows, and
	 * two charts on different windows cannot be compared - which is the question
	 * an operator came here to ask.
	 *
	 * It stands on the strip, after the tabs, at every width. From
	 * `frame.breakpoints_px[1]` up it shares one row with them and the row sticks
	 * to the top of the screen, so the span is in reach nine panels down. Below
	 * that width it takes a row of its own under the tabs and does not stick.
	 *
	 * Each tile is the number alone. The word `days` is said once, in the
	 * control's own label, and every tile still says it to a screen reader. The
	 * sentence about what the span is showing is `WindowStatus.svelte`, under the
	 * band: on the strip it would make the strip two rows.
	 *
	 * Radio buttons rather than a menu: every option on the page at once, so the
	 * cost of the wide one is readable without opening anything. And a short
	 * list rather than a slider, because every span is a different number of
	 * month files to fetch and most of the spans between these look the same
	 * once drawn.
	 */
	import { plural } from '$lib/format';

	let {
		days,
		presets,
		monthsFor,
		busy = false,
		ready = false,
		priceRoom = false,
		onChange
	}: {
		days: number;
		presets: readonly number[];
		/** Month files a preset would fetch that are not already in hand. */
		monthsFor: (days: number) => number;
		busy?: boolean;
		/** False until a browser has run. The control does nothing before that,
		 * so it says so instead of accepting a click it cannot honour. */
		ready?: boolean;
		/** True on a route whose window fetches month files. Every tile then
		 * keeps the room a price needs from the first paint, whether a price is
		 * showing or not, so a price that lands or clears moves nothing. */
		priceRoom?: boolean;
		onChange: (days: number) => void;
	} = $props();
</script>

<fieldset
	class="window-control"
	data-window-control
	data-window-days={days}
	data-window-busy={busy ? 'true' : 'false'}
	data-window-price-room={priceRoom ? 'yes' : 'no'}
	aria-busy={busy}
	aria-describedby="window-control-status"
>
	<!-- The legend names the group for a screen reader. The same two words for
	     the eye sit on the row beside the tiles, where a legend cannot. -->
	<legend class="sr-only">Days shown</legend>
	<span class="window-label" aria-hidden="true">Days shown</span>

	<div class="segments">
		{#each presets as preset (preset)}
			{@const price = monthsFor(preset)}
			<label class="segment" data-window-preset={preset} data-selected={preset === days}>
				<input
					class="segment-input"
					type="radio"
					name="console-window"
					value={preset}
					checked={preset === days}
					disabled={!ready}
					onchange={() => onChange(preset)}
				/>
				<!-- The space is inside the expression: the compiler drops whitespace
				     written at the start of a tag, and a screen reader would then
				     read "1day". -->
				<span class="segment-days"
					>{preset}<span class="sr-only">{` ${preset === 1 ? 'day' : 'days'}`}</span></span
				>
				<!-- The price, before it is paid, and its ROOM is here whether or not
				     there is one to pay. A chip that appeared only when a preset cost
				     something vanished the moment its months landed, and every panel
				     below this control jumped up a line with it - measured 2026-09-09
				     at 1280 CSS px, 15 px, on seven panels. It stays WORDLESS when the
				     window is free: five tiles each saying the same thing is five
				     labels an operator cannot act on. -->
				<span
					class="segment-cost"
					data-window-preset-cost={price > 0 ? preset : null}
					data-window-preset-free={price === 0 ? preset : null}
					aria-hidden={price === 0}
					>{price > 0 ? `+${plural(price, 'month', 'months')}` : ''}</span
				>
			</label>
		{/each}
	</div>
</fieldset>

<style>
	/* No box of its own. It stands on the strip, and the strip is the surface -
	   a raised card inside a band that sticks would be a second edge where the
	   eye needs one. */
	.window-control {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2) var(--space-3);
		min-inline-size: 0;
		margin: 0;
		padding: 0;
		border: 0;
	}

	.window-label {
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
		white-space: nowrap;
	}

	.segments {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
	}

	/* A segment is the target, not the dot beside it. The whole tile is
	   clickable and the tile is what carries the selected state, so a thumb has
	   something the size of a thumb to hit - which is why the tile keeps the
	   2.75rem floor both ways now that it holds one number. */
	.segment {
		position: relative;
		display: flex;
		min-block-size: 2.75rem;
		min-inline-size: 2.75rem;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		padding: var(--space-1) var(--space-2);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		text-align: center;
		cursor: pointer;
	}

	/* Border, tint and weight: the selected tile says so three ways, and none
	   of them is the tint alone. */
	.segment[data-selected='true'] {
		border-color: var(--color-accent);
		background: var(--color-tint-accent);
	}

	.segment:has(.segment-input:disabled) {
		cursor: default;
		opacity: 0.55;
	}

	/* The ring is on the tile, because the input itself is a 1px square. */
	.segment:has(.segment-input:focus-visible) {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}

	.segment-input {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		overflow: hidden;
		clip-path: inset(50%);
	}

	.segment-days {
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		font-weight: 400;
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
	}

	.segment[data-selected='true'] .segment-days {
		font-weight: 600;
	}

	.segment-cost {
		/* One line of room, always. See the markup above: the slot has to hold its
		   height whether or not there is a price in it. */
		min-block-size: var(--leading-xs);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
		white-space: nowrap;
	}

	/* A route whose window fetches nothing never prices a tile, so its tiles
	   hold no room for a price. */
	.window-control[data-window-price-room='no'] .segment-cost[data-window-preset-free] {
		display: none;
	}

	/* And a route whose window does fetch holds the room of the longest price,
	   `+12 months`, on every tile from the first paint. The number alone is
	   narrower than its price, so without this a tile would narrow the moment
	   its months landed - and on the stuck strip, the tile under the pointer
	   would slide sideways. */
	.window-control[data-window-price-room='yes'] .segment-cost {
		min-inline-size: 10ch;
	}

	/* The value matches `frame.breakpoints_px[1]` in `config/appearance.json`; a
	   media query cannot read a custom property, which is the one place this
	   duplication is unavoidable. From there up the control is one row with the
	   tabs, so it never wraps. */
	@media (min-width: 1024px) {
		.window-control,
		.segments {
			flex-wrap: nowrap;
		}
	}
</style>
