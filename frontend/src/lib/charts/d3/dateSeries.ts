/** What is changing: named series over dated points, as lines or as stacked bars.
 *
 * Lines are for reading each series on its own; stacked bars are for the mix
 * of one total, one bar a day. Both shapes come out of this one call over the
 * same days and the same value axis, so switching between them re-draws the
 * same numbers and derives nothing new.
 *
 * **A missing date is a gap, never a zero.** A line breaks across it and a stack
 * draws no segment for it, because a zero says the reading was taken and came
 * back nothing - a claim about a date nobody measured.
 *
 * **The dates on the axis come from `dayTicks`**, the one rule this console has
 * for a date axis, and never from an axis generator.
 */
import { area, line, stack, stackOrderDescending } from 'd3-shape';

import { dayTicks, type DayTick, type Frame } from '../frame';
import type { ChartToken } from '../theme';
import { valueAxis, type ValueAxis } from './axis';
import { bandScale } from './scale';
import { checkedRule, LEGACY_MODEL_RULE, ruleBoundaries, ruleEvents, type ModelRule, type RuleBoundary } from './model-rule';
import { spreadPaint } from './spread-paint';
import { readoutOf, type Readout, type ReadoutInput, type ReadoutInputSeries } from '../readout';
import { formatNumber, type NumberFormatConfig } from '../../number-format';

/** One reading: a calendar year (`YYYY`) or UTC date (`YYYY-MM-DD`), and its
 * value or null where none was recorded. */
export interface SeriesPoint {
	date: string;
	value: number | null;
	/** The band drawn behind the line on this day, from `low` to `high`. The
	 * series must name both edges in `spreadLabels`. */
	spread?: { low: number; high: number };
}

/** What a band's two edges are called in the readout. */
export interface SpreadLabels {
	low: string;
	high: string;
}

export interface SeriesInput {
	label: string;
	token: ChartToken;
	points: readonly SeriesPoint[];
	/** A paint of the series' own in place of its token: a step of an ordered
	 * ramp, which is a mix of a token and not a token. */
	fill?: string;
	/** Drawn as the hatch for a known thing with no reading, in place of a fill. */
	hatched?: boolean;
	/** Printed after each of this series' readings in the readout, so a share
	 * reads `92%` and not `92`, and after each tick of the value axis when every
	 * series on that axis names the same unit. */
	unit?: string;
	/** Required wherever a point carries a spread. The readout prints one row
	 * for each edge, keyed by the band's own paint, so a band is never drawn
	 * without the figures that bound it. */
	spreadLabels?: SpreadLabels;
}

export interface DateSeriesOptions {
	frame: Frame;
	stacked?: boolean;
	/** Rank each day's parts independently; other charts retain their declared series order. */
	stackOrder?: 'series' | 'descending';
	/** `chart.tick_density` - the most dates the axis may carry. */
	density: number;
	/** How many ticks the value axis aims for. */
	valueTicks: number;
	/** How the value axis writes a tick, for a caller whose ticks need more than
	 * the series' unit after them. It wins over that unit. Without it a tick
	 * carries the unit every series names, or else uses the shared number style. */
	valueFormat?: (value: number) => string;
	number_format: NumberFormatConfig;
	/** The share of each day's column left empty beside its bar, 0 to 1. */
	padding: number;
	rule: ModelRule;
	rules?: readonly { at: number; label: string }[];
	domain?: [number, number];
	/** Non-negative stage durations stay intact; overlap is deducted beside the stack. */
	reconciliation?: {
		elapsed: SeriesInput;
		overlap: SeriesInput;
	};
}

/** Old callers keep their drawing; new chart options require a declared rule. */
export type LegacyDateSeriesOptions = Omit<DateSeriesOptions, 'rule' | 'rules' | 'domain' | 'reconciliation' | 'valueFormat'> & {
	rule?: never; rules?: never; domain?: never; reconciliation?: never; valueFormat?: never;
};

export interface PlacedPoint {
	date: string;
	value: number;
	x: number;
	y: number;
	/** No reading on either side of it, so a line cannot draw it and the
	 * component puts a dot there. */
	alone: boolean;
}

export interface SeriesLine {
	label: string;
	token: ChartToken;
	path: string;
	points: PlacedPoint[];
	spread: string;
}

export interface SeriesBar {
	date: string;
	label: string;
	token: ChartToken;
	/** What the bar is filled with: the series' own paint, or its token. */
	fill: string;
	hatched: boolean;
	value: number;
	x: number;
	y: number;
	width: number;
	height: number;
}

/** Where two stacked segments of one day meet. A line of the ground is drawn
 * over it, so two segments of one colour still read as two, and neither loses
 * height to it. */
export interface SeriesJoin {
	x: number;
	y: number;
	width: number;
}

export interface SeriesGeometry {
	frame: Frame;
	dates: string[];
	/** Where each day's column is centred, in the chart's own pixels. */
	columns: number[];
	/** How wide one day's column is drawn, in the chart's own pixels. */
	bandwidth: number;
	ticks: DayTick[];
	axis: ValueAxis;
	stacked: boolean;
	/** Empty when stacked. */
	lines: SeriesLine[];
	/** Empty when not stacked. */
	bars: SeriesBar[];
	/** Empty when not stacked. */
	joins: SeriesJoin[];
	rule: ModelRule;
	boundaries: RuleBoundary[];
	events: NonNullable<ReadoutInput['events']>;
	readout: Readout;
	rules: { at: number; label: string; y: number }[];
	reconciliation?: {
		elapsed: { label: string; token: ChartToken };
		overlap: { label: string; token: ChartToken };
		marks: {
			date: string;
			elapsed: number;
			overlap: number;
			top: number;
			y: number;
			x: number;
			end: number;
			bracket: number;
		}[];
	};
}

const DATE_OR_YEAR = /^\d{4}(?:-\d{2}-\d{2})?$/;

function validDateOrYear(value: string): boolean {
	if (!DATE_OR_YEAR.test(value)) return false;
	if (value.length === 4) return true;
	const date = new Date(`${value}T00:00:00Z`);
	return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

/** Each series' readings keyed by day, refusing what cannot be one reading a day. */
function byDay(series: readonly SeriesInput[]): Map<string, number | null>[] {
	const labels = new Set<string>();
	return series.map((entry) => {
		if (labels.has(entry.label)) throw new Error(`Two series are both called "${entry.label}".`);
		labels.add(entry.label);
		const days = new Map<string, number | null>();
		for (const point of entry.points) {
			if (!validDateOrYear(point.date)) {
				throw new Error(`"${point.date}" is not a UTC date written YYYY-MM-DD or a year written YYYY.`);
			}
			if (days.has(point.date)) throw new Error(`"${entry.label}" has two readings for ${point.date}.`);
			days.set(point.date, point.value !== null && Number.isFinite(point.value) ? point.value : null);
		}
		return days;
	});
}

/** A reading in the shared number style, then its unit. The readout and the
 * value axis both write a series' figures this way, so they cannot disagree
 * about the unit. */
function withUnit(numberFormat: NumberFormatConfig, unit: string | undefined): (value: number) => string {
	return (value) => `${formatNumber(value, numberFormat)}${unit ?? ''}`;
}

/** The unit every series on one axis names, or undefined where they differ or
 * none names one: a suffix on the axis would be wrong for a series that
 * measures something else. */
function sharedUnit(series: readonly SeriesInput[]): string | undefined {
	const [first] = series;
	return first !== undefined && series.every((entry) => entry.unit === first.unit) ? first.unit : undefined;
}

/** The readout rows for a series' two spread edges, none where it draws no band. */
function spreadRows(
	entry: SeriesInput,
	dates: readonly string[],
	format: (value: number) => string
): ReadoutInputSeries[] {
	const labels = entry.spreadLabels;
	if (labels === undefined) return [];
	const byDate = new Map(entry.points.map((point) => [point.date, point.spread]));
	return (['low', 'high'] as const).map((edge) => ({
		label: labels[edge],
		swatch: spreadPaint(entry.token),
		values: dates.map((date) => byDate.get(date)?.[edge] ?? null),
		format
	}));
}

/** The series over their days, or null where not one day holds a reading. */
export function dateSeries(series: readonly SeriesInput[], opts: DateSeriesOptions): SeriesGeometry | null;
export function dateSeries(series: readonly SeriesInput[], opts: LegacyDateSeriesOptions): SeriesGeometry | null;
export function dateSeries(series: readonly SeriesInput[], opts: DateSeriesOptions | LegacyDateSeriesOptions): SeriesGeometry | null {
	const box = opts.frame;
	const rule = checkedRule(opts.rule ?? LEGACY_MODEL_RULE);
	const stacked = opts.stacked ?? false;
	const reconciliation = opts.reconciliation;
	if (reconciliation !== undefined && (!stacked || opts.padding <= 0 || opts.padding >= 1)) {
		throw new Error('Elapsed reconciliation needs stacked durations with space between their bars.');
	}
	const readings = byDay(series);
	const extra = reconciliation === undefined ? [] : [reconciliation.elapsed, reconciliation.overlap];
	for (const entry of extra) {
		for (const point of entry.points) {
			if (point.value !== null && (!Number.isFinite(point.value) || point.value < 0)) {
				throw new Error(`"${entry.label}" needs a non-negative reading or null on ${point.date}.`);
			}
		}
	}
	const extraReadings = extra.length === 0 ? [] : byDay([...series, ...extra]).slice(series.length);
	const allReadings = [...readings, ...extraReadings];
	const dates = [...new Set(allReadings.flatMap((days) => [...days.keys()]))].sort();
	const values = readings.flatMap((days) => [...days.values()].filter((value): value is number => value !== null));
	if (values.length === 0) return null;
	if (stacked && values.some((value) => value < 0)) {
		throw new RangeError('A stacked bar adds its parts, and a negative part cannot be added to a total.');
	}

	const band = bandScale(dates, box, 'x', opts.padding);
	const columns = dates.map((date) => (band(date) ?? 0) + band.bandwidth() / 2);
	const ticks = dayTicks(dates, { density: opts.density, columns, bounds: [box.left, box.right], labels: box.labels });
	const rules = opts.rules ?? [];
	for (const named of rules) {
		if (!Number.isFinite(named.at) || !named.label.trim()) throw new Error('A date series rule needs at and a label.');
	}
	const spreads = series.flatMap((entry) => entry.points.flatMap((point) => {
		if (point.spread === undefined) return [];
		if (stacked) throw new Error(`"${entry.label}" carries a spread, and a stacked bar draws none.`);
		if (entry.spreadLabels === undefined) throw new Error(`"${entry.label}" draws a spread on ${point.date} and does not name its two edges.`);
		const { low, high } = point.spread;
		if (point.value === null || !Number.isFinite(low) || !Number.isFinite(high) || low > point.value || high < point.value) throw new Error(`"${entry.label}" has an invalid spread on ${point.date}.`);
		return [low, high];
	}));
	const metadata = {
		rule,
		boundaries: ruleBoundaries(rule, dates, columns, box.left),
		events: ruleEvents(rule, dates),
		readout: readoutOf({
			type: 'dateSeries',
			columns: dates,
			series: [...series, ...extra].flatMap((entry, index) => {
				const format = withUnit(opts.number_format, entry.unit);
				return [{
					label: entry.label,
					swatch: entry.fill ?? `var(${entry.token})`,
					values: dates.map((date) => allReadings[index].get(date) ?? null),
					format
				}, ...spreadRows(entry, dates, format)];
			}),
			notMeasured: 'Not recorded.',
			resting: 'last'
		})
	};
	const unit = sharedUnit(series);
	const tickFormat = opts.valueFormat ?? (unit === undefined ? undefined : withUnit(opts.number_format, unit));
	function axisFor(readings: readonly number[]): ValueAxis {
		const axis = valueAxis([...readings, ...spreads, ...rules.map((named) => named.at)], box, {
			along: 'y',
			ticks: opts.valueTicks,
			format: tickFormat,
			number_format: opts.number_format
		});
		if (opts.domain === undefined) return axis;
		const [low, high] = opts.domain;
		if (!Number.isFinite(low) || !Number.isFinite(high) || low >= high || [...readings, ...spreads, ...rules.map((named) => named.at)].some((value) => value < low || value > high)) throw new Error('The date series domain must contain all readings, spreads and rules.');
		const placed = valueAxis([low, high], box, {
			along: 'y',
			ticks: opts.valueTicks,
			zero: false,
			format: tickFormat,
			number_format: opts.number_format
		});
		const scale = (value: number) => box.bottom - (value - low) / (high - low) * box.innerHeight;
		return { ...placed, domain: [low, high], scale, ticks: placed.ticks.filter((tick) => tick.value >= low && tick.value <= high).map((tick) => ({ ...tick, at: scale(tick.value) })) };
	}

	if (!stacked) {
		const axis = axisFor(values);
		const lines = series.map((entry, index) => {
			const row = dates.map((date) => readings[index].get(date) ?? null);
			const draw = line<number | null>()
				.defined((value) => value !== null)
				.x((_, at) => columns[at])
				.y((value) => axis.scale(value as number));
			const points = row.flatMap((value, at) =>
				value === null
					? []
					: [
							{
								date: dates[at],
								value,
								x: columns[at],
								y: axis.scale(value),
								alone: (row[at - 1] ?? null) === null && (row[at + 1] ?? null) === null
							}
						]
			);
			const byDate = new Map(entry.points.map((point) => [point.date, point.spread]));
			const spread = area<string>().defined((date) => byDate.get(date) !== undefined)
				.x((_, at) => columns[at])
				.y0((date) => axis.scale(byDate.get(date)?.low ?? 0))
				.y1((date) => axis.scale(byDate.get(date)?.high ?? 0))(dates) ?? '';
			return { label: entry.label, token: entry.token, path: draw(row) ?? '', points, spread };
		});
		return { frame: box, dates, columns, bandwidth: band.bandwidth(), ticks, axis, stacked, lines, bars: [], joins: [], ...metadata, rules: rules.map((named) => ({ ...named, y: axis.scale(named.at) })) };
	}

	const keys = series.map((entry) => entry.label);
	const table = dates.map((date) =>
		Object.fromEntries(readings.map((days, index) => [keys[index], days.get(date) ?? null]))
	);
	const layers = stack<Record<string, number | null>, string>()
		.keys(keys)
		.value((day, key) => day[key] ?? 0)(table);
	const rankedStack = stack<Record<string, number | null>, string>()
		.keys([...keys].sort().reverse())
		.value((day, key) => day[key] ?? 0)
		.order(stackOrderDescending);
	const ranked = opts.stackOrder === 'descending'
		? table.map((day) => new Map(rankedStack([day]).map((layer) => [layer.key, layer[0]])))
		: null;
	const totals = layers.length === 0 ? [] : layers[layers.length - 1].map((span) => span[1]);
	const reconciled = reconciliation === undefined ? [] : dates.flatMap((date, index) => {
		const elapsed = extraReadings[0].get(date) ?? null;
		const overlap = extraReadings[1].get(date) ?? null;
		if (elapsed === null && overlap === null) return [];
		if (elapsed === null || overlap === null || readings.some((days) => (days.get(date) ?? null) === null)) {
			throw new Error(`Elapsed reconciliation needs every stage, elapsed and overlap reading on ${date}.`);
		}
		const total = totals[index] ?? 0;
		// Means can differ by the floating-point rounding of their separate sums.
		const tolerance = Number.EPSILON * Math.max(1, total, elapsed, overlap) * (series.length + 2);
		if (Math.abs(total - overlap - elapsed) > tolerance) {
			throw new Error(`Stacked durations minus overlap do not equal elapsed time on ${date}.`);
		}
		return [{ date, total, elapsed, overlap }];
	});
	const axis = axisFor([0, ...totals, ...reconciled.map((point) => point.elapsed)]);
	const bars = layers.flatMap((layer, index) =>
		layer.flatMap((span, at) => {
			const value = table[at][layer.key];
			if (value === null || value === 0) return [];
			const placed = ranked === null ? span : ranked[at].get(layer.key)!;
			const top = axis.scale(placed[1]);
			const entry = series[index];
			return [
				{
					date: dates[at],
					label: layer.key,
					token: entry.token,
					fill: entry.fill ?? `var(${entry.token})`,
					hatched: entry.hatched ?? false,
					value,
					x: band(dates[at]) ?? 0,
					y: top,
					width: band.bandwidth(),
					height: axis.scale(placed[0]) - top
				}
			];
		})
	);
	// Every segment's top edge but the highest one a day: that is where the next
	// segment up begins.
	const highest = new Map<string, number>();
	for (const bar of bars) highest.set(bar.date, Math.min(highest.get(bar.date) ?? Infinity, bar.y));
	const joins = bars
		.filter((bar) => bar.y > (highest.get(bar.date) ?? bar.y))
		.map((bar) => ({ x: bar.x, y: bar.y, width: bar.width }));
	return {
		frame: box, dates, columns, bandwidth: band.bandwidth(), ticks, axis, stacked, lines: [], bars, joins,
		...metadata, rules: rules.map((named) => ({ ...named, y: axis.scale(named.at) })),
		...(reconciliation === undefined ? {} : {
			reconciliation: {
				elapsed: { label: reconciliation.elapsed.label, token: reconciliation.elapsed.token },
				overlap: { label: reconciliation.overlap.label, token: reconciliation.overlap.token },
				marks: reconciled.map((point) => {
					const x = band(point.date) ?? box.left;
					const end = x + band.bandwidth();
					return {
						date: point.date, elapsed: point.elapsed, overlap: point.overlap,
						top: axis.scale(point.total), y: axis.scale(point.elapsed), x, end,
						bracket: end + (band.step() - band.bandwidth()) / 2
					};
				})
			}
		})
	};
}
