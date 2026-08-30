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

import type { EChartsOption } from 'echarts';
import type { RunSummary } from '$lib/server/payload';
import { donut } from './donut';
import { sparkline } from './sparkline';
import { stacked } from './stacked';
import { targetBar } from './targetbar';
import { paint } from './theme';
import type { StageFailureSeries } from './series';

export interface GlanceDay {
	date: string;
	published: number;
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
	const median = middleOf(timed);
	// The median, not the mean, because the rule the page states is about the
	// median day and one pathological day would otherwise decide it.
	return targetBar(median, ROUTER_MINUTES_TARGET, 'lower-is-better', 'Router minutes per chart');
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
 * between 2,478 and 4,542 bytes - which is a quantity a change to the payload
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
