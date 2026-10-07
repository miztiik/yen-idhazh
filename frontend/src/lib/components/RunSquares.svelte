<script lang="ts">
	/** Every run of every day, one square a run, stacked on the day it ran.
	 *
	 * Two shapes, one question. Under the chart the squares take the chart's own
	 * day slots, so a day's runs stand under that day's bars and a reader reading
	 * down lands on the day he read across. Where the chart draws its narrow shape,
	 * or where a slot cannot hold even the smallest square, they keep the strip
	 * they have always had: 16px squares with a date row of their own, scrolling
	 * sideways and opening on the newest day.
	 *
	 * Within a day, runs rise from a shared baseline. Run 1 sits on the ground and
	 * later runs stack upward, so a busy day is visibly taller than a quiet one,
	 * while the DOM still reads run 1 first.
	 *
	 * A column is drawn for every day of the window, run or no run. An empty
	 * column is the fact this figure exists to show - a day nothing ran - and it
	 * is the column a reader most needs to see picked.
	 */
	import type { DaySlots } from '$lib/charts/day-slots';
	import { pointerReadout, type ReadoutMark } from '$lib/charts/readout';
	import {
		axisLabels,
		cellFor,
		centreOffset,
		slotCellFor,
		type LabelAlign
	} from '$lib/charts/run-history';
	import { HEALTH_FILL, type DayColumn } from '$lib/console/run-square';
	import { countDays, nameSpan } from '$lib/console/span-words';

	let {
		days,
		slots,
		narrow,
		tickDensity,
		selected = $bindable(null)
	}: {
		/** One entry per day of the window, oldest first. */
		days: DayColumn[];
		/** Where the chart above put each day, in its own pixels. */
		slots: DaySlots;
		/** The chart above is drawing its narrow shape. */
		narrow: boolean;
		/** `chart.tick_density`, for the strip's own date row. */
		tickDensity: number;
		/** The day both figures are showing, or null for the newest. */
		selected?: number | null;
	} = $props();

	/** The square under the chart, or null where the strip has to be drawn. */
	const under = $derived(narrow ? null : slotCellFor(slots.slot));

	/** What the keys are told the squares are. One day has no other day for Left
	 * and Right to reach, so at one day the label names the day instead. */
	const keysLabel = $derived(
		days.length === 1
			? `Run health, one column for ${nameSpan(days.length)}.`
			: 'Run health, one column a day. Left and Right read a day, Escape returns to the newest.'
	);
	/** The strip's name. At one day only the runs stacked in its one column have an order. */
	const stripLabel = $derived(
		`Run health history over ${countDays(days.length)}, ${days.length === 1 ? 'runs ' : ''}oldest to newest`
	);

	/** How tall a day's stack is, from the ground to its last run's top edge. */
	function stackHeight(runs: number, cell: number, gap: number): number {
		return runs === 0 ? 0 : runs * cell + (runs - 1) * gap;
	}

	const tallest = $derived(
		under === null
			? 0
			: Math.max(0, ...days.map((day) => stackHeight(day.squares.length, under.cell, under.gap)))
	);

	/** A position on the chart as a share of its width. The drawing is capped at
	 * its column's width before anything has measured it, and a share follows the
	 * cap the way the chart's own marks do; a pixel would not. */
	function share(x: number): string {
		return `${((x / Math.max(1, slots.width)) * 100).toFixed(4)}%`;
	}

	const underMarks: ReadoutMark[] = $derived(slots.centres.map((x) => ({ x })));

	// The strip, for a phone. It keeps the pair it has always drawn at and
	// scrolls instead of shrinking, and it centres when it cannot fill its room.
	const strip_ = $derived(cellFor(slots.width, days.length));
	const stripPad = $derived(centreOffset(slots.width, strip_.width));
	/** Which columns of the strip carry a date. The cell grows with the room the
	 * strip has, so the number of labels that fit is a measurement. */
	const axis = $derived(
		axisLabels(
			days.map((day) => day.date),
			{ density: tickDensity, pitch: strip_.cell + strip_.gap }
		)
	);
	const stripMarks: ReadoutMark[] = $derived(
		days.map((_, index) => ({ x: index * (strip_.cell + strip_.gap) + strip_.cell / 2 }))
	);

	/** A label is placed inside its column, not laid out by it, so the widest
	 * date on the axis cannot push a single day track out of step. */
	const ANCHOR: Record<LabelAlign, string> = {
		start: 'left: 0',
		centre: 'left: 50%; transform: translateX(-50%)',
		end: 'right: 0'
	};

	let strip = $state<HTMLDivElement | null>(null);

	// The newest run is the one an operator came to see, and it sits at the far
	// end. One frame, so the strip has been laid out before it is moved, and
	// never again - after this the scroll position belongs to the operator.
	$effect(() => {
		const node = strip;
		if (!node) return;
		const frame = requestAnimationFrame(() => {
			node.scrollLeft = node.scrollWidth - node.clientWidth;
		});
		return () => cancelAnimationFrame(frame);
	});

	/** Bring one day's column into the strip's view, and move it no further than
	 * that. Under the chart every day is already on screen, so there is nothing
	 * to move. */
	export function reveal(index: number): void {
		const node = strip;
		if (!node) return;
		const column = node.querySelectorAll<HTMLElement>('[data-day]')[index];
		if (!column) return;
		const room = node.getBoundingClientRect();
		const box = column.getBoundingClientRect();
		if (box.left < room.left) node.scrollLeft -= room.left - box.left;
		else if (box.right > room.right) node.scrollLeft += box.right - room.right;
	}
</script>

{#if under !== null}
	<!-- Directly under the chart's date row, and at the chart's own width: the
	     width attribute the chart draws at, capped by the column the same way, so
	     a day's column lands on that day's bars before and after anything has
	     measured the page. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<div
		class="run-squares relative max-w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
		style="width: {slots.width}px; height: {tallest}px"
		tabindex="0"
		role="group"
		aria-label={keysLabel}
		data-run-history="under-chart"
		data-grid="days"
		use:pointerReadout={{
			marks: underMarks,
			width: slots.width,
			onSelect: (index) => (selected = index),
			selected,
			onPick: reveal
		}}
	>
		{#each days as day, index (day.date)}
			<!-- Column-reverse, so run 1 sits on the baseline and later runs stack
			     upward, while the DOM keeps reading run 1 first. The full height of the
			     figure, so a day with no run still has a column to point at and to
			     tint. -->
			<div
				class="absolute inset-y-0 flex flex-col-reverse justify-start"
				style="left: calc({share(slots.centres[index] ?? 0)} - {under.cell / 2}px); width: {under.cell}px; gap: {under.gap}px"
				data-day={day.date}
				data-day-selected={selected === index ? 'true' : null}
			>
				{#each day.squares as square (square.runId)}
					<span
						class="shrink-0 rounded-sm"
						style="width: {under.cell}px; height: {under.cell}px; background: {HEALTH_FILL[square.health]}"
						aria-label={square.label}
						data-health={square.health}
						role="img"
					></span>
				{/each}
			</div>
		{/each}
	</div>
{:else}
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<div
		class="run-squares overflow-x-auto pb-1"
		role="region"
		tabindex="0"
		aria-label={stripLabel}
		bind:this={strip}
		data-run-history="strip"
	>
		<!-- Left-anchored while it overflows, centred while it does not. Where it
		     opens when it overflows is a different question: on the newest day. -->
		<div
			class="grid w-max items-end justify-start"
			style="grid-template-columns: repeat({days.length}, {strip_.cell}px); gap: {strip_.gap}px; margin-inline-start: {stripPad}px"
			data-grid="days"
			data-strip-pad={stripPad}
			tabindex="0"
			role="group"
			aria-label={keysLabel}
			use:pointerReadout={{
				marks: stripMarks,
				width: strip_.width,
				onSelect: (index) => (selected = index),
				selected,
				onPick: reveal
			}}
		>
			{#each days as day, index (day.date)}
				<!-- Stretched to the row rather than sized by its squares. A day with no
				     run has no squares, so a column sized by its content is a zero-height
				     box: nothing to point at, and no room for the tint that says which day
				     the readout is on. -->
				<div
					class="flex flex-col-reverse justify-start self-stretch"
					style="grid-row: 1; grid-column: {index + 1}; gap: {strip_.gap}px"
					data-day={day.date}
					data-day-selected={selected === index ? 'true' : null}
				>
					{#each day.squares as square (square.runId)}
						<span
							class="rounded-sm"
							style="width: {strip_.cell}px; height: {strip_.cell}px; background: {HEALTH_FILL[square.health]}"
							aria-label={square.label}
							data-health={square.health}
							role="img"
						></span>
					{/each}
				</div>
			{/each}

			{#each axis as label (label.column)}
				<div class="relative h-4" style="grid-row: 2; grid-column: {label.column}">
					<span
						class="absolute top-0 whitespace-nowrap text-[0.625rem] leading-4 tabular-nums text-text-tertiary"
						style={ANCHOR[label.align]}
						data-day-axis
						data-axis-label={label.column}
					>
						{label.text}
					</span>
				</div>
			{/each}
		</div>
	</div>
{/if}

<style>
	/* Directly under the chart's date row, with nothing between: the date row is
	   the bottom of the chart's own drawing, so this is measured from its edge. */
	.run-squares {
		margin-block-start: var(--space-2);
	}

	/* The column the readout is printing. A tint behind the day rather than a rule
	   through it: an empty column has no square for a rule to land on, and an empty
	   column is exactly the one a reader most needs to see picked. */
	[data-day-selected] {
		background: var(--color-surface-sunken);
		box-shadow: 0 0 0 2px var(--color-surface-sunken);
		border-radius: 2px;
	}
</style>
