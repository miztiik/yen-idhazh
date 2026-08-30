/** The console's headline answers, and the arithmetic behind each one.
 *
 * Six questions, six different shapes, because one shape repeated six times is
 * what made this page read as a single grey instrument. Each function here is
 * pure and is tested without a browser. Most hand the engine an option; the
 * skyline hands back geometry, because a strip of bars inside a card needs no
 * engine and a shape drawn as markup is finished before any script runs.
 *
 * Nothing is invented for the sake of a complete vocabulary. Every question
 * below is one the page already answered in prose or in a table, and each one
 * names the threshold it is measured against where the page states one.
 */

import type { RunSummary } from '$lib/server/payload';
import { donut } from './donut';
import { sparkline } from './sparkline';
import { stacked } from './stacked';
import { targetBar } from './targetbar';
import { daysInWindow, type TimeWindow } from './viewport';
import { waterfall } from './waterfall';
import type { StageFailureSeries } from './series';

export interface GlanceDay {
	date: string;
	published: number;
	minutesPerChart: number | null;
}

/** How many days of history a card's trend line is allowed to carry. Long
 * enough to have a shape, short enough that a card is still a card. */
const TREND_DAYS = 14;

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
 * The page already states the rule: over 14 days the arm is retired if the
 * median day spends more than 6 router minutes per published chart. That is a
 * value against a target, and a number without its target beside it cannot be
 * acted on.
 */
export const ROUTER_MINUTES_TARGET = 6;

/** The span the retirement rule is stated over.
 *
 * A window narrower than this cannot show the rule, and a median taken over the
 * wrong span is worse than no median: it is the same figure with a different
 * meaning and nothing on the page to say which one you are reading. So the card
 * prints the rule's own span and no number at all.
 */
export const RULE_WINDOW_DAYS = 14;

export function routerCost(days: readonly GlanceDay[]) {
	const timed = days.map((d) => d.minutesPerChart).filter((m): m is number => m !== null);
	if (timed.length === 0) {
		return targetBar(null, ROUTER_MINUTES_TARGET, 'lower-is-better', 'Router minutes per chart');
	}
	// The median, not the mean, because the rule the page states is about the
	// median day and one pathological day would otherwise decide it.
	const sorted = [...timed].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	const median =
		sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
	return targetBar(median, ROUTER_MINUTES_TARGET, 'lower-is-better', 'Router minutes per chart');
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

/** One bar a day: how much was published, and on which days.
 *
 * Bars, never a line. A count per day is a discrete quantity, and a line drawn
 * between two days claims a value for the hours in between that nobody
 * counted. The busiest day in the window sets the height of every other bar,
 * so the shape answers "which days were heavy" while the count beside it
 * answers "how many".
 *
 * The columns are the window the control set, not the days that happen to
 * carry a run. A chart that sizes itself to its own data while the control
 * above it reads thirty days puts two spans on one page, and two spans cannot
 * be compared - which is the question the operator came here to ask.
 *
 * Geometry only. Every value is a share of the drawing box, so the same bars
 * fit whatever width a card gives them and the markup does no arithmetic.
 */
export interface SkylineBar {
	date: string;
	published: number;
	/** Left edge and width, as a share of the box. */
	x: number;
	width: number;
	/** Height as a share of the box, measured up from the baseline. A day that
	 * published nothing is zero high and still has a bar, so the column count is
	 * the day count whatever the ledger holds. */
	height: number;
}

export interface Skyline {
	bars: SkylineBar[];
	/** Everything the window published. The count beside the bars is this. */
	total: number;
	/** The busiest day, which every other bar is drawn against. */
	busiest: number;
	/** True where the window published nothing at all. A strip of thirty zeros
	 * is an empty plot area, which is worse than no plot. */
	empty: boolean;
}

/** How much of a column a bar fills, leaving the rest as the gap beside it. A
 * share rather than a pixel, so ninety columns separate as cleanly as seven. */
const BAR_SHARE = 0.8;

export function publishedSkyline(days: readonly GlanceDay[], span: TimeWindow): Skyline {
	const calendar = daysInWindow(span);
	const onDate = new Map(days.map((day) => [day.date, day.published]));
	const counts = calendar.map((date) => onDate.get(date) ?? 0);
	const busiest = counts.reduce((high, count) => Math.max(high, count), 0);
	const pitch = 1 / calendar.length;
	const width = pitch * BAR_SHARE;
	return {
		total: counts.reduce((sum, count) => sum + count, 0),
		busiest,
		empty: busiest === 0,
		bars: calendar.map((date, index) => ({
			date,
			published: counts[index],
			x: index * pitch + (pitch - width) / 2,
			width,
			height: busiest === 0 ? 0 : counts[index] / busiest
		}))
	};
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
