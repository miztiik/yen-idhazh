<script lang="ts">
	/** How many days the console is showing.
	 * Null leaves every tile unchecked for a caller's custom span.
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
	 * Five short tiles, `1D 7D 14D 30D 90D`, and nothing beside them: 236 by 44
	 * CSS px at every width. The `D` carries the unit, and each tile says the
	 * whole word to a screen reader, so `14D` is heard as "14 days". The group's
	 * name, `Days shown`, is its legend, which only a screen reader hears.
	 *
	 * **What a wider span would fetch is not on the tiles.** It is in the
	 * sentence under the band, `WindowStatus.svelte`, which is always drawn and
	 * keeps the room its longest form needs - so a price that lands or clears
	 * moves nothing, and no tile reserves a second line for a price it may never
	 * show.
	 *
	 * A short list rather than a slider, because every span is a different number
	 * of month files to fetch and most of the spans between these look the same
	 * once drawn.
	 */
	import { plural } from '$lib/format';
	import ChoiceTiles from './ChoiceTiles.svelte';

	let {
		days,
		presets,
		busy = false,
		ready = false,
		onChange
	}: {
		days: number | null;
		presets: readonly number[];
		busy?: boolean;
		/** False until a browser has run. The control does nothing before that,
		 * so it says so instead of accepting a click it cannot honour. */
		ready?: boolean;
		onChange: (days: number) => void;
	} = $props();

	const items = $derived(
		presets.map((preset) => ({
			value: preset,
			shown: `${preset}D`,
			spoken: plural(preset, 'day', 'days')
		}))
	);
</script>

<fieldset
	class="window-control"
	data-window-control
	data-window-days={days ?? undefined}
	data-window-busy={busy ? 'true' : 'false'}
	aria-busy={busy}
	aria-describedby="window-control-status"
>
	<legend class="sr-only">Days shown</legend>
	<ChoiceTiles
		name="console-window"
		{items}
		selected={days}
		disabled={!ready}
		tileAttribute="data-window-preset"
		{onChange}
	/>
</fieldset>

<style>
	/* No box of its own. It stands on the strip, and the strip is the surface -
	   a raised card inside a band that sticks would be a second edge where the
	   eye needs one. */
	.window-control {
		min-inline-size: 0;
		margin: 0;
		padding: 0;
		border: 0;
	}
</style>