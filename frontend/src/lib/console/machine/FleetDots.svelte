<script lang="ts">
	/** Draw one square per recorded job, preserving categorical machine identity. */
	import type { FleetDots } from '$lib/charts/fleet';
	import { columnPick, pointerReadout, readoutMarks, type Readout } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import type { HoverReadout } from '$lib/charts/readout-hover';

	let {
		geometry,
		readout,
		hover,
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
		hover: HoverReadout;
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
	/** How far the outline of a day held open stands off its squares. */
	const HELD = 2;

	let selected = $state<number | null>(null);
	/** A day held open is the strip's resting day until it is closed, so a tap
	 * that opened a list leaves that day's numbers under the plot. */
	const shown = $derived(selected ?? picked);
	const box = $derived(geometry.frame);
	const marks = $derived(readoutMarks(geometry.columns));
	const showing = $derived(shown ?? readout.resting);
	const gradients = $derived([...new Map(geometry.squares.flatMap((square) =>
		square.gradient === null ? [] : [[square.row, square.gradient] as const])).entries()]);
	const gradientIds = $derived(new Map(gradients.map(([key], index) => [key, `${name}-square-fill-${index}`])));
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
		use:pointerReadout={{ marks, width: box.width, hover, onSelect: (index) => (selected = index) }}
		use:columnPick={{ marks, width: box.width, showing, onPick }}
	>
		<defs>
			{#each gradients as [key, gradient] (key)}
				<linearGradient id={gradientIds.get(key)} x1="0%" y1="0%" x2="0%" y2="100%">
					<stop offset="0%" stop-color={gradient.bottom} style:stop-color={gradient.top} />
					<stop offset="100%" stop-color={gradient.bottom} />
				</linearGradient>
			{/each}
		</defs>
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
					y={box.bottom + TICK + box.labels.fontSize}
					text-anchor={tick.anchor}
					fill="var(--color-text-tertiary)"
					font-size={box.labels.fontSize}>{tick.text}</text
				>
			{/if}
		{/each}

		<g data-lede data-fleet-squares={geometry.squares.length}>
			{#each geometry.squares as square, at (at)}
				<rect
					x={square.x}
					y={square.y}
					width={square.size}
					height={square.size}
					style:fill={square.gradient === null ? square.colour : `url(#${gradientIds.get(square.row)}) ${square.colour}`}
					data-fleet-square={square.row}
					data-readout-key={square.row}
				/>
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
				pointer-events="none"
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
				pointer-events="none"
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
	[data-fleet-square] {
		stroke: var(--chart-axis);
		stroke-width: var(--console-chart-axis-width);
	}
</style>
