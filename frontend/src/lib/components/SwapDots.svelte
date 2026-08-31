<script lang="ts">
	/** Did the model swap move anything - seven measures, one axis.
	 *
	 * Seven measures in four units cannot share a scale, so each one is drawn
	 * against itself: the old model sits at 100 percent on every row and the new
	 * model sits wherever it landed. That is the only axis all seven can share,
	 * and the question is the same for all seven anyway - did it move, and which
	 * way.
	 *
	 * **Direction is carried by the arrowhead first and by hue second.** Until
	 * 2026-08-31 the hue was refused outright, because nobody had said which way
	 * was worse for each of the seven. Five of them now say so themselves - the
	 * polarity is declared on the measure in `model-work.ts` - and the two that
	 * genuinely have no agreed direction, summary length and copying, keep the
	 * grey they always had and print the reason under the chart. So a hue here
	 * is never a guess: it is a property of the measure, and a measure with no
	 * property gets no hue.
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
	import { movementVerdict } from '$lib/charts/theme';
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
	/** The drawn rows nobody has agreed a direction for. Named under the chart,
	 * because a grey row beside six coloured ones has to say why it is grey. */
	const greyed = $derived(drawn.filter((measure) => measure.polarity === 'no-agreed-direction'));

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

	/** Did this measure move the way we wanted.
	 *
	 * Read off the same rounded percentage the track is drawn to and the row
	 * prints, so a move that rounds to `no change` can never be coloured as a
	 * move - the words and the hue come from one number. */
	function change(measure: SwapMeasure): number {
		return (pct(measure) - 100) / 100;
	}

	function verdict(measure: SwapMeasure): string {
		return movementVerdict(change(measure), measure.polarity);
	}

	function sentence(measure: SwapMeasure): string {
		const read = `${measure.label}: ${reading(measure, measure.before)} on ${swap.before.model}, ${reading(measure, measure.after)} on ${swap.after.model} - ${moved(measure)}`;
		const said = verdict(measure);
		if (said === 'good') return `${read}, the way we want.`;
		if (said === 'bad') return `${read}, the wrong way.`;
		if (measure.polarity === 'no-agreed-direction') {
			return `${read}. No direction is agreed for this one.`;
		}
		return `${read}.`;
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

<div class="plot" data-model-swap-plot data-swap-at={swap.at}>
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
					data-movement={change(measure).toFixed(4)}
					data-polarity={measure.polarity}
					data-movement-verdict={verdict(measure)}
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
						stroke-width="2"
						data-swap-cell="track"
						data-movement-paint="stroke"
					/>
					<circle
						cx={round(x(100))}
						cy={y}
						r="3.5"
						fill="var(--color-surface)"
						stroke-width="2"
						data-swap-cell="before"
						data-movement-paint="stroke"
					/>
					<polygon
						points={head(measure, y)}
						data-swap-cell="after"
						data-movement-paint="fill"
					/>
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
	{#if greyed.length > 0}
		<p class="mt-2 text-[0.75rem] text-text-tertiary" data-swap-no-direction>
			{#each greyed as measure, index (measure.label)}{index > 0 ? ', ' : ''}{measure.label}{/each}
			{greyed.length === 1 ? 'is drawn' : 'are drawn'} grey: nobody has agreed which way is the
			better way, so the row says how far it moved and stops there.
		</p>
	{/if}
</div>

<style>
	.plot {
		margin-top: var(--space-4);
	}

	/* The movement pair, never the confidence ramp: a summary that got slower is
	   not a broken run. The arrowhead already carries the direction and the two
	   values are printed on the row, so the hue is the third signal and never
	   the only one. */
	[data-movement-verdict='good'] [data-swap-cell='track'],
	[data-movement-verdict='good'] [data-swap-cell='before'] {
		stroke: var(--movement-good);
	}
	[data-movement-verdict='good'] [data-swap-cell='after'] {
		fill: var(--movement-good);
	}

	[data-movement-verdict='bad'] [data-swap-cell='track'],
	[data-movement-verdict='bad'] [data-swap-cell='before'] {
		stroke: var(--movement-bad);
	}
	[data-movement-verdict='bad'] [data-swap-cell='after'] {
		fill: var(--movement-bad);
	}

	/* No agreed direction, or nothing moved. One neutral across every movement
	   surface on the console, so a grey delta and a grey row are the same
	   statement. */
	[data-movement-verdict='neutral'] [data-swap-cell='track'],
	[data-movement-verdict='neutral'] [data-swap-cell='before'] {
		stroke: var(--color-text-secondary);
	}
	[data-movement-verdict='neutral'] [data-swap-cell='after'] {
		fill: var(--color-text-secondary);
	}
</style>
