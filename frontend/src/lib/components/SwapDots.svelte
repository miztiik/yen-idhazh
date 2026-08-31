<script lang="ts">
	/** Did the model swap move anything - seven measures, one axis.
	 *
	 * Seven measures in four units cannot share a scale, so each one is drawn
	 * against itself: the old model sits at 100 percent on every row and the new
	 * model sits wherever it landed. That is the only axis all seven can share,
	 * and the question is the same for all seven anyway - did it move, and which
	 * way.
	 *
	 * **Direction is carried by the arrowhead and never by hue.** A red-for-worse
	 * ramp would need somebody to have agreed which way is worse for each of the
	 * seven, and nobody has: a shorter summary is what a smaller model was picked
	 * for, and more copying is not obviously worse than more invention. So the
	 * chart says how far and which way, and leaves worse to the reader.
	 *
	 * Both absolute values print on the row, because a ratio with no magnitude
	 * behind it can be a rounding error wearing a percentage. And both article
	 * counts print above the chart: two models over two article sets is two
	 * measurements, not a trend.
	 *
	 * Hand-written SVG, so the panel is complete before any script runs.
	 */
	import { chartWidth, frame, observeWidth, type Margin } from '$lib/charts/frame';
	import { swapScale } from '$lib/charts/series';
	import type { ModelSwap, SwapMeasure } from '../../routes/console/model/+page.server';

	let {
		swap,
		width
	}: {
		swap: ModelSwap;
		width: number;
	} = $props();

	/** One measure: the name, the two values under it, and the track between. */
	const ROW = 38;
	/** The longest label is `Outside the length we asked for` at 31 characters,
	 * and the two values sit on their own line below it. */
	const LABEL_ROOM = 196;
	const AXIS_ROOM = 34;
	const TOP = 18;
	/** Under this, the two dots overlap and the arrow has nowhere to point. It
	 * is drawn anyway - a measure that did not move is an answer. */
	const ARROW = 5;

	let measured = $state<number | null>(null);

	/** Every measure that has a ratio at all. A before of zero has no ratio,
	 * because a move away from nothing has no size, and the row says so in words
	 * rather than drawing a track to infinity. */
	const drawn = $derived(swap.measures.filter((measure) => measure.ratio !== null));
	const unmeasured = $derived(swap.measures.filter((measure) => measure.ratio === null));

	const box = $derived(
		frame(chartWidth(measured, width), TOP + drawn.length * ROW + AXIS_ROOM, {
			top: TOP,
			right: 16,
			bottom: AXIS_ROOM,
			left: LABEL_ROOM
		} satisfies Margin)
	);

	/** Symmetric about no change, so the same distance either side of the rule
	 * means the same size of move. */
	const scale = $derived(swapScale(drawn.map((measure) => pct(measure))));

	function x(percent: number): number {
		return box.left + scale.at(percent) * box.innerWidth;
	}

	function pct(measure: SwapMeasure): number {
		return Math.round((measure.ratio as number) * 100);
	}

	function round(value: number): number {
		return Math.round(value * 10) / 10;
	}

	/** Whole units only, and `<1` where a real measurement rounds away. */
	function reading(measure: SwapMeasure, value: number): string {
		const whole = Math.round(value);
		const short = whole === 0 && value > 0;
		if (measure.unit === 'seconds') return short ? '<1 s' : `${whole} s`;
		if (measure.unit === 'words') return short ? '<1 word' : `${whole} words`;
		if (measure.unit === 'percent') return short ? '<1%' : `${whole}%`;
		return short ? '<1 in 100' : `${whole} in 100`;
	}

	function moved(measure: SwapMeasure): string {
		const change = pct(measure) - 100;
		if (change === 0) return 'no change';
		return change > 0 ? `up ${change}%` : `down ${Math.abs(change)}%`;
	}

	function sentence(measure: SwapMeasure): string {
		return `${measure.label}: ${reading(measure, measure.before)} on ${swap.before.model}, ${reading(measure, measure.after)} on ${swap.after.model} - ${moved(measure)}.`;
	}

	/** The arrowhead, pointing the way the measure went. */
	function head(measure: SwapMeasure, y: number): string {
		const to = x(pct(measure));
		const back = pct(measure) >= 100 ? to - ARROW * 1.6 : to + ARROW * 1.6;
		return `${round(to)},${round(y)} ${round(back)},${round(y - ARROW)} ${round(back)},${round(y + ARROW)}`;
	}

	const description = $derived(
		`Seven measures either side of the day the model changed, each against its own value on ${swap.before.model}. ` +
			`${swap.before.model} wrote ${swap.before.articles} articles to ${swap.before.to}; ${swap.after.model} has written ${swap.after.articles} since ${swap.after.from}. ` +
			swap.measures
				.map((measure) =>
					measure.ratio === null
						? `${measure.label}: nothing to compare, ${swap.before.model} measured none.`
						: sentence(measure)
				)
				.join(' ')
	);
</script>

<div
	class="plot"
	data-model-swap-plot
	data-swap-at={swap.at}
	data-readout-none="one row per measure, each against its own baseline, so no column is shared"
>
	<div use:observeWidth={(next) => (measured = next)}>
		<svg
			class="block max-w-full"
			width={box.width}
			height={box.height}
			viewBox={`0 0 ${box.width} ${box.height}`}
			role="img"
			aria-label={description}
		>
			<!-- No change. Every row starts on this rule, so it is the chart's
			     baseline rather than a threshold anybody set. -->
			<line
				x1={round(x(100))}
				x2={round(x(100))}
				y1={box.top - 8}
				y2={box.bottom}
				stroke="var(--color-rule-strong)"
				data-swap-baseline
			/>

			{#each scale.ticks as tick (tick)}
				<text
					x={round(x(tick))}
					y={box.bottom + 14}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-tick="x"
				>
					{tick}%
				</text>
			{/each}

			<text
				x={box.left}
				y={box.bottom + 28}
				fill="var(--color-text-tertiary)"
				font-size="10"
				data-axis-title
			>
				Against the same measure on {swap.before.model}, percent
			</text>

			{#each drawn as measure, index (measure.label)}
				{@const y = box.top + index * ROW + 12}
				<g
					data-swap-row={measure.label}
					data-swap-pct={pct(measure)}
					data-swap-before={Math.round(measure.before)}
					data-swap-after={Math.round(measure.after)}
				>
					<title>{sentence(measure)}</title>
					<text
						x={box.left - 12}
						y={y + 3}
						text-anchor="end"
						fill="var(--color-text)"
						font-size="11"
						data-swap-cell="name"
					>
						{measure.label}
					</text>
					<text
						x={box.left - 12}
						y={y + 16}
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-swap-cell="values"
					>
						{reading(measure, measure.before)}, then {reading(measure, measure.after)}
					</text>

					<line
						x1={round(x(100))}
						x2={round(x(pct(measure)))}
						y1={y}
						y2={y}
						stroke="var(--chart-1)"
						stroke-width="2"
						data-swap-cell="track"
					/>
					<circle
						cx={round(x(100))}
						cy={y}
						r="3.5"
						fill="var(--color-surface)"
						stroke="var(--chart-1)"
						stroke-width="2"
						data-swap-cell="before"
					/>
					<polygon points={head(measure, y)} fill="var(--chart-1)" data-swap-cell="after" />
				</g>
			{/each}
		</svg>
	</div>

	{#if unmeasured.length > 0}
		<p class="mt-2 text-[0.75rem] text-text-tertiary" data-swap-unmeasured>
			{#each unmeasured as measure, index (measure.label)}{index > 0 ? ', ' : ''}{measure.label}{/each}
			measured nothing on {swap.before.model}, so there is nothing to compare against.
		</p>
	{/if}
</div>

<style>
	.plot {
		margin-top: var(--space-4);
	}
</style>
