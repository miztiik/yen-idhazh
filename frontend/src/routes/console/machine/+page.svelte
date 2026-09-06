<script lang="ts">
	/** The hardware the model ran on, and how much it varied.
	 *
	 * The pipeline has written one row per shard per run to
	 * `state/runtime-counters.csv` since 2026-08-26 and, until this page, nothing
	 * had ever drawn a cell of it. That is not a cosmetic gap. Measured on the
	 * committed ledger, the fastest shard of a single run read its prompts 4.31x
	 * faster than the slowest shard of the SAME run, and every throughput figure
	 * this project has quoted was an average taken across that spread. So the
	 * shard is the unit on this page and every run figure carries how many shards
	 * it was made from.
	 *
	 * **Every figure over a span reads the control above it**, the same 7/14/30/90
	 * the other two routes carry and the same `idhazh:console-window` key, so a
	 * span picked on Pipelines is the span this route opens on. Each span is
	 * answered on the server, because the browser holds no ledger to re-aggregate.
	 *
	 * **A panel about one run does not follow it.** The shard board, the
	 * reading-against-writing split, the clock check and the latency curves are
	 * snapshots of one run or one day, and narrowing a span cannot narrow a
	 * single run. Each names what it is about instead.
	 *
	 * **Absence is drawn as absence.** `job_seconds` and `cpu_model` are empty on
	 * 24 of the 54 committed rows and the three host cells on 34 of them, because
	 * each landed on a day after the ledger started. Every one of those prints a
	 * dash or a sentence, never a zero: a server that read no tokens and a scrape
	 * that never happened are different facts.
	 */
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import Chart from '$lib/charts/Chart.svelte';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import ConsoleBand from '$lib/components/ConsoleBand.svelte';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import RateControl from '$lib/components/RateControl.svelte';
	import ShapeSwitch from '$lib/components/ShapeSwitch.svelte';
	import ShardBoard from '$lib/components/ShardBoard.svelte';
	import SpanPanel from './SpanPanel.svelte';
	import TargetBar from '$lib/components/TargetBar.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import {
		cacheChart,
		cacheColumns,
		clockColumns,
		clocksChart,
		contextColumns,
		costOf,
		curveOf,
		gib,
		latencyColumns,
		money,
		percentileChart,
		percentileColumns,
		seconds,
		tokenChart,
		PERCENTILES,
		RUNNER_MEMORY_BYTES
	} from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';
	import {
		chartWidth,
		columnStrip,
		dayColumnX,
		dayColumns,
		dayTicks,
		frame,
		linearAxis,
		modelRuleTitle,
		modelRules,
		noModelRuleNote,
		observeWidth,
		pointerReadout,
		readoutMarks,
		MODEL_RULE_ROW,
		type Frame
	} from '$lib/charts/frame';
	import { shortDate } from '$lib/format';
	import type { StackShape } from '$lib/charts/stacked';

	let { data } = $props();

	/** The same key the other two routes read, so the operator's choice of span
	 * follows him between them rather than resetting on every click. */
	const WINDOW_KEY = 'idhazh:console-window';

	const presets = $derived(data.console.window_presets);

	// svelte-ignore state_referenced_locally
	let windowDays = $state(data.console.default_window_days);
	/** False until a browser has run this page. */
	let ready = $state(false);

	onMount(() => {
		ready = true;
		if (typeof localStorage === 'undefined') return;
		const stored = Number(localStorage.getItem(WINDOW_KEY));
		if (presets.includes(stored) && stored !== windowDays) show(stored);
	});

	function show(days: number, remember = true) {
		windowDays = days;
		if (remember && typeof localStorage !== 'undefined') {
			localStorage.setItem(WINDOW_KEY, String(days));
		}
	}

	/** Nothing on this route is fetched. Every span it can draw is already
	 * inlined, so no preset costs a month file and none of them is priced. */
	function monthsFor(): number {
		return 0;
	}

	/** Every figure the open span answers, decided on the server for each span
	 * the control offers. The fallback is the span the document was drawn at, so
	 * a stored preset the config no longer offers cannot blank the page. */
	const view = $derived(
		data.windows[String(windowDays)] ?? data.windows[String(data.console.default_window_days)]
	);

	// The option a live chart hydrates from is rebuilt here rather than handed
	// over by `load`. Everything a load returns is serialised into the prerendered
	// document, and an option carries the magenta sentinels `toCssVariables` swaps
	// out of the SVG - so passing one across would ship a colour no reader may
	// ever see, and `charts.spec.ts` fails the build over exactly that. The server
	// draws the SVG; the browser redraws from the same numbers.
	//
	// The cache chart is the one that takes a shape. The server drew stacked, so
	// the first paint matches the prerendered document; picking `Lines` redraws
	// the identical values with no transform between them.
	let cacheShape = $state<StackShape>('bars');
	const cacheOption = $derived(cacheChart(view.cacheDays, cacheShape).option);
	const clocksOption = $derived(clocksChart(data.clocks.pairs).option);
	const newestCurve = $derived(data.newestTail === null ? [] : [curveOf(data.newestTail)]);
	const percentileOption = $derived(percentileChart(newestCurve).option);
	const inputOption = $derived(
		tokenChart(view.tokens, (run) => run.input, 'prompt tokens', '--chart-1').option
	);
	const outputOption = $derived(
		tokenChart(view.tokens, (run) => run.output, 'written tokens', '--chart-4').option
	);

	// The strips under every chart that has a column to land on. Built here from
	// the same arrays the options are, so a column the strip prints and a column
	// the chart drew can never be two different columns - which is why the two
	// that follow the span read `view` and the two that describe one run read
	// `data`.
	const cacheStrip = $derived(cacheColumns(view.cacheDays));
	const clockStrip = $derived(clockColumns(data.clocks.pairs));
	const percentileStrip = $derived(percentileColumns(newestCurve));
	/** The insets `percentileChart` draws its grid at. The strip's column centres
	 * are computed from them, so a pointer and the strip agree. */
	const PERCENTILE_GRID = { left: 60, right: 44 };
	/** One series each, and each still earns a strip: the axis carries the run's
		* day and the strip carries the run itself, so the bar a pointer is on is
		* the one place a run id and its count can be read together. These read the
		* open span, because the bars do. */
	const tokenRuns = $derived(view.tokens.map((run) => run.runId));
	const inputStrip = $derived(
		columnStrip(tokenRuns, [
			{
				label: 'Prompt tokens',
				colour: 'var(--chart-1)',
				value: (index) => grouped(view.tokens[index]?.input ?? 0)
			},
			{
				label: 'Items that reported both counts',
				colour: '',
				value: (index) => grouped(view.tokens[index]?.items ?? 0)
			}
		])
	);
	const outputStrip = $derived(
		columnStrip(tokenRuns, [
			{
				label: 'Written tokens',
				colour: 'var(--chart-4)',
				value: (index) => grouped(view.tokens[index]?.output ?? 0)
			},
			{
				label: 'Items that reported both counts',
				colour: '',
				value: (index) => grouped(view.tokens[index]?.items ?? 0)
			}
		])
	);

	// ---------------------------------------------------------------------
	// The two run-by-run charts
	//
	// Both draw one mark a RUN rather than one a day, so the span decides which
	// rows to keep and nothing else. The rows are carried once, bounded to the
	// widest preset, and filtered here - the server filters the same pair of
	// dates the same way, so the chart it drew and the chart a browser redraws
	// are built from one set.
	// ---------------------------------------------------------------------

	const inSpan = <T extends { date: string }>(rows: readonly T[]): T[] =>
		rows.filter((row) => row.date >= view.start && row.date <= view.end);

	/** One date a run, with a repeat blanked.
	 *
	 * `modelRules` draws a rule where a drawn column's date is a boundary. A day
	 * with three runs is three columns carrying one date, and drawing three rules
	 * for one change would say the pipeline changed three times. The first run of
	 * the day keeps the date, so the rule falls on the leading edge of the day -
	 * which is where the shared helper puts it on a calendar axis too.
	 */
	function firstOfDay(rows: readonly { date: string }[]): string[] {
		return rows.map((row, index) => (rows[index - 1]?.date === row.date ? '' : row.date));
	}

	/** A date axis whose columns are runs: a repeated day is labelled once.
	 *
	 * `dayTicks` owns the measured thinning and the anchoring. What it cannot
	 * know is that two neighbouring columns can be the same day, and two identical
	 * dates side by side read as a chart that lost its order. Read backwards, so
	 * the NEWER of two runs on one day keeps the label: it is the end of the axis
	 * and the column an operator reads first. The tick mark stays either way - a
	 * reader counting columns needs the grid.
	 */
	function runTicks(dates: readonly string[], columns: readonly number[]) {
		const ticks = dayTicks(dates, { density: data.chart.tick_density, columns });
		let carried = '';
		for (let at = ticks.length - 1; at >= 0; at -= 1) {
			if (ticks[at].text === '') continue;
			if (ticks[at].text === carried) ticks[at] = { ...ticks[at], text: '' };
			else carried = ticks[at].text;
		}
		return ticks;
	}

	// --- Context headroom ------------------------------------------------

	/** How much room the oldest and newest marks need inside the plot. */
	const MARK_PAD = 6;

	let contextWidth = $state<number | null>(null);
	let contextAt = $state<number | null>(null);

	const contextRuns = $derived(inSpan(data.series.context));
	const contextBox = $derived(
		frame(chartWidth(contextWidth, data.chart.width_px), data.chart.height_px, {
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
	/** The window is in the domain, so the limit is a line on the plot rather
	 * than a number off the top of it. Zero-anchored: the height of a mark is
	 * the size of the sequence. */
	const contextY = $derived(
		linearAxis(
			[
				0,
				data.contextWindow,
				...contextRuns.flatMap((run) => [run.longest ?? 0, run.spare ?? 0])
			],
			[contextBox.bottom, contextBox.top]
		)
	);
	const contextAxis = $derived(
		runTicks(
			contextRuns.map((run) => run.date),
			contextX
		)
	);
	const contextRules = $derived(
		modelRules(data.modelChanges, firstOfDay(contextRuns), contextX)
	);
	const contextStrip = $derived(
		contextColumns(contextRuns, data.contextWindow).map((column, index) => ({
			...column,
			x: contextX[index] ?? 0,
			rows: contextRules.some((rule) => rule.date === contextRuns[index]?.date)
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

	// --- Run latency, one plot per percentile ----------------------------

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

	const tailRuns = $derived(inSpan(data.series.latency));
	const tailW = $derived(chartWidth(tailWidth, data.chart.width_px));
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
		linearAxis(
			tailRuns.flatMap((run) => run.ms.map((ms) => ms / 1000)),
			[TAIL_CELL_PX - TAIL_MARGIN.bottom, TAIL_MARGIN.top]
		)
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
			tailX
		)
	);
	const tailRules = $derived(modelRules(data.modelChanges, firstOfDay(tailRuns), tailX));
	const tailStrip = $derived(
		latencyColumns(tailRuns).map((column, index) => ({
			...column,
			x: tailX[index] ?? 0,
			rows: tailRules.some((rule) => rule.date === tailRuns[index]?.date)
				? [...column.rows, MODEL_RULE_ROW]
				: column.rows
		}))
	);
	const tailMarks = $derived(readoutMarks(tailStrip));
	const tailResting = $derived(tailStrip.at(-1) ?? null);
	const tailReadout = $derived(tailAt === null ? tailResting : (tailStrip[tailAt] ?? tailResting));
	function tailLine(at: number): string {
		return tailRuns
			.map((run, index) => `${tailX[index]},${tailAtY(at, (run.ms[at] ?? 0) / 1000)}`)
			.join(' ');
	}
	const tailSpan = $derived(
		tailRuns.length === 0
			? ''
			: `${shortDate(tailRuns[0].date)} to ${shortDate(tailRuns[tailRuns.length - 1].date)}`
	);

	// One shared rate for every cost figure below. It starts at the configured
	// pair so the first paint matches the prerendered document, and `RateControl`
	// replaces it on mount if the operator has typed one before. Deliberately not
	// derived: after mount the operator owns these two numbers, not the payload.
	// svelte-ignore state_referenced_locally
	let inputRate = $state(data.rate.inputPerMillion);
	// svelte-ignore state_referenced_locally
	let outputRate = $state(data.rate.outputPerMillion);
	let rateSource = $state<'configured' | 'yours'>('configured');

	const rate = $derived({
		currency: data.rate.currency,
		inputPerMillion: inputRate,
		outputPerMillion: outputRate
	});
	const inputCost = $derived(costOf({ input: view.tokenTotals.input, output: 0 }, rate));
	const outputCost = $derived(costOf({ input: 0, output: view.tokenTotals.output }, rate));
	const totalCost = $derived(inputCost + outputCost);
	const perArticle = $derived(
		view.tokenTotals.items === 0 ? null : totalCost / view.tokenTotals.items
	);
</script>

<svelte:head>
	<title>Console: Hardware &mdash; {data.ui.site_title}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<section class="py-6" data-surface="operator" data-console-route="machine">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Console</h1>

	<ConsoleNav routes={data.routes} active="machine" />
	<ConsoleBand band={data.band} />
	<WindowControl days={windowDays} {presets} {monthsFor} {ready} onChange={show} />

	<!-- One sentence, no chart. It is what stops this route reading as a page
	     about a machine nothing ran on. -->
	<p class="console-carry" data-console-carry="pipelines">
		{data.carries.machine}
		<a class="carry-link" href="{base}/console/">Pipelines &rarr;</a>
	</p>

	<p
		class="mt-4 text-[0.9375rem] text-text-secondary"
		data-machine="intro"
		data-windowed="machine-runs"
		data-window-days={windowDays}
	>
		{view.runsRead === 0
			? `No run in these ${view.days} days committed a counters row.`
			: `${view.runsRead} ${view.runsRead === 1 ? 'run' : 'runs'} in these ${view.days} days committed counters the model server wrote itself.`}
		{view.start} to {view.end}. Every figure below is the model server's own count, read at build
		time and published nowhere.
	</p>

	<!-- What the recording was doing, before anything says what it recorded.
	     None of these is an error and none is styled as one: each states a fact
	     about the instrument, at body size, in the route it governs. A day the
	     scrape never ran and a day the machine did nothing draw the same gap,
	     and only a sentence can tell them apart. -->
	{#if view.recording.off}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="off">
			{view.recording.off}
		</p>
	{/if}
	{#if view.recording.sampled}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="sampled">
			{view.recording.sampled}
		</p>
	{/if}
	{#if view.recording.startedMidWindow}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="started">
			{view.recording.startedMidWindow}
		</p>
	{/if}
	{#if view.recording.scoresOnly}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="scores-only">
			{view.recording.scoresOnly}
		</p>
	{/if}

	{#if view.refused.length > 0}
		<!-- Named, never dropped. A run count that quietly excludes one is a run
		     count nobody can check, and the cause is a real defect in how the
		     ledger is merged rather than a rendering choice. It follows the window
		     without declaring it: a clean span renders nothing at all, and a
		     surface that comes and goes cannot report a day count. -->
		<div class="refused" data-machine-refused={view.refused.length}>
			<p class="refused-head">
				{view.refused.length}
				{view.refused.length === 1 ? 'run is' : 'runs are'} left out of every windowed figure on this
				page.
			</p>
			<ul>
				{#each view.refused as run (run.runId)}
					<li data-refused-run={run.runId}>
						<strong>{run.runId}</strong> holds {run.rows} rows: {run.why}. Summing them would
						report a machine that never existed, so nothing here reads the run at all.
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<!-- The panels below are one run or one day, so the control above does not
	     reach them. A window is a span; a snapshot is not something a span can
	     narrow, and a board that emptied at 7 days would say the run had stopped
	     existing. -->
	<p class="mt-4 text-[0.8125rem] text-text-tertiary" data-window-exempt="newest-run">
		{data.newestRunId === null
			? 'The panels below read the newest run each ledger holds, and do not follow the window. No run has committed a counters row yet.'
			: `The panels below do not follow the window; each reads one run or one day, because a span cannot narrow a single run. The hardware panels read the newest run the counters hold, ${data.newestRunId}. The span breakdown reads its own ledger and names the run it found.`}
	</p>

	<Panel
		title="Shards of the newest run"
		note="One row per shard, ranked by how long its job took. It answers whether a slow day was the work or the machine: a long bar at a normal read rate is a lot of articles, and a long bar at a quarter of its neighbour's read rate is the host."
		wide
	>
		<ShardBoard board={data.board} timeoutMinutes={data.shardTimeoutMinutes} />
	</Panel>

	<Panel
		title="Where a shard's clock went"
		note="Each shard of the newest traced run as one bar of its whole clock: the four sub-steps no ledger column times, the rest of the item work, and - on the right, drawn hollow - the overhead between items that no span covers. The item time plus that overhead is the shard's whole clock, so the residual is a figure that reconciles rather than an estimate."
		wide
	>
		<SpanPanel breakdown={data.spanBreakdown} />
	</Panel>

	<Panel
		title="Peak memory, and how near the runner's ceiling it got"
		note="What llama-server's own high-water mark reached on each shard of the newest run. The run's figure is the LARGEST of these and never their total: shards are separate jobs on separate hosts, so adding them would report a machine that never existed. Every bar runs to the same 16 GB the runner has, so their lengths compare."
	>
		{#if data.memory.empty}
			<p class="empty" data-machine-panel-empty="memory">
				No shard of the newest run recorded a memory high-water mark. The cell landed on
				2026-08-30, so a run older than that reports nothing here - which is a missing reading and
				not a run that used no memory.
			</p>
		{:else}
			<div class="memory" data-peak-memory={data.memory.runId}>
				<div data-memory="run" data-memory-high-water={data.memory.highWater ?? ''}>
					<TargetBar
						marks={data.memory.marks}
						label="The run's high-water mark"
						valueText={gib(data.memory.highWater)}
						targetText="of the runner's {gib(RUNNER_MEMORY_BYTES)} - {data.memory
							.pctOfRunner}%, the largest of the {data.memory.from} shards below and never their
						total"
						emptyNote="This run recorded no memory high-water mark."
					/>
				</div>
				{#each data.memory.shards as shard (shard.shard)}
					<div data-memory-shard={shard.shard} data-memory-bytes={shard.bytes}>
						<TargetBar
							marks={shard.marks}
							label="Shard {shard.shard}"
							valueText={gib(shard.bytes)}
							targetText="of the runner's {gib(RUNNER_MEMORY_BYTES)} - {Math.round(
								(shard.bytes / RUNNER_MEMORY_BYTES) * 100
							)}%"
							emptyNote="This shard recorded no memory high-water mark."
						/>
					</div>
				{/each}
			</div>
			<!-- No tint and no band. Nobody has agreed how near 16 GB is too near,
			     and a colour would publish a threshold that does not exist. -->
			<p class="reads" data-memory-basis>
				Over {data.memory.from} of the run's {data.memory.outOf} shards.
				{#if data.memory.from < data.memory.outOf}
					The other {data.memory.outOf - data.memory.from} recorded nothing, and are left out rather
					than drawn as shards that used no memory.
				{/if}
				A run the reader refuses is in none of this: its rows cannot be made into one run, so it has
				no shards to take a maximum over.
			</p>
		{/if}
	</Panel>

	<Panel
		title="Reading against writing"
		note="Two rows over the same shards: how the model server's seconds split, and how its tokens split. Read the mismatch between them - that is the price of a written token."
	>
		{#if data.split.empty}
			<p class="empty" data-machine-panel-empty="reading-writing">
				No shard of the newest run reported all four counters, so there is nothing to split.
			</p>
		{:else}
			<div class="splits" data-reading-writing={data.split.runId}>
				{#each data.split.rows as row (row.label)}
					<div class="split-row" data-split-row={row.label} data-split-read-pct={row.readPct}>
						<p class="split-head">
							<span>{row.label}</span>
							<span class="tabular-nums">{row.totalText}</span>
						</p>
						<div
							class="track"
							role="img"
							aria-label="{row.label}: {row.readText} reading against {row.writeText} writing, {row.readPct} percent of it reading."
						>
							<span class="seg read" style="inline-size: {row.readWidth}"></span>
							<span class="seg write" style="inline-size: {row.writeWidth}"></span>
						</div>
						<p class="split-legend">
							<span class="key read"></span>reading {row.readText} ({row.readPct}%)
							<span class="key write"></span>writing {row.writeText} ({100 - row.readPct}%)
						</p>
					</div>
				{/each}
			</div>
			<p class="reads" data-reading-writing-sentence>
				Reading took {data.split.rows[0].readPct} percent of the seconds and
				{data.split.rows[1].readPct} percent of the tokens.
				{#if data.split.readTokensPerSecond !== null && data.split.writeTokensPerSecond !== null}
					Reading runs at {data.split.readTokensPerSecond.toFixed(2)} tokens a second and writing at
					{data.split.writeTokensPerSecond.toFixed(2)}, so a written token costs
					<strong>{(data.split.writeCostRatio ?? 0).toFixed(1)}x</strong> a read one.
				{/if}
				Over {data.split.from} of the run's {data.split.outOf} shards.
			</p>
		{/if}
	</Panel>

	<div
		data-windowed="machine-cache"
		data-window-days={windowDays}
		data-model-rule="no"
		data-model-rule-name="machine-cache"
		data-model-rule-none="a change moves this, and an engine-drawn axis carries no rule yet"
	>
		<Panel
			title="Prompt cache"
			note="Prompt tokens the server read, against the ones it reused instead of reading, over the last {windowDays} days. Read whether a bigger cache would save wall clock."
		>
			{#if view.cacheDays.length === 0}
				<p class="empty" data-machine-panel-empty="cache">
					No run in these {view.days} days reported both a read count and a cached count, so there is
					no split to draw.
				</p>
			{:else}
				<!-- Keyed on the span, so a chart hydrated at one window is torn down
				     and rebuilt at the next. The engine takes its option once, at
				     hydration, and never looks at it again. -->
				{#key windowDays}
					<Chart
						svg={data.cacheSvg ?? ''}
						option={cacheOption}
						width={data.chart.width_px}
						height={data.chart.height_px}
						label="Prompt tokens per day over {view.days} days, split into the tokens the model server read and the tokens it served from its own cache. One column is one day."
						columns={cacheStrip}
						readoutName="cache"
						readoutMaxShare={data.chart.readout_max_share}
						restingNote=", the newest day"
						hint="Point at a day to read both halves. Left and Right step through the days, Escape returns to the newest."
					/>
				{/key}
				<!-- Stacked says how many prompt tokens the day needed; lines say whether
				     the read half fell while the cached half rose. One array, two shapes,
				     nothing re-shaped between them. -->
				<ShapeSwitch bind:shape={cacheShape} name="cache" label="How to draw the prompt cache" />
				<!-- No threshold marker and no tint. Nobody has agreed a floor for this,
				     and a tint would invent one and publish it. -->
				<ul class="shares" data-cache-days>
					{#each view.cacheDays as day (day.date)}
						<li data-cache-day={day.date} data-cache-pct={day.cachedPct ?? ''}>
							<strong>{day.date}</strong>: the cache covered {day.cachedPct}% of the
							{grouped(day.read + day.cached)} prompt tokens
							{day.runs === 1 ? 'that run' : `those ${day.runs} runs`} needed.
						</li>
					{/each}
				</ul>
			{/if}
		</Panel>
	</div>

	<div
		data-windowed="machine-context"
		data-window-days={windowDays}
		data-model-rule={contextRuns.length > 1 ? 'yes' : 'no'}
		data-model-rule-name="machine-context"
		data-model-rule-none={contextRuns.length > 1
			? undefined
			: 'one run drawn, so there is no edge between two of them to draw between'}
		data-model-rule-from={contextRuns[0]?.date ?? ''}
		data-model-rule-to={contextRuns.at(-1)?.date ?? ''}
	>
		<Panel
			title="Context headroom"
			note="The longest sequence each run saw, prompt and answer together, against the window the server was given. One mark a run over the last {windowDays} days, oldest on the left. This is the panel that says whether raising the truncation cap is even possible - which is a question about the worst run in the span, not the newest."
		>
			{#if contextRuns.length === 0}
				<p class="empty" data-machine-panel-empty="context">
					No run in these {view.days} days recorded a longest sequence.
				</p>
			{:else}
				<div
					class="plot"
					data-context-window={data.contextWindow}
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
								data.contextWindow
							)}-token context window, over {view.days} days. One mark is one run, oldest on the left."
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
								y1={contextAtY(data.contextWindow)}
								y2={contextAtY(data.contextWindow)}
								stroke="var(--chart-marker)"
								stroke-width="1.5"
								data-context-limit={data.contextWindow}
							>
								<title>
									{`The server was given a ${grouped(data.contextWindow)}-token context window. A run cannot cross this line.`}
								</title>
							</line>
							<text
								x={contextBox.right}
								y={contextAtY(data.contextWindow) - 4}
								text-anchor="end"
								fill="var(--color-text-tertiary)"
								font-size="10"
								data-context-limit-label
							>
								{grouped(data.contextWindow)}-token window
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
								points={line(contextRuns.map((run) => run.spare))}
								fill="none"
								stroke="var(--chart-3)"
								stroke-width="1.5"
								stroke-dasharray="2 3"
								data-context-series="spare"
							/>
							<g data-context-series="longest">
								<polyline
									points={line(contextRuns.map((run) => run.longest))}
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
						maxShare={data.chart.readout_max_share}
						resting={contextAt === null}
						restingNote=", the last run"
						hint="Point at a run to read it. Left and Right step through them, Escape returns to the last."
					/>
				</div>

				{#if contextRules.length === 0 && contextRuns.length > 1}
					<p class="reads">
						<span data-model-rule-empty="machine-context">{noModelRuleNote(view.days)}</span>
					</p>
				{/if}

				<p class="reads" data-context-basis>
					{contextRuns.length}
					{contextRuns.length === 1 ? 'run' : 'runs'} of these {view.days} days recorded a longest
					sequence, out of {view.runsRead} the ledger could read. The worst of them reached
					<strong>{grouped(Math.max(0, ...contextRuns.map((run) => run.longest ?? 0)))}</strong>
					tokens of the {grouped(data.contextWindow)} the server was given.
				</p>

				<!-- Every run's own three numbers, for a reader who cannot see the
				     plot. The chart is the shape of the question; this is the table
				     it was made from, and nothing is only in the picture. -->
				<ul class="sr-only" data-context-runs>
					{#each contextRuns as run (run.runId)}
						<li data-context-run={run.runId} data-context-longest={run.longest ?? ''}>
							{run.runId}: {grouped(run.longest ?? 0)} of {grouped(data.contextWindow)} tokens,
							{run.usedPct}% used, {grouped(run.spare ?? 0)} spare, over {run.from} of {run.outOf} shards.
						</li>
					{/each}
				</ul>
			{/if}
		</Panel>
	</div>

	<Panel
		title="The two clocks, compared"
		note="Prompt tokens a second, counted twice: once by the item ledger and once by the model server itself. The runtime ledger was created for this check and nothing performed it on a screen. A day where the two disagree is a day whose rates cannot be trusted."
	>
		{#if data.clocksSvg === null}
			<p class="empty" data-machine-panel-empty="clocks">
				One of the two instruments recorded nothing for the newest run, so there is nothing to
				compare. That is a missing reading, not an agreement.
			</p>
		{:else}
			<Chart
				svg={data.clocksSvg}
				option={clocksOption}
				width={data.chart.width_px}
				height={data.chart.height_px}
				label="Prompt tokens a second as the item ledger counted them, beside the same figure as the model server counted it, per {data
					.clocks.grain}."
				columns={clockStrip}
				readoutName="clocks"
				readoutMaxShare={data.chart.readout_max_share}
				restingNote=", the last one"
				hint="Point at a {data.clocks.grain} to read both instruments. Left and Right step through them, Escape returns to the last."
			/>
			<ul class="shares" data-clock-pairs={data.clocks.grain}>
				{#each data.clocks.pairs as pair (pair.label)}
					<li data-clock-pair={pair.label} data-clock-gap={pair.gapPct?.toFixed(2) ?? ''}>
						<strong>{pair.label}</strong>:
						{#if pair.gapPct === null}
							one of the two instruments recorded nothing here.
						{:else}
							the ledger reads {(pair.ledger ?? 0).toFixed(2)} and the server
							{(pair.server ?? 0).toFixed(2)} tokens a second -
							<strong>{pair.gapPct.toFixed(2)}% apart</strong>,
							{pair.agrees ? 'inside' : 'past'} the {data.clocksTolerancePct}% the reconciliation
							audit allows.
						{/if}
					</li>
				{/each}
			</ul>
			<p class="reads" data-clock-grain={data.clocks.grain}>
				{#if data.clocks.grain === 'shard'}
					Compared per shard: all {data.clocks.itemRows} item rows of this run carry a shard.
				{:else}
					Compared per run, not per shard: {data.clocks.shardRows} of
					{data.clocks.itemRows} item rows of this run carry a shard, and a shard the ledger cannot
					name cannot be matched to the server that ran it.
				{/if}
			</p>
		{/if}
	</Panel>

	<div data-windowed="machine-host" data-window-days={windowDays}>
		<Panel
			title="The host under the newest run"
			note="What the machine and the server did outside the model call. Each figure carries its ceiling: a counter without one is not a measurement. Each also carries its span over the last {windowDays} days, which is what says whether the newest run was unusual."
		>
			<dl class="host">
				<div data-host="processors">
					<dt>Processors drawn</dt>
					<dd>
						{#if data.host.cpuModels === null || data.host.cpuModels.value === null}
							<span class="absent">Not recorded on this run.</span>
						{:else}
							{data.host.cpuModels.value.join('; ')}
							<span class="unit">
								over {data.host.cpuModels.from} of {data.host.cpuModels.outOf} shards
							</span>
						{/if}
					</dd>
				</div>

				<div data-host="cpu-busy" data-host-value={data.host.cpuBusy?.value ?? ''}>
					<dt>Least busy shard</dt>
					<dd>
						{#if data.host.cpuBusy === null || data.host.cpuBusy.value === null}
							<span class="absent">Not recorded on this run.</span>
						{:else}
							{data.host.cpuBusy.value.toFixed(2)}% of every processor second
							<span class="unit">
								Near 100 is the expected reading, so the gap is the share of that shard's job spent
								waiting rather than computing. Over these {view.days} days the lowest reading ran
								{(view.cpuBusySpan.low ?? 0).toFixed(2)}% to
								{(view.cpuBusySpan.high ?? 0).toFixed(2)}%, on
								{view.cpuBusySpan.from} of {view.cpuBusySpan.outOf} runs.
							</span>
						{/if}
					</dd>
				</div>

				<!-- The newest run's own high-water mark and its shards are a panel of
				     their own above. What belongs here is the other half of the
				     question - whether that run was unusual over the span - and
				     printing the bar again would be one fact drawn twice. -->
				<div data-host="peak-memory" data-host-value={view.peakRssSpan.high ?? ''}>
					<dt>Peak memory over the span</dt>
					<dd>
						{#if view.peakRssSpan.high === null}
							<span class="absent">No run in this span recorded a memory high-water mark.</span>
						{:else}
							{gib(view.peakRssSpan.high)} at the highest
							<span class="unit">
								{gib(view.peakRssSpan.low)} at the lowest, over these {view.days} days, on
								{view.peakRssSpan.from} of {view.peakRssSpan.outOf} runs. Each of those is itself
								the largest of a run's shards. The newest run's own shards are drawn above.
							</span>
						{/if}
					</dd>
				</div>

				<div data-host="model-load" data-host-value={data.host.modelLoad?.value ?? ''}>
					<dt>Opening the weights</dt>
					<dd>
						{#if data.host.modelLoad === null || data.host.modelLoad.value === null}
							<span class="absent">Not recorded on this run.</span>
						{:else}
							{grouped(Math.round(data.host.modelLoad.value))} ms on its slowest shard
							<span class="unit">
								Over these {view.days} days: {grouped(
									Math.round(view.modelLoadSpan.low ?? 0)
								)} to {grouped(Math.round(view.modelLoadSpan.high ?? 0))} ms, on
								{view.modelLoadSpan.from} of {view.modelLoadSpan.outOf} runs.
							</span>
						{/if}
					</dd>
				</div>

				<!-- One line of text, not a chart. It reads 1.0 on every row the ledger
				     holds because `models.inference.n_parallel` is 1, and it earns a
				     chart the day that knob moves. -->
				<div data-host="batching" data-batching={view.batching.highest ?? ''}>
					<dt>Batching</dt>
					<dd>
						{#if view.batching.highest === null}
							<span class="absent">No run in this span reported slots per decode.</span>
						{:else if view.batching.highest <= 1}
							Off; every decode served one request.
							<span class="unit">
								1.0 slot a decode on all {view.batching.from} of {view.batching.outOf} runs that
								reported it.
							</span>
						{:else}
							Up to {view.batching.highest.toFixed(2)} slots a decode.
							<span class="unit">Over {view.batching.from} of {view.batching.outOf} runs.</span>
						{/if}
					</dd>
				</div>
			</dl>
		</Panel>
	</div>

	<div
		data-windowed="machine-latency"
		data-window-days={windowDays}
		data-model-rule={tailRuns.length > 1 ? 'yes' : 'no'}
		data-model-rule-name="machine-latency"
		data-model-rule-none={tailRuns.length > 1
			? undefined
			: 'one run drawn, so there is no edge between two of them to draw between'}
		data-model-rule-from={tailRuns[0]?.date ?? ''}
		data-model-rule-to={tailRuns.at(-1)?.date ?? ''}
	>
		<Panel
			title="How the tail moved"
			note="One plot a percentile, one mark a run, over the last {windowDays} days. Five lines on one chart is a bundle a reader has to untangle by colour; separated, each is a trend read in one look. All five share one scale, which is the point of the arrangement - a p99 twenty times its own p50 has to look twenty times taller, and five plots on five scales would draw the same shape five times."
		>
			{#if tailRuns.length === 0}
				<p class="empty" data-machine-panel-empty="latency">
					No run in these {view.days} days timed {data.latency.floor} items, which is the floor
					below which a p99 is just the last item.
				</p>
			{:else}
				<div class="plot" data-readout-columns={tailStrip.length}>
					<div use:observeWidth={(px) => (tailWidth = px)}>
						<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
						<svg
							class="w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
							height={tailH}
							viewBox={`0 0 ${tailW} ${tailH}`}
							role="img"
							tabindex="0"
							aria-label="Per-item model time at the 50th, 75th, 90th, 95th and 99th percentile, one plot each and one mark per run, {tailSpan}, over {view.days} days. All five plots share one scale."
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
										points={tailLine(at)}
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
									stroke="var(--color-text-tertiary)"
									stroke-dasharray="3 3"
									data-model-rule-line={rule.date}
								>
									<title>{modelRuleTitle(rule.date)}</title>
								</line>
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
						readout={tailReadout}
						name="latency"
						maxShare={data.chart.readout_max_share}
						resting={tailAt === null}
						restingNote=", the last run"
						hint="Point at a run to read every percentile of it at once. Left and Right step through the runs, Escape returns to the last."
					/>
				</div>

				{#if tailRules.length === 0 && tailRuns.length > 1}
					<p class="reads">
						<span data-model-rule-empty="machine-latency">{noModelRuleNote(view.days)}</span>
					</p>
				{/if}

				<p class="reads" data-latency-note>
					{tailRuns.length}
					{tailRuns.length === 1 ? 'run' : 'runs'} of these {view.days} days. The value is
					<code>summarize_ms</code>, the whole model call for one item, and a percentile is
					interpolated linearly between the two nearest ranks - at about a hundred items the
					nearest-rank rule and this one disagree by more than the difference between two runs, so
					the rule is named rather than assumed. Runs are never pooled: two runs of one day draw
					different processors.
					{#if data.latency.tooFew.length > 0}
						{data.latency.tooFew.length}
						{data.latency.tooFew.length === 1 ? 'run' : 'runs'} timed fewer than
						{data.latency.floor} items and {data.latency.tooFew.length === 1 ? 'is' : 'are'} printed
						rather than drawn:
						{data.latency.tooFew.map((run) => `${run.runId} (${run.items})`).join(', ')}.
					{/if}
				</p>

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

	<Panel
		title="How long the newest run's tail was"
		note="The whole distribution of one run at once, which is a different question from whether the tail is growing. It reads the newest run the item ledger timed, so it holds still while the window moves."
	>
		{#if data.percentileSvg === null || data.newestTail === null}
			<p class="empty" data-machine-panel-empty="percentiles">
				No run the item ledger holds timed {data.latency.floor} items, which is the floor below
				which a p99 is just the last item.
			</p>
		{:else}
			<div
				data-window-exempt="newest-run-tail"
				data-model-rule="no"
				data-model-rule-name="machine-tail"
				data-model-rule-none="one run's own distribution, so no day edge falls inside it"
			>
				<p class="mt-1 text-[0.8125rem] text-text-tertiary">
					{data.newestTail.runId}, on {data.newestTail.date}. This panel does not follow the window.
				</p>
				<Chart
					svg={data.percentileSvg}
					option={percentileOption}
					width={data.chart.width_px}
					height={data.chart.height_px}
					label="Per-item model time at the 50th, 75th, 90th, 95th and 99th percentile for run {data
						.newestTail.runId}."
					columns={percentileStrip}
					readoutName="percentiles"
					readoutMaxShare={data.chart.readout_max_share}
					grid={PERCENTILE_GRID}
					restingNote=", the slowest one in a hundred"
					hint="Point at a percentile to read it. Left and Right step through them, Escape returns to p99."
				/>
			</div>
			<p class="reads" data-percentile-note>
				<strong>{data.newestTail.runId}</strong> timed {grouped(data.newestTail.items)} items. Its
				slowest one in a hundred took
				<strong>{seconds((data.newestTail.ms.at(-1) ?? 0) / 1000)}</strong>
				against {seconds((data.newestTail.ms[0] ?? 0) / 1000)} for a normal one.
				{#if data.latency.shardRows === data.latency.itemRows && data.latency.itemRows > 0}
					Every item row the ledger holds carries a shard, so a curve per shard is possible; twenty
					overlaid curves is not a chart, so the shard is the unit of the board above and of the
					clock check.
				{:else}
					{grouped(data.latency.shardRows)} of {grouped(data.latency.itemRows)} item rows carry a
					shard, so the curve is per run.
				{/if}
			</p>
		{/if}
	</Panel>

	<div
		data-windowed="machine-tokens"
		data-window-days={windowDays}
		data-model-rule="no"
		data-model-rule-name="machine-tokens"
		data-model-rule-none="one bar a run, so there is no day edge to draw between"
	>
		<Panel
			title="Tokens per run"
			note="Prompt tokens and written tokens, one bar per run over the last {windowDays} days. They are different quantities with different prices, so each carries its own axis."
		>
			{#if view.tokens.length === 0}
				<p class="empty" data-machine-panel-empty="tokens">
					No run in these {view.days} days recorded both a prompt count and a written count.
				</p>
			{:else}
				<div class="pair">
					<!-- Keyed on the span for the same reason the cache chart is, and the
					     readouts sit inside the key with the charts: a strip built at one
					     window and a chart drawn at another would name two different runs. -->
					{#key windowDays}
						<figure class="pane" data-token-chart="input">
							<figcaption>Prompt tokens</figcaption>
							<Chart
								svg={data.inputSvg ?? ''}
								option={inputOption}
								width={data.chart.width_px}
								height={data.chart.height_px}
								label="Prompt tokens each run sent to the model over {view.days} days. One bar is one run."
								columns={inputStrip}
								readoutName="tokens-input"
								readoutMaxShare={data.chart.readout_max_share}
								grid={data.inputGrid}
								restingNote=", the last run"
								hint="Point at a run to read it. Left and Right step through them, Escape returns to the last."
							/>
						</figure>
						<figure class="pane" data-token-chart="output">
							<figcaption>Written tokens</figcaption>
							<Chart
								svg={data.outputSvg ?? ''}
								option={outputOption}
								width={data.chart.width_px}
								height={data.chart.height_px}
								label="Tokens each run's answers were made of over {view.days} days. One bar is one run."
								columns={outputStrip}
								readoutName="tokens-output"
								readoutMaxShare={data.chart.readout_max_share}
								grid={data.outputGrid}
								restingNote=", the last run"
								hint="Point at a run to read it. Left and Right step through them, Escape returns to the last."
							/>
						</figure>
					{/key}
				</div>
				<p class="reads" data-token-totals>
					{grouped(view.tokenTotals.input)} prompt tokens and {grouped(view.tokenTotals.output)}
					written, over {view.tokens.length}
					{view.tokens.length === 1 ? 'run' : 'runs'} and {grouped(view.tokenTotals.items)} items.
				</p>
			{/if}
		</Panel>
	</div>

	<div data-windowed="machine-cost" data-window-days={windowDays}>
		<Panel
			title="What this would have cost somewhere else"
			note="A counterfactual, never a bill, over the last {windowDays} days. Nothing bills us - Actions minutes are free on a public repository - which is why the wall clock alone cannot say whether the runner time was a good trade. Priced at a hosted provider's rate, it can."
			tone="info"
		>
			{#if view.tokens.length === 0}
				<p class="empty" data-machine-panel-empty="cost">
					No run in these {view.days} days recorded a token count, so there is nothing to price.
				</p>
			{:else}
				<RateControl
					configured={data.rate}
					bind:inputRate
					bind:outputRate
					bind:source={rateSource}
				/>

				<dl class="cost" data-cost-figures data-cost-source={rateSource}>
					<div data-cost="input">
						<dt>Reading the prompts</dt>
						<dd class="tabular-nums">{money(inputCost, rate.currency, 2)}</dd>
					</div>
					<div data-cost="output">
						<dt>Writing the answers</dt>
						<dd class="tabular-nums">{money(outputCost, rate.currency, 2)}</dd>
					</div>
					<div data-cost="total">
						<dt>These {view.days} days</dt>
						<dd class="tabular-nums">{money(totalCost, rate.currency, 2)}</dd>
					</div>
					<div data-cost="per-article">
						<dt>An article</dt>
						<dd class="tabular-nums">
							{perArticle === null ? '-' : money(perArticle, rate.currency, 4)}
						</dd>
					</div>
				</dl>

				<p class="reads" data-cost-basis>
					What {view.tokens.length}
					{view.tokens.length === 1 ? 'run' : 'runs'} would have cost at that rate, if a hosted
					provider had done the work instead of the runner. It is not an amount owed and no invoice
					exists. The wall clock is the real budget and the shard board above draws it; this figure
					is the second unit, and it says whether that clock was worth spending.
				</p>
			{/if}
		</Panel>
	</div>
</section>

<style>
	.empty {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.refused {
		margin-top: var(--space-4);
		padding: var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--tint-warn);
	}

	.refused-head {
		margin: 0 0 var(--space-2);
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text);
	}

	.refused ul,
	.shares {
		margin: 0;
		padding-inline-start: var(--space-5);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.shares {
		margin-top: var(--space-3);
	}

	.splits {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.split-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--space-3);
		margin: 0 0 var(--space-1);
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
	}

	.track {
		display: flex;
		block-size: 18px;
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	.seg {
		display: block;
		block-size: 100%;
	}

	.seg.read {
		background: var(--chart-1);
	}

	.seg.write {
		background: var(--chart-4);
	}

	.split-legend {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-3);
		margin: var(--space-1) 0 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	.key {
		display: inline-block;
		inline-size: 10px;
		block-size: 10px;
		border-radius: 2px;
		margin-inline-end: 4px;
	}

	.key.read {
		background: var(--chart-1);
	}

	.key.write {
		background: var(--chart-4);
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

	/* The run's own mark first, then a bar a shard. Every bar runs to the same
	   16 GB ceiling, so their lengths compare. */
	.memory {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
		gap: var(--space-4) var(--space-5);
	}

	/* The run's own mark first, then a bar a shard. One column below the
	   breakpoint, because a memory bar squeezed into half a phone is a bar
	   nobody can compare with the one beside it. */
	.memory {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
		gap: var(--space-4) var(--space-5);
	}

	.host {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
		gap: var(--space-4) var(--space-5);
		margin: 0;
	}

	.host dt {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.host dd {
		margin: var(--space-1) 0 0;
		font-size: var(--text-base);
		color: var(--color-text);
	}

	.unit {
		display: block;
		margin-top: var(--space-1);
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	.absent {
		color: var(--color-text-tertiary);
	}

	.pair {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
		gap: var(--space-5);
	}

	.pane {
		margin: 0;
		min-inline-size: 0;
	}

	.pane figcaption {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.cost {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
		gap: var(--space-4) var(--space-5);
		margin: var(--space-4) 0 0;
	}

	.cost dt {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.cost dd {
		margin: var(--space-1) 0 0;
		font-size: var(--text-lg);
		font-weight: 600;
		color: var(--color-text);
	}
</style>
