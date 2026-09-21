<script lang="ts">
	/** What the model's reading limit already costs, not only whether it could grow.
	 *
	 * The panel used to draw one mark a run - the longest thing that run read -
	 * and a dotted line for the room left over. The dotted line was the solid
	 * one reflected in the limit rule, so it carried no second reading, and one
	 * mark cannot say both what an ordinary article takes and what the worst one
	 * takes. It now draws both ends: the longest article of the run, and the
	 * high percentile under it. The gap between the top mark and the rule is the
	 * slack, and it is the finding.
	 */
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { contextColumns, highLabel, type ContextRun, type ContextSpan } from './context-cost';
	import { grouped } from '$lib/charts/series';
	import {
		chartWidth,
		dayColumns,
		frame,
		linearAxis,
		modelRuleTitle,
		modelRules,
		noModelRuleNote,
		observeWidth,
		pointerReadout,
		readoutMarks,
		MODEL_RULE_ROW
	} from '$lib/charts/frame';
	import { boundaryDates, firstOfDay, inSpan, runTicks, MARK_PAD } from './run-axis';
	import type { ChartConfig } from '$lib/server/config';

	let {
		rows,
		start,
		end,
		contextWindow,
		cost,
		modelChanges,
		chart,
		windowDays,
		days
	}: {
		rows: readonly ContextRun[];
		start: string;
		end: string;
		contextWindow: number;
		/** The span's own figures, worked out on the server from the same rows. */
		cost: ContextSpan;
		modelChanges: readonly string[];
		chart: ChartConfig;
		windowDays: number;
		days: number;
	} = $props();

	let contextWidth = $state<number | null>(null);
	let contextAt = $state<number | null>(null);

	const contextRuns = $derived(inSpan(rows, start, end));
	/** The limit the measured rows ran under. Where the span holds one it is
	 * that one; where the setting moved inside the span no single token figure
	 * is about the span, so the rule falls back to the configured value and the
	 * sentence below names every limit it saw. */
	const limit = $derived(cost.limits.length === 1 ? cost.limits[0] : contextWindow);
	// The four shapes below are a function of the RUNS alone, so a resize reuses
	// them and only a new span rebuilds them.
	const contextDates = $derived(firstOfDay(contextRuns));
	const contextData = $derived(contextColumns(contextRuns, limit, cost.percentile));
	const contextBoundaries = $derived(boundaryDates(modelChanges, contextDates));
	/** The domain the plot is drawn against. Zero-anchored, and the limit is one
	 * of its bounds, so the ceiling is a line on the plot rather than a number
	 * off the top - which is the whole point when every mark sits far below it. */
	const contextExtent = $derived([
		0,
		limit,
		...contextRuns.flatMap((run) => [run.largest ?? 0, run.high ?? 0])
	]);
	const contextBox = $derived(
		frame(chartWidth(contextWidth, chart.width_px), chart.height_px, {
			top: 14,
			right: 12,
			bottom: 22,
			left: 52
		})
	);
	const contextX = $derived(
		// Rounded where they are made rather than at every use. `dayColumnX` divides
		// a plot by its column count, so a raw value carries seventeen digits into
		// the document for a tenth of a pixel nobody can see.
		dayColumns(contextRuns.length, contextBox, MARK_PAD).map((x) => Math.round(x * 10) / 10)
	);
	const contextY = $derived(linearAxis(contextExtent, [contextBox.bottom, contextBox.top]));
	const contextAxis = $derived(
		runTicks(
			contextRuns.map((run) => run.date),
			contextX,
			chart.tick_density
		)
	);
	const contextRules = $derived(modelRules(modelChanges, contextDates, contextX));
	const contextStrip = $derived(
		contextData.map((column, index) => ({
			...column,
			x: contextX[index] ?? 0,
			// One set membership a column, built once a span, in place of a scan of
			// the rule list a column. The set holds a boundary DAY's date and every
			// run of that day carries it, so all its columns take the rule.
			rows: contextBoundaries.has(contextRuns[index]?.date ?? '')
				? [...column.rows, MODEL_RULE_ROW]
				: column.rows
		}))
	);
	const contextMarks = $derived(readoutMarks(contextStrip));
	const contextResting = $derived(contextStrip.at(-1) ?? null);
	const contextReadout = $derived(
		contextAt === null ? contextResting : (contextStrip[contextAt] ?? contextResting)
	);
	/** Two polylines, built once each rather than per mark. */
	function line(values: readonly (number | null)[]): string {
		return values
			.map((value, index) => (value === null ? '' : `${contextX[index]},${contextAtY(value)}`))
			.filter((point) => point !== '')
			.join(' ');
	}
	function contextAtY(value: number): number {
		return Math.round(contextY.scale(value) * 10) / 10;
	}
	/** The two series as polylines, built once a span-and-width rather than once
	 * a render: inlined in the template, both were rebuilt on every hover. */
	const contextHighLine = $derived(line(contextRuns.map((run) => run.high)));
	const contextLargestLine = $derived(line(contextRuns.map((run) => run.largest)));
	const highName = $derived(highLabel(cost.percentile).toLowerCase());
</script>

<div
	data-windowed="machine-context"
	data-window-days={windowDays}
	data-context-domain={JSON.stringify(contextY.domain)}
	data-model-rule={contextRuns.length > 1 ? 'yes' : 'no'}
	data-model-rule-name="machine-context"
	data-model-rule-none={contextRuns.length > 1
		? undefined
		: 'one run drawn, so there is no edge between two of them to draw between'}
	data-model-rule-from={contextRuns[0]?.date ?? ''}
	data-model-rule-to={contextRuns.at(-1)?.date ?? ''}
>
	<Panel
		heading="h3"
		id="context-headroom"
		title="How much of the model's reading limit an article actually takes"
		note="A limit far above every article ever read is room a setting could give back - one mark a run, over the last {windowDays} days."
	>
		{#if contextRuns.length === 0}
			<p class="empty" data-machine-panel-empty="context">
				No run in these {days} days recorded both the limit it ran under and an article's own
				tokens, so nothing here can say what the limit cost.
			</p>
		{:else}
			<div
				class="plot"
				data-context-window={limit}
				data-readout-columns={contextStrip.length}
			>
				<div use:observeWidth={(px) => (contextWidth = px)}>
					<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
					<svg
						class="w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
						height={contextBox.height}
						viewBox={`0 0 ${contextBox.width} ${contextBox.height}`}
						role="img"
						tabindex="0"
						aria-label="The longest article and {highName} of each of {contextRuns.length} runs, against the {grouped(
							limit
						)}-token limit, over {days} days. One column is one run, oldest on the left."
						use:pointerReadout={{
							marks: contextMarks,
							width: contextBox.width,
							onSelect: (index) => (contextAt = index)
						}}
					>
						<line
							x1={contextBox.left}
							x2={contextBox.right}
							y1={contextBox.bottom}
							y2={contextBox.bottom}
							stroke="var(--color-rule)"
						/>
						{#each contextY.ticks as tick (tick)}
							<text
								x={contextBox.left - 6}
								y={contextAtY(tick) + 3}
								text-anchor="end"
								fill="var(--color-text-tertiary)"
								font-size="10"
							>
								{grouped(tick)}
							</text>
						{/each}

						<!-- The limit is a rule and never a bar. A limit is a line a
						     series approaches; a bar beside a bar invites the reader to
						     compare two lengths and forget which one is the ceiling. -->
						<line
							x1={contextBox.left}
							x2={contextBox.right}
							y1={contextAtY(limit)}
							y2={contextAtY(limit)}
							stroke="var(--chart-marker)"
							stroke-width="1.5"
							data-context-limit={limit}
						>
							<title>
								{`The server was given a ${grouped(limit)}-token limit. One call cannot cross this line.`}
							</title>
						</line>
						<text
							x={contextBox.right}
							y={contextAtY(limit) - 4}
							text-anchor="end"
							fill="var(--color-text-tertiary)"
							font-size="10"
							data-context-limit-label
						>
							{grouped(limit)}-token limit
						</text>

						{#each contextRules as rule (rule.date)}
							<line
								x1={rule.x}
								x2={rule.x}
								y1={contextBox.top}
								y2={contextBox.bottom}
								stroke="var(--color-text-tertiary)"
								stroke-dasharray="3 3"
								data-model-rule-line={rule.date}
							>
								<title>{modelRuleTitle(rule.date)}</title>
							</line>
						{/each}

						{#if contextAt !== null && contextX[contextAt] !== undefined}
							<line
								x1={contextX[contextAt]}
								x2={contextX[contextAt]}
								y1={contextBox.top}
								y2={contextBox.bottom}
								stroke="var(--color-text-tertiary)"
								stroke-opacity="0.5"
								data-context-guide
							/>
						{/if}

						<!-- Both ends of every run. The lower line is the crowd and the
						     upper one is the worst case; the decision to cut the limit
						     turns on the upper one, so it takes the heavier stroke. -->
						<g data-context-series="high">
							<polyline
								points={contextHighLine}
								fill="none"
								stroke="var(--chart-3)"
								stroke-width="1.5"
							/>
							{#each contextRuns as run, index (run.runId)}
								{#if run.high !== null}
									<circle
										cx={contextX[index]}
										cy={contextAtY(run.high)}
										r="2"
										fill="var(--chart-3)"
									/>
								{/if}
							{/each}
						</g>
						<g data-context-series="largest">
							<polyline
								points={contextLargestLine}
								fill="none"
								stroke="var(--chart-1)"
								stroke-width="2"
							/>
							{#each contextRuns as run, index (run.runId)}
								{#if run.largest !== null}
									<circle
										cx={contextX[index]}
										cy={contextAtY(run.largest)}
										r="2.5"
										fill="var(--chart-1)"
									/>
								{/if}
							{/each}
						</g>

						{#each contextAxis as label (label.index)}
							<line
								x1={contextX[label.index]}
								x2={contextX[label.index]}
								y1={contextBox.bottom}
								y2={contextBox.bottom + 4}
								stroke="var(--color-text-tertiary)"
								data-day-tick={label.date}
							/>
							{#if label.text}
								<text
									x={contextX[label.index]}
									y={contextBox.bottom + 16}
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
					readout={contextReadout}
					name="context"
					maxShare={chart.readout_max_share}
					resting={contextAt === null}
					restingNote=", the last run"
					hint="Point at a run to read it. Left and Right step through them, Escape returns to the last."
				/>
			</div>

			{#if contextRules.length === 0 && contextRuns.length > 1}
				<p class="reads">
					<span data-model-rule-empty="machine-context">{noModelRuleNote(days)}</span>
				</p>
			{/if}

			<!-- The finding, in the order a reader needs it: what has never been
			     used, how far the limit sits above an ordinary article, and whether
			     anything was ever cut short. -->
			<p class="reads" data-context-cost data-context-unused-pct={cost.unusedPct ?? ''}>
				{#if cost.unusedPct === null || cost.largest === null}
					{cost.items} of the {cost.rowsRead} articles these {days} days recorded carried both the
					limit they ran under and their own tokens, which is too few to say what the limit cost.
				{:else}
					The longest article of these {days} days held
					<strong>{grouped(cost.largest)}</strong>
					tokens, which is {cost.largestPct}% of the {grouped(limit)} the server was given -
					<strong>{cost.unusedPct}% of the limit has never been used, not once</strong>. A middle
					article held {grouped(cost.median ?? 0)}, so the limit is
					<strong>{cost.timesMedian}</strong> times the article it usually reads. Measured over
					{cost.items} of the {cost.rowsRead} articles these days recorded; the rest are older than
					the cells this reads.
				{/if}
			</p>

			<p class="reads" data-context-cutoff data-context-cutoff-calls={cost.cutOff}>
				{#if cost.calls === 0}
					No call in these {days} days recorded why its reply stopped, so nothing here can say
					whether anything ran out of room.
				{:else if cost.cutOff === 0}
					Nothing has been cut short: across {grouped(cost.calls)} model calls the server never
					once said a reply stopped because it ran out of room. It said
					{cost.reasons.map((one) => `${one.reason} ${grouped(one.calls)} times`).join(', ')}.
				{:else}
					{grouped(cost.cutOff)} of {grouped(cost.calls)} model calls stopped because the reply
					ran out of room, which is a budget that no longer fits.
				{/if}
			</p>

			{#if cost.limits.length > 1}
				<p class="reads" data-context-limits-moved>
					The limit moved inside these {days} days - it was set to
					{cost.limits.map((one) => grouped(one)).join(' and ')} tokens - so the shares above are
					each article against its own limit and the rule is drawn at the configured
					{grouped(contextWindow)}.
				</p>
			{/if}

			<!-- Every run's own numbers, for a reader who cannot see the plot. The
			     chart is the shape of the question; this is the table it was made
			     from, and nothing is only in the picture. -->
			<ul class="sr-only" data-context-runs>
				{#each contextRuns as run (run.runId)}
					<li
						data-context-run={run.runId}
						data-context-largest={run.largest ?? ''}
						data-context-high={run.high ?? ''}
					>
						{#if run.largest === null}
							{run.runId}: no article recorded both the limit and its own tokens.
						{:else}
							{run.runId}: the longest article held {grouped(run.largest)} tokens,
							{run.largestPct === null ? 'an unrecorded share' : `${run.largestPct}%`} of the limit;
							{highName} held {run.high === null ? 'an unrecorded number' : grouped(run.high)}
							tokens,
							{run.highPct === null ? 'an unrecorded share' : `${run.highPct}%`}; over {run.items}
							{run.items === 1 ? 'article' : 'articles'}.
						{/if}
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
