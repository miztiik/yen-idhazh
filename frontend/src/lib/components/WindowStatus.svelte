<script lang="ts">
	/** Say which record the window holds without moving the content on selection. */
	import { plural } from '$lib/format';
	import { recordWindowSentence, type RecordWindow } from '$lib/console/waiting';

	let {
		days,
		presets,
		monthsFor,
		busy = false,
		ready = false,
		statusLine = null,
		record = null,
		recordLabel = null
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
		recordLabel?: string | null;
	} = $props();

	const pending = $derived(monthsFor(days));
	let previousRecord = $state.raw<RecordWindow | null>(null);
	$effect(() => { if (record !== null) previousRecord = record; });
	const sizingRecord = $derived(record ?? previousRecord);
	const recordSizes = $derived(!ready || sizingRecord === null ? [] :
		presets.map((asked) => recordWindowSentence({ ...sizingRecord, asked }, recordLabel ?? undefined)));

	/** Each wider preset that would fetch something, narrowest first. */
	const priced = $derived(
		presets
			.filter((preset) => preset > days)
			.map((preset) => ({ preset, months: monthsFor(preset) }))
			.filter((entry) => entry.months > 0)
	);

	const status = $derived.by(() => {
		if (record !== null) return ready ? recordWindowSentence(record, recordLabel ?? undefined) : '';
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

<div class="window-status">
	<p id="window-control-status" data-window-status>{status}</p>
	{#each recordSizes as sentence}
		<span class="window-status-measure" aria-hidden="true">{sentence}</span>
	{/each}
</div>

<style>
	.window-status {
		display: grid;
		min-block-size: var(--console-small-leading);
		margin: 0;
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		font-weight: var(--console-small-weight);
		letter-spacing: var(--console-small-tracking);
		color: var(--color-text-secondary);
	}
	p, .window-status-measure {
		grid-area: 1 / 1;
		margin: 0;
	}
	/* Intrinsic copies reserve the largest configured preset at the current type. */
	.window-status-measure { visibility: hidden; pointer-events: none; }
</style>