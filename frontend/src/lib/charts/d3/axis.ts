/** The ticks, the words and the spacing of a value axis - never a date axis.
 *
 * A date axis on this console has one home, `dayTicks` in `frame.ts`. Its
 * label-thinning rule was measured after four console axes drew their dates on
 * top of each other, and a second date axis here would fork that rule. So this
 * module answers only for a value: which ticks, what each one says, and which
 * labels are drawn without two of them touching.
 *
 * The tick count is the caller's, from config. The domain is rounded out to
 * whole steps of it and anchored at zero unless the caller says the value has
 * no zero worth showing: a bar that does not start at zero is a lie, and an
 * axis of change centred on no change is not a bar.
 */
import { tickStep } from 'd3-array';

import { AXIS_LABEL_GAP_PX, AXIS_LABEL_PX, thinLabels, type Frame } from '../frame';
import { grouped } from '../series';
import { linearScale, type Along } from './scale';

/** One tick on a value axis. */
export interface ValueTick {
	value: number;
	/** Where the tick sits, in the chart's own pixels along the axis. */
	at: number;
	/** What the label says, or '' where the spacing rule dropped it. The tick
	 * mark is drawn either way, so the grid keeps its shape. */
	text: string;
}

export interface ValueAxis {
	domain: [number, number];
	along: Along;
	scale: (value: number) => number;
	ticks: ValueTick[];
}

export interface ValueAxisOptions {
	along: Along;
	/** How many ticks the axis aims for. d3 may land one either side of it,
	 * because it only ever steps by one, two or five times a power of ten. */
	ticks: number;
	/** Anchor the domain at zero. True unless the caller says otherwise. */
	zero?: boolean;
	/** The words for a tick. Grouped digits, at the precision of one step,
	 * unless the caller has a unit to print. */
	format?: (value: number) => string;
}

/** A tick as words, at the precision its step needs and no finer.
 *
 * An ASCII hyphen for a minus, grouped thousands, and every label on one axis
 * carrying the same number of decimals, so a column of labels lines up.
 */
function tickText(value: number, precision: number): string {
	const fixed = Math.abs(value).toFixed(precision);
	const [whole, fraction] = fixed.split('.');
	const sign = value < 0 && Number(fixed) !== 0 ? '-' : '';
	const digits = grouped(Number(whole));
	return fraction === undefined ? `${sign}${digits}` : `${sign}${digits}.${fraction}`;
}

/** The labels an upright axis can carry with a line of air between each two.
 *
 * The lowest is always kept: it is the zero or the floor the whole axis is read
 * from. A dropped label keeps its tick.
 */
function spacedUpright(ticks: readonly ValueTick[]): ValueTick[] {
	const room = AXIS_LABEL_PX + AXIS_LABEL_GAP_PX;
	let last = Number.NaN;
	return ticks.map((tick) => {
		if (!Number.isNaN(last) && Math.abs(tick.at - last) < room) return { ...tick, text: '' };
		last = tick.at;
		return tick;
	});
}

/** The labels a level axis can carry, by the measured rule every console axis
 * uses (`thinLabels`). */
function spacedLevel(ticks: readonly ValueTick[]): ValueTick[] {
	const kept = new Set(
		thinLabels(ticks.map((tick) => ({ x: tick.at, text: tick.text }))).map((label) => label.x)
	);
	return ticks.map((tick) => (kept.has(tick.at) ? tick : { ...tick, text: '' }));
}

/** A value axis over the values a chart will draw.
 *
 * An empty or non-finite set still returns a usable axis over nought to one.
 * The chart that asked for it has already decided whether there is anything
 * to draw.
 */
export function valueAxis(
	values: readonly number[],
	box: Frame,
	options: ValueAxisOptions
): ValueAxis {
	const { along, ticks: count, zero = true } = options;
	let low = Number.POSITIVE_INFINITY;
	let high = Number.NEGATIVE_INFINITY;
	for (const value of values) {
		if (!Number.isFinite(value)) continue;
		low = Math.min(low, value);
		high = Math.max(high, value);
	}
	if (low > high) [low, high] = [0, 1];
	if (zero) [low, high] = [Math.min(0, low), Math.max(0, high)];
	if (low === high) high = low + 1;

	const scale = linearScale([low, high], box, along).nice(count);
	const domain = scale.domain() as [number, number];
	const step = Math.abs(tickStep(domain[0], domain[1], count));
	const precision = step > 0 ? Math.max(0, -Math.floor(Math.log10(step))) : 0;
	const format = options.format ?? ((value: number) => tickText(value, precision));
	const raw = scale.ticks(count).map((value) => ({ value, at: scale(value), text: format(value) }));
	return {
		domain,
		along,
		scale: (value: number) => scale(value),
		ticks: along === 'y' ? spacedUpright(raw) : spacedLevel(raw)
	};
}
