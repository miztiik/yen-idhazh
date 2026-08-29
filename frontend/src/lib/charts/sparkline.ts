/** Direction at a glance, inside a card.
 *
 * The question: which way is this going. Not "by how much" - the number beside
 * it says that. So the sparkline carries no axis, no gridline and no label: it
 * is a shape, and anything else on it is competing with the number it exists to
 * support.
 *
 * The domain is the drawn extent rather than zero. A sparkline is about change,
 * and anchoring at zero flattens every series whose variation is small next to
 * its level - which is most of them.
 */

import type { EChartsOption } from 'echarts';
import { paint } from './theme';

export interface Sparkline {
	option: EChartsOption;
	/** Last minus first, as a share of first. Null where the first is zero or
	 * there is nothing to compare. The card prints this; the line only shows it. */
	movement: number | null;
	rising: boolean;
	empty: boolean;
}

/** The same series with no engine attached, for a sparkline drawn as markup.
 *
 * A trend inside a list row cannot be a chart instance - a failure ledger has
 * one per row. So the domain rule, the movement rule and the two-point minimum
 * live here, and both drawings read them from one place. */
export interface SparklineShape {
	/** The finite values, in order. */
	values: number[];
	min: number;
	max: number;
	movement: number | null;
	rising: boolean;
	empty: boolean;
}

/** The shape plus the points to draw. Kept apart so the console does not carry
 * the normalising arithmetic for a line it does not draw as markup. */
export interface SparklineMarks extends SparklineShape {
	/** The points in the unit square, y measured downward the way SVG does. A
	 * flat series sits on the middle line rather than on an edge. */
	points: { x: number; y: number }[];
}

export function sparklineShape(values: readonly number[]): SparklineShape {
	const points = values.filter((v) => Number.isFinite(v));
	// Two points is the minimum that has a direction. One is a dot, and a dot
	// with a trend arrow beside it is a lie.
	if (points.length < 2) {
		return { values: points, min: 0, max: 0, movement: null, rising: false, empty: true };
	}

	const first = points[0];
	const last = points[points.length - 1];

	return {
		values: points,
		min: Math.min(...points),
		max: Math.max(...points),
		movement: first === 0 ? null : (last - first) / first,
		rising: last >= first,
		empty: false
	};
}

/** The line a component draws. */
export function sparklineMarks(values: readonly number[]): SparklineMarks {
	const shape = sparklineShape(values);
	if (shape.empty) return { ...shape, points: [] };

	const span = shape.max - shape.min;
	return {
		...shape,
		points: shape.values.map((v, i) => ({
			x: i / (shape.values.length - 1),
			y: span === 0 ? 0.5 : 1 - (v - shape.min) / span
		}))
	};
}

export function sparkline(values: readonly number[]): Sparkline {
	const shape = sparklineShape(values);
	if (shape.empty) return { option: {}, movement: null, rising: false, empty: true };

	const { values: points, movement, rising, min, max } = shape;
	const token = rising ? '--band-high' : '--chart-4';

	return {
		movement,
		rising,
		empty: false,
		option: {
			animation: false,
			grid: { left: 1, right: 1, top: 2, bottom: 2, containLabel: false },
			tooltip: { show: false },
			xAxis: { type: 'category', data: points.map((_, i) => String(i)), show: true, boundaryGap: false, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { show: false } },
			yAxis: { type: 'value', min, max, show: false },
			series: [
				{
					type: 'line',
					data: [...points],
					showSymbol: false,
					smooth: 0.25,
					lineStyle: { width: 1.75, color: paint(token) },
					areaStyle: { color: paint(token), opacity: 0.12 }
				}
			]
		}
	};
}
