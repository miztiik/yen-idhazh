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
import { sparkline } from './sparkline';
import { stacked } from './stacked';
import { targetBar } from './targetbar';
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

/** Which way is publishing going? Direction only - the count says how much. */
export function publishedTrend(days: readonly GlanceDay[]) {
	const ordered = [...days].sort((a, b) => a.date.localeCompare(b.date)).slice(-TREND_DAYS);
	return sparkline(ordered.map((d) => d.published));
}

/** Which way is the site's size going? Same shape, different question. */
export function sizeTrend(manifests: readonly RunSummary[]) {
	const ordered = [...manifests].sort((a, b) => a.date.localeCompare(b.date)).slice(-TREND_DAYS);
	return sparkline(ordered.map((m) => m.siteBytes));
}
