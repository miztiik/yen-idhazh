/** Which pixel a name, a value or an instant lands on inside a chart's frame.
 *
 * Three scales and no more: a band for named columns or rows, a linear scale
 * for a value, and a time scale for a real clock. Each one reads its range
 * from the frame, so a chart cannot map its data onto pixels the frame does
 * not own.
 *
 * **The time scale is UTC, always.** Every instant this project writes is UTC
 * (CLAUDE.md section 2), and d3's local-time scale rounds its domain and puts
 * its ticks on the midnights of whatever machine it runs on. That is every
 * developer machine and no CI runner, so the defect would ship green.
 * `scaleUtc` rounds to 00:00 UTC wherever it runs.
 *
 * Pure: every number is an argument, and nothing here draws.
 */
import {
	scaleBand,
	scaleLinear,
	scaleUtc,
	type ScaleBand,
	type ScaleLinear,
	type ScaleTime
} from 'd3-scale';

import type { Frame } from '../frame';

/** Which way a scale runs across the frame. */
export type Along = 'x' | 'y';

/** The pixels a scale maps onto. Up the page for `y`, because a larger value
 * sits higher. */
export function rangeOf(box: Frame, along: Along): [number, number] {
	return along === 'x' ? [box.left, box.right] : [box.bottom, box.top];
}

/** Named columns or rows, each an equal band of the frame.
 *
 * `padding` is the share of each step left empty between two bands, from 0 to
 * 1. It is the caller's, because how much air a bar needs is a property of the
 * panel and not of the scale.
 */
export function bandScale(
	keys: readonly string[],
	box: Frame,
	along: Along,
	padding: number
): ScaleBand<string> {
	return scaleBand<string>()
		.domain([...keys])
		.range(rangeOf(box, along))
		.padding(padding);
}

/** A value to a pixel, over a domain the caller has already decided. */
export function linearScale(
	domain: readonly [number, number],
	box: Frame,
	along: Along
): ScaleLinear<number, number> {
	return scaleLinear()
		.domain([...domain])
		.range(rangeOf(box, along));
}

/** An instant, as epoch milliseconds, to a pixel across the frame's width. */
export function timeScale(domain: readonly [number, number], box: Frame): ScaleTime<number, number> {
	return scaleUtc()
		.domain([new Date(domain[0]), new Date(domain[1])])
		.range(rangeOf(box, 'x'));
}
