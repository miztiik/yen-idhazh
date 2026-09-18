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
		observeWidth,
		pointerReadout,
		readoutMarks,
		type DayReadout
	} from '$lib/charts/frame';
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { dayMonth } from '$lib/format';
	import {
		agreementCorridor,
		rateWithDenominator,
		type AgreementLimits,
		type JudgeDay
	} from '$lib/console/merge-line';

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
	/** Only the days a leg actually read something. A day with nothing judged has
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

	const marks = $derived(
		read.map((day, index) => ({
			date: day.date,
			x: px(columnsX[index]),
			disagreeY: px(yAxis.scale(Math.min(day.disagreementRate, corridor[1]))),
			unclearY: px(yAxis.scale(Math.min(day.unclearRate, corridor[1]))),
			day
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

	const columns = $derived<DayReadout[]>(
		marks.map((mark) => ({
			x: mark.x,
			date: dayMonth(mark.day.date),
			rows: [
				{
					label: 'Disagreed with itself',
					value: `${percent(mark.day.disagreementRate)} of ${mark.day.pairsJudged}`,
					colour: 'var(--chart-1)'
				},
				{
					label: 'Could not tell',
					value: `${percent(mark.day.unclearRate)} of ${mark.day.pairsJudged}`,
					colour: 'var(--chart-3)'
				}
			]
		}))
	);
	const resting = $derived(selected === null);
	const readout = $derived(columns.length === 0 ? null : columns[selected ?? columns.length - 1]);
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
		data-readout-columns={columns.length > 0 ? columns.length : undefined}
		data-readout-none={columns.length > 0
			? undefined
			: 'no pair has been read twice, so there is no column to read'}
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
				aria-label="How often the judge disagreed with its own second reading, a day"
				use:pointerReadout={{
					marks: readoutMarks(columns),
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
					<g data-agreement-day={mark.date} data-agreement-judged={mark.day.pairsJudged}>
						<title
							>{dayMonth(mark.day.date)} - {percent(mark.day.disagreementRate)} of {mark.day
								.pairsJudged} pairs disagreed with their own second reading, and {percent(
								mark.day.unclearRate
							)} could not tell.</title
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
			name="judge-agreement"
			maxShare={readoutMaxShare}
			{resting}
			restingNote="the newest day"
		/>

		<p class="agreement-note">
			{#if read.length === 0}
				<span data-agreement-state="none"
					>No pair has been read twice yet, so there is nothing to compare.</span
				>
			{:else if disagreeShare === null}
				<span data-agreement-state="filling"
					>{judged} pairs have been read twice. That is too few to report a share, so the
					counts are below.</span
				>
			{:else if heldByJudge > 0}
				<span data-agreement-state="past-mark"
					>The two readings disagreed on {disagreeShare}, which is past the mark. No line
					was fitted on {heldByJudge}
					{heldByJudge === 1 ? 'day' : 'days'} because of it.</span
				>
			{:else}
				<span data-agreement-state="inside"
					>{disagreeShare} disagreed with their own second reading, and {unclearShare} could
					not tell. Both rates are inside the marks.</span
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
