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
import type { ChartToken } from './theme';
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

/** The three stages in the categorical ramp, in pipeline order. */
const STAGE_TOKENS: readonly ChartToken[] = ['--chart-1', '--chart-2', '--chart-3'];

/** The band under the failures: items that got through all three stages.
 *
 * A neutral rather than a fourth ramp colour, because colour is spent on a
 * failure and this is the ground the failures sit on. Neutral, not faint:
 * `--chart-grid` reaches the light theme at #e6eaf3 on a #f4f6fb page, which is
 * 1.07 to 1, and this band is most of the column on most days. The column
 * height IS the volume, so a band nobody can see loses the one fact this chart
 * was rebuilt to carry.
 */
const FINISHED_TOKEN: ChartToken = '--chart-axis';

/** Items the run listed and never fetched. Zero on every day measured so far,
 * so it draws only when it is not. The last stop of the ramp is the slate one,
 * which reads as another neutral beside the ground rather than a fourth kind of
 * failure. */
const SKIPPED_TOKEN: ChartToken = '--chart-8';

export interface FailureBand {
	key: string;
	label: string;
	token: ChartToken;
	value: number;
}

/** One day of the volume column, bottom of the stack first. */
export interface FailureColumn {
	date: string;
	planned: number;
	bands: FailureBand[];
}

/** One day of one stage's line: the share, and what it was taken over. */
export interface FailurePoint {
	date: string;
	rate: number | null;
	reached: number;
}

/** One stage over the whole window: the rate, and the volume behind it. */
export interface FailureStage {
	stage: string;
	label: string;
	token: ChartToken;
	/** The denominator. Items that got as far as this stage. */
	reached: number;
	failures: number;
	/** Nought to one, or null where too few items reached the stage to divide
	 * by. Null is not zero and never prints as one. */
	rate: number | null;
	/** Something reached the stage, but under `min_attempts_for_rate` of it. */
	lowSample: boolean;
	/** One entry per day. `rate` is null where the day is empty or too thin to
	 * divide, so the line breaks rather than drawing a share nobody measured,
	 * and `reached` travels with it so a mark can name its own denominator. */
	points: FailurePoint[];
}

export interface FailureLoad {
	dates: string[];
	columns: FailureColumn[];
	stages: FailureStage[];
	/** The tallest column. The volume axis is drawn to this. */
	peak: number;
	/** Nothing was planned in this window at all. */
	empty: boolean;
}

/** Failure rate against the volume it was measured on.
 *
 * Three panels became one chart. Three of anything at 492px on a 1600px frame
 * is the layout that produced two text nodes each, and the split was the
 * problem rather than the content: a rate and the volume behind it are one
 * picture, and reading them off two charts is arithmetic the operator should
 * not have to do. A 100 percent failure on two items and an outage look the
 * same until the column height is beside the line.
 *
 * The denominator is the stage's own, never the day's. `series.ts` carries why.
 *
 * Nothing is drawn for a stage the window is too thin to measure. A share over
 * four items is not a measurement (`min_attempts_for_rate`), and the same knob
 * decides it here and in the source-cut table, so two shares on one page cannot
 * disagree about when a denominator is too small.
 */
export function failureLoad(
	series: readonly StageFailureSeries[],
	minAttempts: number
): FailureLoad {
	const dates = series[0]?.days.map((day) => day.date) ?? [];
	const stages = series.map((entry, index) => {
		const token = STAGE_TOKENS[index % STAGE_TOKENS.length];
		const reached = entry.days.reduce((sum, day) => sum + day.reached, 0);
		const failures = entry.days.reduce((sum, day) => sum + day.failures, 0);
		const thin = reached > 0 && reached < minAttempts;
		return {
			stage: entry.stage,
			label: entry.label,
			token,
			reached,
			failures,
			rate: reached < minAttempts ? null : failures / reached,
			lowSample: thin,
			points: entry.days.map((day) => ({
				date: day.date,
				rate: day.reached < minAttempts ? null : day.rate,
				reached: day.reached
			}))
		};
	});

	const columns = dates.map((date, index) => {
		const planned = series[0]?.days[index]?.planned ?? 0;
		const lastStage = series.at(-1)?.days[index];
		const finished =
			lastStage === undefined ? 0 : Math.max(0, lastStage.reached - lastStage.failures);
		// The day splits exactly: never fetched, plus what died at each stage, plus
		// what got through. So the column height is the day and no band is a
		// residue nobody can name.
		const skipped = Math.max(0, planned - (series[0]?.days[index]?.reached ?? 0));
		const bands: FailureBand[] = [
			{ key: 'finished', label: 'Finished', token: FINISHED_TOKEN, value: finished },
			...series.map((entry, stageIndex) => ({
				key: entry.stage,
				label: entry.label,
				token: STAGE_TOKENS[stageIndex % STAGE_TOKENS.length],
				value: entry.days[index]?.failures ?? 0
			})),
			{ key: 'skipped', label: 'Never fetched', token: SKIPPED_TOKEN, value: skipped }
		];
		return { date, planned, bands: bands.filter((band) => band.value > 0) };
	});

	return {
		dates,
		columns,
		stages,
		peak: columns.reduce((most, column) => Math.max(most, column.planned), 0),
		empty: columns.every((column) => column.planned === 0)
	};
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
