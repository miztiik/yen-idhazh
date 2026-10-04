import type { StageTiming, StageTimingDay } from '$lib/charts/series';
import { windowOfDays } from '$lib/charts/viewport';
import { chartFlow } from '$lib/charts/chart-flow';
import type { ExtractionDay } from '$lib/charts/extraction-trend';
import type { RunYieldSource } from '$lib/charts/run-yield';
import { itemCost, type ItemCost } from '$lib/console/item-cost';
import { recordNotes } from '$lib/console/recording';
import { extraction, type Extraction } from '$lib/console/extraction';
import { health, runOutcome, squareLabel, type DayColumn } from '$lib/console/run-square';
import { pipelineChanges, wasCut } from '$lib/server/model-work';
import { loadRunTimeline, runTimelineView } from '$lib/server/run-timeline';
import { chartConfig, consoleConfig, panelGroupsFor, retentionConfig, runConfig, summarizeConfig, visualsConfig } from '$lib/server/config';
import { evalRows, itemHealthRows } from '$lib/server/ledger-rows';
import {
	dayMetrics,
	latestDate,
	loadManifests,
	publishedCharts,
	publishedItems,
	shardDays,
	telemetryRows,
	TELEMETRY_ROOT,
	type DayVisuals,
	type RunRecord,
	type RunSummary
} from '$lib/server/payload';

export const prerender = true;

type TimingStats = StageTimingDay;

export type { ItemCost } from '$lib/console/item-cost';
export type { Extraction } from '$lib/console/extraction';

/** What one day's chart drawing cost and what it produced.
 *
 * Four counts and one division. Two gaps carry the whole story: reached against
 * asked is the check that runs before the model, drafted against published is
 * the pair of checks that run after it.
 *
 * `plannerMinutes` and `minutesPerChart` are null rather than zero wherever the
 * number does not exist - a day whose visuals job never ran measured no time, and
 * a day with no chart has no per-chart cost. Zero would read as free.
 */
export interface ChartDay {
	date: string;
	reached: number;
	asked: number;
	drafted: number;
	published: number;
	/** Items the day published, chart or no chart. Chart drawing's second threshold is
	 * a share of this, and a share needs its denominator on the page. */
	items: number;
	plannerMinutes: number | null;
	minutesPerChart: number | null;
}

/** One row per published day, from the day's own manifest and payload.
 *
 * Nothing here is stored as a rate. The manifest carries counts and one
 * millisecond total; the division happens at read time, so a ratio can never
 * disagree with the counts printed beside it.
 */
function chartDays(days: RunSummary[], charts: Map<string, DayVisuals>): ChartDay[] {
	return days.map((day) => {
		const sum = (of: (run: RunRecord) => number) =>
			day.records.reduce((total, run) => total + of(run), 0);
		const timed = day.records.map((run) => run.decisionMs).filter((ms): ms is number => ms !== null);
		const plannerMinutes = timed.length === 0 ? null : timed.reduce((a, b) => a + b, 0) / 60_000;
		const seen = charts.get(day.date);
		const published = seen?.charts ?? 0;
		return {
			date: day.date,
			reached: sum((run) => run.decided + run.prefiltered),
			asked: sum((run) => run.decided),
			drafted: sum((run) => run.chartsDrafted),
			published,
			items: seen?.items ?? 0,
			plannerMinutes,
			minutesPerChart: plannerMinutes === null || published === 0 ? null : plannerMinutes / published
		};
	});
}

/** Null when nothing was timed. Zero is a measurement - a cheap stage really
 * does finish inside a millisecond clock's own resolution - so it can never
 * stand in for the absence of one.
 *
 * It takes a `Sample` rather than an array so that a hand-built list of
 * numbers, and any zero invented to fill an empty cell, has nowhere to land. */
function median(of: Sample): number | null {
	if (of.values.length === 0) return null;
	const sorted = [...of.values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function measured(row: Record<string, string>, name: string): number | null {
	const raw = row[name];
	if (raw === undefined || raw === '') return null;
	const value = Number(raw);
	return Number.isFinite(value) ? value : null;
}

/** One column of one group of rows, and how many rows could have filled it.
 *
 * `timed` against `total` is the fact a bare array cannot carry: eight items
 * timed out of ten and ten out of ten arrive as the same list of numbers.
 */
interface Sample {
	values: number[];
	timed: number;
	total: number;
}

function sample(rows: Record<string, string>[], name: string): Sample {
	const values = rows
		.map((row) => measured(row, name))
		.filter((value): value is number => value !== null);
	return { values, timed: values.length, total: rows.length };
}

/** A sample reduced to what the chart draws: one median, and the two counts
 * that say whether the day was timed in full, in part, or not at all. */
function timing(of: Sample): StageTiming {
	return { ms: median(of), timed: of.timed, total: of.total };
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

/** Articles each run read only the start of, keyed by the run that read them.
 *
 * Counted per address, not per row: a run writes one row per planned item, and
 * the same article coming round on a later run is the same article.
 */
function cutsByRun(rows: Record<string, string>[]): Map<string, number> {
	const seen = new Map<string, Set<string>>();
	for (const row of rows) {
		if (!wasCut(row)) continue;
		const runId = row.run_id ?? '';
		const found = seen.get(runId) ?? new Set<string>();
		found.add(row.url_key ?? row.item_id ?? '');
		seen.set(runId, found);
	}
	return new Map([...seen].map(([runId, keys]) => [runId, keys.size]));
}

/** Every section this route draws, as the ids `console.panel_groups` orders.
 *
 * The list is here rather than in the config because it is a fact about the
 * markup: a section exists because a snippet in `+page.svelte` draws it. The
 * config decides the order, and `panelGroupsFor` refuses a config that
 * disagrees with this list either way round.
 */
const DRAWN_PANELS = [
	'at-a-glance',
	'site-cost-per-item',
	'failure-mix',
	'item-time-split',
	'run-timeline',
	'run-health',
	'throughput-viewport',
	'stage-timings',
	'item-cost',
	'chart-drawing',
	'extraction'
] as const;

/** The console reads the committed ledger and nothing else.
 *
 * Every number here was measured when the run happened and written down. None
 * of it is derived at read time, which is what lets the page be a static file
 * and what stops today's code quietly restating yesterday's numbers.
 */
export async function load() {
	const console = consoleConfig();
	// Read once. It decides how a chart labels its axis AND, through `width_px`,
	// whether a band is wide enough for a browser to paint at all.
	const chart = chartConfig();
	// The widest span the control can reach. Nothing older than this can be drawn
	// whatever the operator does, so every read below is covered by it and no
	// panel loses a day (`CLAUDE.md` Guardrail #12). Read from `console.window_presets`
	// rather than written down here, so raising the widest preset widens the
	// reads with it (Guardrail #6). One cover, in days: all three `state/` ledgers
	// this route reads file by day.
	const widest = Math.max(...console.window_presets);
	const days = shardDays(widest);
	// Both from their packed files, so both stop at the newest packed day and say
	// so below rather than drawing the days after it as quiet ones.
	const scores = await evalRows(days);
	const items = await itemHealthRows(days);
	const { rows } = scores;
	const itemRows = items.rows;
	const floorPct = runConfig().success_floor_pct;
	const itemCeiling = runConfig().safety_ceiling_per_run;
	const siteBudgetMb = retentionConfig().site_budget_mb;
	const summarize = summarizeConfig();

	const itemHealthByDate = byDate(itemRows);

	// A day is kept when something on it was timed. Judging it by its medians
	// would drop a day whose only measurement was a zero, which is the same
	// mistake one level up.
	//
	// The three stages an item waits on. `score_ms` was a fourth entry here until
	// 2026-08-31: the scorer runs after the summary is written, so nothing waits
	// on it, and a fourth line on a critical-path chart read as a fourth thing the
	// run is held up by. It is on the Model route now, beside the cost of writing
	// the summary it checks.
	const timingDays: TimingStats[] = [...itemHealthByDate.entries()]
		.map(([date, group]) => ({
			date,
			items: group.length,
			fetch: timing(sample(group, 'fetch_ms')),
			extract: timing(sample(group, 'extract_ms')),
			summarize: timing(sample(group, 'summarize_ms'))
		}))
		.filter((day) => [day.fetch, day.extract, day.summarize].some((stage) => stage.timed > 0))
		.sort((a, b) => b.date.localeCompare(a.date));

	const manifests = loadManifests(undefined, widest);
	const readInPartByRun = cutsByRun(itemRows);
	// The strip is a time axis, so it reads oldest to newest. The Runs table under
	// it still reads newest first, which is why this copies rather than reverses:
	// an in-place reverse would silently turn that table upside down too.
	const grid: DayColumn[] = [...manifests].reverse().map((day) => ({
		date: day.date,
		squares: day.records.map((run) => ({
			runId: run.runId,
			n: run.n,
			health: health(run, floorPct),
			label: squareLabel(day.date, run, floorPct, readInPartByRun.get(run.runId) ?? 0),
			outcome: runOutcome(run, floorPct, readInPartByRun.get(run.runId) ?? 0)
		}))
	}));

	const charts = chartDays(manifests, publishedCharts(undefined, widest));
	const flow = chartFlow(charts);
	const today = new Date().toISOString().slice(0, 10);
	// The cost section is reduced here, once per span the control offers, and it
	// is the reason those eight columns were published at all.
	//
	// This reads the ledger and only the reduction of it crosses. Two binnings
	// and about twenty counts per preset, against the 3,334 KB the rows
	// themselves used to cost this document (measured 2026-09-09) - which is the
	// same trade the Summaries route's own distributions take.
	//
	// The price is that the section follows the window's LENGTH and not a pan,
	// exactly as `Sources cut short most often` below it does. A pan asks a
	// question about days the reduction was not taken over, and the browser has
	// only the months it has fetched to re-take it from.
	const costRows = telemetryRows(TELEMETRY_ROOT, widest).rows;
	const costDates = [...new Set(costRows.map((row) => row.date ?? '').filter(Boolean))].sort();
	const itemCostByWindow: ItemCost[] = console.window_presets.map((days) => {
		const span = windowOfDays(costDates, today, days, console.today_anchor);
		return itemCost(costRows, { ...span, days });
	});
	// One day record per date the window holds, read once at the widest preset and
	// sliced per preset from that map. `charts` already names every published day,
	// so this adds no listing of the tree - only `widest` file opens, whatever the
	// archive holds behind it (`CLAUDE.md` Guardrail #12).
	const chartDates = charts.map((day) => day.date).sort();
	const widestSpan = windowOfDays(chartDates, today, widest, console.today_anchor);
	const recordsByDate = dayMetrics(
		chartDates.filter((date) => date >= widestSpan.start && date <= widestSpan.end)
	);
	const extractionByWindow: Extraction[] = console.window_presets.map((days) => {
		const span = windowOfDays(chartDates, today, days, console.today_anchor);
		const inside = chartDates.filter((date) => date >= span.start && date <= span.end);
		return extraction(
			inside.map((date) => recordsByDate.get(date)?.extraction ?? null),
			days
		);
	});
	// The same records again, kept per day rather than summed, because the
	// direction the panel's own text tells the operator to read is not in a sum.
	// Two counts a day over the widest preset, which is 90 numbers at the cap.
	const extractionDays: ExtractionDay[] = chartDates
		.filter((date) => date >= widestSpan.start && date <= widestSpan.end)
		.flatMap((date) => {
			const block = recordsByDate.get(date)?.extraction;
			return block === undefined || block === null
				? []
				: [{ date, chartable: block.chartable, charted: block.chartableCharted }];
		});
	// The same records a third time, for the three item counts the glance chart
	// draws. Four numbers a day over the widest preset, sliced from the map above
	// rather than read again: this opens no file the page was not already opening
	// (`CLAUDE.md` Guardrail #12). Only the cells the chart reads cross, so the
	// extraction block above is not shipped twice.
	const runYieldDays: RunYieldSource[] = chartDates
		.filter((date) => date >= widestSpan.start && date <= widestSpan.end)
		.flatMap((date) => {
			const record = recordsByDate.get(date);
			return record === undefined
				? []
				: [
						{
							date,
							itemsPlanned: record.itemsPlanned,
							itemsPublished: record.itemsPublished,
							itemsFailed: record.itemsFailed
						}
					];
		});
	return {
		timingDays,
		manifests,
		// Where the newest published run's time actually went, one bar an item or one
		// bar a shard. A snapshot and not a window: a bar's position is measured from
		// its own run's start, and a span cannot narrow one run, so the panel names
		// the run it drew. It reads one published directory bounded to two months,
		// which is the whole series (`CLAUDE.md` Guardrail #12).
		runTimeline: runTimelineView(loadRunTimeline()[0] ?? null, console.timeline_bars),
		// What one item cost the model, one entry per span the control offers. The
		// browser picks the open one; nothing re-reads a ledger to change window.
		itemCostByWindow,
		// Articles per published day, read from the same tree `site_bytes` measures.
		// The denominator of the console's per-article cost, and the numerator's own
		// corpus - a count taken from anywhere else divides one tree's bytes by
		// another tree's articles.
		publishedItems: Object.fromEntries(publishedItems(undefined, widest)),
		charts,
		// The three glance charts and the flow diagram are drawn in the browser,
		// from arrays that already cross. The server drew them here until
		// 2026-09-09, which put 143 KB of finished SVG in a document that had to
		// come in under 400 KB, and a drawing the operator cannot re-take is a
		// drawing the window control cannot move.
		flowNote: flow.reason,
		grid,
		// Every day the pipeline that writes the summaries changed, derived once here
		// over the widest window preset and handed to the charts a change can move.
		// Derived per component it would be derived three times off three different
		// day lists, and two of them would eventually disagree about when it happened.
		// The manifests carry each run's recorded inputs and the score rows carry a
		// digest; which of the two a day holds is what decides how it is read.
		modelChanges: pipelineChanges(rows, manifests),
		floorPct,
		itemCeiling,
		siteBudgetMb,
		// What the extractor found and what the page drew from it, one reduction per
		// span the control offers - the same trade the cost section above takes.
		//
		// Read from the committed day records rather than re-reduced off the
		// item-health ledger: the record exists so the console stops re-counting what
		// a run already settled, and a second reducer here is the defect it removed.
		// `dayMetrics` opens one file per date it is handed and never lists the tree,
		// so the cost is the widest preset - 90 files - however many days the archive
		// holds behind it (`CLAUDE.md` Guardrail #12).
		extractionByWindow,
		// The direction behind those sums, one row a measured day. The panel slices
		// it to the open preset, so the trend and the cards can never be drawn over
		// two different spans.
		extractionDays,
		runYieldDays,
		// **No telemetry rows.** The page fetches its months, and the list of which
		// months exist rides on the band the layout already fetched. Inlined they
		// were 3,414,043 of this document's 3,880,361 bytes - 88 percent of what an
		// operator downloaded to open the console, for panels most visits never
		// scroll to (measured 2026-09-09, Intel Core i7-1265U, one build).
		console,
		// The order the sections above are drawn in, and the headings they group
		// under, from `config/appearance.json` rather than from markup order.
		panelGroups: panelGroupsFor('pipelines', DRAWN_PANELS),
		// How many separate figures of one unit make an article chartable. The
		// extraction panel prints it, and the pass it reports on reads the same knob.
		visuals: visualsConfig(),
		// How a chart labels its axis and how wide its readout may be. Two knobs an
		// operator moves without editing a component.
		chart,
		summarizeBands: summarize.bands,
		// What the page says about the two records it read before any panel draws
		// from them: one not packed yet, one that did not load, one packed some
		// days short of the newest published day, or one with a day it has no
		// record for or files it set aside unread.
		recordNotes: recordNotes(
			[
				{ record: 'article', read: items.read },
				{ record: 'score', read: scores.read }
			],
			latestDate(undefined, 1)
		),
		today
	};
}
