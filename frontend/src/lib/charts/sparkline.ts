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

export function sparkline(values: readonly number[]): Sparkline {
	const points = values.filter((v) => Number.isFinite(v));
	// Two points is the minimum that has a direction. One is a dot, and a dot
	// with a trend arrow beside it is a lie.
	if (points.length < 2) return { option: {}, movement: null, rising: false, empty: true };

	const first = points[0];
	const last = points[points.length - 1];
	const movement = first === 0 ? null : (last - first) / first;
	const rising = last >= first;
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
			yAxis: { type: 'value', min: Math.min(...points), max: Math.max(...points), show: false },
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
