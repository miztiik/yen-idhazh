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

import type { EChartsOption } from 'echarts';
import type { RunSummary } from '$lib/server/payload';
import { donut } from './donut';
import type { DayReadout } from './frame';
import { sparklineMarks, type SparklineMarks } from './sparkline';
import { stacked, type StackShape } from './stacked';
import { targetMarks, type TargetMarks } from './targetbar';
import { daysInWindow, type TimeWindow } from './viewport';
import { paint, type ChartToken } from './theme';
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

/** GitHub Pages refuses a site larger than this (Rule #2).
 *
 * A constant and not a config knob, for the reason
 * `backend/idhazh/retention.py` gives for its own copy: it is a property of the
 * host, and a knob would invite raising it instead of shrinking the site.
 */
export const PAGES_CAP_BYTES = 1024 * 1024 * 1024;

/** The middle value, or null where there is nothing to take a middle of.
 *
 * The median and not the mean everywhere on this page: one pathological day
 * would otherwise decide a figure the operator reads as typical.
 */
function middleOf(values: readonly number[]): number | null {
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
			? `No router time is on record for these ${days} days`
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
	const minutes = middleOf(costs);
	const coverage = middleOf(reach);

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

/** One published day's marginal cost, in bytes of payload tree per article. */
export interface SiteCostDay {
	date: string;
	/** What the tree gained that day, over the articles that day published. */
	bytesPerItem: number;
	/** Further from the window's median than one standard deviation. */
	flagged: boolean;
}

export interface SiteCost {
	option: EChartsOption;
	days: SiteCostDay[];
	/** The window's median cost, or null where no day in it has a rate. */
	median: number | null;
	/** Root-mean-square distance from that median, in the same unit. */
	spread: number | null;
	empty: boolean;
}

/** What one more published article costs, day by day.
 *
 * The chart this replaced drew megabytes added per day, and that number is the
 * item ceiling wearing a size label: measured over the ten committed manifests
 * on 2026-08-30, a day's gain ran 0.04 MB to 2.82 MB purely because the day
 * published 4 articles or 731. Divided by the articles, the same ten days sit
 * between 2,478 and 4,541 bytes - which is a quantity a change to the payload
 * can actually move.
 *
 * The band is one standard deviation about the MEDIAN rather than about the
 * mean: the line drawn on the chart is the median, and a band whose centre and
 * whose width came from two different statistics is asymmetric about its own
 * centre for no reason a reader can see.
 *
 * `window` bounds what is drawn and never what is differenced. A day's cost is
 * its own bytes minus the previous manifest's, so the oldest day on screen
 * still reads against the day before it rather than against zero.
 */
export function siteCost(
	manifests: readonly RunSummary[],
	items: ReadonlyMap<string, number>,
	window: { start: string; end: string } | null = null
): SiteCost {
	const ordered = [...manifests].sort((a, b) => a.date.localeCompare(b.date));
	const measured: { date: string; bytesPerItem: number }[] = [];
	for (let i = 1; i < ordered.length; i += 1) {
		const day = ordered[i];
		if (window !== null && (day.date < window.start || day.date > window.end)) continue;
		const published = items.get(day.date) ?? 0;
		// A day that published nothing has no rate. Zero here would say its
		// articles were free, and there were none.
		if (published <= 0) continue;
		measured.push({
			date: day.date,
			bytesPerItem: (day.siteBytes - ordered[i - 1].siteBytes) / published
		});
	}

	const middle = middleOf(measured.map((d) => d.bytesPerItem));
	if (middle === null) {
		return { option: {}, days: [], median: null, spread: null, empty: true };
	}

	// A spread of one observation is not a spread. Reported as absent rather
	// than as zero, because a zero band would call the one day on the chart
	// perfectly typical of itself.
	const spread =
		measured.length < 2
			? null
			: Math.sqrt(
					measured.reduce((sum, d) => sum + (d.bytesPerItem - middle) ** 2, 0) / measured.length
				);
	const days: SiteCostDay[] = measured.map((d) => ({
		...d,
		flagged: spread !== null && Math.abs(d.bytesPerItem - middle) > spread
	}));

	const rule = (dash: boolean) => ({
		lineStyle: {
			color: paint('--chart-marker'),
			width: dash ? 1 : 1.5,
			type: dash ? ('dashed' as const) : ('solid' as const)
		},
		label: { show: false }
	});

	const band =
		spread === null
			? []
			: [
					{ yAxis: Math.round(middle + spread), ...rule(true) },
					{ yAxis: Math.round(middle - spread), ...rule(true) }
				];

	return {
		days,
		median: middle,
		spread,
		empty: false,
		option: {
			animation: false,
			grid: { left: 56, right: 14, top: 34, bottom: 26, containLabel: false },
			tooltip: { trigger: 'axis' },
			xAxis: {
				type: 'category',
				data: days.map((d) => d.date.slice(5)),
				axisLine: { lineStyle: { color: paint('--chart-axis') } },
				axisTick: { show: false },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11, hideOverlap: true }
			},
			yAxis: {
				type: 'value',
				// The quantity, then the unit, in the one form every axis title on
				// this site takes (design-system.md). A bare four-digit number on an
				// axis is not readable as bytes.
				name: 'Payload bytes per article',
				nameLocation: 'end',
				nameGap: 12,
				nameTextStyle: { color: paint('--color-text-tertiary'), fontSize: 11, align: 'left' },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
				splitLine: { lineStyle: { color: paint('--chart-grid') } }
			},
			series: [
				{
					name: 'Payload bytes per article',
					type: 'line',
					showSymbol: true,
					// The mark that says "look here" is the marker token, never the
					// confidence ramp: a day outside the band is unusual, and nobody
					// has agreed that unusual is bad.
					data: days.map((d) => ({
						value: Math.round(d.bytesPerItem),
						symbolSize: d.flagged ? 10 : 5,
						itemStyle: { color: paint(d.flagged ? '--chart-marker' : '--chart-3') }
					})),
					lineStyle: { width: 1.75, color: paint('--chart-3') },
					markLine: {
						silent: true,
						symbol: 'none',
						data: [{ yAxis: Math.round(middle), ...rule(false) }, ...band]
					}
				}
			]
		}
	};
}

/** Published days of room left, at the cost the window measured.
 *
 * The same arithmetic `backend/idhazh/retention.py` runs against the built
 * bundle: headroom divided by one published day's growth, where a day's growth
 * is the per-article cost times the articles a day is allowed to publish. The
 * item ceiling and not an average of the days on disk - a day that published 97
 * articles is not evidence the next one will, and the ceiling is the most a day
 * may cost (Rule #10).
 *
 * Null where there is no rate to divide by. A tree that did not grow over the
 * window has no date attached to it, and printing one anyway is the whole
 * defect this replaced.
 */
export interface SiteRunway {
	/** Bytes one more published day is expected to add. */
	perDay: number;
	/** Published days to the alarm point. Negative once it is behind us. */
	toAlarm: number;
	/** Published days to the Pages cap. */
	toCap: number;
}

export function siteRunway(
	bytesUsed: number,
	bytesPerItem: number | null,
	itemsPerDay: number,
	alarmBytes: number,
	capBytes: number = PAGES_CAP_BYTES
): SiteRunway | null {
	if (bytesPerItem === null || bytesPerItem <= 0 || itemsPerDay <= 0) return null;
	const perDay = bytesPerItem * itemsPerDay;
	return {
		perDay,
		toAlarm: (alarmBytes - bytesUsed) / perDay,
		toCap: (capBytes - bytesUsed) / perDay
	};
}

/** What is failing, and is the mix changing?
 *
 * Stacked rather than grouped: the total per day is half the question, and
 * grouped bars answer "how big is each" while losing it. The same array also
 * draws as lines - see `ShapeSwitch` - which answers the other half, what one
 * stage did on its own.
 */
export function failureMix(series: readonly StageFailureSeries[], shape: StackShape = 'bars') {
	const columns = series[0]?.days.map((d) => d.date.slice(5)) ?? [];
	return stacked(
		columns,
		series.map((s, i) => ({
			label: s.label,
			token: MIX_TOKENS[i % MIX_TOKENS.length],
			values: s.days.map((d) => d.failures)
		})),
		shape
	);
}

const MIX_TOKENS = ['--chart-1', '--chart-2', '--chart-3', '--chart-4'] as const;

/** Every stage's failure count on one day, for the strip under the chart.
 *
 * A stack is the hardest shape to read one band off, so the band a reader
 * wants is the one the eye cannot measure. The strip prints all four at the
 * hovered column, which is what turns four hovers into one.
 */
export function failureMixColumns(series: readonly StageFailureSeries[]): DayReadout[] {
	const dates = series[0]?.days.map((d) => d.date) ?? [];
	return dates.map((date, index) => ({
		x: 0,
		date,
		rows: series.map((stage, position) => ({
			label: stage.label,
			value: String(stage.days[index]?.failures ?? 0),
			colour: `var(${MIX_TOKENS[position % MIX_TOKENS.length]})`
		}))
	}));
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

/** How many bytes the tree gained across the window.
 *
 * The card's own number is the latest absolute measurement and never moves with
 * the window. This is the other half of it, and it is bytes rather than a share
 * for a measured reason: the oldest committed manifest recorded 13,595 bytes,
 * so a share taken from there read `+73,933%` on 2026-08-30 - true, useless, and
 * painted green by the card's own up-is-good rule, which for a site size is the
 * wrong verdict as well as an unasked-for one.
 *
 * Null under two measurements. One measurement has nothing to move from.
 */
export function sizeGain(manifests: readonly RunSummary[]): number | null {
	const ordered = [...manifests].sort((a, b) => a.date.localeCompare(b.date));
	if (ordered.length < 2) return null;
	return ordered[ordered.length - 1].siteBytes - ordered[0].siteBytes;
}
