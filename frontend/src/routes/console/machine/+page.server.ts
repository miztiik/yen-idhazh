import { renderToSvg } from '$lib/server/chart-render';
import {
	cacheByDay,
	cacheChart,
	clockAgreement,
	clocksChart,
	contextHeadroom,
	curveOf,
	peakMemory,
	percentileChart,
	percentileHistory,
	shardBoard,
	tokenChart,
	tokensByRun,
	type CacheDay,
	type ContextBar,
	type CostRate,
	type LatencyRun,
	type RunTokens
} from '$lib/charts/machine';
import { splitByMachine } from '$lib/charts/machine-split';
import { machineCards, type MachineCards } from '$lib/charts/machine-cards';
import { machineKeys, machineRamp } from '$lib/charts/machine-colour';
import { fleetOverWindow, type FleetView } from '$lib/charts/fleet';
import { hostFingerprints, machineRecordDays, watchedFlags } from '$lib/server/host-fingerprint';
import { windowOfDays } from '$lib/charts/viewport';
import { recordingNotes, type LostDay, type RecordingNotes } from '$lib/console/recording';
import {
	chartConfig,
	consoleConfig,
	inferenceConfig,
	observabilityConfig,
	runConfig
} from '$lib/server/config';
import { itemHealthRows, evalRows, loadDay, loadManifests, shardDays, shardMonths } from '$lib/server/payload';
import { pipelineChanges } from '$lib/server/model-work';
import {
	CLOCKS_AGREE_WITHIN_PCT,
	loadMachineCounters,
	machineLimits,
	type MachineRun,
	type RefusedRun
} from '$lib/server/machine-counters';
import { loadSpanRollup, spanBreakdown } from '$lib/server/span-rollup';
import { loadRunTimeline, runTimelineView } from '$lib/server/run-timeline';

export const prerender = true;

/** The span of a figure across the runs that reported it, and how many did.
 *
 * A range and not a mean: the whole finding this route exists to publish is
 * that two shards of one run differ by more than 4x, and a mean of a lottery
 * reports neither end of it. `from` of zero means nothing measured it, which is
 * a different fact from a measurement of zero.
 */
function spanOf(
	values: readonly (number | null)[]
): { low: number | null; high: number | null; from: number; outOf: number } {
	const known = values.filter((value): value is number => value !== null);
	return {
		low: known.length === 0 ? null : Math.min(...known),
		high: known.length === 0 ? null : Math.max(...known),
		from: known.length,
		outOf: values.length
	};
}

export type FigureSpan = ReturnType<typeof spanOf>;

/** Everything one span of days answers, worked out once for each span the
 * control offers.
 *
 * The browser holds no ledger, so it cannot re-aggregate a window: a token
 * total, a cache share and a recording note all read rows this page never
 * receives. Four small objects is the price of a control that works with no
 * fetch, and it is bounded - the widest preset is the widest anything here can
 * reach, so a run older than that is never carried at any span.
 */
export interface MachineWindow {
	days: number;
	start: string;
	end: string;
	runsRead: number;
	refused: RefusedRun[];
	recording: RecordingNotes;
	/** What the MACHINE record was doing, which is a different instrument from
	 * the counters above and can be in a different state on the same day. */
	machineRecord: RecordingNotes;
	cacheDays: CacheDay[];
	/** The most parallel slots any item's server was started with, over the
	 * items that recorded the cell. */
	parallelSlots: { highest: number | null; from: number; outOf: number };
	cpuBusySpan: FigureSpan;
	peakRssSpan: FigureSpan;
	modelLoadSpan: FigureSpan;
	/** What kinds of machine the platform gave us over this span, and how often. */
	fleet: FleetView;
	tokens: RunTokens[];
	tokenTotals: { input: number; output: number; items: number };
}

/** Everything a run-by-run chart draws, carried once rather than once a span.
 *
 * The two run-by-run charts - context headroom and the latency multiples - draw
 * a mark per run rather than per day, so a span only ever decides which of
 * these rows to keep. Carrying four copies of the same eighteen rows, one per
 * preset, would put the identical numbers in the document four times; a date
 * compare in the browser gives the same set for a fraction of the bytes,
 * because a span is a pair of dates and every row carries its own.
 *
 * Bounded to the WIDEST preset, so a run older than the widest span is never in
 * the document at any span. Without that bound the page grows for ever.
 */
export interface RunSeries {
	context: ContextBar[];
	latency: LatencyRun[];
}

/** What the two surviving ledgers counted, read once at build time.
 *
 * The whole route reads `state/host-fingerprint/` and `state/item-health/`,
 * both of which sit under `state/` and are never published, through
 * `$lib/server/` - the same place and for the same reason `model-work.ts` reads
 * `state/scores.csv`. No cell of either crosses to a reader and this route adds
 * no published telemetry column.
 *
 * **Every span the control offers is answered here**, not in the browser. Since
 * 2026-08-31 this route carries the same 7/14/30/90 control as the other two
 * and reads the same `idhazh:console-window` key, so an operator comparing a
 * slow day across Pipelines and Hardware sees both on one span.
 *
 * **A panel about one run does not follow the window.** The shard board, the
 * reading/writing split, the peak-memory bars, the clock check and the newest
 * run's own latency curve are snapshots: a window is a span, and a span cannot
 * narrow a single run. Each names the run or the day it is about instead.
 */
export async function load() {
	const console_ = consoleConfig();
	// The widest span the control can reach. Nothing older can be drawn whatever
	// the operator does, so nothing older is read (`CLAUDE.md` Guardrail #12), and the
	// cover follows `console.window_presets` rather than a literal so raising a
	// preset widens it (Guardrail #6). Two covers, because a `state/` ledger files
	// by day and a published mirror by month: `shards` is the span rollup's.
	const widestPreset = Math.max(...console_.window_presets);
	const shards = shardMonths(widestPreset);
	const days = shardDays(widestPreset);
	const chart = chartConfig();
	const limits = machineLimits();
	const counters = loadMachineCounters(days);
	const health = itemHealthRows(days).rows;
	const observability = observabilityConfig();
	const today = new Date().toISOString().slice(0, 10);

	// One row a job, bounded to the same cover every other read on this route
	// takes (Guardrail #12), and the twelve flag names out of the generated schema
	// rather than a list typed here.
	const fingerprints = hostFingerprints(days);
	const flagNames = watchedFlags();

	// **The third state this route has to be able to say.** A day the machine
	// record opened a file for and kept no row of, that published articles
	// anyway, lost what it measured - the run worked, the measurement did not
	// survive. It is not the day the record had not started on, and it is not a
	// quiet day, and until 2026-09-17 all three drew the same sentence.
	//
	// A day payload is opened only for a candidate, and a candidate is a day
	// whose record file exists and holds nothing. A healthy archive has none, so
	// this costs nothing on a healthy archive and stays bounded by the same
	// cover on a broken one (`CLAUDE.md` Guardrail #12).
	const recordedDays = new Set(fingerprints.map((row) => row.date));
	const lostDays: LostDay[] = machineRecordDays(days)
		.filter((date) => !recordedDays.has(date))
		.map((date) => ({ date, articles: loadDay(date)?.items.length ?? 0 }))
		.filter((day) => day.articles > 0)
		.sort((left, right) => left.date.localeCompare(right.date));

	// **One ramp for the whole page, assigned over every machine any panel can
	// show at any preset.** Assigned per panel or per span, a machine would change
	// colour when the operator moved the window - and comparing spans is what the
	// control is for. The key set is bounded by the widest preset, so it is fixed
	// for a build whatever the reader does.
	const seen = [
		...fingerprints.map((row) => ({ fingerprint: row.fingerprint, cpuModel: row.cpuModel })),
		...counters.runs.flatMap((run) =>
			run.reported.map((shard) => ({ fingerprint: null, cpuModel: shard.cpuModel }))
		)
	];
	const keys = machineKeys(seen);
	const ramp = machineRamp(seen.map(keys), console_.machine_colour_stops);

	const dates = [
		...new Set([...counters.runs.map((run) => run.date), ...health.map((row) => row.date ?? '')])
	].filter((date) => date !== '');

	/** One span, and every figure that reads a span. */
	function answer(days: number): MachineWindow {
		const span = windowOfDays(dates, today, days, console_.today_anchor);
		const inSpan = <T extends { date: string }>(rows: readonly T[]): T[] =>
			rows.filter((row) => row.date >= span.start && row.date <= span.end);

		const runs = inSpan(counters.runs);
		const lostInSpan = inSpan(lostDays);
		const spanDays = [...new Set(inSpan(dates.map((date) => ({ date }))).map((row) => row.date))].sort();
		const healthRows = health.filter(
			(row) => (row.date ?? '') >= span.start && (row.date ?? '') <= span.end
		);
		const tokens = tokensByRun(healthRows);
		// One line of text and not a chart. It reads 1 on every row the ledger
		// holds, because `models.summarize.inference.n_parallel` is 1, and it earns
		// a chart the day that knob moves.
		const slots = healthRows
			.map((row) => Number(row.n_parallel))
			.filter((value) => Number.isFinite(value));

		return {
			days,
			start: span.start,
			end: span.end,
			runsRead: runs.length,
			// Never dropped silently: a run whose rows cannot be made into one run
			// is named on the page with the reason, because a run count that quietly
			// excludes one is a run count nobody can check.
			refused: inSpan(counters.refused),
			// What the recording itself was doing. Every panel below reads the model
			// server's own counters, so a day the scrape never ran is a gap in the
			// recording rather than a machine that did nothing - and the two states
			// look identical on a chart unless the page says which one it is. The
			// item ledger is the other instrument: a day it covers and the counters
			// do not is the state most committed days are in.
			recording: recordingNotes({
				enabled: observability.host_fingerprint,
				rate: observability.sample_rate,
				recorded: [...new Set(runs.map((run) => run.date))].sort(),
				window: spanDays,
				coveredElsewhere: [...new Set(healthRows.map((row) => row.date ?? ''))]
					.filter((date) => date !== '')
					.sort()
			}),
			// The machine record is the other instrument on this route, and it has
			// its own three states. It carries no sampling knob, so it owes no
			// sampling caveat and passes no rate.
			machineRecord: recordingNotes({
				enabled: observability.host_fingerprint,
				recorded: [...new Set(inSpan(fingerprints).map((row) => row.date))].sort(),
				window: spanDays,
				lost: lostInSpan,
				figures: 'machine record'
			}),
			cacheDays: cacheByDay(runs),
			parallelSlots: {
				highest: slots.length === 0 ? null : Math.max(...slots),
				from: slots.length,
				outOf: healthRows.length
			},
			// The newest run's own reading is a snapshot and sits below; these three
			// say whether that reading was unusual over the span.
			cpuBusySpan: spanOf(runs.map((run) => run.lowestCpuBusyPct.value)),
			peakRssSpan: spanOf(runs.map((run) => run.peakRssBytes.value)),
			modelLoadSpan: spanOf(runs.map((run) => run.slowestModelLoadMs.value)),
			// Counted once a preset here rather than in a browser, which holds no
			// ledger to count. At most eight kinds a span, so five presets is forty
			// small objects.
			fleet: fleetOverWindow(fingerprints, {
				days,
				minRows: console_.fleet_min_rows,
				colourStops: console_.machine_colour_stops,
				recording: observability.host_fingerprint,
				ramp,
				keys,
				start: span.start,
				end: span.end,
				lost: lostInSpan
			}),
			tokens,
			tokenTotals: tokens.reduce(
				(carry, run) => ({
					input: carry.input + run.input,
					output: carry.output + run.output,
					items: carry.items + run.items
				}),
				{ input: 0, output: 0, items: 0 }
			)
		};
	}

	// The default span is answered whether or not it is one of the presets, so
	// the document the browser is handed always has an entry to fall back to.
	const spans = [...new Set([console_.default_window_days, ...console_.window_presets])];
	const windows = new Map<number, MachineWindow>(spans.map((days) => [days, answer(days)]));
	// The span the prerendered document opens on. Its drawings are the ones
	// inlined; a browser redraws from the arrays when the operator moves the
	// control, so widening costs a repaint rather than four more SVGs.
	const opening = windows.get(console_.default_window_days) as MachineWindow;

	// Every run-by-run row the widest preset can reach, carried once. A narrower
	// span keeps a subset of these by date, in the browser and here, through the
	// one filter below - so the chart the server drew and the chart a browser
	// redraws cannot be built from two different sets.
	const widest = Math.max(...spans);
	const bound = windows.get(widest) as MachineWindow;
	const latency = percentileHistory(health, console_.min_attempts_for_rate);
	const series: RunSeries = {
		context: contextHeadroom(
			counters.runs.filter((run) => run.date >= bound.start && run.date <= bound.end),
			limits.contextWindow
		)
			// Oldest first: a chart reads left to right, and the reader hands runs
			// over newest first.
			.reverse(),
		latency: latency.runs.filter((run) => run.date >= bound.start && run.date <= bound.end)
	};
	const inWindow = <T extends { date: string }>(rows: readonly T[], span: MachineWindow): T[] =>
		rows.filter((row) => row.date >= span.start && row.date <= span.end);

	// Newest first, as the reader hands them over. The panels below read one
	// run or one day, so they read the newest the ledger holds whatever the
	// control says - a window is a span, and narrowing a span cannot narrow a
	// single run into something smaller.
	const newest: MachineRun | null = counters.runs[0] ?? null;
	const board = shardBoard(newest, limits.jobTimeoutSeconds);
	const memory = peakMemory(newest);
	// One group a machine, never one figure over all of them. Measured 2026-09-17
	// over the committed counters ledger, 86 of the 90 runs that name a processor
	// drew more than one kind, so a pooled rate was a number about neither.
	const newestFingerprints = fingerprints.filter((row) => row.runId === (newest?.runId ?? ''));
	const split = splitByMachine(newest, {
		colourStops: console_.machine_colour_stops,
		// Two machines reporting one model name are not the same machine, so the
		// digest is the key wherever the record reached the shard.
		fingerprints: new Map(
			newestFingerprints
				.filter((row) => row.job === 'work')
				.map((row) => [row.shard, row.fingerprint])
		),
		ramp,
		keys
	});
	const machines: MachineCards = machineCards(newest, newestFingerprints, {
		watchedFlags: flagNames,
		colourStops: console_.machine_colour_stops,
		recording: observability.host_fingerprint,
		ramp,
		keys,
		// A snapshot like the panels around it, so the loss is this run's own day
		// rather than anything the window says.
		lost: lostDays.find((day) => day.date === (newest?.date ?? '')) ?? null
	});
	const clocks = clockAgreement(newest, health, CLOCKS_AGREE_WITHIN_PCT);
	const clocksPlot = clocksChart(clocks.pairs);

	// The newest run that folded its spans, and where its shards' seconds went.
	// A snapshot like the board above, not a window: the residual is a per-shard
	// quantity of one run, and a span cannot narrow a single run. It reads its
	// own ledger - `state/span-rollup/`, empty until a traced run commits - so it
	// is often a different run from `newest`, and its own empty state when the
	// real rollup holds nothing.
	const spanView = spanBreakdown(loadSpanRollup(shards)[0] ?? null);

	// The newest run the published item timeline holds, and where each of its
	// items sat on the run's clock. A snapshot for the same reason the two above
	// are: a bar's position is measured from its own run's start, and a window
	// cannot narrow one run. It reads its own published mirror, so it is often a
	// different run again and carries its own empty state.
	const timeline = runTimelineView(loadRunTimeline()[0] ?? null, console_.timeline_bars);

	// The newest run the item ledger timed enough items on, which is not always
	// the newest run the counters reached: a run can publish before its shards
	// scrape. It is the last entry of the same array the multiples draw, so
	// "the tail today" and "the newest mark on the p99 chart" are one number.
	const newestTail = series.latency.at(-1) ?? null;
	const percentilePlot = percentileChart(newestTail === null ? [] : [curveOf(newestTail)]);

	const rate: CostRate = {
		currency: observability.cost_currency,
		inputPerMillion: observability.cost_input_per_million,
		outputPerMillion: observability.cost_output_per_million
	};
	const cache = cacheChart(opening.cacheDays);
	const inputPlot = tokenChart(opening.tokens, (run) => run.input, 'prompt tokens', '--chart-1');
	const outputPlot = tokenChart(opening.tokens, (run) => run.output, 'written tokens', '--chart-4');

	// Three cells that landed on 2026-08-30 and that no page had printed. The
	// newest run's own reading; the span across the open window sits beside it on
	// the page, from the object above. The processors the run drew left this
	// object on 2026-09-17: a run is not a machine, so they are cards of their own.
	const host = {
		runId: newest?.runId ?? null,
		cpuBusy: newest?.lowestCpuBusyPct ?? null,
		peakRss: newest?.peakRssBytes ?? null,
		modelLoad: newest?.slowestModelLoadMs ?? null
	};

	// Drawn on the server so every mark is on the page before a script runs, and
	// stays there if none ever does. Colour leaves as a custom-property
	// reference, so both themes work with no JavaScript at all.
	//
	// Only the SVG crosses. The `option` a live chart hydrates from is rebuilt in
	// the component from the same arrays, because everything a `load` returns is
	// serialised into the prerendered document - and an option carries the
	// magenta sentinels `toCssVariables` swaps out of the SVG, which
	// `charts.spec.ts` fails the build over. It also keeps the payload to the
	// numbers rather than to a drawing of them.
	const draw = async (
		plot: { option: import('echarts').EChartsOption; empty: boolean },
		height: number
	) => (plot.empty ? null : await renderToSvg(plot.option, { width: chart.width_px, height }));

	return {
		// One entry per span the control offers, keyed by its day count. The page
		// picks the open one; nothing is recomputed in a browser.
		windows: Object.fromEntries(windows),
		// One copy of every run-by-run row, bounded to the widest preset. The page
		// keeps the rows inside the open span.
		series,
		// Every day the pipeline that writes the summaries changed, derived once
		// here over the rows this route read and handed to the two charts a change
		// can move: a longest sequence is prompt plus answer, and an item's model
		// time is the model call itself. Derived per chart it would be derived twice
		// off two different day lists, and the two would eventually disagree. The
		// rows stop at the widest preset, which is as far back as either chart draws
		// (`CLAUDE.md` Guardrail #12), and the manifests are bounded the same way.
		modelChanges: pipelineChanges(evalRows(days).rows, loadManifests(undefined, widest)),
		board,
		spanBreakdown: spanView,
		runTimeline: timeline,
		memory,
		newestRunId: newest?.runId ?? null,
		split,
		machines,
		cacheSvg: await draw(cache, chart.height_px),
		cacheGrid: cache.grid,
		clocks,
		clocksSvg: await draw(clocksPlot, chart.height_px),
		host,
		latency: {
			floor: latency.floor,
			// Runs the item ledger timed too few items on to quote a p99. Bounded to
			// the widest preset for the same reason the series above is.
			tooFew: inWindow(latency.tooFew, bound),
			shardRows: latency.shardRows,
			itemRows: latency.itemRows
		},
		newestTail,
		percentileSvg: await draw(percentilePlot, chart.height_px),
		inputSvg: await draw(inputPlot, chart.height_px),
		inputGrid: inputPlot.grid,
		outputSvg: await draw(outputPlot, chart.height_px),
		outputGrid: outputPlot.grid,
		rate,
		limits,
		shardTimeoutMinutes: runConfig().shard_timeout_minutes,
		contextWindow: inferenceConfig().n_ctx,
		clocksTolerancePct: CLOCKS_AGREE_WITHIN_PCT,
		console: console_,
		chart
	};
}
