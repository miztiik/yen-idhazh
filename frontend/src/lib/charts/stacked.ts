/** Composition over time.
 *
 * The question: what is the mix, and is the mix changing. Stacked, not grouped:
 * grouped bars answer "how big is each" and lose the total, and the total is
 * half the question here. Absolute, not normalised to 100 percent - a
 * normalised stack hides a quiet day, and a quiet day looks identical to a
 * clean one.
 *
 * One colour per series, bound to the series and never to its size, so sorting
 * a legend never repaints a chart.
 */

import type { EChartsOption } from 'echarts';
import { paint, type ChartToken } from './theme';

export interface StackSeries {
	label: string;
	token: ChartToken;
	/** One value per column, same length as `columns`. */
	values: number[];
}

export interface Stacked {
	option: EChartsOption;
	/** Column totals. The oracle recomputes them from the series. */
	totals: number[];
	empty: boolean;
}

/** The two shapes this one array can take.
 *
 * `bars` stacks, so the column height is the total and the bands are the mix.
 * `lines` draws each series from zero, so two series that both doubled are two
 * parallel climbs rather than one column that grew.
 *
 * They read the same array. **Nothing is re-shaped between them** - the values
 * handed to the engine are byte-for-byte the same list either way, and only
 * `type` and `stack` differ. That is the whole test for whether a chart may
 * carry the switch: where the data would need massaging to fit the second
 * shape, the switch does not ship.
 */
export type StackShape = 'bars' | 'lines';

export function stacked(
	columns: readonly string[],
	series: readonly StackSeries[],
	shape: StackShape = 'bars'
): Stacked {
	const drawn = series.filter((s) => s.values.some((v) => v > 0));
	if (columns.length === 0 || drawn.length === 0) {
		return { option: {}, totals: [], empty: true };
	}

	const totals = columns.map((_, i) => drawn.reduce((sum, s) => sum + (s.values[i] ?? 0), 0));

	return {
		totals,
		empty: false,
		option: {
			animation: false,
			grid: { left: 48, right: 12, top: 30, bottom: 26, containLabel: false },
			// One pointer position, every series at that column. Asking about one
			// band at a time is what makes a stack hard to read.
			tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
			legend: {
				data: drawn.map((s) => s.label),
				top: 0,
				itemGap: 16,
				textStyle: { color: paint('--color-text-secondary'), fontSize: 12 }
			},
			xAxis: {
				type: 'category',
				data: [...columns],
				axisLine: { lineStyle: { color: paint('--chart-axis') } },
				axisTick: { show: false },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11, hideOverlap: true }
			},
			yAxis: {
				type: 'value',
				minInterval: 1,
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
				splitLine: { lineStyle: { color: paint('--chart-grid') } }
			},
			series: drawn.map((s) => ({
				name: s.label,
				...(shape === 'bars'
					? { type: 'bar' as const, stack: 'total', barMaxWidth: 26 }
					: { type: 'line' as const, symbolSize: 5, lineStyle: { width: 1.5 } }),
				itemStyle: { color: paint(s.token) },
				data: columns.map((_, i) => s.values[i] ?? 0)
			}))
		}
	};
}
