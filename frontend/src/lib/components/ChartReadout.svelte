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
	import { readoutCapStyle, type DayReadout } from '$lib/charts/frame';

	let {
		readout,
		name,
		maxShare,
		resting = false,
		restingNote = '',
		hint = 'Point at a column to read it. Left and Right step through them, Escape returns to the newest.'
	}: {
		/** The column to print. Null draws nothing at all. */
		readout: DayReadout | null;
		/** What the strip is of, so a page with several can be told apart. */
		name: string;
		/** `chart.readout_max_share`. */
		maxShare: number;
		/** True while no column has been picked, so the heading can say which
		 * column it fell back to rather than looking like a choice. */
		resting?: boolean;
		restingNote?: string;
		hint?: string;
	} = $props();
</script>

{#if readout}
	<dl
		class="mt-3 text-[0.75rem] text-text-tertiary"
		style={readoutCapStyle(maxShare)}
		data-readout={name}
		aria-live="polite"
	>
		<dt class="font-semibold text-text-secondary" data-readout-day>
			{readout.date}{resting ? restingNote : ''}
		</dt>
		{#each readout.rows as row (row.label)}
			<div class="mt-1 flex items-center gap-2" data-readout-row={row.label}>
				{#if row.colour}
					<span class="size-3 shrink-0 rounded-sm" style="background: {row.colour}"></span>
				{/if}
				<dd class="grow">{row.label}</dd>
				<dd class="tabular-nums text-text-secondary">{row.value}</dd>
			</div>
		{/each}
	</dl>
	<p class="mt-2 text-[0.75rem] text-text-tertiary" data-readout-hint={name}>{hint}</p>
{/if}
