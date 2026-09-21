import { renderToSvg } from '$lib/server/chart-render';
import {
	cacheByDay,
	cacheChart,
	clockAgreement,
	clocksChart,
	memoryBoard,
	percentileHistory,
	readAgainstWritten,
	shardBoard,
	workChart,
	DEFAULT_WORK_UNIT,
	type CacheDay,
	type CostRate,
	type LatencyRun,
	type ReadWriteSummary,
	type RunWork
} from '$lib/charts/machine';
import {
	contextCost,
	type ContextOptions,
	type ContextRun,
	type ContextSpan
} from '$lib/console/machine/context-cost';
import { costChart, costOverDays, DEFAULT_COST_SHAPE } from '$lib/charts/cost';
import { memoryHeld } from '$lib/console/machine/memory-held';
import { splitByMachine } from '$lib/charts/machine-split';
import { machineCards, type MachineCards } from '$lib/charts/machine-cards';
import { machineKeys, machineRamp } from '$lib/charts/machine-colour';
import { fleetChart, fleetOverWindow, type FleetView } from '$lib/charts/fleet';
import { hostFingerprints, machineRecordDays, watchedFlags } from '$lib/server/host-fingerprint';
import { windowOfDays } from '$lib/charts/viewport';
import { recordingNotes, type LostDay, type RecordingNotes } from '$lib/console/recording';
import {
	chartConfig,
	consoleConfig,
	inferenceConfig,
	observabilityConfig,
	panelGroupsFor,
	runConfig
} from '$lib/server/config';
import { itemHealthRows, evalRows, loadDay, loadManifests, shardDays } from '$lib/server/payload';
import { pipelineChanges } from '$lib/server/model-work';
import {
	CLOCKS_AGREE_WITHIN_PCT,
	loadMachineCounters,
	machineLimits,
	type MachineRun,
	type RefusedRun
} from '$lib/server/machine-counters';

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
	peakRssSpan: FigureSpan;
	/** What kinds of machine the platform gave us over this span, and how often. */
	fleet: FleetView;
	tokens: RunWork[];
	/** Everything about the read-against-written comparison that is not a row:
	 * the ratio each unit measured, which side it makes taller, and whether that
	 * ratio passed the shared-axis limit. Scalars only - the rows are `tokens`,
	 * and carrying them twice would put the same numbers in the document twice. */
	work: ReadWriteSummary;
	tokenTotals: { input: number; output: number; items: number };
	/** What the model's reading limit cost over this span. Scalars only, on the
	 * same terms as `work`: the run marks are in `series.context`, out of the
	 * same call, so the sentence and the chart cannot be two answers. */
	context: ContextSpan;
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
	context: ContextRun[];
	latency: LatencyRun[];
}

/** Every panel this route draws, as the ids `console.panel_groups` orders.
 *
 * The list is here rather than in the config because it is a fact about the
 * markup: a panel exists because a snippet in `+page.svelte` draws it. The
 * config decides the order and the headings, and `panelGroupsFor` refuses a
 * config that disagrees with this list either way round.
 */
const DRAWN_PANELS = [
	'shard-board',
	'memory-board',
	'memory-held',
	'reading-against-writing',
	'prompt-cache',
	'context-headroom',
	'two-clocks',
	'machine-cards',
	'platform-mix',
	'tail-trend',
	'read-against-written',
	'counterfactual-cost'
] as const;

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
 * reading/writing split, the peak-memory bars and the clock check are
 * snapshots: a window is a span, and a span cannot narrow a single run. Each
 * names the run or the day it is about instead.
 */
export async function load() {
	const console_ = consoleConfig();
	// The widest span the control can reach. Nothing older can be drawn whatever
	// the operator does, so nothing older is read (`CLAUDE.md` Guardrail #12), and the
	// cover follows `console.window_presets` rather than a literal so raising a
	// preset widens it (Guardrail #6). Every ledger this route reads files by day.
	const widestPreset = Math.max(...console_.window_presets);
	const days = shardDays(widestPreset);
	const chart = chartConfig();
	const limits = machineLimits();
	const counters = loadMachineCounters(days);
	const health = itemHealthRows(days).rows;
	const observability = observabilityConfig();
	const today = new Date().toISOString().slice(0, 10);

	// One row a job, bounded to the same cover every other read on this route
	// takes (Guardrail #12), and the twelve flag names out of the generated
	// contract rather than a list typed here.
	const fingerprints = hostFingerprints(days);
	const flagNames = watchedFlags();
	// Both context figures come from one call per row set, so the sentence under
	// the chart and the marks on it cannot disagree about method.
	const contextOptions: ContextOptions = {
		percentile: console_.context_high_percentile,
		cutOffReason: console_.context_cut_off_reason
	};

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
		...fingerprints.map((row) => ({ fingerprint: row.fingerprint, cpuModel: row.cpu_model })),
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
		// One call, both units, one row set. A row qualifies on its token counts
		// and its durations are summed over exactly those rows, so the two grains
		// can never cover different runs.
		const { runs: tokens, ...work } = readAgainstWritten(healthRows);
		// The rows stay behind: they are carried once, bounded to the widest preset,
		// in `series.context`. Only the scalars differ per span.
		const context = contextCost(healthRows, contextOptions).span;

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
			// The newest run's own reading is a snapshot and sits on the memory
			// board; this says whether that reading was unusual over the span.
			peakRssSpan: spanOf(runs.map((run) => run.peakRssBytes.value)),
			// Counted once a preset here rather than in a browser, which holds no
			// ledger to count. At most eight kinds a span, so five presets is forty
			// small objects.
			fleet: fleetOverWindow(fingerprints, {
				days,
				minRows: console_.fleet_min_rows,
				colourStops: console_.machine_colour_stops,
				topKinds: console_.fleet_top_kinds,
				recording: observability.host_fingerprint,
				ramp,
				keys,
				start: span.start,
				end: span.end,
				lost: lostInSpan
			}),
			tokens,
			work,
			tokenTotals: tokens.reduce(
				(carry, run) => ({
					input: carry.input + run.input,
					output: carry.output + run.output,
					items: carry.items + run.items
				}),
				{ input: 0, output: 0, items: 0 }
			),
			context
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
		// Oldest first: a chart reads left to right, and `contextCost` sorts by run
		// id, which is `<date>-<n>`.
		context: contextCost(
			health.filter((row) => (row.date ?? '') >= bound.start && (row.date ?? '') <= bound.end),
			contextOptions
		).runs,
		latency: latency.runs.filter((run) => run.date >= bound.start && run.date <= bound.end)
	};
	const inWindow = <T extends { date: string }>(rows: readonly T[], span: MachineWindow): T[] =>
		rows.filter((row) => row.date >= span.start && row.date <= span.end);

	// Newest first, as the reader hands them over. The panels below read one
	// run or one day, so they read the newest the ledger holds whatever the
	// control says - a window is a span, and narrowing a span cannot narrow a
	// single run into something smaller.
	const newest: MachineRun | null = counters.runs[0] ?? null;
	const board = shardBoard(newest, limits.jobTimeoutSeconds, console_.chart_width);
	// Item grain and shard grain from one call, because a panel that offers two
	// grains built from two derivations can show two answers to one question. The
	// window grain is the span the loop above already derived for every preset,
	// which this panel reads rather than deriving a second time.
	const memory = memoryBoard(newest, health);
	// One bar a day, over every day the widest preset reaches, so the panel can
	// take the open span off the control without this deriving a second time.
	// Split from `memoryBoard` on purpose: that panel asks how near one run came
	// to the ceiling, and this one asks what the whole machine was holding.
	const held = memoryHeld(health);
	// One group a machine, never one figure over all of them. Measured 2026-09-17
	// over the committed counters ledger, 86 of the 90 runs that name a processor
	// drew more than one kind, so a pooled rate was a number about neither.
	const newestFingerprints = fingerprints.filter((row) => row.run_id === (newest?.runId ?? ''));
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
		// The margin the probe sized its own buffer with, so a row this build grades
		// is graded by the rule that wrote it rather than by a second copy of it.
		cacheMargin: observability.host_fingerprint_bandwidth_cache_multiple,
		ramp,
		keys,
		// A snapshot like the panels around it, so the loss is this run's own day
		// rather than anything the window says.
		lost: lostDays.find((day) => day.date === (newest?.date ?? '')) ?? null
	});
	const clocks = clockAgreement(newest, health, CLOCKS_AGREE_WITHIN_PCT);
	const clocksPlot = clocksChart(clocks.pairs);

	const rate: CostRate = {
		currency: observability.cost_currency,
		inputPerMillion: observability.cost_input_per_million,
		outputPerMillion: observability.cost_output_per_million
	};
	const cache = cacheChart(opening.cacheDays);
	// Drawn at the unit the panel opens on, so the first paint and the radio that
	// is already checked agree before a script has run.
	const workPlot = workChart(opening.tokens, opening.work, DEFAULT_WORK_UNIT);
	// Both shapes of the counterfactual out of one call, priced at the configured
	// rate because that is the rate the prerendered document states. An operator
	// who types his own gets the same arrays multiplied by it, in the browser.
	const costShapes = costOverDays(opening.tokens, rate, { heightPx: chart.height_px });
	const costPlot = costChart(costShapes, DEFAULT_COST_SHAPE, rate.currency);
	// The fleet trend at the span the page opens on. It is drawn only where the
	// count cleared the list floor, because under it the panel is a list.
	const fleetPlot = fleetChart(opening.fleet.trend);

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
		memory,
		memoryHeld: held,
		newestRunId: newest?.runId ?? null,
		split,
		machines,
		cacheSvg: await draw(cache, chart.height_px),
		cacheGrid: cache.grid,
		clocks,
		clocksSvg: await draw(clocksPlot, chart.height_px),
		latency: {
			floor: latency.floor,
			// Runs the item ledger timed too few items on to quote a p99. Bounded to
			// the widest preset for the same reason the series above is.
			tooFew: inWindow(latency.tooFew, bound)
		},
		workSvg: await draw(workPlot, chart.height_px),
		workGrid: workPlot.grid,
		workUnit: DEFAULT_WORK_UNIT,
		costSvg: await draw(costPlot, chart.height_px),
		costGrid: costPlot.grid,
		costShape: DEFAULT_COST_SHAPE,
		fleetSvg: opening.fleet.drawBars ? await draw(fleetPlot, chart.height_px) : null,
		fleetGrid: fleetPlot.grid,
		rate,
		limits,
		shardTimeoutMinutes: runConfig().shard_timeout_minutes,
		contextWindow: inferenceConfig().n_ctx,
		clocksTolerancePct: CLOCKS_AGREE_WITHIN_PCT,
		panelGroups: panelGroupsFor('machine', DRAWN_PANELS),
		console: console_,
		chart
	};
}
