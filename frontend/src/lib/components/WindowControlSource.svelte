<script lang="ts">
	/** Hand the active route's window, record reach and fetch state to the layout. */
	import { fillWindowSlot } from '$lib/console/window-slot';
	import type { RecordWindow } from '$lib/console/waiting';
	import type { TimeWindow } from '$lib/charts/viewport';
	import type { ConsoleDestinationId } from '$lib/console/console-destinations';

	let {
		route,
		days,
		presets,
		monthsFor,
		busy = false,
		ready = false,
		record = null,
		publishedWindow = null,
		statusLine = null,
		sourceNotes = [],
		onChange
	}: {
		route: ConsoleDestinationId;
		days: number;
		presets: readonly number[];
		/** Month files a preset would fetch that are not already in hand. */
		monthsFor: (days: number) => number;
		busy?: boolean;
		/** False until a browser has run the route. */
		ready?: boolean;
		record?: RecordWindow | null;
		publishedWindow?: TimeWindow | null;
		statusLine?: string | null;
		sourceNotes?: readonly string[];
		onChange: (days: number) => void;
	} = $props();

	fillWindowSlot({
		get route() {
			return route;
		},
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
		get record() {
			return record;
		},
		get publishedWindow() {
			return publishedWindow;
		},
		get statusLine() {
			return statusLine;
		},
		get sourceNotes() {
			return sourceNotes;
		},
		monthsFor: (preset) => monthsFor(preset),
		onChange: (preset) => onChange(preset)
	});
</script>
