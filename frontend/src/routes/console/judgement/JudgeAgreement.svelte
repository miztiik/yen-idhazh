<script lang="ts">
	/** Whether the judge agrees with itself, day by day, against the two limits
	 * that hold a run.
	 *
	 * **This is the only quality reading on the judge that needs no second
	 * model.** Every pair is read twice, once in each order with the two
	 * summaries swapped, and a pair whose two readings differ is a fact about
	 * the judge rather than about the pair.
	 *
	 * Two rates, one axis. Both are a share of the same denominator, so a reader
	 * comparing them is comparing like with like; two panels at two scales would
	 * invite the comparison and make it wrong.
	 *
	 * **The axis is the two knobs and never the data.** Neither rate can reach 1
	 * without the run holding first, so 0 to 1 would leave half the plot in a
	 * region the data cannot enter. Fitted to the data, a healthy two percent
	 * would fill the panel and say the judge is in trouble.
	 */
	import {
		chartWidth,
		dayColumns,
		dayTicks,
		frame,
		linearAxis,
		observeWidth
	} from '$lib/charts/frame';
	import { pointerReadout, readoutMarks, readoutOf } from '$lib/charts/readout';
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { dayMonth, plural } from '$lib/format';
	import {
		agreementCorridor,
		rateWithDenominator,
		type AgreementLimits,
		type JudgeDay
	} from '$lib/console/merge-line';
	import { countDays, nameSpan } from '$lib/console/span-words';

	let {
		days,
		limits,
		viewport,
		height,
		width,
		tickDensity,
		readoutMaxShare,
		attemptsFloor
	}: {
		days: JudgeDay[];
		limits: AgreementLimits;
		viewport: TimeWindow;
		height: number;
		width: number;
		tickDensity: number;
		readoutMaxShare: number;
		/** `console.min_attempts_for_rate`. Under it a share is not a measurement. */
		attemptsFloor: number;
	} = $props();

	let measured = $state<number | null>(null);
	let selected = $state<number | null>(null);

	const windowDays = $derived(daysBetween(viewport.start, viewport.end));
	const drawn = $derived(
		days.filter((day) => day.date >= viewport.start && day.date <= viewport.end)
	);
	/** Only the days a shard actually read something. A day with nothing judged has
	 * no rate, and a zero on the line would say the judge agreed with itself
	 * perfectly on a day it was never asked. */
	const read = $derived(drawn.filter((day) => day.pairsJudged > 0));
	const corridor = $derived(agreementCorridor(limits));

	const box = $derived(frame(chartWidth(measured, width), height));
	const yAxis = $derived(
		linearAxis(corridor, [box.bottom, box.top], { tickCount: 4, zero: false, nice: false })
	);
	const columnsX = $derived(dayColumns(read.length, box, 2));
	const ticks = $derived(
		dayTicks(
			read.map((day) => day.date),
			{ density: tickDensity, columns: columnsX }
		)
	);

	function px(value: number): number {
		return Math.round(value * 10) / 10;
	}

	function percent(share: number): string {
		return `${Math.round(share * 100)}%`;
	}

	/** One day's two readings in words: what the strip prints at that day, and
	 * the name its two dots carry, written together so the two never differ.
	 *
	 * A share needs `attemptsFloor` pairs behind it, the floor the sentence under
	 * the strip keeps through `rateWithDenominator`, so the strip and the
	 * sentence agree about when a share is a measurement. Under it the day prints
	 * its counts and no share, which are the counts that sentence points at.
	 * "Could not tell" is counted against the pairs whose two readings agreed,
	 * the only pairs its share is taken over. The words are Reader's.
	 */
	function readingsOf(day: JudgeDay): { disagreed: string; unclear: string; name: string } {
		const date = dayMonth(day.date);
		const shares = {
			disagreed: rateWithDenominator(
				day.disagreementRate * day.pairsJudged,
				day.pairsJudged,
				attemptsFloor
			),
			unclear: rateWithDenominator(day.unclearRate * day.pairsJudged, day.pairsJudged, attemptsFloor)
		};
		if (shares.disagreed !== null && shares.unclear !== null) {
			return {
				disagreed: shares.disagreed,
				unclear: shares.unclear,
				name: `${date}: ${shares.disagreed} disagreed with the second reading, and ${percent(day.unclearRate)} could not tell.`
			};
		}
		const disagreedCount = Math.round(day.disagreementRate * day.pairsJudged);
		const agreedCount = day.pairsJudged - disagreedCount;
		const disagreedWords = `${disagreedCount} of ${plural(day.pairsJudged, 'pair', 'pairs')}`;
		if (agreedCount === 0) {
			const notCounted = 'not counted, no pair agreed';
			return {
				disagreed: disagreedWords,
				unclear: notCounted,
				name: `${date}: ${disagreedWords} disagreed with the second reading. Could not tell: ${notCounted}.`
			};
		}
		const unclearWords = `${Math.round(day.unclearRate * agreedCount)} of the ${agreedCount} that agreed`;
		return {
			disagreed: disagreedWords,
			unclear: unclearWords,
			name: `${date}: ${disagreedWords} disagreed with the second reading, and ${unclearWords} could not tell.`
		};
	}

	const marks = $derived(
		read.map((day, index) => ({
			date: day.date,
			x: px(columnsX[index]),
			disagreeY: px(yAxis.scale(Math.min(day.disagreementRate, corridor[1]))),
			unclearY: px(yAxis.scale(Math.min(day.unclearRate, corridor[1]))),
			day,
			said: readingsOf(day)
		}))
	);
	const disagreePath = $derived(marks.map((mark) => `${mark.x},${mark.disagreeY}`).join(' '));
	const unclearPath = $derived(marks.map((mark) => `${mark.x},${mark.unclearY}`).join(' '));

	/** How many pairs the window read altogether. The denominator every sentence
	 * on this panel prints beside its share. */
	const judged = $derived(read.reduce((total, day) => total + day.pairsJudged, 0));
	const disagreed = $derived(
		read.reduce((total, day) => total + day.disagreementRate * day.pairsJudged, 0)
	);
	const unclear = $derived(
		read.reduce((total, day) => total + day.unclearRate * day.pairsJudged, 0)
	);
	const disagreeShare = $derived(rateWithDenominator(disagreed, judged, attemptsFloor));
	const unclearShare = $derived(rateWithDenominator(unclear, judged, attemptsFloor));
	const heldByJudge = $derived(
		drawn.filter((day) => day.heldReason === 'judge_unstable' || day.heldReason === 'judge_uncertain')
			.length
	);

	/** A day's two readings, as its strip prints them and as its marks name them:
	 * every word of the sentence is in the strip at that day. */
	const readout = $derived(
		readoutOf({
			type: 'dateSeries',
			columns: marks.map((mark) => dayMonth(mark.day.date)),
			series: [
				{
					label: 'Disagreed with the second reading',
					swatch: 'var(--chart-1)',
					values: marks.map((mark) => mark.day.disagreementRate),
					format: (_: number, column: number) => marks[column].said.disagreed
				},
				{
					label: 'Could not tell',
					swatch: 'var(--chart-3)',
					values: marks.map((mark) => mark.day.unclearRate),
					format: (_: number, column: number) => marks[column].said.unclear
				}
			],
			notMeasured: 'No pair was read twice on this day',
			resting: 'last'
		})
	);
	const count = $derived(readout.columns.length);
</script>

<Panel
	title="Whether the judge agrees with itself"
	note="Every pair is read twice, with the two summaries swapped. One line is how often the two readings differed. The other is how often the reading could not tell. The two rules are where a run stops moving the line."
>
	<div
		data-windowed="judge-agreement"
		data-window-days={windowDays}
		data-agreement-domain={`${corridor[0]},${corridor[1]}`}
		data-agreement-days={read.length}
		data-readout-columns={count > 0 ? count : undefined}
		data-readout-none={count > 0
			? undefined
			: 'no pair has been read twice, so there is no column to read; agreed with Susan'}
	>
		<div use:observeWidth={(next) => (measured = next)}>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<svg
				class="block max-w-full overflow-visible focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				tabindex="0"
				aria-label={windowDays === 1
					? `How often the judge disagreed with its own second reading, in ${nameSpan(windowDays)}`
					: 'How often the judge disagreed with its own second reading, a day'}
				use:pointerReadout={{
					marks: readoutMarks(marks.map((mark) => mark.x)),
					width: box.width,
					onSelect: (index) => (selected = index)
				}}
			>
				<line x1={box.left} x2={box.right} y1={box.bottom} y2={box.bottom} stroke="var(--color-rule)" />
				<line x1={box.left} x2={box.left} y1={box.top} y2={box.bottom} stroke="var(--color-rule)" />

				{#each yAxis.ticks as tick (tick)}
					<text
						x={box.left - 6}
						y={yAxis.scale(tick)}
						dy="0.32em"
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-tick="y"
					>
						{percent(tick)}
					</text>
				{/each}

				<!-- The two limits, drawn whether or not a series is. They are what the
				     panel is about: a reader sees where the run stops rather than
				     subtracting one number from another. -->
				{#each [{ at: limits.disagreementMax, name: 'disagreement' }, { at: limits.unclearMax, name: 'unclear' }] as rule (rule.name)}
					<line
						x1={box.left}
						x2={box.right}
						y1={yAxis.scale(rule.at)}
						y2={yAxis.scale(rule.at)}
						stroke="var(--color-text-tertiary)"
						stroke-dasharray="3 3"
						data-agreement-marker={rule.name}
						data-agreement-marker-at={rule.at}
					/>
					<text
						x={box.right}
						y={yAxis.scale(rule.at) - 4}
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-agreement-marker-label={rule.name}
					>
						{rule.name === 'disagreement'
							? `${percent(rule.at)} - the run stops moving the line`
							: `${percent(rule.at)} - the run stops here too`}
					</text>
				{/each}

				{#if marks.length > 1}
					<polyline
						points={disagreePath}
						fill="none"
						stroke="var(--chart-1)"
						stroke-width="2"
						data-agreement-series="disagreement"
					/>
					<polyline
						points={unclearPath}
						fill="none"
						stroke="var(--chart-3)"
						stroke-width="2"
						data-agreement-series="unclear"
					/>
				{/if}

				{#each marks as mark (mark.date)}
					<g
						role="img"
						aria-label={mark.said.name}
						data-agreement-day={mark.date}
						data-agreement-judged={mark.day.pairsJudged}
					>
						<circle cx={mark.x} cy={mark.disagreeY} r="2.5" fill="var(--chart-1)" />
						<circle cx={mark.x} cy={mark.unclearY} r="2.5" fill="var(--chart-3)" />
					</g>
				{/each}

				{#each ticks as tick (tick.index)}
					<text
						x={px(columnsX[tick.index])}
						y={box.bottom + 16}
						text-anchor={tick.anchor}
						fill="var(--color-text-tertiary)"
						font-size="10"
					>
						{dayMonth(tick.date)}
					</text>
				{/each}
			</svg>
		</div>

		<ChartReadout
			{readout}
			at={selected}
			name="judge-agreement"
			maxShare={readoutMaxShare}
			restingNote=", the newest day"
		/>

		<p class="agreement-note">
			{#if read.length === 0}
				<span data-agreement-state="none"
					>No pair was read twice in {nameSpan(windowDays)}, so there is nothing to compare.</span
				>
			{:else if disagreeShare === null}
				<span data-agreement-state="filling"
					>{plural(judged, 'pair', 'pairs')}
					{judged === 1 ? 'was' : 'were'} read twice in {nameSpan(windowDays)}. That is too few
					to report a share, so the counts are above.</span
				>
			{:else if heldByJudge > 0}
				<span data-agreement-state="past-mark"
					>The two readings disagreed on {disagreeShare} in {nameSpan(windowDays)}. No line was
					fitted on {heldByJudge} of {countDays(windowDays)}, because a rate was past its mark on
					{heldByJudge === 1 ? 'that day' : 'those days'}.</span
				>
			{:else}
				<span data-agreement-state="inside"
					>In {nameSpan(windowDays)}, {disagreeShare} disagreed with their own second reading, and
					{unclearShare} could not tell. Both rates are inside the marks.</span
				>
			{/if}
		</p>
	</div>
</Panel>

<style>
	.agreement-note {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
