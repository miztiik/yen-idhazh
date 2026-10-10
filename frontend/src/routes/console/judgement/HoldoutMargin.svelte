<script lang="ts">
	/** The pairs a person marked apart, and the room the merge line has left.
	 *
	 * One horizontal score axis, a rule at the line the newest day was built
	 * with, every pair somebody read as two different stories on it, and the
	 * pairs they read as one story on a range strip below.
	 *
	 * **The margin is the panel.** It is the distance between the rule and the
	 * closest dot, and it is the whole safety case for fitting the line at all. A
	 * negative margin - a dot to the RIGHT of the rule - means the line would
	 * merge two stories a person read as two, and it is drawn exactly where the
	 * arithmetic puts it. Clamping it to the rule would draw a panel that never
	 * shows the state it exists for.
	 *
	 * **The axis is the line and one day's legal fall, not the band.** On the
	 * band the margin drew at 5.8 px of a 1033 px plot and the dot covered the
	 * rule it was measured against, so a reader could not see which side of it
	 * the dot was on. The band is already the axis of `MergeLinePlot` further up
	 * this route.
	 *
	 * **The tinted zone is what tomorrow can fold.** A mark inside it clears the
	 * line today and would not after one day's legal fall, which is the fact the
	 * figure alone cannot carry.
	 *
	 * **Every mark reads into a record strip under the plot.** A dot is one pair,
	 * a chip is the pairs off one edge of the scale, and the strip below is the
	 * pairs read as one story. None of them shares a column with another, so a
	 * pointer, a tap or an arrow key picks one at a time, left to right.
	 */
	import { chartWidth, frame, linearAxis, observeWidth, tickAnchor } from '$lib/charts/frame';
	import { factsOf, markReadout, recordsOf, type ReadoutFacts } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { shortDate } from '$lib/format';
	import {
		agreedNote,
		belowLine,
		holdoutDomain,
		holdoutMargin,
		holdoutNote,
		holdoutReach,
		holdoutState,
		holdoutTone,
		marginDistance,
		markedApart,
		reachNote,
		reachZone,
		scoreRange,
		scoredNote,
		skipNote,
		weightsNote,
		type HoldoutMark,
		type HoldoutSkip,
		type ScoredHoldout,
		type ScoreWeights
	} from '$lib/console/holdout';

	let {
		marks: inputMarks,
		evidence = [],
		agreedScores: inputAgreedScores,
		skipped,
		marked,
		applied,
		maxDownStep,
		fitted,
		weights,
		scored,
		height,
		width,
		readoutMaxShare
	}: {
		/** The marks that set a floor - every pair read as two different stories.
		 * The pairs read as one story reach the page as `agreedScores` and no
		 * further: they set no floor, so two addresses and two headlines a row of
		 * them would be weight in a prerendered document for nothing the panel
		 * draws. */
		marks: HoldoutMark[] | null;
		evidence?: string[];
		/** Every score a person read as one story, and nothing else about them.
		 * 196 numbers is 1.7 KB; the same rows with their addresses and headlines
		 * are 88 KB, for a strip that draws three of them. */
		agreedScores: number[] | null;
		skipped: HoldoutSkip[];
		/** How many rows the file holds, scored or not. */
		marked: number;
		/** The line the newest day was built with. */
		applied: number;
		/** The furthest the line may fall in one day, off config. The unit this
		 * whole panel is measured in - the axis, the zone and the sentence. */
		maxDownStep: number;
		/** False where no day has fitted a line yet. */
		fitted: boolean;
		weights: ScoreWeights;
		/** The last committed reading of the line against these marks, or null
		 * where nobody has taken one. A person types the verb that writes it, so
		 * null is an ordinary state and the panel says so. */
		scored: ScoredHoldout | null;
		height: number;
		width: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare: number;
	} = $props();

	/** How far under a dot its own label sits, and how far under that the row
	 * label of the strip sits. Laid out from the top of the plot so the panel is
	 * the same height whatever it has to draw. */
	const MARK_ROW = 56;
	const STRIP_ROW = 130;

	let measured = $state<number | null>(null);
	const marks = $derived(inputMarks ?? []);
	const agreedScores = $derived(inputAgreedScores ?? []);
	const absent = $derived(inputMarks === null || inputAgreedScores === null);

	const outcome = $derived(holdoutMargin(applied, marks));
	// Not `state`: Svelte reads `$state` as an auto-subscription to a local of
	// that name, so the rune below stops compiling.
	const reading = $derived(holdoutState(outcome, fitted));
	const apart = $derived(markedApart(marks));
	const reach = $derived(holdoutReach(applied, maxDownStep, marks));
	const skips = $derived(skipNote(skipped));
	const agreedAt = $derived(scoreRange(agreedScores));
	const agreedBelow = $derived(belowLine(agreedScores, applied));
	const apartAt = $derived(scoreRange(apart.map((mark) => mark.score)));

	const box = $derived(frame(chartWidth(measured, width), height));
	const domain = $derived(holdoutDomain(applied, maxDownStep));
	const zone = $derived(reachZone(applied, maxDownStep));
	// The domain is the line and one knob, so rounding it outward would move
	// every mark to buy a tick label that reads the same either way.
	const xAxis = $derived(linearAxis(domain, [box.left, box.right], { zero: false, nice: false }));

	/** A score as a position, clamped to the plot.
	 *
	 * The axis is a window a few days' legal fall wide, and a hand mark is not a
	 * line - two articles about nothing in common score nowhere near it. Widening
	 * the axis to fit one would shrink the part the margin lives in, which is the
	 * one part that has to stay readable. So a mark outside is counted at the edge
	 * it left and its score is printed in words.
	 */
	function at(score: number): number {
		return Math.min(box.right, Math.max(box.left, xAxis.scale(score)));
	}

	function outside(score: number): boolean {
		return score < domain[0] || score > domain[1];
	}

	const drawn = $derived(apart.filter((mark) => !outside(mark.score)));
	const offLow = $derived(apart.filter((mark) => mark.score < domain[0]));
	const offHigh = $derived(apart.filter((mark) => mark.score > domain[1]));
	/** True where any part of the one-story population reaches the scale. Where
	 * none of it does, a strip clamped to the edge is a zero-width line saying
	 * nothing, so the row carries a chip at that edge instead. */
	const agreedOnScale = $derived(
		agreedAt !== null && agreedAt.max >= domain[0] && agreedAt.min <= domain[1]
	);
	/** The two marks that carry a label: the closest call and the one with the
	 * most room. The rest read into the strip under the plot, because four
	 * strings inside one row of dots is four strings nobody reads. */
	const labelled = $derived(
		new Set([drawn[0]?.score, drawn[drawn.length - 1]?.score].filter((score) => score !== undefined))
	);

	const ruleX = $derived(xAxis.scale(applied));
	const markY = $derived(box.top + MARK_ROW);
	const stripY = $derived(box.top + STRIP_ROW);
	const violated = $derived(reading === 'violation');
	const tone = $derived(holdoutTone(reading, reach));

	function reads(value: number): string {
		return value.toFixed(3);
	}

	function offNote(off: HoldoutMark[], side: string): string {
		const scores = off.map((mark) => mark.score.toFixed(4)).join(', ');
		return (
			`${off.length} marked ${off.length === 1 ? 'pair scores' : 'pairs score'} ${side} this ` +
			`scale, at ${scores}. The scale is a window a few days' fall wide around the line, so a ` +
			'mark far from the line is off it rather than pinned to a place it is not.'
		);
	}

	/** How many marked pairs sit off one edge of the scale, as a chip's record
	 * names them. The reason a mark is off the scale is said under the plot. */
	function offCount(off: HoldoutMark[], side: string): string {
		return `${off.length} marked ${off.length === 1 ? 'pair scores' : 'pairs score'} ${side} this scale`;
	}

	function offScores(off: HoldoutMark[]): string {
		return off.map((mark) => mark.score.toFixed(4)).join(', ');
	}

	/** One thing a pointer, a tap or a key can land on, in reading order: the
	 * chip off the low edge, the dots left to right, the chip off the high edge,
	 * then the strip of pairs read as one story on the row below. */
	type HoldoutPoint =
		| { kind: 'dot'; key: string; mark: HoldoutMark }
		| { kind: 'off'; key: string; side: 'low' | 'high'; off: HoldoutMark[] }
		| { kind: 'agreed'; key: string };

	const points = $derived<HoldoutPoint[]>([
		...(offLow.length > 0 ? [{ kind: 'off' as const, key: 'off-low', side: 'low' as const, off: offLow }] : []),
		...[...drawn]
			.sort((left, right) => left.score - right.score)
			.map((mark) => ({ kind: 'dot' as const, key: `dot:${mark.leftTitle}|${mark.rightTitle}`, mark })),
		...(offHigh.length > 0
			? [{ kind: 'off' as const, key: 'off-high', side: 'high' as const, off: offHigh }]
			: []),
		...(agreedAt !== null ? [{ kind: 'agreed' as const, key: 'agreed' }] : [])
	]);
	/** Which point each mark is, so a mark carries the index its record sits at. */
	const pointAt = $derived(new Map(points.map((point, index) => [point.key, index])));

	/** What each mark says to a screen reader: the sentence its tooltip carried. */
	function pointName(point: HoldoutPoint): string {
		if (point.kind === 'dot') {
			return `${point.mark.leftTitle} against ${point.mark.rightTitle}, scoring ${point.mark.score.toFixed(4)}`;
		}
		if (point.kind === 'off') {
			return `${offCount(point.off, point.side === 'low' ? 'below' : 'above')}, at ${offScores(point.off)}`;
		}
		if (agreedAt === null) return '';
		return agreedOnScale
			? `${agreedScores.length} pairs read as one story, running ${agreedAt.min.toFixed(4)} to ${agreedAt.max.toFixed(4)}, middle ${agreedAt.median.toFixed(4)}`
			: `${agreedScores.length} pairs read as one story, all of them off this scale, running ${agreedAt.min.toFixed(4)} to ${agreedAt.max.toFixed(4)}`;
	}

	/** Each point's record: every word its name says, and what it means for the
	 * line. A panel with nothing marked still prints one record saying so. */
	const records = $derived.by((): ReadoutFacts[] => {
		const four = (value: number) => value.toFixed(4);
		const built = points.map((point) => {
			if (point.kind === 'dot') {
				return factsOf(
					`${point.mark.leftTitle} against ${point.mark.rightTitle}`,
					[
						{ label: 'Scoring', value: point.mark.score, format: four },
						{
							label: 'Against the line',
							value:
								point.mark.score >= applied
									? 'at or above it, so the line merges this pair'
									: 'below it, so the pair stays two stories'
						},
						{
							label: 'Marked',
							value: point.mark.markedOn === '' ? null : shortDate(point.mark.markedOn)
						}
					],
					'not recorded'
				);
			}
			if (point.kind === 'off') {
				return factsOf(
					offCount(point.off, point.side === 'low' ? 'below' : 'above'),
					[{ label: 'At', value: offScores(point.off) }],
					'not recorded'
				);
			}
			const range = agreedAt === null ? null : `${four(agreedAt.min)} to ${four(agreedAt.max)}`;
			return factsOf(
				agreedOnScale
					? `${agreedScores.length} pairs read as one story`
					: `${agreedScores.length} pairs read as one story, all of them off this scale`,
				[
					{ label: 'Running', value: range },
					...(agreedOnScale && agreedAt !== null
						? [{ label: 'Middle', value: agreedAt.median, format: four }]
						: []),
					{ label: 'Below the line', value: agreedBelow, format: String }
				],
				'not recorded'
			);
		});
		return built.length > 0
			? recordsOf(built)
			: [factsOf('No scored hand marks were returned, so there is no pair to read', [], 'not recorded')];
	});

	/** The point a pointer, a tap or a key has picked, or null for the first. */
	let picked = $state<number | null>(null);
</script>

<Panel
	id="holdout-margin"
	title="The pairs a person marked apart"
	note="Every pair somebody read as two different stories sets a floor the merge line has to stay above. The dots are those pairs, the rule is the line, and the tinted zone is as far as the line may fall in one day."
	{tone}
>
	<div
		data-holdout
		data-panel-question="How much room does the line leave above pairs a person marked apart?"
		data-model-rule="no"
		data-model-rule-name="holdout-margin"
		data-model-rule-none="the judge's record, not how summaries are written"
		data-holdout-state={absent ? 'missing' : reading}
		data-holdout-tone={tone}
		data-readout-records={absent ? undefined : records.length}
		data-readout-none={absent
			? 'the hand-marked pairs are unavailable, so there is no pair to read; agreed with Susan'
			: undefined}
		data-holdout-domain={`${domain[0].toFixed(4)},${domain[1].toFixed(4)}`}
		data-holdout-zone={`${zone[0].toFixed(4)},${zone[1].toFixed(4)}`}
		data-holdout-margin={outcome.margin === null ? '' : marginDistance(outcome.margin)}
		data-holdout-violations={outcome.violations}
		data-holdout-reach={`${reach.today},${reach.tomorrow},${reach.dayAfter}`}
	>
		<p class="comparison" data-comparison="Each hand-marked pair's score against the merge line.">
			Each hand-marked pair's score against the merge line.
		</p>
		{#each evidence as note}<p data-evidence-note>{note}</p>{/each}
		{#if absent}
			<p class="headline" data-empty="missing">
				<span class="figure" data-lede>The hand-marked pairs are unavailable.</span>
			</p>
		{:else}
		<p class="headline" data-holdout-headline>
			{#if outcome.margin === null}
				<span class="figure" data-lede data-holdout-figure>-</span>
				<span class="words">of room; no scored pairs marked apart were returned</span>
			{:else}
				<span class="figure" data-lede data-holdout-figure>{marginDistance(outcome.margin)}</span>
				<span class="words"
					>{violated
						? 'below the closest pair a person marked as two stories'
						: 'of room above the closest pair a person marked as two stories'}</span
				>
			{/if}
		</p>

		{#if apart.length > 0}
			<!-- The consequence, not the bare number. A distance says how much room
			     there is and never how fast it can be spent, and it can be spent in
			     one night. -->
			<p class="consequence" data-holdout-reach-note>
				{reachNote(reach, maxDownStep, apart.length)}
			</p>
		{/if}

		<div use:observeWidth={(next) => (measured = next)}>
			<!-- One tab stop for every mark, never one per dot: Left and Right step
			     them in reading order, Escape returns to the first. -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<svg
				data-chart-type="distribution"
				class="block max-w-full overflow-visible focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="group"
				tabindex="0"
				aria-label={`Where the merge line sits against the pairs a person marked as two stories. ${holdoutNote(outcome, reading, marked, applied)} ${agreedNote(agreedScores, applied)}`}
				use:markReadout={{
					count: points.length,
					walk: 'row',
					onSelect: (index) => (picked = index),
					selected: picked
				}}
			>
				<!-- The zone first, so every mark and both rules sit on top of it. A
				     mark inside it clears the line today and would not after one day's
				     legal fall. -->
				<rect
					x={at(zone[0])}
					y={box.top}
					width={Math.max(0, at(zone[1]) - at(zone[0]))}
					height={box.bottom - box.top}
					fill="var(--tint-warn)"
					data-holdout-zone-mark={`${zone[0].toFixed(4)}`}
				/>
				<line
					x1={at(zone[0])}
					x2={at(zone[0])}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--color-rule-strong)"
					data-holdout-zone-edge={zone[0].toFixed(4)}
				/>
				<text
					x={at(zone[0]) + 4}
					y={box.bottom - 6}
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-holdout-zone-label
				>
					one day's fall
				</text>

				<!-- The axis itself, so the panel draws a frame on a day it has
				     nothing to plot. A panel that shrinks to one sentence on a quiet
				     day is a panel an operator stops opening. -->
				<line
					x1={box.left}
					x2={box.right}
					y1={box.bottom}
					y2={box.bottom}
					stroke="var(--color-rule)"
				/>

				{#if outcome.closest !== null && !outside(outcome.closest.score)}
					<!-- The margin, drawn as the distance it is. On a violation it runs
					     backwards, which is what a negative margin looks like and is the
					     point. -->
					<line
						x1={ruleX}
						x2={at(outcome.closest.score)}
						y1={markY}
						y2={markY}
						stroke="var(--color-text-secondary)"
						stroke-width="2"
						data-holdout-span={marginDistance(outcome.margin ?? 0)}
					/>
					<text
						x={(ruleX + at(outcome.closest.score)) / 2}
						y={markY - 10}
						text-anchor="middle"
						fill="var(--color-text-secondary)"
						font-size="10"
						data-holdout-span-label
					>
						{marginDistance(outcome.margin ?? 0)}
					</text>
				{/if}

				<!-- The line is a setting and not a fault, so it is the neutral rule
				     and never a red one. It is the only full-height dashed rule. -->
				<line
					x1={ruleX}
					x2={ruleX}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--color-text-tertiary)"
					stroke-dasharray="3 3"
					data-holdout-rule={applied.toFixed(4)}
				/>
				<text
					x={ruleX}
					y={box.top + 10}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-holdout-rule-label
				>
					the line, {reads(applied)}
				</text>

				<text
					x={box.left}
					y={markY - 24}
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-holdout-row-label="apart"
				>
					{apartAt === null
						? 'No scored pairs marked two stories were returned'
						: `read as two stories: ${apartAt.min.toFixed(4)} to ${apartAt.max.toFixed(4)}`}
				</text>

				{#each drawn as mark (mark.leftTitle + mark.rightTitle)}
					{@const point = { kind: 'dot' as const, key: `dot:${mark.leftTitle}|${mark.rightTitle}`, mark }}
					<circle
						cx={at(mark.score)}
						cy={markY}
						r="5"
						fill={mark.score >= applied ? 'var(--fill-low)' : 'var(--chart-4)'}
						stroke={picked === pointAt.get(point.key) ? 'var(--color-text)' : 'var(--color-surface)'}
						stroke-width="1.5"
						role="img"
						aria-label={pointName(point)}
						data-readout-at={pointAt.get(point.key)}
						data-holdout-dot={mark.score.toFixed(4)}
						data-holdout-dot-side={mark.score >= applied ? 'wrong' : 'clear'}
					/>
					{#if labelled.has(mark.score)}
						<text
							x={at(mark.score)}
							y={markY + 20}
							text-anchor="middle"
							fill="var(--color-text-secondary)"
							font-size="10"
							data-holdout-dot-label={mark.score.toFixed(4)}
						>
							{mark.score.toFixed(4)}
						</text>
					{/if}
				{/each}

				{#each [{ off: offLow, x: box.left, side: 'low' }, { off: offHigh, x: box.right, side: 'high' }] as edge (edge.side)}
					{#if edge.off.length > 0}
						{@const point = {
							kind: 'off' as const,
							key: `off-${edge.side}`,
							side: edge.side as 'low' | 'high',
							off: edge.off
						}}
						<!-- A mark off the scale is counted at the edge it left, never
						     pinned to a place it is not. -->
						<rect
							x={edge.side === 'low' ? edge.x : edge.x - 4}
							y={markY - 7}
							width="4"
							height="14"
							fill="var(--chart-4)"
							role="img"
							aria-label={pointName(point)}
							data-readout-at={pointAt.get(point.key)}
							data-holdout-offscale={edge.side}
							data-holdout-offscale-count={edge.off.length}
						/>
					{/if}
				{/each}

				<text
					x={box.left}
					y={stripY - 14}
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-holdout-strip-label
				>
					{agreedAt === null
						? 'No scored pairs marked one story were returned'
						: `read as one story: ${agreedAt.min.toFixed(4)} to ${agreedAt.max.toFixed(4)}, middle ${agreedAt.median.toFixed(4)}, ${agreedBelow} below the line`}
				</text>

				{#if agreedAt !== null && agreedOnScale}
					<!-- The shape `VerdictSplit` ships two of, on this panel's axis: the
					     population the line is supposed to fold, so a reader sees both
					     costs of the number rather than one. -->
					<line
						x1={at(agreedAt.min)}
						x2={at(agreedAt.max)}
						y1={stripY}
						y2={stripY}
						stroke="var(--chart-1)"
						stroke-width="6"
						stroke-linecap="butt"
						role="img"
						aria-label={pointName({ kind: 'agreed', key: 'agreed' })}
						data-readout-at={pointAt.get('agreed')}
						data-holdout-strip={`${agreedAt.min.toFixed(4)},${agreedAt.max.toFixed(4)}`}
						data-holdout-strip-below={agreedBelow}
					/>
					{#if !outside(agreedAt.median)}
						<circle
							cx={at(agreedAt.median)}
							cy={stripY}
							r="3"
							fill="var(--color-surface)"
							data-holdout-strip-median={agreedAt.median.toFixed(4)}
						/>
					{/if}
				{:else if agreedAt !== null}
					<!-- Every one of them is off this scale, which the canary tree is.
					     A strip clamped to the edge would be a zero-width line saying
					     nothing; a chip at the edge says which way they went. -->
					<rect
						x={agreedAt.max < domain[0] ? box.left : box.right - 4}
						y={stripY - 3}
						width="4"
						height="6"
						fill="var(--chart-1)"
						role="img"
						aria-label={pointName({ kind: 'agreed', key: 'agreed' })}
						data-readout-at={pointAt.get('agreed')}
						data-holdout-strip-offscale={agreedAt.max < domain[0] ? 'low' : 'high'}
					/>
				{/if}

				{#each xAxis.ticks as tick, index (tick)}
					<text
						x={xAxis.scale(tick)}
						y={box.bottom + 12}
						text-anchor={tickAnchor(index, xAxis.ticks.length)}
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-tick="x"
					>
						{reads(tick)}
					</text>
				{/each}
			</svg>
		</div>

		<!-- Under the plot: the one mark a reader is on, every word its old tooltip
		     said and what it means for the line. -->
		<ChartReadout
			readout={records[picked ?? 0] ?? null}
			resting={picked === null}
			name="holdout"
			maxShare={readoutMaxShare}
			restingNote=", the first mark"
			hint="Point at a dot, an edge chip or the strip below them to read it. Left and Right step through them, Escape returns to the first."
		/>

		<p class="reading" data-holdout-note>
			{marked === 0 ? 'No hand marks were returned. This does not show whether a person has marked a pair.' : holdoutNote(outcome, reading, marked, applied)}
		</p>
		<p class="reading" data-holdout-agreed={agreedScores.length}>
			{agreedNote(agreedScores, applied)}
		</p>
		{#each [{ off: offLow, side: 'below' }, { off: offHigh, side: 'above' }] as edge (edge.side)}
			{#if edge.off.length > 0}
				<p class="under" data-holdout-offscale-note={edge.side}>{offNote(edge.off, edge.side)}</p>
			{/if}
		{/each}
		<p class="under" data-holdout-weights>{weightsNote(weights)}</p>
		{#if apart.length > 0}
			<details class="detail" data-holdout-table>
				<summary>Every pair a person marked as two stories</summary>
				<table>
					<thead>
						<tr>
							<th scope="col">Score</th>
							<th scope="col">One headline</th>
							<th scope="col">The other</th>
							<th scope="col">Marked</th>
						</tr>
					</thead>
					<tbody>
						{#each apart as mark (mark.leftTitle + mark.rightTitle)}
							<tr data-holdout-row={mark.score.toFixed(4)}>
								<th scope="row">{mark.score.toFixed(4)}</th>
								<td>{mark.leftTitle}</td>
								<td>{mark.rightTitle}</td>
								<td>{mark.markedOn}</td>
							</tr>
						{/each}
					</tbody>
				</table>
				<p class="under">
					{agreedScores.length} more marked pairs were read as one story. They set no floor, so
					they are drawn as the strip above and not listed.
				</p>
			</details>
		{/if}
		{/if}
		<p class="under" data-holdout-scored={scored === null ? 'none' : scored.date}>
			{scoredNote(scored)}
		</p>
		{#if skips !== null}
			<p class="under" data-holdout-skips={skipped.length}>{skips}</p>
		{/if}
	</div>
</Panel>

<style>
	.comparison {
		margin: 0 0 var(--space-3);
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
	}
	.headline {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2);
		margin: 0 0 var(--space-3);
	}

	.figure {
		font-size: var(--text-2xl);
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
	}

	.words {
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	/* The consequence sits between the figure and the chart, at reading weight
	   rather than the caveat weight below: it is what the figure means, not a
	   footnote to it. */
	.consequence {
		margin: 0 0 var(--space-3);
		font-size: var(--text-base);
		line-height: var(--leading-base);
		color: var(--color-text);
	}

	.reading {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.under {
		margin: var(--space-2) 0 0;
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	/* Shut it drops its border and background, the way the verdict table does,
	   so the attention cost of a closed detail is zero. */
	.detail {
		margin: var(--space-4) 0 0;
		font-size: var(--text-sm);
	}

	table {
		width: 100%;
		border-collapse: collapse;
		margin-top: var(--space-2);
	}

	th,
	td {
		padding: var(--space-2);
		text-align: left;
		border-bottom: 1px solid var(--color-rule);
		font-weight: 400;
		color: var(--color-text-secondary);
	}

	th[scope='col'] {
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
	}

	th[scope='row'] {
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
		white-space: nowrap;
	}
</style>
