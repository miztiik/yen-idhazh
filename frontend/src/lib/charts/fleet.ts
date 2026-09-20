/** What the platform has been giving us, counted over a window.
 *
 * One entry per kind of machine, counted over the job placements the machine
 * record holds for the open span. A count of what happened and never a rate: the
 * share of a *future* draw is precisely what the processor lottery refuses to
 * quote, so no percentage, no probability and no pie belongs on this panel.
 *
 * **Under a stated number of rows it is a list and not a chart.** Bars over a
 * handful of placements read as a distribution and it is not one - and the
 * damage is not cosmetic, because a reader who has read a distribution off nine
 * rows will act on it. `console.fleet_min_rows` is the number, a declared
 * estimate derived from the rarest kind's 3.1 percent share of 356 committed
 * counter rows and the 5-observation floor `console.min_attempts_for_rate`
 * already sets.
 *
 * **Over the threshold it is a trend, because that is what the title asks.** One
 * group a day and one bar a kind, with everything past `console.fleet_top_kinds`
 * folded into one named row so a day's band keeps bars a reader can see.
 *
 * Pure. The threshold, the fold, the window and the switch arrive as arguments.
 */

import type { EChartsOption } from 'echarts';
import type { HostFingerprint } from '$lib/server/host-fingerprint';
import type { LostDay } from '$lib/console/recording';
import { dayMonth, shortDate } from '$lib/format';
import { columnStrip, type DayReadout } from './frame';
import { valueGutter } from './machine';
import {
	machineKeys,
	machineRamp,
	FOLDED_KEY,
	FOLDED_NAME,
	UNRECORDED_STOP,
	type MachineIdentity,
	type MachineKey,
	type MachineRamp,
	type MachineSeen
} from './machine-colour';
import { paint, type ChartToken } from './theme';

/** One kind's placements, day by day, in the order `FleetTrend.days` holds. */
export interface FleetSeries {
	identity: MachineIdentity;
	/** One entry per day drawn. Zero where the day recorded another kind only. */
	counts: number[];
	/** The window total. The figure the top-K fold is taken on. */
	placements: number;
}

/** The count as a trend: one group a day, one bar a kind, folded past top K.
 *
 * **The day grain is derived here and declared nowhere.** Every fingerprint row
 * carries its own `date`, so grouping by it needs no payload field - and a
 * declared one would be a second place for the grain to disagree with itself.
 *
 * **Only days that recorded something are drawn.** A day the machine record
 * never reached is not a day the platform gave us no machine, and a zero-height
 * group would say it was. How many of the window's days are missing is printed
 * above the plot instead.
 */
export interface FleetTrend {
	/** The days that recorded a placement, ascending. One group each. */
	days: string[];
	/** Kept kinds, biggest first, then the fold row last where one exists. */
	series: FleetSeries[];
	/** Kinds folded into that last row. Zero where nothing folded. */
	folded: number;
	/** The fold bar's own window total, read off the series that is drawn. */
	other: number;
	/** The same figure summed off the kinds that fell outside the top K. Two
	 * derivations of one quantity, so the page can be held to them agreeing. */
	outsideTop: number;
	/** The K the fold was taken at, so the panel can print the knob it read. */
	topKinds: number;
	/** Days of the window that recorded no placement at all. */
	daysWithout: number;
}

export interface FleetView {
	/** Every kind and its count, biggest first, with its colour. */
	kinds: { identity: MachineIdentity; placements: number }[];
	/** Job placements the count was made from. The denominator, printed. */
	placements: number;
	/** Days the window covers. */
	days: number;
	/** The threshold, so the sentence under the gate can state it. */
	minRows: number;
	/** True at or above the threshold. Below it the panel lists and draws no bar. */
	drawBars: boolean;
	/** The same count arranged by day, which is what the bars are drawn from. */
	trend: FleetTrend;
	/** Why there is nothing. Null where there is something.
	 *
	 * `record-lost` and `none` are the two the panel could not tell apart until
	 * 2026-09-17: a window whose every recorded day published articles and kept
	 * no row is a window that lost its count, not one waiting for a first run.
	 */
	nothing: 'recording-off' | 'record-lost' | 'none' | null;
}

/** Machine kinds over the window, ranked by how often the platform gave us one. */
export function fleetOverWindow(
	rows: readonly HostFingerprint[],
	options: {
		days: number;
		minRows: number;
		colourStops: number;
		/** How many kinds keep a bar of their own before the rest fold into one. */
		topKinds: number;
		/** False where the machine record is switched off. */
		recording: boolean;
		ramp?: MachineRamp;
		/** The page's own key resolver, built over the same population as the ramp. */
		keys?: (seen: MachineSeen) => MachineKey;
		/** Rows outside the open span are dropped before they are counted. */
		start?: string;
		end?: string;
		/** Days in this span that published articles and that the record kept no
		 * row of. Only their presence is read here; the sentence is the route's. */
		lost?: readonly LostDay[];
	}
): FleetView {
	const inWindow = rows.filter(
		(row) =>
			(options.start === undefined || row.date >= options.start) &&
			(options.end === undefined || row.date <= options.end)
	);
	const seen = inWindow.map((row) => ({ fingerprint: row.fingerprint, cpuModel: row.cpu_model }));
	const resolve = options.keys ?? machineKeys(seen);
	const keys = seen.map(resolve);
	const ramp = options.ramp ?? machineRamp(keys, options.colourStops);

	const counts = new Map<string, number>();
	for (const key of keys) {
		const identity = ramp.at.get(key.key);
		if (identity === undefined) continue;
		counts.set(identity.key, (counts.get(identity.key) ?? 0) + 1);
	}

	const kinds = ramp.rows
		.filter((identity) => (counts.get(identity.key) ?? 0) > 0)
		.map((identity) => ({ identity, placements: counts.get(identity.key) ?? 0 }))
		.sort((a, b) => b.placements - a.placements || a.identity.key.localeCompare(b.identity.key));

	return {
		kinds,
		placements: inWindow.length,
		days: options.days,
		minRows: options.minRows,
		drawBars: inWindow.length >= options.minRows,
		trend: trendOf(
			inWindow.map((row, index) => ({
				date: row.date,
				identity: ramp.at.get(keys[index].key) ?? null
			})),
			kinds,
			options.topKinds,
			options.days
		),
		nothing: !options.recording
			? 'recording-off'
			: inWindow.length > 0
				? null
				: (options.lost ?? []).length > 0
					? 'record-lost'
					: 'none'
	};
}

/** The lowest stop of the ramp no kept kind is holding.
 *
 * The fold row cannot take a colour a drawn kind already has - two kinds in one
 * hue with nothing on the page to say so - and it cannot take the reserved grey,
 * which would read as an absence. A fold only happens past K, and K is bounded
 * below the ramp's stops, so one is always free.
 */
function freeStop(taken: readonly number[]): number {
	for (let stop = 1; stop < UNRECORDED_STOP; stop += 1) {
		if (!taken.includes(stop)) return stop;
	}
	return UNRECORDED_STOP - 1;
}

/** The same placements arranged by day, with everything past K folded into one.
 *
 * The fold is taken on the window total and never per day, so a kind keeps the
 * same colour in every group. Folding per day would let one machine be its own
 * bar on Monday and part of `other` on Tuesday.
 */
function trendOf(
	placements: readonly { date: string; identity: MachineIdentity | null }[],
	kinds: readonly { identity: MachineIdentity; placements: number }[],
	topKinds: number,
	windowDays: number
): FleetTrend {
	const days = [...new Set(placements.map((one) => one.date))].sort();
	const at = new Map(days.map((date, index) => [date, index]));
	const perDay = new Map<string, number[]>();
	for (const one of placements) {
		if (one.identity === null) continue;
		const counts = perDay.get(one.identity.key) ?? days.map(() => 0);
		counts[at.get(one.date) ?? 0] += 1;
		perDay.set(one.identity.key, counts);
	}

	const keep = kinds.slice(0, Math.max(1, topKinds));
	const rest = kinds.slice(keep.length);
	const series: FleetSeries[] = keep.map((kind) => ({
		identity: kind.identity,
		counts: perDay.get(kind.identity.key) ?? days.map(() => 0),
		placements: kind.placements
	}));
	if (rest.length > 0) {
		const counts = days.map((_, index) =>
			rest.reduce((carry, kind) => carry + (perDay.get(kind.identity.key)?.[index] ?? 0), 0)
		);
		const total = rest.reduce((carry, kind) => carry + kind.placements, 0);
		const names = rest.map((kind) => kind.identity.name);
		// The ramp may already have folded, and its row can be one of the kept.
		// Two rows both called `Other machines` is the one shape that cannot ship.
		const already = series.find((one) => one.identity.key === FOLDED_KEY);
		if (already === undefined) {
			series.push({
				identity: {
					key: FOLDED_KEY,
					name: FOLDED_NAME,
					colourStop: freeStop(keep.map((kind) => kind.identity.colourStop)),
					folded: names
				},
				counts,
				placements: total
			});
		} else {
			already.identity = { ...already.identity, folded: [...already.identity.folded, ...names] };
			already.counts = already.counts.map((count, index) => count + counts[index]);
			already.placements += total;
		}
	}

	return {
		days,
		series,
		folded: rest.length,
		other: series.find((one) => one.identity.key === FOLDED_KEY)?.placements ?? 0,
		outsideTop: rest.reduce((carry, kind) => carry + kind.placements, 0),
		topKinds,
		daysWithout: Math.max(0, windowDays - days.length)
	};
}

/** One strip column a day, one row a kind: every count the tooltip carries.
 *
 * Printed, because a tooltip is never the only carrier of a fact and the
 * dominant reading device has no hover. It is the legend too - every kind drawn
 * is named and swatched here, so no second key is drawn beside the plot.
 */
export function fleetColumns(trend: FleetTrend): DayReadout[] {
	return columnStrip(
		trend.days.map(shortDate),
		trend.series.map((one) => ({
			label: one.identity.name,
			colour: `var(--chart-${one.identity.colourStop})`,
			value: (index: number) => `${one.counts[index] ?? 0}`
		}))
	);
}

/** One group a day, one bar a kind: what the platform handed us, over time.
 *
 * **A trend question takes a time axis.** The panel asks what has been given
 * lately, and a ranked list answers which is biggest - never what is changing.
 * The ordering the list carried survives as the sentence above the plot.
 *
 * **One quantity, so one adaptive domain.** Every bar counts placements, so the
 * bars are comparable by construction and there is no ceiling for the domain to
 * be fixed against. The 20x rule governs two series of one quantity choosing
 * between one axis and two rows; here the fold is what bounds the series count,
 * and every count is printed in the strip whatever height it draws at.
 */
export function fleetChart(trend: FleetTrend): {
	option: EChartsOption;
	empty: boolean;
	grid: { left: number; right: number };
} {
	const highest = Math.max(0, ...trend.series.flatMap((one) => one.counts));
	const grid = { left: valueGutter(highest), right: 12 };
	if (trend.days.length === 0 || trend.series.length === 0) {
		return { option: {}, empty: true, grid };
	}
	return {
		empty: false,
		grid,
		option: {
			animation: false,
			grid: { ...grid, top: 30, bottom: 26, containLabel: false },
			tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
			xAxis: {
				type: 'category',
				data: trend.days.map(dayMonth),
				axisLine: { lineStyle: { color: paint('--chart-axis') } },
				axisTick: { show: false },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 10, hideOverlap: true }
			},
			yAxis: {
				type: 'value',
				name: 'placements',
				nameTextStyle: { color: paint('--color-text-tertiary'), fontSize: 11 },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
				splitLine: { lineStyle: { color: paint('--chart-grid') } },
				minInterval: 1
			},
			series: trend.series.map((one) => ({
				name: one.identity.name,
				type: 'bar' as const,
				barMaxWidth: 24,
				itemStyle: { color: paint(`--chart-${one.identity.colourStop}` as ChartToken) },
				data: one.counts
			}))
		}
	};
}
