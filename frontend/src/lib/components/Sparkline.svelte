<script lang="ts">
	/** Direction at a glance, inside a list row.
	 *
	 * The engine-backed sparkline is one chart instance, which is right on a
	 * card and wrong in a failure ledger where every row wants one. This draws
	 * the same shape as markup: it is finished before any script runs, it costs
	 * no chunk, and a hundred of them are a hundred polylines.
	 *
	 * One colour, never the trend ramp. A rising line is not a good line - a
	 * failure code climbing is the same shape as a published count climbing, and
	 * green on the first would be a verdict nobody agreed to.
	 */
	import type { SparklineMarks } from '../charts/sparkline';

	let {
		marks,
		label,
		width = 96,
		height = 22,
		rules = []
	}: {
		marks: SparklineMarks;
		/** What the line is, for anyone who cannot see it. A sentence. */
		label: string;
		width?: number;
		height?: number;
		/** Where the series stopped being one comparable thing.
		 *
		 * `at` is the same unit-square x the points use, so a rule and the point it
		 * names cannot land in two places. It carries no arrow and no delta: a rule
		 * says the ground moved, and nothing measured says it moved the line. */
		rules?: { at: number; label: string }[];
	} = $props();

	// Inset by the stroke, or a point sitting on the domain's edge is drawn half
	// outside the box.
	const atX = $derived((x: number) => x * (width - 2) + 1);
	const drawn = $derived(
		marks.points.map((p) => `${atX(p.x).toFixed(2)},${(p.y * (height - 4) + 2).toFixed(2)}`).join(' ')
	);
</script>

{#if marks.empty}
	<!-- A blank of the same size, never a dash. The row keeps its height, so a
	     list where only some rows have a history does not stagger. -->
	<span
		class="spark-empty"
		data-sparkline="empty"
		style="inline-size: {width}px; block-size: {height}px"
		aria-hidden="true"
	></span>
{:else}
	<svg
		class="spark"
		data-sparkline="line"
		width={width}
		height={height}
		viewBox="0 0 {width} {height}"
		role="img"
		aria-label={label}
	>
		<!-- Under the line, never over it: the rule is the context and the line is
		     the answer. -->
		{#each rules as rule (rule.at)}
			<line
				class="spark-rule"
				data-sparkline-rule={rule.at.toFixed(4)}
				x1={atX(rule.at)}
				x2={atX(rule.at)}
				y1="0"
				y2={height}
			>
				<title>{rule.label}</title>
			</line>
		{/each}
		<polyline points={drawn} />
	</svg>
{/if}

<style>
	/* A drawn width is a maximum, not a demand. A card narrower than the line it
	   holds scales the line down rather than pushing a scrollbar under the grid. */
	.spark {
		display: block;
		overflow: visible;
		max-inline-size: 100%;
	}

	.spark polyline {
		fill: none;
		stroke: var(--chart-2);
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
