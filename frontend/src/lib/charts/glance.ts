/** The arithmetic behind the console's drawing rule, site cost and headline counts. */
import type { RunSummary } from '$lib/server/payload';
import { countDays, nameSpan, openWithSpan } from '../console/span-words';
import { sparklineMarks, type SparklineMarks } from './sparkline';
import { targetMarks, type TargetMarks } from './targetbar';
import { daysInWindow, type TimeWindow } from './viewport';
import { grouped } from './series';
import { formatNumber, type NumberFormatConfig } from '../number-format';

export interface GlanceDay {
	date: string;
	published: number;
	items: number;
	minutesPerChart: number | null;
}

/** GitHub Pages refuses a site larger than this; it is a host limit, not a knob. */
export const PAGES_CAP_BYTES = 1024 * 1024 * 1024;

function middleOf(values: readonly number[]): number | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

/** A day that published nothing has no coverage measurement, not zero coverage. */
export function coverageOf(day: GlanceDay): number | null {
	if (day.items <= 0) return null;
	return (day.published / day.items) * 100;
}

export interface ChartThresholds {
	ruleDays: number;
	minutesTarget: number;
	coveragePct: number;
}

export interface ChartRule {
	narrow: boolean;
	minutes: number | null;
	coverage: number | null;
	minutesMarks: TargetMarks;
	coverageMarks: TargetMarks;
	minutesTrend: SparklineMarks;
	coverageTrend: SparklineMarks;
	minutesDays: number;
	coverageDays: number;
	verdict: string;
}

export function minutesText(minutes: number, numberFormat: NumberFormatConfig): string {
	return formatNumber(minutes, numberFormat, { si: false });
}

export function coverageText(coverage: number, numberFormat: NumberFormatConfig): string {
	return `${formatNumber(coverage, numberFormat, { si: false })}%`;
}

function verdictOf(
	minutes: number | null,
	coverage: number | null,
	thresholds: ChartThresholds,
	days: number,
	numberFormat: NumberFormatConfig
): string {
	const day = days === 1 ? openWithSpan(days) : 'The median day';
	const cost =
		minutes === null
			? `${day} has no minutes on record${days === 1 ? '' : ` over ${nameSpan(days)}`}`
			: `${day} spends ${minutesText(minutes, numberFormat)} minutes per visual, ` +
				`${minutes > thresholds.minutesTarget ? 'past' : 'inside'} the ` +
				`${formatNumber(thresholds.minutesTarget, numberFormat, { si: false })} that retires chart drawing`;
	const reach =
		coverage === null
			? days === 1
				? 'did not publish anything to put a visual on'
				: 'no day published anything to put a visual on'
			: `puts a visual on ${coverageText(coverage, numberFormat)} of what it published, ` +
				`${coverage < thresholds.coveragePct ? 'below' : 'above'} the ` +
				`${formatNumber(thresholds.coveragePct, numberFormat, { si: false })}% floor`;
	return `${cost}, and ${reach}.`;
}

/** The rule's span is the open window, not the count of days that answered it. */
export function chartRule(
	days: readonly GlanceDay[],
	thresholds: ChartThresholds,
	windowDays: number,
	numberFormat: NumberFormatConfig
): ChartRule {
	const narrow = windowDays < thresholds.ruleDays;
	const ordered = narrow ? [] : [...days].sort((a, b) => a.date.localeCompare(b.date));
	// Each day's reading with its date beside it, so the line and its strip
	// drop a day nobody measured together and cannot name the wrong day.
	const minutesTrend = sparklineMarks(
		ordered.map((day) => ({ date: day.date, value: day.minutesPerChart }))
	);
	const coverageTrend = sparklineMarks(
		ordered.map((day) => ({ date: day.date, value: coverageOf(day) }))
	);
	const minutes = middleOf(minutesTrend.values);
	const coverage = middleOf(coverageTrend.values);

	return {
		narrow,
		minutes,
		coverage,
		minutesMarks: targetMarks(minutes, thresholds.minutesTarget, 'lower-is-better'),
		coverageMarks: targetMarks(coverage, thresholds.coveragePct, 'higher-is-better'),
		minutesTrend,
		coverageTrend,
		minutesDays: minutesTrend.values.length,
		coverageDays: coverageTrend.values.length,
		verdict: verdictOf(minutes, coverage, thresholds, windowDays, numberFormat)
	};
}

export interface SiteCostDay {
	date: string;
	bytesPerItem: number;
	flagged: boolean;
}

export interface SiteCost {
	days: SiteCostDay[];
	median: number | null;
	/** Root-mean-square distance from the median, not from the mean. */
	spread: number | null;
	empty: boolean;
}

/** The window bounds the rates shown, never the predecessor used to price a day. */
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
	if (middle === null) return { days: [], median: null, spread: null, empty: true };
	// One observation has no spread; it is not perfectly typical of itself.
	const spread =
		measured.length < 2
			? null
			: Math.sqrt(
					measured.reduce((sum, d) => sum + (d.bytesPerItem - middle) ** 2, 0) / measured.length
				);
	return {
		days: measured.map((d) => ({
			...d,
			flagged: spread !== null && Math.abs(d.bytesPerItem - middle) > spread
		})),
		median: middle,
		spread,
		empty: false
	};
}

const DAYS_A_YEAR = 365.25;

export interface PublishingHorizon {
	articles: number;
	articlesPerDay: number;
	years: number;
}

/** Both measured rates use the same published days; neither assumes runs per day. */
export function publishingHorizon(
	bytesUsed: number | null,
	cost: SiteCost,
	items: ReadonlyMap<string, number>,
	capBytes: number = PAGES_CAP_BYTES
): PublishingHorizon | null {
	if (bytesUsed === null || cost.median === null || cost.median <= 0) return null;
	const perDay = middleOf(
		cost.days.map((day) => items.get(day.date) ?? 0).filter((count) => count > 0)
	);
	if (perDay === null || perDay <= 0) return null;
	const articles = (capBytes - bytesUsed) / cost.median;
	return { articles, articlesPerDay: perDay, years: articles / perDay / DAYS_A_YEAR };
}

export function siteCostMeasure(windowDays: number): string {
	return windowDays === 1
		? `Bytes the committed payload tree gained in ${nameSpan(windowDays)}, over the articles the day published.`
		: `Bytes the committed payload tree gained on each published day, over the articles that day published. Over ${countDays(windowDays)}.`;
}

export function horizonRate(
	articlesPerDay: number,
	windowDays: number,
	numberFormat: NumberFormatConfig
): string {
	const rate = `${grouped(Math.round(articlesPerDay), numberFormat)} articles a published day`;
	return windowDays === 1 ? `${rate}, ${nameSpan(windowDays)}'s count` : `a median of ${rate}`;
}

export interface SkylineBar {
	date: string;
	published: number;
	x: number;
	width: number;
	height: number;
}

export interface Skyline {
	bars: SkylineBar[];
	total: number;
	busiest: number;
	empty: boolean;
}

const BAR_SHARE = 0.8;
export type PublishedMeasure = 'items' | 'published';

/** One discrete bar per calendar day, including the days with no published count. */
export function publishedSkyline(
	days: readonly GlanceDay[],
	span: TimeWindow,
	measure: PublishedMeasure = 'published'
): Skyline {
	const calendar = daysInWindow(span);
	const onDate = new Map(days.map((day) => [day.date, day[measure]]));
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

/** Absolute bytes gained need two measurements, not a percentage of the oldest tree. */
export function sizeGain(manifests: readonly RunSummary[]): number | null {
	if (manifests.length < 2) return null;
	// The earliest-dated and latest-dated manifest, in one pass. A full sort only
	// to read its two ends is a cost the card pays for nothing. Ties resolve as
	// the sort did - the first manifest of the earliest date, the last of the
	// latest - so a same-day correction still moves the gain by what it should.
	let earliest = manifests[0];
	let latest = manifests[0];
	for (const run of manifests) {
		if (run.date.localeCompare(earliest.date) < 0) earliest = run;
		if (run.date.localeCompare(latest.date) >= 0) latest = run;
	}
	return latest.siteBytes - earliest.siteBytes;
}
