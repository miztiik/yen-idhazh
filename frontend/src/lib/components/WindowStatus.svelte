<script lang="ts">
	/** What the days control is holding, said as one sentence under the band.
	 *
	 * It was the control's own line until the control moved onto the strip. A
	 * sentence is not a control, so it did not go with it: it stays under the
	 * band and over the panels it describes, and the strip stays one row.
	 */
	import { plural } from '$lib/format';

	let {
		days,
		presets,
		monthsFor,
		busy = false,
		ready = false
	}: {
		days: number;
		presets: readonly number[];
		/** Month files a preset would fetch that are not already in hand. */
		monthsFor: (days: number) => number;
		busy?: boolean;
		/** False until a browser has run the route. */
		ready?: boolean;
	} = $props();

	const pending = $derived(monthsFor(days));
	const priced = $derived(presets.some((preset) => monthsFor(preset) > 0));

	const status = $derived.by(() => {
		if (!ready) {
			// It said the sections below were "showing N days" until 2026-09-09.
			// That stopped being true when the page stopped holding telemetry rows
			// before a browser fetches them: with no script the windowed sections
			// hold their reserved shape and nothing else.
			return `The days control above needs JavaScript, and so do the sections below - they draw rows a browser fetches. Their shape is ${plural(days, 'day', 'days')}.`;
		}
		if (busy) return `Fetching ${plural(pending, 'month', 'months')}.`;
		const shown = `Every windowed section below is showing ${plural(days, 'day', 'days')}.`;
		return priced ? `${shown} A month count on a preset is what picking it will fetch.` : shown;
	});
</script>

<p id="window-control-status" class="window-status" data-window-status>{status}</p>

<style>
	.window-status {
		/* Two lines, always. The four sentences this slot holds are different
		   lengths, and the no-script one is the longest - so without a floor the
		   slot loses a line the moment a browser hydrates and every panel below it
		   jumps 16 px up. Measured 2026-09-09 at 1280 CSS px on an Intel Core
		   i7-1265U: seven panels moved by exactly that, for a sentence changing. */
		min-block-size: calc(2 * var(--leading-xs));
		margin: var(--space-3) 0 0;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}
</style>
