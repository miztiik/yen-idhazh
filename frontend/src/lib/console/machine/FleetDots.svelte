<script lang="ts">
	/** Draws the machine kinds as one square a job, a column a day.
	 *
	 * The shape the panel takes under `console.fleet_min_rows` placements, when a
	 * bar over a small count would read as a rate the count cannot support. Every
	 * square is a job a reader can point at, coloured by its machine's speed, and
	 * a day's squares fill from the bottom in the same order a bar would stack.
	 * A known machine with no speed reading is a hollow square: stripes on a
	 * square this small are one or two lines and read as the flat grey of no
	 * machine recorded.
	 *
	 * Its hover data is the readout strip under the plot, as on every chart here:
	 * the plot is one tab stop, and a pointer, a key or a tap picks a day. A click
	 * or Enter holds the day open, outlined, for the list under the plot.
	 */
	import { AXIS_LABEL_PX } from '$lib/charts/frame';
	import type { FleetDots } from '$lib/charts/fleet';
	import { columnPick, pointerReadout, readoutMarks, type Readout } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';

	let {
		geometry,
		readout,
		name,
		label,
		readoutMaxShare,
		restingNote = ', the newest day',
		hint,
		hintOne = '',
		picked = null,
		onPick
	}: {
		geometry: FleetDots;
		/** The strip under the plot, one column a day in the geometry's order. */
		readout: Readout;
		name: string;
		label: string;
		/** `chart.readout_max_share`. */
		readoutMaxShare: number;
		restingNote?: string;
		hint: string;
		/** What the strip's hint line says at one column; see `ChartReadout`. */
		hintOne?: string;
		/** The day held open, outlined on the plot. */
		picked?: number | null;
		/** Told of a day a click or Enter picked. */
		onPick: (column: number) => void;
	} = $props();

	/** A tick mark's length, the same as the reserved frame draws. */
	const TICK = 4;
	/** The outline a hollow square is drawn with. */
	const RING = 1.5;
	/** How far the outline of a day held open stands off its squares. */
	const HELD = 2;

	let selected = $state<number | null>(null);
	/** A day held open is the strip's resting day until it is closed, so a tap
	 * that opened a list leaves that day's numbers under the plot. */
	const shown = $derived(selected ?? picked);
	const box = $derived(geometry.frame);
	const marks = $derived(readoutMarks(geometry.columns));
	const showing = $derived(shown ?? readout.resting);
</script>

<div class="fleet-dots-plot" data-readout-columns={readout.columns.length}>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<svg
		class="fleet-dots"
		viewBox="0 0 {box.width} {box.height}"
		width={box.width}
		height={box.height}
		role="img"
		aria-label={label}
		tabindex="0"
		data-chart-type="dateSeries"
		data-chart-name={name}
		data-fleet-square-size={geometry.size}
		use:pointerReadout={{ marks, width: box.width, onSelect: (index) => (selected = index) }}
		use:columnPick={{ marks, width: box.width, showing, onPick }}
	>
		<line x1={box.left} x2={box.right} y1={box.bottom} y2={box.bottom} stroke="var(--chart-axis)" />
		{#each geometry.ticks as tick (tick.index)}
			<line
				x1={geometry.columns[tick.index]}
				x2={geometry.columns[tick.index]}
				y1={box.bottom}
				y2={box.bottom + TICK}
				stroke="var(--chart-axis)"
			/>
			{#if tick.text}
				<text
					x={geometry.columns[tick.index]}
					y={box.bottom + TICK + AXIS_LABEL_PX}
					text-anchor={tick.anchor}
					fill="var(--color-text-tertiary)"
					font-size={AXIS_LABEL_PX}>{tick.text}</text
				>
			{/if}
		{/each}

		<g data-lede data-fleet-squares={geometry.squares.length}>
			{#each geometry.squares as square, at (at)}
				{#if square.drawing === 'untimed'}
					<rect
						x={square.x + RING / 2}
						y={square.y + RING / 2}
						width={Math.max(0, square.size - RING)}
						height={Math.max(0, square.size - RING)}
						fill="none"
						style:stroke={square.colour}
						stroke-width={RING}
						data-fleet-square={square.row}
					/>
				{:else}
					<rect
						x={square.x}
						y={square.y}
						width={square.size}
						height={square.size}
						style:fill={square.colour}
						data-fleet-square={square.row}
					/>
				{/if}
			{/each}
		</g>

		{#if picked !== null && geometry.blocks[picked] !== undefined}
			{@const block = geometry.blocks[picked]}
			<rect
				x={block.left - HELD}
				y={block.top - HELD}
				width={block.right - block.left + HELD * 2}
				height={box.bottom - block.top + HELD}
				fill="none"
				stroke="var(--color-text)"
				stroke-width="1"
				data-fleet-held={picked}
			/>
		{/if}
		{#if selected !== null && geometry.columns[selected] !== undefined}
			<line
				x1={geometry.columns[selected]}
				x2={geometry.columns[selected]}
				y1={box.top}
				y2={box.bottom}
				stroke="var(--color-text-tertiary)"
				stroke-opacity="0.5"
				data-fleet-guide
			/>
		{/if}
	</svg>
	<ChartReadout {readout} at={shown} {name} maxShare={readoutMaxShare} {restingNote} {hint} {hintOne} />
</div>

<style>
	/* Drawn at the width the panel measured; until it has measured one, the plot
	   shrinks to its column rather than pushing the page sideways. */
	.fleet-dots {
		display: block;
		max-inline-size: 100%;
		block-size: auto;
	}

	.fleet-dots:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}
</style>
