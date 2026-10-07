<script lang="ts">
	/** Whether the tail is growing, one plot a percentile.
	 *
	 * Five lines on one chart is a bundle a reader has to untangle by colour;
	 * separated, each is a trend read in one look. All five share one scale,
	 * which is the point of the arrangement - a p99 twenty times its own p50 has
	 * to look twenty times taller.
	 */
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import {
		latencyColumns,
		seconds,
		PERCENTILES,
		type LatencyHistory,
		type LatencyRun
	} from '$lib/charts/machine';
	import {
		chartWidth,
		dayColumns,
		frame,
		linearAxis,
		modelRuleRow,
		modelRuleTitle,
		MODEL_RULE_LABEL,
		MODEL_RULE_NOTE,
		modelRules,
		noModelRuleNote,
		observeWidth,
		type Frame
	} from '$lib/charts/frame';
	import { pointerReadout, readoutMarks } from '$lib/charts/readout';
	import { shortDate } from '$lib/format';
	import {
		namesMoved,
		namesMovedShort,
		settingsByDate,
		unreadRuleNote,
		type SettingsMoved
	} from '$lib/console/settings-moved';
	import { boundaryDates, firstOfDay, inSpan, runTicks, MARK_PAD } from './run-axis';
	import { countDays, nameSpan } from '$lib/console/span-words';
	import type { ChartConfig } from '$lib/server/config';

	let {
		rows,
		start,
		end,
		modelChanges,
		missingMarkers,
		moved,
		chart,
		windowDays,
		days,
		floor,
		tooFew
	}: {
		rows: readonly LatencyRun[];
		start: string;
		end: string;
		modelChanges: readonly string[];
		/** The line for the days this span's markers could only come from the score
		 * record, when that record did not read; null when no marker was lost. */
		missingMarkers: string | null;
		/** What the run record says moved, by date. A date in `modelChanges` with no
		 * entry here moved something the record cannot name. */
		moved: readonly SettingsMoved[];
		chart: ChartConfig;
		windowDays: number;
		days: number;
		floor: number;
		tooFew: LatencyHistory['tooFew'];
	} = $props();

	/** One sub-plot, and the air between two of them. Five stacked rather than
	 * five side by side: they share the day axis at the foot, so a reader
	 * comparing p50 with p99 on one run reads straight down one column. */
	const TAIL_CELL_PX = 96;
	const TAIL_GAP_PX = 12;
	const TAIL_MARGIN = { top: 16, right: 12, bottom: 8, left: 52 };
	/** The shared date axis under the last cell. */
	const TAIL_AXIS_PX = 22;

	let tailWidth = $state<number | null>(null);
	let tailAt = $state<number | null>(null);

	const tailRuns = $derived(inSpan(rows, start, end));
	// A function of the runs alone, so a resize reuses them (as the context chain
	// on its own panel does): the caption columns, the boundary set and the
	// shared domain no longer rebuild on a drag.
	const tailDates = $derived(firstOfDay(tailRuns));
	const tailData = $derived(
		latencyColumns(tailRuns, {
			lines: tailRuns.map((run) =>
				tailBoundaries.has(run.date)
					? [modelRuleRow(namesMovedShort(movedOn.get(run.date) ?? []))]
					: []
			)
		})
	);
	const tailBoundaries = $derived(boundaryDates(modelChanges, tailDates));
	const tailExtent = $derived(tailRuns.flatMap((run) => run.ms.map((ms) => ms / 1000)));
	const tailW = $derived(chartWidth(tailWidth, chart.width_px));
	const tailH = $derived(
		PERCENTILES.length * TAIL_CELL_PX + (PERCENTILES.length - 1) * TAIL_GAP_PX + TAIL_AXIS_PX
	);
	/** Where one percentile's own plot sits inside the shared drawing. */
	function tailBox(at: number): Frame {
		const box = frame(tailW, TAIL_CELL_PX, TAIL_MARGIN);
		const down = at * (TAIL_CELL_PX + TAIL_GAP_PX);
		return { ...box, top: box.top + down, bottom: box.bottom + down };
	}
	/** ONE domain across all five, which is the whole check: five plots on five
	 * domains are five pictures of the same shape, and a reader cannot tell from
	 * them that the p99 is twenty times the p50. The scale is built in the first
	 * cell's pixels and every other cell is the same box moved down. */
	const tailY = $derived(
		linearAxis(tailExtent, [TAIL_CELL_PX - TAIL_MARGIN.bottom, TAIL_MARGIN.top])
	);
	function tailAtY(at: number, value: number): number {
		return Math.round((tailY.scale(value) + at * (TAIL_CELL_PX + TAIL_GAP_PX)) * 10) / 10;
	}
	const tailX = $derived(
		dayColumns(tailRuns.length, tailBox(0), MARK_PAD).map((x) => Math.round(x * 10) / 10)
	);
	const tailAxis = $derived(
		runTicks(
			tailRuns.map((run) => run.date),
			tailX,
			chart.tick_density
		)
	);
	const tailRules = $derived(modelRules(modelChanges, tailDates, tailX));
	/** The words for one date, or none where the record could not name them. */
	const movedOn = $derived(settingsByDate(moved));
	/** Days this span covers, that a setting moved on, and that no run of this
	 * chart timed enough items to draw. Decision 4 of Row #22: the rule and the
	 * absence are both drawn, because the days nobody measured are exactly the
	 * days a before-and-after is least safe to read across. */
	const tailUnread = $derived(
		moved.filter(
			(one) =>
				one.date >= start &&
				one.date <= end &&
				!tailRuns.some((run) => run.date === one.date)
		)
	);
	const tailMarks = $derived(readoutMarks(tailRuns.map((_, index) => tailX[index] ?? 0)));
	function tailLine(at: number): string {
		return tailRuns
			.map((run, index) => `${tailX[index]},${tailAtY(at, (run.ms[at] ?? 0) / 1000)}`)
			.join(' ');
	}
	/** One polyline a percentile, built once a span-and-width. Five were rebuilt
	 * on every render before, once for each `{#each PERCENTILES}` pass. */
	const tailLines = $derived(PERCENTILES.map((_, at) => tailLine(at)));
	/** The runs' dates and the window's days, as the label names them. Where
	 * every run is on one date, that date already says one day, so it stands
	 * alone, never as a date to itself. */
	const tailSpan = $derived.by(() => {
		const first = tailRuns.at(0)?.date;
		const last = tailRuns.at(-1)?.date;
		if (first === undefined || last === undefined) return '';
		return first === last
			? shortDate(first)
			: `${shortDate(first)} to ${shortDate(last)}, over ${countDays(days)}`;
	});

	/** How far the newest run's slow end sits from its own middle.
	 *
	 * The five plots show whether that gap is moving; a reader who wanted to
	 * know how wide it is today was reading it off a curve by eye. Printed, it
	 * is one number rather than a comparison of two heights. The ends are the
	 * lowest and the highest percentile drawn, so a change to `PERCENTILES`
	 * moves the sentence with the plots. */
	const newest = $derived(tailRuns.at(-1) ?? null);
	const spread = $derived.by(() => {
		const middle = newest?.ms[0] ?? 0;
		const slowest = newest?.ms.at(-1) ?? 0;
		if (newest === null || middle <= 0 || slowest <= 0) return null;
		return { run: newest, middle, slowest, times: slowest / middle };
	});
</script>

<div
	data-windowed="machine-latency"
	data-window-days={windowDays}
	data-tail-domain={JSON.stringify(tailY.domain)}
	data-model-rule={tailRuns.length > 1 ? 'yes' : 'no'}
	data-model-rule-name="machine-latency"
	data-model-rule-none={tailRuns.length > 1
		? undefined
		: 'one run drawn, so there is no edge between two of them to draw between'}
	data-model-rule-from={tailRuns[0]?.date ?? ''}
	data-model-rule-to={tailRuns.at(-1)?.date ?? ''}
>
	<Panel
		heading="h3"
		id="tail-trend"
		title="Whether the slowest articles are getting slower"
		note="A slow end that keeps drifting is the one that eventually runs a job past its limit - one mark a run, over {nameSpan(windowDays)}."
	>
		{#if tailRuns.length === 0}
			<p class="empty" data-machine-panel-empty="latency">
				No run in {nameSpan(days)} timed {floor} items, which is the floor
				below which a p99 is just the last item.
			</p>
			{#if tailUnread.length > 0}
				<p class="reads" data-model-rule-unread="machine-latency">{unreadRuleNote(tailUnread)}</p>
			{/if}
		{:else}
			<div class="plot" data-readout-columns={tailData.columns.length}>
				<div use:observeWidth={(px) => (tailWidth = px)}>
					<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
					<svg
						class="w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
						height={tailH}
						viewBox={`0 0 ${tailW} ${tailH}`}
						role="img"
						tabindex="0"
						aria-label="Per-item model time at the 50th, 75th, 90th, 95th and 99th percentile, one plot each and one mark per run, {tailSpan}. All five plots share one scale."
						data-latency-runs={tailRuns.length}
						use:pointerReadout={{
							marks: tailMarks,
							width: tailW,
							onSelect: (index) => (tailAt = index)
						}}
					>
						{#each PERCENTILES as percentile, at (percentile)}
							{@const box = tailBox(at)}
							<line
								x1={box.left}
								x2={box.right}
								y1={box.bottom}
								y2={box.bottom}
								stroke="var(--color-rule)"
							/>
							<text
								x={box.left - 6}
								y={box.bottom + 3}
								text-anchor="end"
								fill="var(--color-text-tertiary)"
								font-size="10"
							>
								0
							</text>
							<text
								x={box.left - 6}
								y={box.top + 8}
								text-anchor="end"
								fill="var(--color-text-tertiary)"
								font-size="10"
								data-latency-top={tailY.domain[1]}
							>
								{tailY.domain[1].toFixed(0)}s
							</text>
							<text
								x={box.left}
								y={box.top - 4}
								fill="var(--color-text-secondary)"
								font-size="11"
								data-latency-plot={`p${percentile}`}
							>
								p{percentile}
							</text>
							<!-- One colour for all five. They are one measure at five
							     quantiles, so a second colour would name a distinction that
							     is not in the data. -->
							<g data-latency-series={`p${percentile}`}>
								<polyline
									points={tailLines[at]}
									fill="none"
									stroke="var(--chart-1)"
									stroke-width="2"
								/>
								{#each tailRuns as run, index (run.runId)}
									<circle
										cx={tailX[index]}
										cy={tailAtY(at, (run.ms[at] ?? 0) / 1000)}
										r="2.5"
										fill="var(--chart-1)"
									/>
								{/each}
							</g>
						{/each}

						<!-- One line a boundary, down every plot at once. The change
						     applies to the whole distribution, so a rule per plot would
						     be one event drawn five times. -->
						{#each tailRules as rule (rule.date)}
							<line
								x1={rule.x}
								x2={rule.x}
								y1={tailBox(0).top}
								y2={tailBox(PERCENTILES.length - 1).bottom}
								stroke="var(--chart-change)"
								stroke-width="1.5"
								stroke-dasharray="3 3"
								role="img"
								aria-label={modelRuleTitle(rule.date, namesMoved(movedOn.get(rule.date) ?? []))}
								data-model-rule-line={rule.date}
							/>
							<text
								x={rule.x + 3}
								y={tailBox(0).top + 9}
								fill="var(--chart-change)"
								font-size="10"
								data-model-rule-label={rule.date}
							>
								{MODEL_RULE_LABEL}
							</text>
						{/each}

						{#if tailAt !== null && tailX[tailAt] !== undefined}
							<line
								x1={tailX[tailAt]}
								x2={tailX[tailAt]}
								y1={tailBox(0).top}
								y2={tailBox(PERCENTILES.length - 1).bottom}
								stroke="var(--color-text-tertiary)"
								stroke-opacity="0.5"
								data-latency-guide
							/>
						{/if}

						{#each tailAxis as label (label.index)}
							{@const foot = tailBox(PERCENTILES.length - 1).bottom}
							<line
								x1={tailX[label.index]}
								x2={tailX[label.index]}
								y1={foot}
								y2={foot + 4}
								stroke="var(--color-text-tertiary)"
								data-day-tick={label.date}
							/>
							{#if label.text}
								<text
									x={tailX[label.index]}
									y={foot + 16}
									text-anchor={label.anchor}
									fill="var(--color-text-tertiary)"
									font-size="10"
									data-day-axis
								>
									{label.text}
								</text>
							{/if}
						{/each}
					</svg>
				</div>
				<ChartReadout
					readout={tailData}
					at={tailAt}
					name="latency"
					maxShare={chart.readout_max_share}
					restingNote=", the last run"
					hint="Point at a run to read every percentile of it at once. Left and Right step through the runs, Escape returns to the last."
				/>
			</div>

			<!-- The dashed-rule sentence, then what a score read that did not read cost
			     the rules. While that line prints, the chart never says nothing changed:
			     it cannot see the days the line names. -->
			{#if tailRules.length > 0}
				<p class="reads">
					<span data-model-rule-note="machine-latency">{MODEL_RULE_NOTE}</span>
				</p>
			{/if}
			{#if missingMarkers !== null}
				<p class="reads" data-markers-missing="machine-latency">{missingMarkers}</p>
			{:else if tailRules.length === 0 && tailRuns.length > 1}
				<p class="reads">
					<span data-model-rule-empty="machine-latency">{noModelRuleNote(days)}</span>
				</p>
			{/if}

			{#if tailUnread.length > 0}
				<p class="reads" data-model-rule-unread="machine-latency">{unreadRuleNote(tailUnread)}</p>
			{/if}

			<p class="reads" data-latency-note>
				{tailRuns.length}
				{tailRuns.length === 1 ? 'run' : 'runs'} of {nameSpan(days)}. The value is
				<code>summarize_ms</code>, the whole model call for one item, and a percentile is
				interpolated linearly between the two nearest ranks - at about a hundred items the
				nearest-rank rule and this one disagree by more than the difference between two runs, so
				the rule is named rather than assumed. Runs are never pooled: two runs of one day draw
				different processors.
				{#if tooFew.length > 0}
					{tooFew.length}
					{tooFew.length === 1 ? 'run' : 'runs'} timed fewer than
					{floor} items and {tooFew.length === 1 ? 'is' : 'are'} printed
					rather than drawn:
					{tooFew.map((run) => `${run.runId} (${run.items})`).join(', ')}.
				{/if}
			</p>

			{#if spread !== null}
				<p class="reads" data-latency-spread={spread.times.toFixed(2)}>
					On {spread.run.runId}, the newest run drawn, the slowest articles took
					<strong>{spread.times.toFixed(1)} times as long</strong>
					as the middle one: {seconds(spread.slowest / 1000)} against
					{seconds(spread.middle / 1000)}. That is how wide the spread is today; the plots above
					are whether it is widening.
				</p>
			{/if}

			<ul class="sr-only" data-latency-values>
				{#each tailRuns as run (run.runId)}
					<li data-latency-run={run.runId}>
						{run.runId}, {run.items} items:
						{PERCENTILES.map(
							(percentile, at) => `p${percentile} ${((run.ms[at] ?? 0) / 1000).toFixed(1)}s`
						).join(', ')}.
					</li>
				{/each}
			</ul>
		{/if}
	</Panel>
</div>

<style>
	.empty {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.reads {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	/* A hand-drawn plot and the strip under it. Positioned, because the
	   selected-column guide is drawn inside the SVG and the strip below it. */
	.plot {
		position: relative;
		margin-top: var(--space-2);
	}
</style>
