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
	 * **Every day of the window is a column.** A day that read no pair draws no
	 * dot and carries no name, both lines break there, and the strip can still
	 * select it and says why it holds no reading. Spaced only over the days
	 * that read a pair, a line would join straight across a day nobody measured
	 * (Jony, 2026-10-09).
	 *
	 * **The axis holds both marks and every share that draws a dot, niced to a
	 * whole tick step.** A top fixed at the looser mark would clip a share past
	 * it onto the mark's own line, which hides the one reading this panel
	 * exists to show. Fitted to the shares alone, a healthy two percent would
	 * still fill the panel and read as trouble, so the two marks are always in
	 * the set the axis nices from.
	 */
	import {
		AXIS_LABEL_PX,
		chartWidth,
		dayColumns,
		dayTicks,
		frame,
		labelWidth,
		linearAxis,
		observeWidth
	} from '$lib/charts/frame';
	import { pointerReadout, readoutMarks, readoutOf } from '$lib/charts/readout';
	import { daysBetween, daysInWindow, type TimeWindow } from '$lib/charts/viewport';
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

	/** One day's dots and strip words, for a day that read a pair. */
	interface Reading {
		day: JudgeDay;
		disagreeY: number | null;
		unclearY: number | null;
		said: { disagreed: string; unclear: string; name: string };
	}

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
	/** Every day of the window, oldest first, once at least one day read a pair.
	 * None while no day did: the sentence already says so, and a strip of
	 * columns that would all print the same empty line says it again at each
	 * one. */
	const dates = $derived(read.length === 0 ? [] : daysInWindow(viewport));
	const readOn = $derived(new Map(read.map((day) => [day.date, day] as const)));
	/** The days that carry a row here, read or not. A row that read no pair had
	 * no readings come in; a day with no row at all may not be packed yet, or
	 * may have had no run - this page cannot tell those two apart. */
	const rowOn = $derived(new Set(drawn.map((day) => day.date)));

	/** Whether a share is a measurement: the pairs it is taken over reach the
	 * floor. One rule for which shares draw a dot and which the axis nices from. */
	function reachesFloor(pairs: number): boolean {
		return pairs >= attemptsFloor;
	}
	/** Every share that draws a dot, which joins the two marks in the set the
	 * axis is niced from. */
	const shares = $derived(
		read.flatMap((day) => [
			...(reachesFloor(day.pairsJudged) ? [day.disagreementRate] : []),
			...(reachesFloor(day.pairsUsable) ? [day.unclearRate] : [])
		])
	);
	const corridor = $derived(agreementCorridor(limits, shares));

	const box = $derived(frame(chartWidth(measured, width), height));
	const yAxis = $derived(
		linearAxis(corridor, [box.bottom, box.top], { tickCount: 4, zero: false, nice: false })
	);
	const columnsX = $derived(dayColumns(dates.length, box, 2));
	const ticks = $derived(dayTicks(dates, { density: tickDensity, columns: columnsX }));

	function px(value: number): number {
		return Math.round(value * 10) / 10;
	}

	function percent(share: number): string {
		return `${Math.round(share * 100)}%`;
	}

	/** One dashed mark's own label text, shared between drawing it and keeping
	 * a stranded date label (below) off it. */
	function markLabel(name: 'disagreement' | 'unclear', at: number): string {
		return name === 'disagreement'
			? `${percent(at)} - the "disagreed" mark`
			: `${percent(at)} - the "could not tell" mark`;
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
	 * would place a share the strip calls too few to report. The axis is niced
	 * from every drawn share, so no share can fall above it. */
	function heightOf(share: number, pairs: number): number | null {
		if (!reachesFloor(pairs)) return null;
		return px(yAxis.scale(share));
	}

	/** What the strip says at a column with no reading. A day whose row read no
	 * pair had no readings come in; a day with no row at all may not be packed
	 * yet, or there may have been none - the page does not know which. Neither
	 * says the judge did nothing. The words are Reader's. */
	const NO_READINGS = 'No readings came in for this day';
	const NO_NUMBERS = 'The numbers for this day are not here yet, or there are none';

	/** One column a day of the window: where it sits, and either its reading or
	 * why it holds none. */
	const marks = $derived(
		dates.map((date, index) => {
			const day = readOn.get(date);
			const reading: Reading | null =
				day === undefined
					? null
					: {
							day,
							disagreeY: heightOf(day.disagreementRate, day.pairsJudged),
							unclearY: heightOf(day.unclearRate, day.pairsUsable),
							said: readingsOf(day)
						};
			return {
				date,
				x: px(columnsX[index]),
				unread: reading !== null ? null : rowOn.has(date) ? NO_READINGS : NO_NUMBERS,
				reading
			};
		})
	);

	/** Only the columns with a reading: what the dots and their accessible
	 * names draw from. An unread day keeps its column for the axis and the
	 * strip, but draws no mark and carries no name - it has nothing to name
	 * (Jony's ruling). */
	const drawnMarks = $derived(
		marks.flatMap((mark) =>
			mark.reading === null ? [] : [{ date: mark.date, x: mark.x, reading: mark.reading }]
		)
	);

	/** The dates the shared axis gives a tick to. `dayTicks` samples a fixed
	 * number of evenly spaced days before it ever looks at which ones hold a
	 * reading (`chart.tick_density`), so a day can carry a real dot and no
	 * axis tick at all - never thinned down to a bare mark, simply never
	 * sampled. */
	const tickedDates = $derived(new Set(ticks.map((tick) => tick.date)));

	/** The two limits, named, in drawing order: shared between the template's
	 * own loop and the mark-label boxes below, so the two cannot name the
	 * limits differently. */
	const limitRules = $derived([
		{ at: limits.disagreementMax, name: 'disagreement' as const },
		{ at: limits.unclearMax, name: 'unclear' as const }
	]);

	/** Each dashed mark's own label, as the small box it occupies: text-anchor
	 * `end` at the plot's right edge, so its left edge is its width back from
	 * there. Read, never drawn from - kept only so a stranded date label
	 * (below) does not land on top of one. */
	const markLabelBoxes = $derived(
		limitRules.map(({ name, at }) => {
			const baseline = yAxis.scale(at) - 4;
			const width = labelWidth(markLabel(name, at));
			return { top: baseline - AXIS_LABEL_PX, bottom: baseline, left: box.right - width, right: box.right };
		})
	);

	function boxesOverlap(
		a: { top: number; bottom: number; left: number; right: number },
		b: { top: number; bottom: number; left: number; right: number }
	): boolean {
		return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
	}

	/** A day's own date, drawn beside its topmost dot, for a day whose axis
	 * tick the sampling above left out while the day immediately before or
	 * after it, inside the drawn window, held no reading.
	 *
	 * Not every day with a dot and no tick: at a wide preset most days carry a
	 * reading, and labelling each one the sampling skipped would print dozens
	 * of dates over the marks the chart is about. A day with an unread
	 * neighbour on either side has no tick close enough on that side for a
	 * glancing reader to read its date off of, which this fires on; a window
	 * with few gaps has few or no such days (Jony and Susan, 2026-10-09). The
	 * label repeats what the day's own accessible name already says, so it is
	 * `aria-hidden`.
	 *
	 * Raised clear of either dashed mark's own label where the two would
	 * otherwise overlap - a stranded day can sit at a mark's own height, and
	 * near the plot's right edge the two labels compete for the same corner
	 * (Jony, 2026-10-09). Left open: a mark within about `AXIS_LABEL_PX * 2`
	 * of the plot's own top, where this clearance and the top clamp below
	 * could still collide; narrow enough to leave until it is hit.
	 */
	const strandedLabels = $derived(
		marks.flatMap((mark, index) => {
			if (mark.reading === null || tickedDates.has(mark.date)) return [];
			const before = marks[index - 1];
			const after = marks[index + 1];
			const hasUnreadNeighbour =
				(before !== undefined && before.reading === null) ||
				(after !== undefined && after.reading === null);
			if (!hasUnreadNeighbour) return [];
			const { disagreeY, unclearY } = mark.reading;
			const topY =
				disagreeY === null
					? unclearY
					: unclearY === null
						? disagreeY
						: Math.min(disagreeY, unclearY);
			if (topY === null) return [];
			const width = labelWidth(dayMonth(mark.date));
			let y = topY - 8;
			for (const markBox of markLabelBoxes) {
				const box_ = { top: y - AXIS_LABEL_PX, bottom: y, left: mark.x - width / 2, right: mark.x + width / 2 };
				if (boxesOverlap(box_, markBox)) y = Math.min(y, markBox.top - 2);
			}
			// Clamped so the label's own ascender never climbs past the plot's top
			// margin, where an isolated dot sits close enough to the axis top.
			return [{ date: mark.date, x: mark.x, y: Math.max(y, box.top + 2) }];
		})
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
	const disagreeRuns = $derived(
		runsOf(marks.map((mark) => ({ x: mark.x, y: mark.reading?.disagreeY ?? null })))
	);
	const unclearRuns = $derived(
		runsOf(marks.map((mark) => ({ x: mark.x, y: mark.reading?.unclearY ?? null })))
	);

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
	 * sentence already says so. Only the days that read a pair count: a day with
	 * no reading is not under the floor, and its own strip entry already says
	 * why it is empty. One such day shows no gap, so it keeps the rule alone.
	 * The words are Reader's. */
	const floorNote = $derived.by(() => {
		const readings = drawnMarks.map((mark) => mark.reading);
		const leftOut = readings.some((one) => one.disagreeY === null || one.unclearY === null);
		if (!leftOut || disagreeShare === null) return null;
		const fewer = `fewer than ${plural(attemptsFloor, 'pair', 'pairs')}`;
		const rule = `A day has no "disagreed" dot if ${fewer} were read twice, and no "could not tell" dot if ${fewer} agreed.`;
		if (readings.length === 1) return rule;
		return readings.some((one) => one.disagreeY !== null || one.unclearY !== null)
			? `${rule} The chart shows a gap where a dot is left out, and that day's counts are still above.`
			: `${rule} So the chart has no dots, and each day's counts are still above.`;
	});

	/** A day's two readings, as its strip prints them and as its marks name them:
	 * every word of the sentence is in the strip at that day. A column with no
	 * reading says why in its own words, and the strip rests on the newest day
	 * WITH a reading, because the newest one or two days of a window are often
	 * still unread. */
	const readout = $derived(
		readoutOf({
			type: 'dateSeries',
			columns: marks.map((mark) => dayMonth(mark.date)),
			series: [
				{
					label: 'Disagreed with the second reading',
					swatch: 'var(--chart-1)',
					values: marks.map((mark) => mark.reading?.day.disagreementRate ?? null),
					format: (_: number, column: number) => marks[column].reading!.said.disagreed
				},
				{
					label: 'Could not tell',
					swatch: 'var(--chart-3)',
					values: marks.map((mark) => mark.reading?.day.unclearRate ?? null),
					format: (_: number, column: number) => marks[column].reading!.said.unclear
				}
			],
			notMeasured: NO_NUMBERS,
			notMeasuredAt: marks.map((mark) => mark.unread),
			resting: 'newest'
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
				{#each limitRules as rule (rule.name)}
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
						{markLabel(rule.name, rule.at)}
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

				{#each drawnMarks as mark (mark.date)}
					<g
						role="img"
						aria-label={mark.reading.said.name}
						data-agreement-day={mark.date}
						data-agreement-judged={mark.reading.day.pairsJudged}
					>
						{#if mark.reading.disagreeY !== null}
							<circle cx={mark.x} cy={mark.reading.disagreeY} r="2.5" fill="var(--chart-1)" />
						{/if}
						{#if mark.reading.unclearY !== null}
							<circle cx={mark.x} cy={mark.reading.unclearY} r="2.5" fill="var(--chart-3)" />
						{/if}
					</g>
				{/each}

				{#each ticks as tick (tick.index)}
					{#if tick.text}
						<text
							x={px(columnsX[tick.index])}
							y={box.bottom + 16}
							text-anchor={tick.anchor}
							fill="var(--color-text-tertiary)"
							font-size="10"
							data-day-tick={tick.date}
						>
							{tick.text}
						</text>
					{/if}
				{/each}

				<!-- A day whose own axis tick the shared sampling skipped, with an
				     unread neighbour on at least one side: the one case a glancing
				     reader has no nearby tick to read its date off of. Repeats the
				     day's own accessible name, so it carries none of its own. -->
				{#each strandedLabels as label (label.date)}
					<text
						x={label.x}
						y={label.y}
						text-anchor="middle"
						fill="var(--color-text-tertiary)"
						font-size="10"
						aria-hidden="true"
						data-agreement-stranded-label={label.date}
					>
						{dayMonth(label.date)}
					</text>
				{/each}
			</svg>
		</div>

		<ChartReadout
			{readout}
			at={selected}
			name="judge-agreement"
			maxShare={readoutMaxShare}
			restingNote=", the newest day with numbers"
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
