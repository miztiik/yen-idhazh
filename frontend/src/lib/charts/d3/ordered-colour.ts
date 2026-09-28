/** Which colour an ordered quantity takes, and the two marks that mean "no reading".
 *
 * **An ordered ramp is one hue in steps, weakest to strongest.** It is for a
 * quantity with a direction - a machine's speed, say - and it is not the
 * categorical ramp. `--chart-1` to `--chart-7` are seven hues that say "these
 * are different things", and nobody can rank seven hues. One token mixed toward
 * the page surface in even steps says "more" and "less" in the way every
 * reader already reads.
 *
 * **The steps are cut at the quantiles of the whole record, not of the open
 * window.** A value keeps its step when the operator changes the span, which is
 * the one thing a colour that carries rank has to survive.
 *
 * **One grey, and it is never on the ramp.** `RESERVED_GREY` is the stop
 * `machine-colour.ts` already keeps for a machine nobody recorded, re-exported
 * rather than minted again, so the console has one grey for an absence and not
 * two that drift. The hatch is that grey in stripes on the page surface, for a
 * known thing with no reading, and it is never laid over a grey fill: flat grey
 * already means "not recorded", and a hatch on grey would read the same.
 *
 * Colour only ever leaves here as a custom-property reference, so both themes
 * resolve it and `tokens.css` stays the one place a colour is decided.
 */
import { scaleQuantile } from 'd3-scale';

import { machineColour, UNRECORDED_STOP } from '../machine-colour';
import type { ChartToken } from '../theme';

export { UNRECORDED_STOP as RESERVED_GREY } from '../machine-colour';

export interface OrderedRamp {
	/** Each step's colour, weakest first. The strongest is the token itself. */
	colours: string[];
	/** The values the steps are cut at, one fewer than the steps. A value
	 * below `cuts[0]` is step 1; a value at or above the last cut is the top
	 * step. A key prints these, so each step is named by its range. */
	cuts: number[];
	/** The 1-based step a value lands on. */
	stepOf: (value: number) => number;
}

/** One step of the ramp: the token at its own share, the rest page surface.
 *
 * Mixed in OKLab, where equal steps of the mix look like equal steps of
 * lightness, which is what makes a rank readable by eye.
 */
function stepColour(token: ChartToken, step: number, stops: number): string {
	const share = Math.round((step / stops) * 100);
	return share === 100
		? `var(${token})`
		: `color-mix(in oklab, var(${token}) ${share}%, var(--color-surface))`;
}

/** The ordered ramp over a whole record.
 *
 * `record` is every value the colour must stay stable across, not only the
 * ones on screen. Null where the record holds no finite value, because there is
 * nothing to rank a value against.
 */
export function orderedRamp(
	record: readonly number[],
	stops: number,
	token: ChartToken
): OrderedRamp | null {
	if (!Number.isInteger(stops) || stops < 1) {
		throw new RangeError(`An ordered ramp has a whole number of steps, one or more; got ${stops}.`);
	}
	const finite = record.filter((value) => Number.isFinite(value));
	if (finite.length === 0) return null;
	const steps = Array.from({ length: stops }, (_, index) => index + 1);
	const quantile = scaleQuantile<number>().domain(finite).range(steps);
	return {
		colours: steps.map((step) => stepColour(token, step, stops)),
		cuts: quantile.quantiles(),
		stepOf: (value: number) => quantile(value)
	};
}

/** The stripes, as the caller measured them. No number here has a default: the
 * angle is a config knob and the spacing is the panel's to choose. */
export interface HatchPattern {
	degrees: number;
	/** Page surface between two stripes, in CSS pixels. */
	gapPx: number;
	/** One stripe's width, in CSS pixels. */
	linePx: number;
}

export interface AbsentHatch extends HatchPattern {
	/** The reserved grey, as a custom-property reference. */
	ink: string;
	/** For markup: a CSS background with transparent gaps, so the page surface
	 * shows between the stripes. */
	background: string;
	/** For SVG: one tile of the pattern, repeated and turned. */
	tile: { size: number; transform: string };
}

/** The hatch for a known thing with no reading.
 *
 * A builder rather than a constant, because the angle is a config value and a
 * pure module cannot read config: the panel reads it and passes it in.
 */
export function absentHatch(pattern: HatchPattern): AbsentHatch {
	const { degrees, gapPx, linePx } = pattern;
	if (!Number.isFinite(degrees) || !(gapPx > 0) || !(linePx > 0)) {
		throw new RangeError(
			`A hatch needs a finite angle and a gap and a stripe wider than nothing; got ${degrees}, ${gapPx}, ${linePx}.`
		);
	}
	const ink = machineColour(UNRECORDED_STOP);
	const size = gapPx + linePx;
	return {
		degrees,
		gapPx,
		linePx,
		ink,
		background: `repeating-linear-gradient(${degrees}deg, transparent 0 ${gapPx}px, ${ink} ${gapPx}px ${size}px)`,
		tile: { size, transform: `rotate(${degrees})` }
	};
}
