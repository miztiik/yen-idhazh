<script lang="ts">
	/** The pairs a person marked apart, and the room the merge line has left.
	 *
	 * One horizontal score axis fixed at the band the line may take, a rule at
	 * the line the newest day was built with, and one dot at the highest-scoring
	 * pair somebody marked as two different stories.
	 *
	 * **The margin is the panel.** It is the distance between the rule and the
	 * dot, and it is the whole safety case for fitting the line at all. A
	 * negative margin - the dot to the RIGHT of the rule - means the line would
	 * merge two stories a person read as two, and it is drawn exactly where the
	 * arithmetic puts it. Clamping it to the rule would draw a panel that never
	 * shows the state it exists for.
	 *
	 * **Only the closest call is on the axis.** The other pairs marked apart are
	 * in a shut table underneath. What that costs the reader is the spread of
	 * misses; buying it back would mean overlapping dots on one axis nobody can
	 * read.
	 */
	import { chartWidth, frame, linearAxis, observeWidth, tickAnchor } from '$lib/charts/frame';
	import Panel from '$lib/components/Panel.svelte';
	import {
		holdoutMargin,
		holdoutNote,
		holdoutState,
		marginDistance,
		skipNote,
		weightsNote,
		type HoldoutMark,
		type HoldoutSkip,
		type ScoreWeights
	} from '$lib/console/holdout';

	let {
		marks,
		agreed,
		skipped,
		marked,
		applied,
		fitted,
		weights,
		band,
		height,
		width
	}: {
		/** The marks that set a floor - every pair read as two different stories.
		 * The pairs read as one story reach the page as `agreed` and no further:
		 * they set no floor, so two addresses and two headlines a row of them would
		 * be weight in a prerendered document for nothing the panel draws. */
		marks: HoldoutMark[];
		/** How many were read as one story. */
		agreed: number;
		skipped: HoldoutSkip[];
		/** How many rows the file holds, scored or not. */
		marked: number;
		/** The line the newest day was built with. */
		applied: number;
		/** False where no day has fitted a line yet. */
		fitted: boolean;
		weights: ScoreWeights;
		/** The whole span a fitted line may take, off config and never off data. */
		band: [number, number];
		height: number;
		width: number;
	} = $props();

	let measured = $state<number | null>(null);

	const outcome = $derived(holdoutMargin(applied, marks));
	// Not `state`: Svelte reads `$state` as a store access on a local of that
	// name, so the rune below stops compiling.
	const reading = $derived(holdoutState(outcome, fitted));
	const apart = $derived([...marks].sort((left, right) => right.score - left.score));
	const skips = $derived(skipNote(skipped));

	const box = $derived(frame(chartWidth(measured, width), height));
	// The domain is the two knobs, so rounding it outward would move every mark
	// to buy a tick label that reads the same either way.
	const xAxis = $derived(linearAxis(band, [box.left, box.right], { zero: false, nice: false }));

	/** True where the closest pair scores outside the axis.
	 *
	 * The axis is the span a fitted LINE may take, and a hand mark is not a line -
	 * two articles about nothing in common score well below 0.88. Widening the
	 * axis to fit a mark would shrink the part of it the margin lives in, which is
	 * the one part that has to stay readable. So the dot is pinned to the edge and
	 * the panel says it is pinned; the figure under it is always the real score.
	 */
	const pinned = $derived(
		outcome.closest !== null &&
			(outcome.closest.score < band[0] || outcome.closest.score > band[1])
	);

	const dotX = $derived(
		outcome.closest === null
			? null
			: Math.min(box.right - 5, Math.max(box.left + 5, xAxis.scale(outcome.closest.score)))
	);

	const ruleX = $derived(xAxis.scale(applied));
	/** The one row of marks, down the middle of the plot. */
	const markY = $derived(Math.round((box.top + box.bottom) / 2));
	const violated = $derived(reading === 'violation');

	function reads(value: number): string {
		return value.toFixed(3);
	}
</script>

<Panel
	title="The pairs a person marked apart"
	note="Every pair somebody read as two different stories sets a floor the merge line has to stay above. The dot is the closest call; the rule is the line."
>
	<div
		data-holdout
		data-holdout-state={reading}
		data-holdout-domain={`${band[0]},${band[1]}`}
		data-holdout-margin={outcome.margin === null ? '' : marginDistance(outcome.margin)}
		data-holdout-violations={outcome.violations}
	>
		<p class="headline" data-holdout-headline>
			{#if outcome.margin === null}
				<span class="figure" data-holdout-figure>-</span>
				<span class="words">of room, because nothing is marked yet</span>
			{:else}
				<span class="figure" data-holdout-figure>{marginDistance(outcome.margin)}</span>
				<span class="words"
					>{violated
						? 'below the closest pair a person marked as two stories'
						: 'of room above the closest pair a person marked as two stories'}</span
				>
			{/if}
		</p>

		<div use:observeWidth={(next) => (measured = next)}>
			<svg
				class="block max-w-full overflow-visible"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				aria-label="Where the merge line sits against the pairs a person marked as two stories"
			>
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

				{#if dotX !== null && outcome.closest !== null}
					<!-- The distance between the two, drawn as the distance it is. On a
					     violation it runs backwards, which is what a negative margin
					     looks like and is the point. -->
					<line
						x1={ruleX}
						x2={dotX}
						y1={markY}
						y2={markY}
						stroke="var(--color-text-tertiary)"
						stroke-width="2"
						data-holdout-span
					/>
				{/if}

				<!-- The line is a setting and not a fault, so it is the neutral rule
				     and never a red one. It is the only vertical rule on the plot. -->
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

				{#if dotX !== null && outcome.closest !== null}
					<circle
						cx={dotX}
						cy={markY}
						r="5"
						fill={violated ? 'var(--fill-low)' : 'var(--chart-4)'}
						stroke="var(--color-surface)"
						stroke-width="1.5"
						stroke-dasharray={pinned ? '2 2' : undefined}
						data-holdout-dot={outcome.closest.score.toFixed(4)}
						data-holdout-pinned={pinned ? 'true' : undefined}
					>
						<title
							>{outcome.closest.leftTitle} against {outcome.closest.rightTitle}, scoring {outcome.closest.score.toFixed(
								4
							)}</title
						>
					</circle>
					<text
						x={dotX}
						y={markY + 22}
						text-anchor="middle"
						fill="var(--color-text-secondary)"
						font-size="10"
						data-holdout-dot-label
					>
						{outcome.closest.score.toFixed(4)}
					</text>
				{/if}

				{#each xAxis.ticks as tick, at (tick)}
					<text
						x={xAxis.scale(tick)}
						y={box.bottom + 12}
						text-anchor={tickAnchor(at, xAxis.ticks.length)}
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-tick="x"
					>
						{reads(tick)}
					</text>
				{/each}
			</svg>
		</div>

		<p class="reading" data-holdout-note>{holdoutNote(outcome, reading, marked, applied)}</p>
		{#if pinned && outcome.closest !== null}
			<p class="under" data-holdout-pinned-note>
				That pair scores {outcome.closest.score.toFixed(4)}, which is off this scale. The scale is
				the span a fitted line may take, so the dot is pinned to the edge and the figure beside it
				is the score itself.
			</p>
		{/if}
		<p class="under" data-holdout-weights>{weightsNote(weights)}</p>
		{#if skips !== null}
			<p class="under" data-holdout-skips={skipped.length}>{skips}</p>
		{/if}

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
					{agreed} more marked pairs were read as one story. They set no floor, so they are counted
					here and not listed.
				</p>
			</details>
		{/if}
	</div>
</Panel>

<style>
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
