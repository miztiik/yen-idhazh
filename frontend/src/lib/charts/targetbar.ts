/** A value against the target it should have hit.
 *
 * The question: are we inside the limit, and by how much. A bare number cannot
 * answer it - "4.1 minutes per chart" means nothing without the 6 that
 * retires the arm. The target is a marker on the track, so the gap is a
 * distance the reader measures with their eye rather than a subtraction.
 *
 * The band is decided by distance from the target, and it is the ONE place a
 * chart may borrow the confidence ramp: here green really does mean "inside the
 * limit" and red really does mean "past it", which is what those hues already
 * say everywhere else on the page.
 */

import type { EChartsOption } from 'echarts';
import { percentOf } from './rank';
import { paint, type ChartToken, type Polarity } from './theme';

/** Which side of the target is the good side. The same property of the same
 * measure the movement colour reads, so a bar and a delta on one figure cannot
 * disagree about which way is better. */
export type TargetSense = Polarity;

export type TargetBand = 'good' | 'near' | 'past';

/** Where the fill ends and where the marker sits, with no drawing attached.
 *
 * The same rule has to serve a chart on its own panel and seventy bars inside a
 * ranked list. Two copies of it would drift, and the drift would show as a
 * marker in one place and a verdict in another disagreeing about the same
 * number - with nothing on screen looking wrong. */
export interface TargetGeometry {
	/** The full length of the track, in the value's own unit. */
	track: number;
	/** Where the fill ends along the track, 0 to 1. */
	valueFraction: number;
	/** Where the marker sits along the track, 0 to 1. The oracle recomputes it. */
	markerFraction: number;
	band: TargetBand;
	empty: boolean;
	/** Which way is better for this measure, carried through from the caller so
	 * a delta drawn beside this bar reads the same polarity the bar was built
	 * with rather than declaring its own. */
	sense: TargetSense;
}

/** The same bar as CSS lengths, for markup. Kept apart from the geometry so the
 * console does not carry the string work for a bar it does not draw. */
export interface TargetMarks extends TargetGeometry {
	valuePercent: string;
	markerPercent: string;
}

export interface TargetBar {
	option: EChartsOption;
	/** Where the marker sits along the track, 0 to 1. The oracle recomputes it. */
	markerFraction: number;
	band: TargetBand;
	empty: boolean;
}

/** How close counts as near. Inside 10 percent of the target is the warning
 * zone - far enough out to act on, close enough that it is not yet a failure. */
const NEAR = 0.1;

export function targetGeometry(
	value: number | null,
	target: number,
	sense: TargetSense
): TargetGeometry {
	// Absence prints as absence. A zero-length bar says the measurement was
	// taken and came back zero, which is a claim nothing supports.
	if (value === null || !Number.isFinite(value) || target <= 0) {
		return { track: 0, valueFraction: 0, markerFraction: 0, band: 'good', empty: true, sense };
	}

	// The track runs to whichever is larger, so a value past its target is still
	// drawn past the marker rather than clipped at it.
	const track = Math.max(value, target) * 1.15;
	const past = sense === 'lower-is-better' ? value > target : value < target;
	const distance = Math.abs(value - target) / target;

	return {
		track,
		valueFraction: value / track,
		markerFraction: target / track,
		band: past ? 'past' : distance <= NEAR ? 'near' : 'good',
		empty: false,
		sense
	};
}

/** The bar a component draws. */
export function targetMarks(
	value: number | null,
	target: number,
	sense: TargetSense
): TargetMarks {
	const geometry = targetGeometry(value, target, sense);
	return {
		...geometry,
		valuePercent: percentOf(geometry.valueFraction),
		markerPercent: percentOf(geometry.markerFraction)
	};
}

export function targetBar(
	value: number | null,
	target: number,
	sense: TargetSense,
	label: string
): TargetBar {
	const geometry = targetGeometry(value, target, sense);
	if (geometry.empty || value === null) {
		return { option: {}, markerFraction: 0, band: 'good', empty: true };
	}

	const { track, markerFraction, band } = geometry;
	const token: ChartToken = band === 'past' ? '--band-low' : band === 'near' ? '--band-medium' : '--band-high';

	return {
		markerFraction,
		band,
		empty: false,
		option: {
			animation: false,
			grid: { left: 0, right: 0, top: 6, bottom: 6, containLabel: false },
			tooltip: {
				trigger: 'item',
				formatter: () =>
					`${label}<br/>${value.toFixed(2)} against a target of ${target.toFixed(2)}`
			},
			xAxis: { type: 'value', max: track, show: false },
			yAxis: { type: 'category', data: [label], show: false },
			series: [
				{
					type: 'bar',
					barWidth: 14,
					itemStyle: { color: paint(token), borderRadius: 7 },
					data: [value],
					markLine: {
						silent: true,
						symbol: 'none',
						// The target is a line across the track, not a second bar. A bar
						// beside a bar invites the reader to compare lengths and forget
						// which one is the limit.
						lineStyle: { color: paint('--chart-marker'), width: 2, type: 'solid' },
						label: {
							formatter: target.toFixed(target < 10 ? 1 : 0),
							position: 'end',
							color: paint('--color-text-tertiary'),
							fontSize: 11
						},
						data: [{ xAxis: target }]
					}
				}
			]
		}
	};
}
