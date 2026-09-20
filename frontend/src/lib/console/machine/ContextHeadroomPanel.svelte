<script lang="ts">
	/** Whether raising the truncation cap is even possible.
	 *
	 * The longest sequence each run saw, prompt and answer together, against the
	 * window the server was given. That is a question about the worst run in the
	 * span rather than about the newest one, which is why the panel draws one
	 * mark a run and keeps every run the span holds.
	 */
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { contextColumns, type ContextBar } from '$lib/charts/machine';
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
		modelChanges,
		chart,
		windowDays,
		days,
		runsRead
	}: {
		rows: readonly ContextBar[];
		start: string;
		end: string;
		contextWindow: number;
		modelChanges: readonly string[];
		chart: ChartConfig;
		windowDays: number;
		days: number;
		runsRead: number;
	} = $props();

	let contextWidth = $state<number | null>(null);
	let contextAt = $state<number | null>(null);

	const contextRuns = $derived(inSpan(rows, start, end));
	// The four shapes below are a function of the RUNS alone, so a resize reuses
	// them and only a new span rebuilds them. `firstOfDay`, the caption columns,
	// the boundary set and the domain used to sit inside the width-dependent
	// derives, so a drag re-derived every caption and re-scanned the rule list a
	// column; split out, a drag moves pixels and nothing else.
	const contextDates = $derived(firstOfDay(contextRuns));
	const contextData = $derived(contextColumns(contextRuns, contextWindow));
	const contextBoundaries = $derived(boundaryDates(modelChanges, contextDates));
	/** The domain the plot is drawn against. It is a function of the sequences
	 * and the window, never the width, so it is retained across a resize.
	 * Zero-anchored, and the window is one of its bounds, so the limit is a line
	 * on the plot rather than a number off the top. */
	const contextExtent = $derived([
		0,
		contextWindow,
		...contextRuns.flatMap((run) => [run.longest ?? 0, run.spare ?? 0])
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
			// run of that day carries it, so all its columns take the rule - which is
			// exactly what the scan did.
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
			.map((value, index) =>
				value === null ? '' : `${contextX[index]},${contextAtY(value)}`
			)
			.filter((point) => point !== '')
			.join(' ');
	}
	function contextAtY(value: number): number {
		return Math.round(contextY.scale(value) * 10) / 10;
	}
	/** The two series as polylines, built once a span-and-width rather than once
	 * a render: inlined in the template, both were rebuilt on every hover. */
	const contextSpareLine = $derived(line(contextRuns.map((run) => run.spare)));
	const contextLongestLine = $derived(line(contextRuns.map((run) => run.longest)));
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
		title="Context headroom"
		note="The longest sequence each run saw, prompt and answer together, against the window the server was given. One mark a run over the last {windowDays} days, oldest on the left. This is the panel that says whether raising the truncation cap is even possible - which is a question about the worst run in the span, not the newest."
	>
		{#if contextRuns.length === 0}
			<p class="empty" data-machine-panel-empty="context">
				No run in these {days} days recorded a longest sequence.
			</p>
		{:else}
			<div
				class="plot"
				data-context-window={contextWindow}
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
						aria-label="The longest sequence each of {contextRuns.length} runs saw, against the {grouped(
							contextWindow
						)}-token context window, over {days} days. One mark is one run, oldest on the left."
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

						<!-- The window is a rule and never a bar. A limit is a line a
						     series approaches; a bar beside a bar invites the reader to
						     compare two lengths and forget which one is the ceiling. -->
						<line
							x1={contextBox.left}
							x2={contextBox.right}
							y1={contextAtY(contextWindow)}
							y2={contextAtY(contextWindow)}
							stroke="var(--chart-marker)"
							stroke-width="1.5"
							data-context-limit={contextWindow}
						>
							<title>
								{`The server was given a ${grouped(contextWindow)}-token context window. A run cannot cross this line.`}
							</title>
						</line>
						<text
							x={contextBox.right}
							y={contextAtY(contextWindow) - 4}
							text-anchor="end"
							fill="var(--color-text-tertiary)"
							font-size="10"
							data-context-limit-label
						>
							{grouped(contextWindow)}-token window
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

						<!-- Spare capacity is derived - it is the window minus the
						     measurement - so it is drawn dotted to say it is not an
						     independent reading of anything. -->
						<polyline
							points={contextSpareLine}
							fill="none"
							stroke="var(--chart-3)"
							stroke-width="1.5"
							stroke-dasharray="2 3"
							data-context-series="spare"
						/>
						<g data-context-series="longest">
							<polyline
								points={contextLongestLine}
								fill="none"
								stroke="var(--chart-1)"
								stroke-width="2"
							/>
							{#each contextRuns as run, index (run.runId)}
								{#if run.longest !== null}
									<circle
										cx={contextX[index]}
										cy={contextAtY(run.longest)}
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

			<p class="reads" data-context-basis>
				{contextRuns.length}
				{contextRuns.length === 1 ? 'run' : 'runs'} of these {days} days recorded a longest
				sequence, out of {runsRead} the ledger could read. The worst of them reached
				<strong>{grouped(Math.max(0, ...contextRuns.map((run) => run.longest ?? 0)))}</strong>
				tokens of the {grouped(contextWindow)} the server was given.
			</p>

			<!-- Every run's own three numbers, for a reader who cannot see the
			     plot. The chart is the shape of the question; this is the table
			     it was made from, and nothing is only in the picture. -->
			<ul class="sr-only" data-context-runs>
				{#each contextRuns as run (run.runId)}
					<li data-context-run={run.runId} data-context-longest={run.longest ?? ''}>
						{#if run.longest === null}
							{run.runId}: no sequence length recorded, over {run.from}
							{run.outOf === null
								? 'shards, and this run manifest recorded no shard count'
								: `of ${run.outOf} shards`}.
						{:else}
							{run.runId}: {grouped(run.longest)} of {grouped(contextWindow)} tokens,
							{run.usedPct === null ? 'an unrecorded share' : `${run.usedPct}%`} used,
							{run.spare === null ? 'unrecorded' : grouped(run.spare)} spare, over {run.from}
							{run.outOf === null
								? 'shards, and this run manifest recorded no shard count'
								: `of ${run.outOf} shards`}.
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
