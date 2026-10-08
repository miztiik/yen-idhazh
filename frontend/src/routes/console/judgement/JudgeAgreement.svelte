<script lang="ts">
	/** Whether the judge agrees with itself, day by day, against the two limits
	 * that hold a run.
	 *
	 * **This is the only quality reading on the judge that needs no second
	 * model.** Every pair is read twice, once in each order with the two
	 * summaries swapped, and a pair whose two readings differ is a fact about
	 * the judge rather than about the pair.
	 *
	 * Two rates, one axis, each against its own mark. They are shares of
	 * different pairs: "disagreed" of every pair read twice, "could not tell" of
	 * the pairs whose two readings agreed. So every figure names the pairs it was
	 * taken over, and two panels at two scales would still invite a comparison
	 * and make it wrong.
	 *
	 * **A rate under the floor gets no dot.** The floor counts the pairs each
	 * share is taken over, so a day can keep one dot and lose the other. That
	 * rate's line breaks there rather than drawing a value through the day, and
	 * the day keeps its column, so the strip still prints its counts. It is the
	 * failure chart's rule for the same floor.
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
		describeUnclear,
		rateWithDenominator,
		wholePercent,
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
	 * Each share is taken over its own pairs, and the floor counts those pairs:
	 * "disagreed" every pair read twice, "could not tell" only the pairs whose
	 * two readings agreed, the day's own count of them. It is the floor the
	 * sentence under the strip keeps, so the two agree about when a share is a
	 * measurement; under it a figure prints its counts. The words are Reader's.
	 */
	function readingsOf(day: JudgeDay): { disagreed: string; unclear: string; name: string } {
		const date = dayMonth(day.date);
		const disagreedCount = day.disagreementRate * day.pairsJudged;
		const disagreed =
			rateWithDenominator(disagreedCount, day.pairsJudged, attemptsFloor) ??
			`${Math.round(disagreedCount)} of ${plural(day.pairsJudged, 'pair', 'pairs')}`;
		const unclear = describeUnclear(
			day.unclearRate * day.pairsUsable,
			day.pairsUsable,
			attemptsFloor
		);
		return {
			disagreed,
			unclear,
			name:
				day.pairsUsable === 0
					? `${date}: ${disagreed} disagreed with the second reading. Could not tell: ${unclear}.`
					: `${date}: ${disagreed} disagreed with the second reading, and ${unclear} could not tell.`
		};
	}

	/** Where a share sits on the axis, or null where the pairs it is taken over
	 * are under the floor: there it is not a measurement, and a dot at its height
	 * would place a share the strip calls too few to report. */
	function heightOf(share: number, pairs: number): number | null {
		if (pairs < attemptsFloor) return null;
		return px(yAxis.scale(Math.min(share, corridor[1])));
	}

	const marks = $derived(
		read.map((day, index) => ({
			date: day.date,
			x: px(columnsX[index]),
			disagreeY: heightOf(day.disagreementRate, day.pairsJudged),
			unclearY: heightOf(day.unclearRate, day.pairsUsable),
			day,
			said: readingsOf(day)
		}))
	);

	/** One rate's line, broken wherever that rate has no dot: each run of
	 * neighbouring dots is one polyline, and a dot with no neighbour stands alone.
	 * Joined across such a day, the line would draw a value there. */
	function runsOf(points: readonly { x: number; y: number | null }[]): string[] {
		const runs: string[][] = [[]];
		for (const { x, y } of points) {
			if (y === null) runs.push([]);
			else runs[runs.length - 1].push(`${x},${y}`);
		}
		return runs.filter((run) => run.length > 1).map((run) => run.join(' '));
	}
	const disagreeRuns = $derived(runsOf(marks.map((mark) => ({ x: mark.x, y: mark.disagreeY }))));
	const unclearRuns = $derived(runsOf(marks.map((mark) => ({ x: mark.x, y: mark.unclearY }))));

	/** How many pairs the window read altogether: what the disagreed share is
	 * taken over, printed beside it. */
	const judged = $derived(read.reduce((total, day) => total + day.pairsJudged, 0));
	const disagreed = $derived(
		read.reduce((total, day) => total + day.disagreementRate * day.pairsJudged, 0)
	);
	/** How many of them got two readings that agreed, from each day's own count:
	 * what "could not tell" is taken over, printed beside it. */
	const agreed = $derived(read.reduce((total, day) => total + day.pairsUsable, 0));
	const unclear = $derived(
		read.reduce((total, day) => total + day.unclearRate * day.pairsUsable, 0)
	);
	const disagreeShare = $derived(rateWithDenominator(disagreed, judged, attemptsFloor));
	const unclearSaid = $derived(describeUnclear(unclear, agreed, attemptsFloor));
	/** Each share against its own mark, read off the share itself and never off
	 * why a day was held: the run first checks whether the record holds enough
	 * to fit on, so a day held for that can carry a share past its mark. A share
	 * is past its mark when it is above it, the test the run holds a day on. */
	const disagreedPast = $derived(judged > 0 && disagreed / judged > limits.disagreementMax);
	const unclearPast = $derived(agreed > 0 && unclear / agreed > limits.unclearMax);
	/** The disagreed share against its mark, for the sentences that judge that
	 * share alone. The words are Reader's. */
	const disagreedVerdict = $derived(
		`The ${wholePercent(disagreed, judged)}% that disagreed is ${disagreedPast ? 'past' : 'inside'} its mark`
	);
	/** Where the sentence prints both shares, the verdict on the two: the state
	 * it names and the words that close the sentence. The words are Reader's. */
	const bothVerdict = $derived.by(() => {
		if (disagreedPast && unclearPast)
			return { state: 'both-past', said: 'Both rates are past their marks.' };
		if (disagreedPast) return { state: 'disagreed-past', said: `${disagreedVerdict}.` };
		if (unclearPast)
			return {
				state: 'unclear-past',
				said: `The ${wholePercent(unclear, agreed)}% that could not tell is past its mark.`
			};
		return { state: 'inside', said: 'Both rates are inside the marks.' };
	});
	const heldByJudge = $derived(
		drawn.filter((day) => day.heldReason === 'judge_unstable' || day.heldReason === 'judge_uncertain')
			.length
	);

	/** Why a dot is missing, as a caption under the window sentence wherever the
	 * chart left one out. Not while the whole window is too few for a share: that
	 * sentence already says so. One column shows no gap, so it keeps the rule
	 * alone. The words are Reader's. */
	const floorNote = $derived.by(() => {
		const leftOut = marks.some((mark) => mark.disagreeY === null || mark.unclearY === null);
		if (!leftOut || disagreeShare === null) return null;
		const fewer = `fewer than ${plural(attemptsFloor, 'pair', 'pairs')}`;
		const rule = `A day has no "disagreed" dot if ${fewer} were read twice, and no "could not tell" dot if ${fewer} agreed.`;
		if (marks.length === 1) return rule;
		return marks.some((mark) => mark.disagreeY !== null || mark.unclearY !== null)
			? `${rule} The chart shows a gap where a dot is left out, and that day's counts are still above.`
			: `${rule} So the chart has no dots, and each day's counts are still above.`;
	});

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
	note={`Every pair is read twice, with the two summaries swapped. A "disagreed" dot shows how often a pair's two readings disagreed. A "could not tell" dot shows how often the pairs whose two readings agreed could not tell. When a day's rate is past its own dashed mark, the run does not move the merge line that day.`}
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
							? `${percent(rule.at)} - the "disagreed" mark`
							: `${percent(rule.at)} - the "could not tell" mark`}
					</text>
				{/each}

				{#each disagreeRuns as points (points)}
					<polyline
						{points}
						fill="none"
						stroke="var(--chart-1)"
						stroke-width="2"
						data-agreement-series="disagreement"
					/>
				{/each}
				{#each unclearRuns as points (points)}
					<polyline
						{points}
						fill="none"
						stroke="var(--chart-3)"
						stroke-width="2"
						data-agreement-series="unclear"
					/>
				{/each}

				{#each marks as mark (mark.date)}
					<g
						role="img"
						aria-label={mark.said.name}
						data-agreement-day={mark.date}
						data-agreement-judged={mark.day.pairsJudged}
					>
						{#if mark.disagreeY !== null}
							<circle cx={mark.x} cy={mark.disagreeY} r="2.5" fill="var(--chart-1)" />
						{/if}
						{#if mark.unclearY !== null}
							<circle cx={mark.x} cy={mark.unclearY} r="2.5" fill="var(--chart-3)" />
						{/if}
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
			{:else if agreed === 0}
				<span data-agreement-state="none-agreed"
					>In {nameSpan(windowDays)}, {disagreeShare} disagreed with their own second reading.
					Could not tell: {unclearSaid}. {disagreedVerdict}.</span
				>
			{:else if agreed < attemptsFloor}
				<span data-agreement-state="few-agreed"
					>In {nameSpan(windowDays)}, {disagreeShare} disagreed with their own second reading, and
					{unclearSaid} could not tell. {disagreedVerdict}, and {agreed} is too few to report a
					share.</span
				>
			{:else}
				<span data-agreement-state={bothVerdict.state}
					>In {nameSpan(windowDays)}, {disagreeShare} disagreed with their own second reading, and
					{unclearSaid} could not tell. {bothVerdict.said}</span
				>
			{/if}
		</p>
		{#if floorNote !== null}
			<p class="floor-note" data-agreement-floor-note>{floorNote}</p>
		{/if}
	</div>
</Panel>

<style>
	.agreement-note {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	/* A rule for reading the chart is a caption, so the verdict above it stays
	   the last thing in its own paragraph. */
	.floor-note {
		margin: var(--space-2) 0 0;
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}
</style>
