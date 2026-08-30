/** The console's headline answers, and the arithmetic behind each one.
 *
 * Six questions, six different shapes, because one shape repeated six times is
 * what made this page read as a single grey instrument. Each function here is
 * pure and is tested without a browser; the drawing belongs to the engine.
 *
 * Nothing is invented for the sake of a complete vocabulary. Every question
 * below is one the page already answered in prose or in a table, and each one
 * names the threshold it is measured against where the page states one.
 */

import type { RunSummary } from '$lib/server/payload';
import { donut } from './donut';
import { sparkline, sparklineMarks, type SparklineMarks } from './sparkline';
import { stacked } from './stacked';
import { targetBar, targetMarks, type TargetMarks } from './targetbar';
import { waterfall } from './waterfall';
import type { StageFailureSeries } from './series';

export interface GlanceDay {
	date: string;
	/** Charts a reader can see on the day's page. */
	published: number;
	/** Items the day published, chart or no chart. The denominator of coverage. */
	items: number;
	minutesPerChart: number | null;
}

/** How many days of history a card's trend line is allowed to carry. Long
 * enough to have a shape, short enough that a card is still a card. */
const TREND_DAYS = 14;

/** The middle value, or null where nothing was measured.
 *
 * The median rather than the mean, because every rule this module reads is
 * stated about the median day and one pathological day would otherwise decide
 * it.
 */
function medianOf(values: readonly number[]): number | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

/** Were the runs clean?
 *
 * Planned against failed across the window. A count of failures on its own does
 * not say whether that is most of the work or a rounding error, which is the
 * only thing the question is asking.
 */
export function runHealth(manifests: readonly RunSummary[]) {
	const planned = manifests.reduce((sum, m) => sum + m.planned, 0);
	const failed = manifests.reduce((sum, m) => sum + m.failed, 0);
	return donut(
		[
			{ label: 'finished', value: Math.max(0, planned - failed), token: '--band-high' },
			{ label: 'failed', value: failed, token: '--band-low' }
		],
		'finished'
	);
}

/** Is the chart arm worth its router time?
 *
 * The page states the rule in its own prose: over the rule's span the arm is
 * retired if the median day spends more than the target in router minutes per
 * published chart. That is a value against a target, and a number without its
 * target beside it cannot be acted on.
 *
 * The target arrives as an argument rather than as a constant here, because an
 * operator moves a threshold in `config/appearance.json` and never in a
 * component (Rule #6).
 */
export function routerCost(days: readonly GlanceDay[], target: number) {
	const median = medianOf(
		days.map((d) => d.minutesPerChart).filter((m): m is number => m !== null)
	);
	return targetBar(median, target, 'lower-is-better', 'Router minutes per chart');
}

/** What share of a day's published items carried a chart, in percent.
 *
 * Null where the day published nothing. A share of no articles is not zero
 * percent, it is no measurement at all, and a zero would read as an arm that
 * ran and reached nobody.
 */
export function coverageOf(day: GlanceDay): number | null {
	if (day.items <= 0) return null;
	return (day.published / day.items) * 100;
}

/** The three numbers the chart arm's retirement rule is written from. */
export interface ArmThresholds {
	/** The span the rule is stated over. */
	ruleDays: number;
	/** Router minutes per published chart that retires the arm. */
	minutesTarget: number;
	/** The share of published items that must carry a chart, in whole percent. */
	coveragePct: number;
}

/** Both halves of the rule, each as a bar, a trend and a clause of one sentence. */
export interface ChartArm {
	/** The window is narrower than the rule's own span, so no median is offered. */
	narrow: boolean;
	/** Window median router minutes per published chart, or null. */
	minutes: number | null;
	/** Window median coverage in percent, or null. */
	coverage: number | null;
	minutesMarks: TargetMarks;
	coverageMarks: TargetMarks;
	minutesTrend: SparklineMarks;
	coverageTrend: SparklineMarks;
	/** How many days each median was actually taken from. A median of one day is
	 * a day, and the page says which it is looking at. */
	minutesDays: number;
	coverageDays: number;
	/** One sentence stating both figures and whether each is inside its threshold. */
	verdict: string;
}

/** A threshold as words - `6`, not `6.0`, and `4.5` where it really is. */
function trim(value: number): string {
	return String(Number(value.toFixed(1)));
}

/** The two clauses of the verdict, joined.
 *
 * Each clause names its figure, its threshold and which side of it the figure
 * fell. A clause that only printed the figure would leave the reader to do the
 * comparison the rule already made.
 */
function verdictOf(
	minutes: number | null,
	coverage: number | null,
	thresholds: ArmThresholds,
	days: number
): string {
	const cost =
		minutes === null
			? `No router time was written down in the last ${days} days`
			: `The median day spends ${minutes.toFixed(1)} router minutes per chart, ` +
				`${minutes > thresholds.minutesTarget ? 'past' : 'inside'} the ` +
				`${trim(thresholds.minutesTarget)} that retires the arm`;
	const reach =
		coverage === null
			? 'no day published anything to put a chart on'
			: `puts a chart on ${Math.round(coverage)}% of what it published, ` +
				`${coverage < thresholds.coveragePct ? 'below' : 'above'} the ` +
				`${trim(thresholds.coveragePct)}% floor`;
	return `${cost}, and ${reach}.`;
}

/**
 * The chart arm judged against its own written rule, over the open window.
 *
 * `windowDays` is the span the page is holding, not the number of days the
 * ledger answered for. Under the rule's own span nothing is measured at all: a
 * median of the wrong span is the same figure with a different meaning, and
 * nothing on the page would say which one is being read.
 */
export function chartArm(
	days: readonly GlanceDay[],
	thresholds: ArmThresholds,
	windowDays: number
): ChartArm {
	const narrow = windowDays < thresholds.ruleDays;
	const ordered = [...days].sort((a, b) => a.date.localeCompare(b.date));
	const costs = narrow
		? []
		: ordered.map((d) => d.minutesPerChart).filter((m): m is number => m !== null);
	const reach = narrow
		? []
		: ordered.map(coverageOf).filter((c): c is number => c !== null);
	const minutes = medianOf(costs);
	const coverage = medianOf(reach);

	return {
		narrow,
		minutes,
		coverage,
		minutesMarks: targetMarks(minutes, thresholds.minutesTarget, 'lower-is-better'),
		coverageMarks: targetMarks(coverage, thresholds.coveragePct, 'higher-is-better'),
		minutesTrend: sparklineMarks(costs),
		coverageTrend: sparklineMarks(reach),
		minutesDays: costs.length,
		coverageDays: reach.length,
		verdict: verdictOf(minutes, coverage, thresholds, windowDays)
	};
}

/** Where did the site's size come from?
 *
 * The 1 GB ceiling is a rate problem, not a level problem, so the useful shape
 * is which days added what - not a line of the running total, which only ever
 * says "up".
 */
export function siteGrowth(manifests: readonly RunSummary[]) {
	const ordered = [...manifests].sort((a, b) => a.date.localeCompare(b.date)).slice(-TREND_DAYS);
	if (ordered.length < 2) return waterfall(0, []);
	const opening = ordered[0].siteBytes;
	const steps = ordered.slice(1).map((day, i) => ({
		label: day.date.slice(5),
		// Megabytes: a waterfall of nine-digit byte counts is a wall of digits.
		delta: Math.round(((day.siteBytes - ordered[i].siteBytes) / 1_000_000) * 10) / 10
	}));
	return waterfall(Math.round(opening / 1_000_000), steps);
}

/** What is failing, and is the mix changing?
 *
 * Stacked rather than grouped: the total per day is half the question, and
 * grouped bars answer "how big is each" while losing it.
 */
export function failureMix(series: readonly StageFailureSeries[]) {
	const columns = series[0]?.days.map((d) => d.date.slice(5)) ?? [];
	const TOKENS = ['--chart-1', '--chart-2', '--chart-3', '--chart-4'] as const;
	return stacked(
		columns,
		series.map((s, i) => ({
			label: s.label,
			token: TOKENS[i % TOKENS.length],
			values: s.days.map((d) => d.failures)
		}))
	);
}

/** Which way is publishing going? Direction only - the count says how much. */
export function publishedTrend(days: readonly GlanceDay[]) {
	const ordered = [...days].sort((a, b) => a.date.localeCompare(b.date)).slice(-TREND_DAYS);
	return sparkline(ordered.map((d) => d.published));
}

/** Which way is the site's size going? Same shape, different question.
 *
 * The card's own number is the latest absolute measurement and never moves with
 * the window. This is the other half of it: the movement and the line are over
 * whatever span the page is showing, so `days` is passed rather than assumed.
 */
export function sizeTrend(manifests: readonly RunSummary[], days: number = TREND_DAYS) {
	const ordered = [...manifests].sort((a, b) => a.date.localeCompare(b.date)).slice(-days);
	return sparkline(ordered.map((m) => m.siteBytes));
}
