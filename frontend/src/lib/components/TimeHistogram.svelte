<script lang="ts">
	/** How long one thing took, drawn as a distribution rather than as a median.
	 *
	 * A median answers "how long does one take" and refuses "how bad does it
	 * get". Over the committed ledger those are different questions by a factor
	 * of six, and the second is the one that decides whether a shard fits its
	 * timeout - so the whole shape is drawn and the two figures anybody quotes
	 * are ruled on it.
	 *
	 * Two panels on the Summaries route draw it: the model writing a summary,
	 * and the checker reading one afterwards. Same question, same shape, one
	 * component - the alternative was a second implementation of a log binning
	 * and a second pair of rules that could drift from the first. What differs
	 * between the two is four strings and a name, and they arrive as props.
	 *
	 * The bars are log-binned: each is one doubling wide. Writing times here run
	 * from a third of a second to twelve minutes, and on a linear axis every bar
	 * but one is a hairline against the left edge. The binning is arithmetic in
	 * `$lib/server/model-work`, not a chart type - nothing new is registered and
	 * no engine is loaded on this route at all.
	 *
	 * The cumulative line is the second reading and it is what makes the rules
	 * legible: a bar says how many landed here, the line says how many are done
	 * by here. They share the horizontal axis and nothing else, so the line
	 * carries its own axis on the right and its own label.
	 *
	 * The edge labels are thinned by measurement, not by a count: a label is
	 * kept only where it clears the last kept one, so the axis cannot overprint
	 * itself at any width. Measured 2026-09-01 at 390, the writing chart carries
	 * eleven edges in 306px of plot and four of them have to go.
	 *
	 * Hand-written SVG, so the chart is complete before any script runs and both
	 * themes work with none - every colour leaves as a custom property.
	 *
	 * It draws no model-change rule, and that is a judgement about the chart and
	 * not about the measure. A change to the model, the prompt or the truncation
	 * cap moves every bar here. But the horizontal axis is seconds, so a day has
	 * no position on it: the window is pooled into one distribution, and a rule
	 * would have to be drawn somewhere no date exists. The chart says so in
	 * `data-model-rule-none` rather than being silently absent from the census.
	 */
	import {
		AXIS_LABEL_GAP_PX,
		AXIS_LABEL_PX,
		chartWidth,
		frame,
		linearAxis,
		observeWidth,
		pointerReadout,
		readoutMarks,
		thinLabels,
		type DayReadout,
		type Margin
	} from '$lib/charts/frame';
	import ChartReadout from './ChartReadout.svelte';
	import { plural } from '$lib/format';
	import type { Distribution } from '../../routes/console/model/+page.server';

	let {
		times,
		name,
		subject,
		verb,
		noun = 'summary',
		nouns = 'summaries',
		noRuleReason,
		width,
		height,
		readoutMaxShare = 0.33
	}: {
		times: Distribution;
		/** What this instance is of, so a page with two can tell them apart. */
		name: string;
		/** What the horizontal axis measures, in words - it becomes the axis
		 * title and opens the description a screen reader is given. */
		subject: string;
		/** What happened to a summary in that time: `written`, `checked`. */
		verb: string;
		/** What one measured thing is, in the singular and the plural. The
		 * Pipelines route bins how long the model spent reading a PROMPT, and a bar
		 * reading "5 summaries read" would name the wrong thing - the model reads
		 * the article and writes the summary. */
		noun?: string;
		nouns?: string;
		/** Why no model-change rule is drawn here, in the chart's own words. */
		noRuleReason: string;
		width: number;
		height: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare?: number;
	} = $props();

	/** Room for the count axis, the percent axis and the two rule labels. */
	const MARGIN: Margin = { top: 26, right: 44, bottom: 44, left: 40 };

	let measured = $state<number | null>(null);

	const box = $derived(frame(chartWidth(measured, width), height, MARGIN));
	const yBars = $derived(
		linearAxis(
			times.bins.map((bin) => bin.n),
			[box.bottom, box.top]
		)
	);

	/** Where a value in seconds sits across the plot.
	 *
	 * The edges double, so a log placement makes every bar the same width and
	 * puts a rule at the true point inside its own bar. The first bar holds
	 * everything under a second and has no lower edge to place, so it borrows
	 * half its upper one - which is the same doubling as every other bar.
	 */
	const lowEdge = $derived(times.bins[0].from === 0 ? times.bins[0].to / 2 : times.bins[0].from);
	const highEdge = $derived(times.bins[times.bins.length - 1].to);

	function x(seconds: number): number {
		const held = Math.min(Math.max(seconds, lowEdge), highEdge);
		const span = Math.log2(highEdge) - Math.log2(lowEdge);
		const at = span === 0 ? 0 : (Math.log2(held) - Math.log2(lowEdge)) / span;
		return box.left + at * box.innerWidth;
	}

	function lowOf(bin: Distribution['bins'][number]): number {
		return bin.from === 0 ? lowEdge : bin.from;
	}

	/** The percent axis on the right, always the full nought to a hundred. A
	 * cumulative curve that ends short of its own top reads as a curve that has
	 * not finished. */
	function yPct(percent: number): number {
		return box.bottom - (percent / 100) * box.innerHeight;
	}

	const bars = $derived(
		times.bins.map((bin) => {
			const left = x(lowOf(bin));
			const right = x(bin.to);
			return {
				bin,
				x: left,
				width: Math.max(1, right - left - 2),
				y: yBars.scale(bin.n),
				height: Math.max(0, box.bottom - yBars.scale(bin.n)),
				// The right edge is where the bar's own count is complete, so the
				// curve's point sits over the bar it finishes rather than beside it.
				pointX: right,
				pointY: yPct(bin.throughPct)
			};
		})
	);

	const curve = $derived(
		[
			`M ${round(box.left)} ${round(yPct(0))}`,
			...bars.map((bar) => `L ${round(bar.pointX)} ${round(bar.pointY)}`)
		].join(' ')
	);

	/** The two figures somebody quotes off this chart, taken over the values and
	 * never off a bar. Reading a percentile out of a bin is a guess at where
	 * inside the bin it fell. */
	const rules = $derived([
		{
			key: 'median',
			seconds: Math.round(times.median / 1000),
			label: `Half inside ${seconds(times.median)}`
		},
		{
			key: 'p95',
			seconds: Math.round(times.p95 / 1000),
			label: `1 in 20 past ${seconds(times.p95)}`
		}
	]);

	function round(value: number): number {
		return Math.round(value * 10) / 10;
	}

	/** Whole seconds, and `<1` where a real measurement rounds away. */
	function seconds(ms: number): string {
		const value = Math.round(ms / 1000);
		return value === 0 && ms > 0 ? '<1 s' : `${value} s`;
	}

	function edgeLabel(bin: Distribution['bins'][number]): string {
		return bin.from === 0 ? '<1' : String(bin.from);
	}

	/** Every edge label, and where it would be drawn.
	 *
	 * The last entry is the axis's own end - the upper edge of the last bar,
	 * which no bar owns because every other label is a boundary two bars share.
	 */
	const edges = $derived([
		...bars.map((bar) => ({ key: String(bar.bin.from), text: edgeLabel(bar.bin), x: bar.x })),
		{ key: 'end', text: String(highEdge), x: box.right }
	]);

	/** The labels that fit, left to right.
	 *
	 * Measured rather than counted, the rule Row #1 settled for every date axis
	 * on this console. `thinLabels` owns it, so an eleven-edge axis at 390 can
	 * be checked without a ledger that happens to span eleven doublings.
	 */
	const shownEdges = $derived(thinLabels(edges, AXIS_LABEL_PX, AXIS_LABEL_GAP_PX));

	function barTitle(bin: Distribution['bins'][number]): string {
		const span = bin.from === 0 ? 'under 1 second' : `${bin.from} to ${bin.to} seconds`;
		return `${plural(bin.n, noun, nouns)} ${verb} in ${span}. ${bin.throughPct}% of the ${times.n} were done by ${bin.to} seconds.`;
	}

	const description = $derived(
		`${subject} over ${plural(times.n, noun, nouns)}, on a doubling scale. ` +
			`Half were ${verb} inside ${seconds(times.median)} and one in twenty took longer than ${seconds(times.p95)}. ` +
			`The fastest took ${seconds(times.fastest)} and the slowest ${seconds(times.slowest)}. ` +
			bars
				.filter((bar) => bar.bin.n > 0)
				.map((bar) => barTitle(bar.bin))
				.join(' ')
	);

	/** The bin a pointer or an arrow key has picked. */
	let selected = $state<number | null>(null);

	/** The bar's own count and the curve's reading at the same bin. Two series
	 * against two different axes is the one shape where reading them together by
	 * eye is hardest, and it is the reason both are drawn at all. */
	const columns = $derived<DayReadout[]>(
		bars.map((bar) => ({
			// The bar's centre, not its right edge: the curve's point sits on the
			// edge, but a reader aiming at a bar aims at the middle of it.
			x: (bar.x + bar.pointX) / 2,
			date: bar.bin.from === 0 ? 'Under 1 second' : `${bar.bin.from} to ${bar.bin.to} seconds`,
			rows: [
				{
					label: `${verb.charAt(0).toUpperCase()}${verb.slice(1)} in this band`,
					value: String(bar.bin.n),
					colour: 'var(--chart-1)'
				},
				{
					label: `Done by ${bar.bin.to} s`,
					value: `${bar.bin.throughPct}%`,
					colour: 'var(--chart-3)'
				}
			]
		}))
	);
	const marks = $derived(readoutMarks(columns));
	/** The last band, which is the tail the panel exists to show. */
	const resting = $derived(columns.length === 0 ? null : columns.length - 1);
	const at = $derived(selected ?? resting);
	const readout = $derived(at === null ? null : (columns[at] ?? null));
	const guide = $derived(selected === null ? null : (columns[selected]?.x ?? null));
</script>

<div
	class="plot"
	data-histogram={name}
	data-histogram-n={times.n}
	data-readout-columns={columns.length}
	data-model-rule="no"
	data-model-rule-name={name}
	data-model-rule-none={noRuleReason}
>
	<div use:observeWidth={(next) => (measured = next)}>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<svg
			class="block max-w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
			width={box.width}
			height={box.height}
			viewBox={`0 0 ${box.width} ${box.height}`}
			role="img"
			tabindex="0"
			aria-label={description}
			use:pointerReadout={{
				marks,
				width: box.width,
				onSelect: (index) => (selected = index)
			}}
		>
			<!-- The count axis. Bars are read against it, so it is anchored at zero
			     and labelled where the bars are. -->
			{#each yBars.ticks as tick (tick)}
				<line
					x1={box.left}
					x2={box.right}
					y1={round(yBars.scale(tick))}
					y2={round(yBars.scale(tick))}
					stroke="var(--color-rule)"
				/>
				<text
					x={box.left - 6}
					y={round(yBars.scale(tick)) + 3}
					text-anchor="end"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-tick="y"
				>
					{tick}
				</text>
			{/each}

			<!-- The percent axis on the right, for the curve alone. Two quantities
			     on one axis would make the curve a count it is not. -->
			{#each [0, 50, 100] as tick (tick)}
				<text
					x={box.right + 6}
					y={round(yPct(tick)) + 3}
					text-anchor="start"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-tick="pct"
				>
					{tick}%
				</text>
			{/each}

			{#each bars as bar (bar.bin.from)}
				<g data-hist-bin={bar.bin.from} data-hist-bin-n={bar.bin.n}>
					<title>{barTitle(bar.bin)}</title>
					<rect
						x={round(bar.x + 1)}
						y={round(bar.y)}
						width={round(bar.width)}
						height={round(bar.height)}
						fill="var(--chart-1)"
					/>
				</g>
			{/each}

			<!-- The edges that fit, first and last always. A dropped label leaves
			     its bar: a reader counting bars needs them all, and it is the type
			     that cannot overprint, not the data. -->
			{#each shownEdges as edge (edge.key)}
				<text
					x={round(edge.x)}
					y={box.bottom + 14}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-tick="x"
				>
					{edge.text}
				</text>
			{/each}

			<path
				d={curve}
				fill="none"
				stroke="var(--chart-3)"
				stroke-width="1.5"
				stroke-linejoin="round"
				data-histogram="cumulative"
			/>

			{#if guide !== null}
				<line
					x1={round(guide)}
					x2={round(guide)}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--color-text-tertiary)"
					stroke-opacity="0.5"
					data-histogram="guide"
				/>
			{/if}

			<!-- Dashed and in the tertiary ink, never on the confidence ramp. A
			     median is where the work sits, not a fault. -->
			{#each rules as rule (rule.key)}
				<line
					x1={round(x(rule.seconds))}
					x2={round(x(rule.seconds))}
					y1={box.top - 6}
					y2={box.bottom}
					stroke="var(--color-text-secondary)"
					stroke-dasharray="3 3"
					data-hist-rule={rule.key}
					data-hist-rule-seconds={rule.seconds}
				/>
				<text
					x={round(x(rule.seconds))}
					y={rule.key === 'median' ? box.top - 14 : box.top - 2}
					text-anchor={x(rule.seconds) > box.right - 90 ? 'end' : 'middle'}
					fill="var(--color-text-secondary)"
					font-size="10"
					data-hist-rule-label={rule.key}
				>
					{rule.label}
				</text>
			{/each}

			<line x1={box.left} x2={box.right} y1={box.bottom} y2={box.bottom} stroke="var(--color-rule)" />

			<text
				x={box.left}
				y={box.bottom + 32}
				fill="var(--color-text-tertiary)"
				font-size="10"
				data-axis-title
			>
				{subject}, seconds
			</text>
			<text
				x={box.right}
				y={box.bottom + 32}
				text-anchor="end"
				fill="var(--color-text-tertiary)"
				font-size="10"
				data-axis-title="cumulative"
			>
				{nouns.charAt(0).toUpperCase()}{nouns.slice(1)} done by then, percent
			</text>
		</svg>
	</div>

	<!-- Below the plot, never over it, and the same strip every chart on this
	     console prints - see `ChartReadout.svelte` for the rules it holds. -->
	<ChartReadout
		{readout}
		{name}
		maxShare={readoutMaxShare}
		resting={selected === null}
		restingNote=", the slowest band"
		hint="Point at a band to read its count and how much of the window is done by then. Left and Right step through the bands, Escape returns to the slowest."
	/>
</div>

<style>
	.plot {
		margin-top: var(--space-4);
	}
</style>
