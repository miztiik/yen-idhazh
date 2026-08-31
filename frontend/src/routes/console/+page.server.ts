import type { StageTiming, StageTimingDay } from '$lib/charts/series';
import { datesIn, failureSeries } from '$lib/charts/series';
import { windowOfDays } from '$lib/charts/viewport';
import { chartFlow, FLOW_HEIGHT } from '$lib/charts/chart-flow';
import { targetMarks, type TargetMarks } from '$lib/charts/targetbar';
import { failureMix, runHealth, siteCost } from '$lib/charts/glance';
import { renderToSvg } from '$lib/server/chart-render';
import { sourceCuts, wasCut, SOURCE_CUT_ROWS } from '$lib/server/model-work';
import {
	chronological,
	failing,
	feedDays,
	resting,
	resultLabel,
	skipped,
	streak,
	type FeedDay,
	type FeedDayOutcome
} from '$lib/feed-health';
import { chartConfig, collectConfig, consoleConfig, retentionConfig, runConfig, summarizeConfig } from '$lib/server/config';
import {
	evalRows,
	feedResults,
	itemHealthRows,
	loadManifests,
	publishedCharts,
	publishedItems,
	telemetryMonths,
	telemetryRows,
	TELEMETRY_ROOT,
	type DayVisuals,
	type FeedResult,
	type RunRecord,
	type RunSummary
} from '$lib/server/payload';

export const prerender = true;

type TimingStats = StageTimingDay;

/** Green: it worked. Amber: look at it. Red: it did not work. */
export type Health = 'green' | 'amber' | 'red';

// The page prints these; the derivation is server-only, so the shape crosses
// as a type and the ledger reader never reaches a browser bundle.
export type { CapPoint, LengthRange, SourceCut, SourceCuts } from '$lib/server/model-work';

export interface RunSquare {
	runId: string;
	n: number;
	health: Health;
	label: string;
}

export interface DayColumn {
	date: string;
	squares: RunSquare[];
}

export interface FeedTrouble {
	feedId: string;
	attempts: number;
	failures: number;
	/** Failures in a row, ending at the newest read. This is the number the
	 * pipeline quarantines on, so it is the number the page prints. */
	streak: number;
	lastResult: string;
	lastDetail: string;
	lastDate: string;
	/** The pipeline's own decision, recomputed by its own rule. */
	resting: boolean;
	/** Where the fill ends and where the rest threshold sits. Drawn here, so the
	 * bar is on the page before any script runs and the browser never has to
	 * agree with it. */
	marks: TargetMarks;
	/** One entry per day this feed has a record on, oldest first. */
	days: FeedDay[];
}

export type { FeedDay, FeedDayOutcome };

/** What one day's chart arm cost and what it produced.
 *
 * Four counts and one division. Two gaps carry the whole story: reached against
 * asked is the check that runs before the model, drafted against published is
 * the pair of checks that run after it.
 *
 * `routerMinutes` and `minutesPerChart` are null rather than zero wherever the
 * number does not exist - a day whose route job never ran measured no time, and
 * a day with no chart has no per-chart cost. Zero would read as free.
 */
export interface ChartDay {
	date: string;
	reached: number;
	asked: number;
	drafted: number;
	published: number;
	/** Items the day published, chart or no chart. The arm's second threshold is
	 * a share of this, and a share needs its denominator on the page. */
	items: number;
	routerMinutes: number | null;
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
		const timed = day.records.map((run) => run.routeMs).filter((ms): ms is number => ms !== null);
		const routerMinutes = timed.length === 0 ? null : timed.reduce((a, b) => a + b, 0) / 60_000;
		const seen = charts.get(day.date);
		const published = seen?.charts ?? 0;
		return {
			date: day.date,
			reached: sum((run) => run.routed + run.prefiltered),
			asked: sum((run) => run.routed),
			drafted: sum((run) => run.chartsDrafted),
			published,
			items: seen?.items ?? 0,
			routerMinutes,
			minutesPerChart: routerMinutes === null || published === 0 ? null : routerMinutes / published
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

function publicTelemetry(row: Record<string, string>) {
	return {
		date: row.date ?? '',
		run_id: row.run_id ?? '',
		item_id: row.item_id ?? '',
		vertical: row.vertical ?? '',
		source_id: row.source_id ?? '',
		stage: row.stage ?? '',
		outcome: row.outcome ?? '',
		code: row.code ?? '',
		source_words: measured(row, 'source_words'),
		summary_words: measured(row, 'summary_words'),
		source_words_before_cap: measured(row, 'source_words_before_cap')
	};
}

/** One square's colour, from what the run wrote down about itself.
 *
 * Skipped items are not failures. An article already published, or one a feed
 * repeated, is skipped by design - counting it against the run would paint a
 * healthy day amber for doing its job. So the rate is over what was attempted.
 *
 * The floor is the same knob CI uses to decide whether a run opens an issue, so
 * a red square and an open issue can never disagree.
 */
function health(run: RunRecord, floorPct: number): Health {
	if (run.status === 'failed') return 'red';
	const attempted = run.succeeded + run.failed;
	// Nothing was attempted. Not a failure, but never what you expect to see.
	if (attempted === 0) return 'amber';
	if ((run.succeeded / attempted) * 100 < floorPct) return 'red';
	if (run.failed > 0 || run.status !== 'completed' || run.sourceListStale) return 'amber';
	return 'green';
}

/** What one run did, in the words the square carries for anyone without a mouse.
 *
 * The cut count rides here rather than on a figure of its own. Measured
 * 2026-08-29 over 19 committed runs it is 1 to 12 articles of 160 to 200, and
 * that swing is which articles the feeds carried that hour - so drawn as a
 * published number it would read as the cap moving when nothing moved. A run is
 * where run-level facts already live.
 */
function describe(date: string, run: RunRecord, readInPart: number): string {
	const parts = [`${date} run ${run.n}`, `${run.succeeded} of ${run.planned} succeeded`];
	if (run.failed > 0) parts.push(`${run.failed} failed`);
	if (run.skipped > 0) parts.push(`${run.skipped} skipped`);
	if (readInPart > 0) parts.push(`${readInPart} read only in part`);
	if (run.sourceListStale) parts.push('source list was stale');
	if (run.status !== 'completed') parts.push(run.status);
	return parts.join(', ');
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

/** Every feed that failed at least once, closest to a rest first.
 *
 * A feed with a clean record is not listed. The operator came here to find what
 * is broken, and a list that names all seventy sources hides the four that are.
 *
 * Ranked by how near the rest is, then by how much has gone wrong in total. A
 * feed four failures into a five-failure rule is one run from being dropped; a
 * feed with twelve failures spread over a month and answering today is not, and
 * a total-failure sort put the second one on top.
 */
function trouble(rows: FeedResult[], quarantineAfter: number): FeedTrouble[] {
	const byFeed = new Map<string, FeedResult[]>();
	for (const row of rows) {
		byFeed.set(row.feedId, [...(byFeed.get(row.feedId) ?? []), row]);
	}

	const found: FeedTrouble[] = [];
	for (const [feedId, group] of byFeed) {
		// A skipped feed was never asked, so it can neither pass nor fail. It still
		// has to stay in `ordered`, because the rest it records is what lets the
		// quarantine lift.
		const ordered = chronological(group);
		const asked = ordered.filter((row) => !skipped(row));
		const failures = asked.filter(failing);
		if (failures.length === 0) continue;
		const newest = asked.at(-1) as FeedResult;
		const inARow = streak(ordered);
		found.push({
			feedId,
			attempts: asked.length,
			failures: failures.length,
			streak: inARow,
			lastResult: resultLabel(newest),
			lastDetail: newest.detail,
			lastDate: newest.date,
			resting: resting(ordered, quarantineAfter),
			// Fewer is better, so the fill runs from nothing to the rest and past it.
			marks: targetMarks(inARow, quarantineAfter, 'lower-is-better'),
			days: feedDays(ordered)
		});
	}
	return found.sort(
		(a, b) => b.streak - a.streak || b.failures - a.failures || a.feedId.localeCompare(b.feedId)
	);
}

/** The console reads the committed ledger and nothing else.
 *
 * Every number here was measured when the run happened and written down. None
 * of it is derived at read time, which is what lets the page be a static file
 * and what stops today's code quietly restating yesterday's numbers.
 */
export async function load() {
	const { rows } = evalRows();
	const itemRows = itemHealthRows().rows;
	const floorPct = runConfig().success_floor_pct;
	const itemCeiling = runConfig().safety_ceiling_per_run;
	const siteBudgetMb = retentionConfig().site_budget_mb;
	const quarantineAfter = collectConfig().quarantine_after_failures;
	const console = consoleConfig();
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

	const manifests = loadManifests();
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
			label: describe(day.date, run, readInPartByRun.get(run.runId) ?? 0)
		}))
	}));

	const results = feedResults();
	// Seeded to the window the viewport opens on, not to every committed month:
	// this list is inlined into the prerendered HTML, so an unbounded seed makes
	// the page grow for as long as the pipeline runs. The compression plot is
	// drawn from these same rows in the browser, so it costs the page nothing and
	// grows by month fetch exactly as the failure panels do.
	const publicRows = telemetryRows(TELEMETRY_ROOT, console.default_window_days).rows.map(
		publicTelemetry
	);
	const charts = chartDays(manifests, publishedCharts());
	const flow = chartFlow(charts);
	// The window the page opens on, drawn here so the prerendered card and the
	// control above it cannot disagree at first paint. The browser recomputes the
	// same card from the same rows when the operator moves the control.
	const today = new Date().toISOString().slice(0, 10);
	const seed = windowOfDays(
		datesIn(publicRows),
		today,
		console.default_window_days,
		console.today_anchor
	);
	// Six questions, six shapes. Each is drawn here so the console is complete
	// before any script runs; the client rebuilds the same option to hydrate.
	const runsDonut = runHealth(manifests);
	const articles = publishedItems();
	const perArticle = siteCost(manifests, articles, seed);
	const mixDates = datesIn(publicRows);
	const mix =
		mixDates.length === 0
			? failureMix([])
			: failureMix(
					failureSeries(publicRows, {
						start: mixDates[0],
						end: mixDates[mixDates.length - 1]
					})
				);
	// The published skyline is not drawn here. It is markup over `charts`, which
	// already crosses, so the page renders it at prerender time and redraws it
	// from the same array when the window moves - one drawing, not two.
	const draw = async (
		chart: { option: import('echarts').EChartsOption; empty: boolean },
		width: number,
		height: number
	) => (chart.empty ? null : await renderToSvg(chart.option, { width, height }));
	return {
		timingDays,
		manifests,
		// Articles per published day, read from the same tree `site_bytes` measures.
		// The denominator of the console's per-article cost, and the numerator's own
		// corpus - a count taken from anywhere else divides one tree's bytes by
		// another tree's articles.
		publishedItems: Object.fromEntries(articles),
		charts,
		glance: {
			healthSvg: await draw(runsDonut, 260, 200),
			healthShare: runsDonut.empty ? null : runsDonut.share,
			healthTotal: runsDonut.total,
			perArticleSvg: await draw(perArticle, 760, 220),
			mixSvg: await draw(mix, 760, 220)
			// No size chart and no published strip beside them: both follow the
			// window, and the page rebuilds each from an array it already carries
			// rather than from a second drawing on the server.
		},
		// Drawn here, so the shape is on the page before any script runs and stays
		// there if none ever does. Colour leaves as a custom-property reference, so
		// both themes work with no JavaScript at all.
		flowSvg: flow.empty
			? null
			: await renderToSvg(flow.option, {
					width: consoleConfig().chart_width,
					height: FLOW_HEIGHT
				}),
		// Printed where the diagram would have been. A panel that is simply absent
		// says nothing about which of the two nothings happened.
		flowNote: flow.reason,
		grid,
		floorPct,
		itemCeiling,
		siteBudgetMb,
		quarantineAfter,
		feeds: trouble(results, quarantineAfter),
		// One date axis for every feed's strip, so two rows can be read against each
		// other. A per-feed axis would put each strip on its own days, and "broken
		// since Tuesday" and "flaky all month" would draw the same picture.
		feedDates: [...new Set(results.map((row) => row.date))].sort(),
		feedsChecked: new Set(results.map((row) => row.feedId)).size,
		feedRuns: new Set(results.map((row) => row.runId)).size,
		// Ten rows and the two sentences under them, aggregated here rather than in
		// the browser. A window of the ledger is thousands of rows and this page
		// inlines whatever it is given, so the ten rows cross and the rows they were
		// made from do not.
		//
		// One table per preset, because the section follows the page's window and the
		// browser has no ledger to re-aggregate. Four tables of ten rows is cheaper
		// than one fetch, and it keeps the section working with no script at all.
		sourceCutsByWindow: console.window_presets.map((days) =>
			sourceCuts(itemRows, {
				days,
				limit: SOURCE_CUT_ROWS
			})
		),
		telemetryRows: publicRows,
		telemetryMonths: telemetryMonths(),
		console,
		// How a chart labels its axis and how wide its readout may be. Two knobs an
		// operator moves without editing a component.
		chart: chartConfig(),
		summarizeBands: summarize.bands,
		today
	};
}
