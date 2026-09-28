<script lang="ts">
	/** The strip a chart prints its hovered column into.
	 *
	 * One implementation, because two charts had grown their own and a third
	 * would have made three. Every rule the row settled lives here rather than in
	 * each chart: the strip sits **below** the plot and never over it, so it
	 * cannot cover a mark at any width; it prints **every series at one column**,
	 * so comparing four series costs one hover rather than four; and it is
	 * **capped at `chart.readout_max_share` of the plot**, because a reader
	 * glancing at a chart reads a short column of values and not a paragraph.
	 *
	 * It is the legend as well. A separate legend would print each series colour
	 * and label a second time, and one fact drawn twice is how two of them drift.
	 *
	 * Nothing here needs a script. The resting column is prerendered, so a reader
	 * with JavaScript off still gets one column's numbers in words - which is
	 * what makes the hover an addition rather than the only way to read a value.
	 */
	import { readoutCapStyle, type Readout, type ReadoutFacts } from '$lib/charts/readout';

	let {
		readout,
		at = null,
		name,
		maxShare,
		resting = false,
		restingNote = '',
		hint = 'Point at a column to read it. Left and Right step through them, Escape returns to the newest.'
	}: {
		/** What `readoutOf` or `factsOf` built. Null draws nothing at all. */
		readout: Readout | ReadoutFacts | null;
		/** The column a pointer or a key picked, or null for the resting one. A
		 * record chart hands the record it picked as `readout` instead. */
		at?: number | null;
		/** What the strip is of, so a page with several can be told apart. */
		name: string;
		/** `chart.readout_max_share`. */
		maxShare: number;
		/** For a record: true while no record has been picked, so the heading can
		 * say which one it fell back to rather than looking like a choice. A
		 * column strip knows this from `at`. */
		resting?: boolean;
		restingNote?: string;
		hint?: string;
	} = $props();

	interface Entry {
		label: string;
		value: string;
		swatch: string | null;
	}

	/** What the strip prints: a heading and its entries, in either shape. */
	const view = $derived.by((): { heading: string; resting: boolean; entries: Entry[] } | null => {
		if (readout === null) return null;
		if ('subject' in readout) {
			return {
				heading: readout.subject,
				resting,
				entries: readout.facts.map((fact) => ({
					label: fact.label,
					value: fact.value ?? readout.notMeasured,
					swatch: fact.swatch
				}))
			};
		}
		if (readout.columns.length === 0) return null;
		const column = Math.min(readout.columns.length - 1, Math.max(0, at ?? readout.resting));
		const measured = readout.series.some((one) => one.values[column] !== null);
		const series: Entry[] = measured
			? readout.series.map((one) => ({
					label: one.note === undefined ? one.label : `${one.label} (${one.note})`,
					value: one.values[column] ?? readout.notMeasured,
					swatch: one.swatch
				}))
			: [{ label: readout.notMeasured, value: '', swatch: null }];
		const events = readout.events[column] ?? [];
		const none: Entry[] =
			events.length === 0 && readout.eventsNone !== ''
				? [{ label: readout.eventsNone, value: '', swatch: null }]
				: [];
		return {
			heading: readout.columns[column],
			resting: at === null,
			entries: [...series, ...events, ...none]
		};
	});
</script>

{#if view}
	<dl
		class="mt-3 text-[0.75rem] text-text-tertiary"
		style={readoutCapStyle(maxShare)}
		data-readout={name}
		aria-live="polite"
	>
		<dt class="font-semibold text-text-secondary" data-readout-day>
			{view.heading}{view.resting ? restingNote : ''}
		</dt>
		{#each view.entries as row, index (`${index}:${row.label}`)}
			<div class="mt-1 flex items-center gap-2" data-readout-row={row.label}>
				{#if row.swatch}
					<span class="size-3 shrink-0 rounded-sm" style="background: {row.swatch}"></span>
				{/if}
				<dd class="grow">{row.label}</dd>
				<dd class="tabular-nums text-text-secondary">{row.value}</dd>
			</div>
		{/each}
	</dl>
	<p class="mt-2 text-[0.75rem] text-text-tertiary" data-readout-hint={name}>{hint}</p>
{/if}
