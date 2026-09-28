<script lang="ts">
	/** Direction at a glance, inside a card or a list row.
	 *
	 * Drawn as markup rather than by the engine: it is finished before any
	 * script runs, it costs no chunk, and a hundred of them are a hundred
	 * polylines - which is what a failure ledger with one a row needs.
	 *
	 * One colour, never the trend ramp. A rising line is not a good line - a
	 * failure code climbing is the same shape as a published count climbing, and
	 * green on the first would be a verdict nobody agreed to.
	 *
	 * A pointer, a tap or an arrow key names one day of the line and its value.
	 * A line on its own prints that strip under itself. A line in a list hands
	 * every pick to the list, which prints one strip for all of its rows: ten
	 * strips under ten rows would print one date ten times.
	 */
	import { pointerReadout, readoutMarks } from '$lib/charts/readout';
	import {
		SPARKLINE_SWATCH,
		sparklineReadout,
		type SparklineMarks,
		type SparklineRule,
		type SparklineSeries
	} from '$lib/charts/sparkline';
	import ChartReadout from '$lib/components/ChartReadout.svelte';

	/** Where the line's strip is printed. Under the line itself, named `name`;
	 * or by the list the line sits in, which is told every change - a column, or
	 * null when the pointer leaves - and hands its own pick back as `selected`,
	 * so only the row being read shows its marker. */
	type Strip =
		| { name: string; maxShare: number; hint: string }
		| { onSelect: (column: number | null) => void; selected: number | null };

	let {
		marks,
		label,
		series,
		strip,
		width = 96,
		height = 22,
		rules = []
	}: {
		marks: SparklineMarks;
		/** What the line is, for anyone who cannot see it. A sentence. */
		label: string;
		/** What the line measures, and the one formatter its values print by. */
		series: SparklineSeries;
		strip: Strip;
		width?: number;
		height?: number;
		/** Where the series stopped being one comparable thing.
		 *
		 * Each names the drawn point it lands on, so a rule and the day it names
		 * cannot land in two places, and its sentence prints in the strip on that
		 * day. It carries no arrow and no delta: a rule says the ground moved, and
		 * nothing measured says it moved the line. */
		rules?: SparklineRule[];
	} = $props();

	const own = $derived('name' in strip ? strip : null);
	/** The day a line that prints its own strip has picked, or null for rest. */
	let picked = $state<number | null>(null);
	const at = $derived('onSelect' in strip ? strip.selected : picked);
	const readout = $derived(own === null ? null : sparklineReadout(marks, series, rules));

	// Inset by the stroke, or a point sitting on the domain's edge is drawn half
	// outside the box.
	const atX = $derived((x: number) => x * (width - 2) + 1);
	const atY = $derived((y: number) => y * (height - 4) + 2);
	const drawn = $derived(
		marks.points.map((p) => `${atX(p.x).toFixed(2)},${atY(p.y).toFixed(2)}`).join(' ')
	);
	/** One column per drawn day, where the line draws it. */
	const columns = $derived(readoutMarks(marks.points.map((p) => atX(p.x))));
	const spot = $derived(at === null ? null : (marks.points[at] ?? null));

	function select(column: number | null): void {
		if ('onSelect' in strip) strip.onSelect(column);
		else picked = column;
	}
</script>

{#snippet line()}
	<!-- One tab stop for the line, never one per day - and none at all in a list,
	     where the list is the stop for every row's line. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<svg
		class="spark"
		data-sparkline="line"
		width={width}
		height={height}
		viewBox="0 0 {width} {height}"
		role="img"
		aria-label={label}
		tabindex={own === null ? undefined : 0}
		use:pointerReadout={{ marks: columns, width, onSelect: select, selected: at }}
	>
		<!-- Under the line, never over it: the rule is the context and the line is
		     the answer. Its sentence stays on it as its name, and the strip prints
		     it on the day it lands on. -->
		{#each rules as rule (rule.point)}
			{@const x = atX(marks.points[rule.point]?.x ?? 0)}
			<line
				class="spark-rule"
				data-sparkline-rule={rule.point}
				x1={x}
				x2={x}
				y1="0"
				y2={height}
				role="img"
				aria-label={rule.label}
			/>
		{/each}
		<polyline points={drawn} style="stroke: {SPARKLINE_SWATCH}" />
		{#if spot !== null}
			<circle
				cx={atX(spot.x).toFixed(2)}
				cy={atY(spot.y).toFixed(2)}
				r="2.5"
				style="fill: {SPARKLINE_SWATCH}"
				data-sparkline-at={at}
			/>
		{/if}
	</svg>
{/snippet}

{#if marks.empty}
	<!-- A blank of the same size, never a dash. The row keeps its height, so a
	     list where only some rows have a history does not stagger. -->
	<span
		class="spark-empty"
		data-sparkline="empty"
		style="inline-size: {width}px; block-size: {height}px"
		aria-hidden="true"
	></span>
{:else if own !== null && readout !== null}
	<div data-readout-columns={readout.columns.length}>
		{@render line()}
		<ChartReadout
			{readout}
			at={picked}
			name={own.name}
			maxShare={own.maxShare}
			hint={own.hint}
			eventRoom
		/>
	</div>
{:else}
	{@render line()}
{/if}

<style>
	/* A drawn width is a maximum, not a demand. A card narrower than the line it
	   holds scales the line down rather than pushing a scrollbar under the grid. */
	.spark {
		display: block;
		overflow: visible;
		max-inline-size: 100%;
	}

	.spark:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}

	.spark polyline {
		fill: none;
		stroke-width: 1.75;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.spark-rule {
		stroke: var(--color-rule-strong);
		stroke-width: 1;
		stroke-dasharray: 2 2;
	}

	.spark-empty {
		display: block;
		max-inline-size: 100%;
	}
</style>
