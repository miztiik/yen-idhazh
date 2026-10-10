<script lang="ts">
	/** What the days control is holding, and what a wider span would fetch, said
	 * as one sentence under the band.
	 *
	 * It was the control's own line until the control moved onto the strip. A
	 * sentence is not a control, so it did not go with it: it stays under the
	 * band and over the panels it describes, and the strip stays one row.
	 *
	 * **The price of a wider span lives here, not on the tiles.** A price that
	 * appeared and disappeared on a tile moved seven panels by 15 px when it
	 * landed or cleared (measured 2026-09-09), so the tiles once kept a second
	 * line for it whether or not one was due. This sentence is always drawn and
	 * keeps room for its longest form, so the price holds still and the tiles
	 * hold one line. What it costs: on a phone the price stands a band's height
	 * below the control, and while the strip is stuck to the top of a wide
	 * screen it is off screen.
	 */
	import { plural } from '$lib/format';
	import { recordWindowSentence, type RecordWindow } from '$lib/console/waiting';

	let {
		days,
		presets,
		monthsFor,
		busy = false,
		ready = false,
		statusLine = null,
		record = null
	}: {
		days: number;
		presets: readonly number[];
		/** Month files a preset would fetch that are not already in hand. */
		monthsFor: (days: number) => number;
		busy?: boolean;
		/** False until a browser has run the route. */
		ready?: boolean;
		statusLine?: string | null;
		record?: RecordWindow | null;
	} = $props();

	const pending = $derived(monthsFor(days));

	/** Each wider preset that would fetch something, narrowest first. */
	const priced = $derived(
		presets
			.filter((preset) => preset > days)
			.map((preset) => ({ preset, months: monthsFor(preset) }))
			.filter((entry) => entry.months > 0)
	);

	const status = $derived.by(() => {
		if (record !== null) return ready ? recordWindowSentence(record) : '';
		if (statusLine !== null) return statusLine;
		if (!ready) {
			// It said the sections below were "showing N days" until 2026-09-09.
			// That stopped being true when the page stopped holding telemetry rows
			// before a browser fetches them: with no script the windowed sections
			// hold their reserved shape and nothing else.
			return `The days control above needs JavaScript, and so do the sections below - they draw rows a browser fetches. Their shape is ${plural(days, 'day', 'days')}.`;
		}
		if (busy) return `Fetching ${plural(pending, 'month', 'months')}.`;
		const shown = `Every windowed section below is showing ${plural(days, 'day', 'days')}.`;
		const [first, ...wider] = priced;
		if (first === undefined) return shown;
		const rest = wider.map((entry) => `, ${entry.preset}D ${entry.months} more`).join('');
		return `${shown} ${first.preset}D would fetch ${plural(first.months, 'more month', 'more months')}${rest}.`;
	});
</script>

<p id="window-control-status" class="window-status" data-window-status>{status}</p>

<style>
	.window-status {
		/* Room for the longest sentence this slot holds, always. The sentences are
		   different lengths - the no-script one, and the price with every wider
		   preset named, are the longest - so without a floor the slot would lose a
		   line the moment a browser hydrates or a price clears, and every panel
		   below it would jump. Measured 2026-09-09 at 1280 CSS px on an Intel Core
		   i7-1265U: seven panels moved by one line for a sentence changing. Three
		   lines on a phone: the longest price, 111 characters, took three lines at
		   320px and two from 360px (measured 2026-10-02, Chromium on Windows). */
		min-block-size: calc(3 * var(--leading-xs));
		margin: var(--space-3) 0 0;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}

	/* The value matches `frame.breakpoints_px[0]` in `config/appearance.json`; a
	   media query cannot read a custom property. From there up the longest
	   sentence takes two lines. */
	@media (min-width: 640px) {
		.window-status {
			min-block-size: calc(2 * var(--leading-xs));
		}
	}
</style>