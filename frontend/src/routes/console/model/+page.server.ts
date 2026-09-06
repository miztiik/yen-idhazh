import {
	chartConfig,
	consoleConfig,
	evaluationConfig,
	observabilityConfig,
	summarizeConfig,
	uiConfig
} from '$lib/server/config';
import { countersWithoutScores, recordingNotes } from '$lib/console/recording';
import {
	evalColumnLabels,
	evalDays,
	evalWithin,
	leadDays,
	leadSeries,
	matchDays,
	matchSeries
} from '$lib/console/eval-instruments';
import {
	reasonColumnLabels,
	reasonDays,
	reasonSeries,
	reasonsWithin,
	type ReasonDay
} from '$lib/console/doubt-reasons';
import {
	itemRates,
	modelByDate,
	modelSwap,
	modelWork,
	runLengths,
	scoreCost,
	sourceDoubts,
	writeTimes,
	type DayWindow
} from '$lib/server/model-work';
import type { RateSpread, ThroughputDay } from '$lib/charts/series';
import { stacked } from '$lib/charts/stacked';
import { windowOfDays } from '$lib/charts/viewport';
import { renderToSvg } from '$lib/server/chart-render';
import { evalRows, itemHealthRows, loadDay, publishedDates } from '$lib/server/payload';

export const prerender = true;

export type {
	CapPoint,
	DayWindow,
	Distribution,
	ModelDay,
	ModelRow,
	ModelSwap,
	RunLength,
	ScoreCost,
	SourceDoubt,
	SourceDoubts,
	SwapMeasure,
	WriteBin,
	WriteTimes
} from '$lib/server/model-work';

export type { ReasonDay } from '$lib/console/doubt-reasons';
export type { EvalDay } from '$lib/console/eval-instruments';

/** Why the checker doubted each day's summaries, from the committed payloads.
 *
 * The reason is a field on the published item, decided by
 * `backend/idhazh/evals/score.py` and written by `assemble.build_day`. It is not
 * a column of `state/scores/`, which carries the inputs it was decided from, so
 * this is the only ledger on disk that can answer the question.
 *
 * Every committed day is opened. That is a build-time read of the same tree
 * `publishedItems` already walks for the Pipelines route, and nothing about it
 * reaches a browser: what ships is one count per reason per day.
 */
function doubtReasonDays(): ReasonDay[] {
	return reasonDays(
		publishedDates()
			.map((date) => {
				const day = loadDay(date);
				if (day === null) return null;
				return {
					date,
					items: day.items.map((item) => ({
						band: item.band,
						reason: item.band_reason
					}))
				};
			})
			.filter((day) => day !== null)
	);
}

function measured(row: Record<string, string>, name: string): number | null {
	const raw = row[name];
	if (raw === undefined || raw === '') return null;
	const value = Number(raw);
	return Number.isFinite(value) ? value : null;
}

function byDate(rows: Record<string, string>[]): Map<string, Record<string, string>[]> {
	const grouped = new Map<string, Record<string, string>[]>();
	for (const row of rows) {
		const date = row.date ?? '';
		if (!date) continue;
		grouped.set(date, [...(grouped.get(date) ?? []), row]);
	}
	return grouped;
}

function quantile(sorted: number[], fraction: number): number {
	if (sorted.length === 1) return sorted[0];
	const position = (sorted.length - 1) * fraction;
	const low = Math.floor(position);
	const high = Math.ceil(position);
	return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

function spread(values: number[]): RateSpread | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	return {
		min: sorted[0],
		p25: quantile(sorted, 0.25),
		median: quantile(sorted, 0.5),
		p75: quantile(sorted, 0.75),
		max: sorted[sorted.length - 1]
	};
}

/** What the model did to the day's own articles.
 *
 * The same two ledgers the Pipelines route reads, asked a different question.
 * Nothing here is a rate the pipeline stored: every ratio is one committed
 * count over another, computed at read time, so a ratio can never disagree with
 * the counts printed beside it.
 */
export async function load() {
	const { rows } = evalRows();
	const itemRows = itemHealthRows().rows;
	const modelOnDate = modelByDate(rows);
	const itemHealthByDate = byDate(itemRows);
	const console = consoleConfig();
	const bands = summarizeConfig().bands;
	const today = new Date().toISOString().slice(0, 10);

	// Every span the control offers, worked out once here. The two distribution
	// panels have to re-read every millisecond to answer for a different span,
	// and a percentile taken off a drawn bar is a guess at where inside the bar
	// it fell - so each span is measured over the values themselves, at build
	// time, and the browser picks the answer rather than recomputing it. Four
	// presets is four small objects; the alternative was inlining every timing
	// the ledger holds so the page could re-bin them.
	//
	// Anchored on the same day list the cards anchor on, so every panel on the
	// page names one span.
	const work = modelWork(rows, itemRows);
	const dated = work.flatMap((row) => (row.kind === 'day' ? [row.day.date] : []));
	const windows = new Map<number, DayWindow>(
		console.window_presets.map((days) => {
			const span = windowOfDays(dated, today, days, console.today_anchor);
			return [days, { start: span.start, end: span.end, days }];
		})
	);
	// The widest span the control can reach. Nothing older than this can be drawn
	// whatever the operator does, so nothing older is inlined.
	const widest = [...windows.values()].reduce((a, b) => (a.days >= b.days ? a : b));

	// Why each day's summaries were doubted. Seeded to the widest span for the
	// same reason `runLengths` is: each day is already seven small numbers, so
	// narrowing the window is a filter and never a re-aggregation, and a day
	// older than the widest preset could never be drawn.
	const reasons = reasonsWithin(doubtReasonDays(), {
		start: widest.start,
		end: widest.end
	});
	// Drawn on the server at the span the page opens on, so every mark is on the
	// page before any script runs. The browser re-draws from the same array when
	// the operator moves the control.
	const openReasons = reasonsWithin(reasons, windows.get(console.default_window_days) ?? widest);
	const reasonsPlot = stacked(reasonColumnLabels(openReasons), reasonSeries(openReasons));
	const reasonsSvg = reasonsPlot.empty
		? null
		: await renderToSvg(reasonsPlot.option, {
				width: console.chart_width,
				height: console.chart_height
			});

	// What the checker measured on every summary, reduced to one small object a
	// day. Seeded to the widest span for the same reason the reasons are: the
	// browser filters this array and re-aggregates nothing, so the number in the
	// strip and the number in the sentence cannot drift apart.
	//
	// The reduction is here rather than in the browser because the ledger is
	// 6,966 rows and growing, and the page draws about a dozen numbers a day off
	// it. Inlining the rows to re-derive those numbers in a browser would put the
	// whole checker's output into every prerendered document.
	const leadFloor = evaluationConfig().lead_coverage_min;
	const evaluated = evalWithin(evalDays(rows, leadFloor), {
		start: widest.start,
		end: widest.end
	});
	const openEval = evalWithin(evaluated, windows.get(console.default_window_days) ?? widest);
	// Lines, never bars, and no shape switch on either. One percentile added to
	// another is not a quantity, and neither is one day's share added to the
	// next day's - so the second shape `stacked()` offers would be a lie here.
	const openMatch = matchDays(openEval);
	const matchPlot = stacked(evalColumnLabels(openMatch), matchSeries(openMatch), 'lines');
	const matchSvg = matchPlot.empty
		? null
		: await renderToSvg(matchPlot.option, {
				width: console.chart_width,
				height: console.chart_height
			});
	const openLead = leadDays(openEval);
	const leadPlot = stacked(evalColumnLabels(openLead), leadSeries(openLead), 'lines');
	const leadSvg = leadPlot.empty
		? null
		: await renderToSvg(leadPlot.option, {
				width: console.chart_width,
				height: console.chart_height
			});

	const observability = observabilityConfig();
	/** The days each instrument answered for, so the page can name a day one of
	 * them missed rather than drawing it as a day nothing happened. */
	const scoredDays = [...new Set(rows.map((row) => row.date ?? ''))].filter((date) => date !== '').sort();
	const timedDays = [...itemHealthByDate.keys()].sort();

	// Two different statistics, both kept on purpose. The candle is the spread of
	// per-item rates, because the worker sorts short articles first and the two
	// ends of a day drift apart. The day figure is the sum of the parts, because
	// a rate is a ratio and averaging per-item rates weighs a release note like a
	// feature. Oldest first: the chart reads left to right.
	const throughputDays: ThroughputDay[] = [...itemHealthByDate.entries()]
		.map(([date, group]) => {
			const reads: number[] = [];
			const writes: number[] = [];
			const perRun = new Map<string, { read: number[]; write: number[] }>();
			let prefillMs = 0;
			let decodeMs = 0;
			let cached = 0;
			let prompt = 0;
			let written = 0;
			for (const row of group) {
				const rate = itemRates(row);
				if (rate.read === null && rate.write === null) continue;
				const bucket = perRun.get(row.run_id ?? '') ?? { read: [], write: [] };
				if (rate.read !== null) {
					reads.push(rate.read);
					bucket.read.push(rate.read);
				}
				if (rate.write !== null) {
					writes.push(rate.write);
					bucket.write.push(rate.write);
				}
				perRun.set(row.run_id ?? '', bucket);
				prefillMs += measured(row, 'prefill_ms') ?? 0;
				decodeMs += measured(row, 'decode_ms') ?? 0;
				cached += measured(row, 'cached_tokens') ?? 0;
				prompt += measured(row, 'input_tokens') ?? 0;
				written += measured(row, 'output_tokens') ?? 0;
			}
			const read = spread(reads);
			const write = spread(writes);
			if (read === null || write === null) return null;
			const evaluated = Math.max(prompt - cached, 0);
			return {
				date,
				items: Math.max(reads.length, writes.length),
				read,
				write,
				readTps: prefillMs > 0 ? evaluated / (prefillMs / 1000) : 0,
				writeTps: decodeMs > 0 ? written / (decodeMs / 1000) : 0,
				cacheHitPct: prompt > 0 ? (cached / prompt) * 100 : 0,
				model: modelOnDate.get(date) ?? null,
				runs: [...perRun.entries()]
					.map(([runId, bucket]) => ({
						runId,
						items: Math.max(bucket.read.length, bucket.write.length),
						read: spread(bucket.read)?.median ?? 0,
						write: spread(bucket.write)?.median ?? 0
					}))
					.sort((a, b) => a.runId.localeCompare(b.runId))
			};
		})
		.filter((day): day is ThroughputDay => day !== null)
		.sort((a, b) => a.date.localeCompare(b.date));

	return {
		modelWork: work,
		throughputDays,
		// What the recording itself was doing. Every quality figure on this route
		// comes from the faithfulness scorer, so a day it was switched off for or
		// sampled past has summaries nobody counted - which is not the same fact as
		// a day the model wrote nothing, and a zero cannot tell them apart.
		recording: {
			...recordingNotes({
				enabled: observability.evaluation_enabled,
				rate: observability.sample_rate,
				recorded: scoredDays,
				window: [...new Set([...scoredDays, ...timedDays])].sort()
			}),
			// The other direction: the machine ran and we timed it, and nothing
			// scored what it wrote. Null where every timed day was also scored.
			countersOnly:
				timedDays.filter((date) => !scoredDays.includes(date)).length === 0
					? null
					: countersWithoutScores()
		},
		// One entry per span the control offers. Null where the span timed
		// nothing, which the panel prints as a sentence rather than as an empty
		// chart of zeroes.
		writeTimes: Object.fromEntries(
			[...windows].map(([days, window]) => [days, writeTimes(itemRows, window)])
		),
		scoreCost: Object.fromEntries(
			[...windows].map(([days, window]) => [days, scoreCost(rows, window)])
		),
		// Which sources the checker doubts, once per span the control offers. The
		// list is capped on the server: an uncapped one inlines a row for every
		// source the window scored, and the tail of it is a source with a single
		// doubt in a month.
		sourceDoubts: Object.fromEntries(
			[...windows].map(([days, window]) => [
				days,
				sourceDoubts(rows, itemRows, window, {
					limit: console.doubt_rows,
					minForShare: console.min_attempts_for_rate
				})
			])
		),
		windows: Object.fromEntries(windows),
		// Every run inside the widest span the control offers. The panel filters it
		// to the open window, so each entry is already three numbers and narrowing
		// recomputes nothing - but a run older than the widest preset can never be
		// drawn, and inlining it would grow this document for as long as the
		// pipeline runs. Trimming a seed the first paint cannot use is a saving,
		// not a cut.
		runLengths: runLengths(rows, bands).filter((run) => run.date >= widest.start),
		// One entry per committed day inside the widest span: the day's own item
		// count, the summaries carrying a reason, the summaries doubted with none,
		// and one count per reason. The browser filters this to the open window.
		reasons,
		reasonsSvg,
		// One entry per scored day inside the widest span, holding what the checker
		// measured on that day's summaries: the faithfulness quartiles, how many
		// summaries the whole article scores differently, the lead coverage, and
		// the four instruments nothing bands. The browser filters this array.
		evaluated,
		matchSvg,
		leadSvg,
		// Printed beside the count it governs, so the panel says which share it is
		// counting against instead of asking a reader to know it (Rule #6).
		leadFloor,
		// Not windowed. A swap is a point in time and its two sides are however
		// many articles ran on each model.
		modelSwap: modelSwap(rows, itemRows, bands, console.min_attempts_for_rate),
		// The explanation lives in docs/, which the site does not publish, so the
		// chart points at the repository rather than restating it in a caption.
		throughputReference: `${uiConfig().repo_url.replace(/\/+$/, '')}/blob/main/docs/architecture/summarize/throughput.md`,
		// Every fixed benchmark figure lives in the write-up and none of them is
		// copied onto this page: two machines and two workloads, so a gap between a
		// bench number and a run reads as a regression nobody measured.
		measurementsReference: `${uiConfig().repo_url.replace(/\/+$/, '')}/blob/main/docs/reference/measurements.md`,
		console,
		chart: chartConfig(),
		today
	};
}
