import { windowOfDays } from '$lib/charts/viewport';
import { chartFlow } from '$lib/charts/chart-flow';
import type { ExtractionDay } from '$lib/charts/extraction-trend';
import type { RunYieldSource } from '$lib/charts/run-yield';
import { itemCost, type ItemCost } from '$lib/console/item-cost';
import { recordNotesByWindow, type OfferedWindow } from '$lib/console/recording';
import { extraction, type Extraction } from '$lib/console/extraction';
import { health, runOutcome, squareLabel, type DayColumn } from '$lib/console/run-square';
import { chartDays } from '$lib/server/chart-days';
import { cutsByRun } from '$lib/server/cuts-by-run';
import { pipelineChanges } from '$lib/server/model-work';
import { loadRunTimeline, runTimelineView } from '$lib/server/run-timeline';
import { chartConfig, consoleConfig, panelGroupsFor, retentionConfig, runConfig, summarizeConfig, visualsConfig } from '$lib/server/config';
import { evalRows, itemHealthRows } from '$lib/server/ledger-rows';
import { stageTimingDays } from '$lib/server/stage-timing-days';
import { windowDay } from '$lib/server/window-day';
import {
	dayMetrics,
	latestDate,
	loadManifests,
	publishedCharts,
	telemetryRows,
	TELEMETRY_ROOT
} from '$lib/server/payload';

export const prerender = true;

export type { ItemCost } from '$lib/console/item-cost';
export type { Extraction } from '$lib/console/extraction';

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
	// reads with it (Guardrail #6). Every window ends on the site's newest
	// published day, so the widest one is every day the two records are read for.
	const widest = Math.max(...console.window_presets);
	const day = windowDay();
	const offered: OfferedWindow[] = console.window_presets.map((days) => ({
		days,
		...windowOfDays(day, days, console.today_anchor)
	}));
	const widestSpan = windowOfDays(day, widest, console.today_anchor);
	// Both from their packed files, so both stop at the newest packed day and say
	// so below rather than drawing the days after it as quiet ones.
	const scores = await evalRows(widestSpan);
	const items = await itemHealthRows(widestSpan);
	const { rows } = scores;
	const itemRows = items.rows;
	const floorPct = runConfig().success_floor_pct;
	const itemCeiling = runConfig().safety_ceiling_per_run;
	const siteBudgetMb = retentionConfig().site_budget_mb;
	const summarize = summarizeConfig();

	// Each day's median time per item at the three stages an item waits on, and
	// how many items each stage timed.
	const timingDays = stageTimingDays(itemRows);

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

	// Each day payload of the widest window, opened once: the articles card, the
	// chart table and the cost panel all take their counts from this read.
	const visuals = publishedCharts(undefined, widest);
	const charts = chartDays(manifests, visuals);
	const flow = chartFlow(charts);
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
	//
	// Read over the widest window and nothing around it, so a projection row
	// dated after the newest published day is in no window, as on every route.
	const costRows = telemetryRows(TELEMETRY_ROOT, widestSpan).rows;
	const itemCostByWindow: ItemCost[] = offered.map((span) => itemCost(costRows, span));
	// One day record per date the window holds, read once at the widest preset and
	// sliced per preset from that map. `charts` already names every published day,
	// so this adds no listing of the tree - only `widest` file opens, whatever the
	// archive holds behind it (`CLAUDE.md` Guardrail #12).
	const chartDates = charts.map((day) => day.date).sort();
	const recordsByDate = dayMetrics(
		chartDates.filter((date) => date >= widestSpan.start && date <= widestSpan.end)
	);
	const extractionByWindow: Extraction[] = offered.map((span) => {
		const inside = chartDates.filter((date) => date >= span.start && date <= span.end);
		return extraction(
			inside.map((date) => recordsByDate.get(date)?.extraction ?? null),
			span.days
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
		// another tree's articles. Taken from the map `charts` was built from, not
		// from `charts`: a day whose payload did not load is left out here, where
		// `charts` gives it no articles.
		publishedItems: Object.fromEntries(
			[...visuals].map(([date, counts]) => [date, counts.items] as const)
		),
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
		// from them, one set for each window the control offers: one not packed
		// yet, one that did not load, one packed short of the newest published day,
		// one whose rows stop before the window, or one with a day it has no record
		// for or files it set aside unread.
		recordNotes: recordNotesByWindow(
			[
				{ record: 'article', read: items.read },
				{ record: 'score', read: scores.read }
			],
			latestDate(undefined, 1),
			offered
		),
		// The day every window on this route ends on: the site's newest published day.
		windowDay: day
	};
}
