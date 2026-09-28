<script lang="ts">
	/** The route's half of the days control: it draws nothing, and hands the
	 * route's window up to the console layout, which draws the control.
	 *
	 * A route renders this where it rendered the control, with the same props,
	 * so the window and everything that follows from it stay in the route that
	 * owns them. The layout is what puts the control on the strip.
	 */
	import { fillWindowSlot } from '$lib/console/window-slot';

	let {
		days,
		presets,
		monthsFor,
		busy = false,
		ready = false,
		onChange
	}: {
		days: number;
		presets: readonly number[];
		/** Month files a preset would fetch that are not already in hand. */
		monthsFor: (days: number) => number;
		busy?: boolean;
		/** False until a browser has run the route. */
		ready?: boolean;
		onChange: (days: number) => void;
	} = $props();

	fillWindowSlot({
		get days() {
			return days;
		},
		get presets() {
			return presets;
		},
		get busy() {
			return busy;
		},
		get ready() {
			return ready;
		},
		monthsFor: (preset) => monthsFor(preset),
		onChange: (preset) => onChange(preset)
	});
</script>
