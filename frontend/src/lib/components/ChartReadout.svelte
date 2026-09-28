<script lang="ts">
	/** The strip a chart prints its hovered column or record into.
	 *
	 * One implementation, because two charts had grown their own and a third
	 * would have made three. Every rule the row settled lives here rather than in
	 * each chart: the strip sits **below** the plot and never over it, so it
	 * cannot cover a mark at any width; it prints **every series at one column**,
	 * so comparing four series costs one hover rather than four; and its entries
	 * **lie side by side**, wrapping to a new line only when the next one does not
	 * fit - never one entry per line stacked under the chart.
	 *
	 * The strip may be as wide as its plot, `chart.readout_max_share` of it. A
	 * share under one wrapped the entries on a phone while the plot still had
	 * room, which is the tall block this layout replaced. From the small
	 * breakpoint up, each value keeps the room its widest reading needs, so
	 * stepping from column to column does not reflow the strip or change the
	 * panel's height. On a phone that room can be wider than the strip itself,
	 * so there it is not kept.
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
		/** The characters the widest reading of this entry needs, or zero. */
		reserve: number;
	}

	/** The widest of a series' readings, so the strip keeps room for it. */
	function widest(values: readonly (string | null)[], missing: string): number {
		return values.reduce((most, value) => Math.max(most, (value ?? missing).length), 0);
	}

	/** What the strip prints: a heading and its entries, in either shape. */
	const view = $derived.by(
		(): { shape: 'columns' | 'record'; heading: string; resting: boolean; entries: Entry[] } | null => {
			if (readout === null) return null;
			if ('subject' in readout) {
				return {
					shape: 'record',
					heading: readout.subject,
					resting,
					entries: readout.facts.map((fact) => ({
						label: fact.label,
						value: fact.value ?? readout.notMeasured,
						swatch: fact.swatch,
						reserve: fact.reserve ?? 0
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
						swatch: one.swatch,
						reserve: widest(one.values, readout.notMeasured)
					}))
				: [{ label: readout.notMeasured, value: '', swatch: null, reserve: 0 }];
			const events = readout.events[column] ?? [];
			const none: Entry[] =
				events.length === 0 && readout.eventsNone !== ''
					? [{ label: readout.eventsNone, value: '', swatch: null, reserve: 0 }]
					: [];
			return {
				shape: 'columns',
				heading: readout.columns[column],
				resting: at === null,
				entries: [...series, ...events.map((line) => ({ ...line, reserve: 0 })), ...none]
			};
		}
	);
</script>

{#if view}
	<dl
		class="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[0.75rem] text-text-tertiary"
		style={readoutCapStyle(maxShare)}
		data-readout={name}
		data-readout-shape={view.shape}
		aria-live="polite"
	>
		<!-- The heading takes a line of its own, so the entries after it start at
		     the same place on every column and the eye does not hunt for them. -->
		<dt
			class="basis-full font-semibold text-text-secondary"
			data-readout-day={view.shape === 'columns' ? '' : undefined}
			data-readout-subject={view.shape === 'record' ? '' : undefined}
		>
			{view.heading}{view.resting ? restingNote : ''}
		</dt>
		{#each view.entries as entry, index (`${index}:${entry.label}`)}
			<!-- An entry wider than the strip wraps inside itself, value under label,
			     rather than pushing the page sideways. The room a value keeps for its
			     widest reading is kept from the small breakpoint up: on a phone that
			     room is wider than the strip, and a strip that scrolls the page
			     sideways costs more than one that reflows as the reader steps. -->
			<div
				class="flex min-w-0 max-w-full flex-wrap items-center gap-x-1.5"
				data-readout-row={entry.label}
			>
				{#if entry.swatch}
					<span class="size-3 shrink-0 rounded-sm" style="background: {entry.swatch}"></span>
				{/if}
				<dd>{entry.label}</dd>
				{#if entry.value !== ''}
					<dd
						class="tabular-nums text-text-secondary sm:min-w-(--readout-reserve)"
						style={entry.reserve > 0 ? `--readout-reserve: ${entry.reserve}ch` : undefined}
					>
						{entry.value}
					</dd>
				{/if}
			</div>
		{/each}
	</dl>
	<p class="mt-2 text-[0.75rem] text-text-tertiary" data-readout-hint={name}>{hint}</p>
{/if}
