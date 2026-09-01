<script lang="ts">
	/** Did the model swap move anything - ten measures, one axis.
	 *
	 * Ten measures in five units cannot share a scale, so each one is drawn
	 * against itself: the old model sits at 100 percent on every row and the new
	 * model sits wherever it landed. That is the only axis all ten can share,
	 * and the question is the same for all ten anyway - did it move, and which
	 * way.
	 *
	 * **A measure only one side recorded is named, never drawn.** The two token
	 * rates arrived on the item ledger part way through its life, so on an older
	 * boundary there is nothing on the left to compare against - and a track
	 * from an absent value would be a claim about a run nobody instrumented.
	 * Those rows print as a sentence under the plot saying which side is
	 * missing.
	 *
	 * **Direction is carried by the arrowhead first and by hue second.** Until
	 * 2026-08-31 the hue was refused outright, because nobody had said which way
	 * was worse for each measure. Six of them now say so themselves - the
	 * polarity is declared on the measure in `model-work.ts` - and the four that
	 * genuinely have no agreed direction keep the grey they always had and print
	 * the reason under the chart. So a hue here is never a guess: it is a
	 * property of the measure, and a measure with no property gets no hue.
	 *
	 * **The panel takes the width it is given.** The label column is measured
	 * against the frame rather than fixed: a 196px gutter was 15 percent of a
	 * 1,342px frame and 60 percent of a 324px one, so on a phone the names took
	 * more of the chart than the plot did. Where they will not fit beside the
	 * plot they go above it, which is the rule `frame.ts` already holds for
	 * every row chart on this console. The row pitch is solved for the frame the
	 * same way, so a page-wide panel is rows of type rather than hairlines with
	 * air nowhere.
	 *
	 * Both absolute values print on the row, because a ratio with no magnitude
	 * behind it can be a rounding error wearing a percentage. And both article
	 * counts print above the chart: two models over two article sets is two
	 * measurements, not a trend.
	 *
	 * Hand-written SVG, so the panel is complete before any script runs.
	 */
	import {
		chartWidth,
		frame,
		labelGutter,
		observeWidth,
		rowPitch,
		ROW_PITCH_MIN,
		type Margin
	} from '$lib/charts/frame';
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

	/** The row label, and the two values on the line under it. */
	const NAME_PX = 11;
	const VALUE_PX = 10;
	/** Clear pixels between the label column and the plot. */
	const GUTTER_GAP = 12;
	/** A row carries two lines of type and a track. Below this the rows touch. */
	const PITCH_MIN = ROW_PITCH_MIN;
	/** Where the label sits above its own track, the row is two lines of type,
	 * then the track, then the air that separates two rows. */
	const PITCH_MIN_STACKED = ROW_PITCH_MIN + 18;
	/** Past this the rows stop reading as one set. */
	const PITCH_MAX = 56;
	const AXIS_ROOM = 34;
	const TOP = 18;
	/** Where the two label lines go when they cannot sit beside the plot. */
	const STACK_NAME_Y = 11;
	const STACK_VALUE_Y = 23;
	const STACK_TRACK_Y = 36;
	/** Under this, the two dots overlap and the arrow has nowhere to point. It
	 * is drawn anyway - a measure that did not move is an answer. */
	const ARROW = 5;
	/** The right-most tick label anchors `middle`, so it needs half its own
	 * width outside the plot. `150%` at 10px is the widest it gets. */
	const RIGHT_ROOM = 16;

	let measured = $state<number | null>(null);

	const chartBox = $derived(chartWidth(measured, width));

	/** Every measure both sides recorded and that has a ratio at all. A before of
	 * zero has no ratio, because a move away from nothing has no size, and the
	 * row says so in words rather than drawing a track to infinity. */
	const drawn = $derived(swap.measures.filter((measure) => measure.ratio !== null));
	const unmeasured = $derived(swap.measures.filter((measure) => measure.ratio === null));
	/** The drawn rows nobody has agreed a direction for. Named under the chart,
	 * because a grey row beside coloured ones has to say why it is grey. */
	const greyed = $derived(drawn.filter((measure) => measure.polarity === 'no-agreed-direction'));

	function valueLine(measure: SwapMeasure): string {
		return `${reading(measure, measure.before)}, then ${reading(measure, measure.after)}`;
	}

	/** The room the two label lines need, or null where the frame cannot spare
	 * it. `labelGutter` refuses a gutter past 30 percent of the frame, which is
	 * the bound that stops a chart becoming a list with a plot in the margin. */
	const gutter = $derived.by(() => {
		const names = labelGutter(
			drawn.map((measure) => measure.label),
			NAME_PX,
			GUTTER_GAP,
			chartBox
		);
		const values = labelGutter(drawn.map(valueLine), VALUE_PX, GUTTER_GAP, chartBox);
		return names === null || values === null ? null : Math.max(names, values);
	});
	const stacked = $derived(gutter === null);
	const leftRoom = $derived(gutter ?? RIGHT_ROOM);
	const innerRoom = $derived(Math.max(1, chartBox - leftRoom - RIGHT_ROOM));
	const pitch = $derived(
		rowPitch(innerRoom, stacked ? PITCH_MIN_STACKED : PITCH_MIN, PITCH_MAX)
	);

	const box = $derived(
		frame(chartBox, TOP + drawn.length * pitch + AXIS_ROOM, {
			top: TOP,
			right: RIGHT_ROOM,
			bottom: AXIS_ROOM,
			left: leftRoom
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

	/** Where a row's track sits, and where its label lines sit against it.
	 * Beside the plot the pair is centred on the track; above it the name leads
	 * and the track follows. */
	function trackY(rowTop: number): number {
		return stacked ? rowTop + STACK_TRACK_Y : rowTop + pitch / 2;
	}

	/** Whole units only, and `<1` where a real measurement rounds away. */
	function reading(measure: SwapMeasure, value: number | null): string {
		if (value === null) return 'nothing recorded';
		const whole = Math.round(value);
		const short = whole === 0 && value > 0;
		if (measure.unit === 'seconds') return short ? '<1 s' : `${whole} s`;
		if (measure.unit === 'words') return short ? '<1 word' : `${whole} words`;
		if (measure.unit === 'percent') return short ? '<1%' : `${whole}%`;
		if (measure.unit === 'tokens-a-second') {
			return short ? '<1 token a second' : `${whole} tokens a second`;
		}
		return short ? '<1 in 100' : `${whole} in 100`;
	}

	function moved(measure: SwapMeasure): string {
		const change = pct(measure) - 100;
		if (change === 0) return 'no change';
		return change > 0 ? `up ${change}%` : `down ${Math.abs(change)}%`;
	}

	/** Which side of the boundary never recorded this measure, in words. */
	function missing(measure: SwapMeasure): string {
		if (measure.before === null && measure.after === null) return 'neither model recorded it';
		if (measure.before === null) return `${swap.before.model} recorded none`;
		if (measure.after === null) return `${swap.after.model} has recorded none`;
		return `${swap.before.model} measured none`;
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
		`${swap.measures.length} measures either side of the day the model changed, each against its own value on ${swap.before.model}. ` +
			`${swap.before.model} wrote ${swap.before.articles} articles to ${swap.before.to}; ${swap.after.model} has written ${swap.after.articles} since ${swap.after.from}. ` +
			swap.measures
				.map((measure) =>
					measure.ratio === null
						? `${measure.label}: nothing to compare, ${missing(measure)}.`
						: sentence(measure)
				)
				.join(' ')
	);
</script>

<div
	class="plot"
	data-model-swap-plot
	data-swap-at={swap.at}
	data-swap-rows={drawn.length}
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
			data-swap-layout={stacked ? 'stacked' : 'beside'}
			data-swap-frame={box.width}
			data-swap-plot={round(box.innerWidth)}
			data-swap-pitch={pitch}
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
				{@const top = box.top + index * pitch}
				{@const y = trackY(top)}
				<g
					data-swap-row={measure.label}
					data-swap-pct={pct(measure)}
					data-swap-before={Math.round(measure.before as number)}
					data-swap-after={Math.round(measure.after as number)}
					data-movement={change(measure).toFixed(4)}
					data-polarity={measure.polarity}
					data-movement-verdict={verdict(measure)}
				>
					<title>{sentence(measure)}</title>
					<text
						x={stacked ? box.left : box.left - GUTTER_GAP}
						y={stacked ? top + STACK_NAME_Y : y + 3}
						text-anchor={stacked ? 'start' : 'end'}
						fill="var(--color-text)"
						font-size={NAME_PX}
						data-swap-cell="name"
					>
						{measure.label}
					</text>
					<text
						x={stacked ? box.left : box.left - GUTTER_GAP}
						y={stacked ? top + STACK_VALUE_Y : y + 16}
						text-anchor={stacked ? 'start' : 'end'}
						fill="var(--color-text-tertiary)"
						font-size={VALUE_PX}
						data-swap-cell="values"
					>
						{valueLine(measure)}
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
			{#each unmeasured as measure, index (measure.label)}{index > 0
					? '; '
					: ''}{measure.label} - {missing(measure)}{/each}. Nothing is drawn for those: a
			measure one side never wrote down is not a comparison.
		</p>
	{/if}
	{#if greyed.length > 0}
		<p class="mt-2 text-[0.75rem] text-text-tertiary" data-swap-no-direction>
			{#each greyed as measure, index (measure.label)}{index > 0 ? ', ' : ''}{measure.label}{/each}
			{greyed.length === 1 ? 'is drawn' : 'are drawn'} grey: nobody has agreed which way is the
			better way, so the row says how far it moved and stops there. The two token rates are set
			by the runner a shard landed on as much as by the model - one committed run read the prompt
			4.35 times faster on its fastest shard than on its slowest.
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
