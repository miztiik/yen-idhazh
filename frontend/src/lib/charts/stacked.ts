/** Composition over time.
 *
 * The question: what is the mix, and is the mix changing. Stacked, not grouped:
 * grouped bars answer "how big is each" and lose the total, and the total is
 * half the question here. Absolute, not normalised to 100 percent - a
 * normalised stack hides a quiet day, and a quiet day looks identical to a
 * clean one.
 *
 * One colour per series, bound to the series and never to its size, so the
 * strip under the chart names each one in the colour it is drawn in.
 *
 * No legend. The readout strip prints every series at the hovered column with
 * its own swatch beside it, and a legend above the plot would draw the same
 * pair a second time - which is how two of them drift. The room the legend took
 * goes back to the plot.
 *
 * `StackOptions` is the one way a caller widens this: a fixed value axis,
 * reference lines somebody agreed elsewhere, one extra tooltip line per column,
 * and the unit its values are in. All of them are optional and all of them are
 * passed IN - this file holds no threshold and picks no axis, so a chart that
 * wants either has to say where its number came from.
 */

import type { EChartsOption } from 'echarts';
import { paint, type ChartToken } from './theme';

export interface StackSeries {
	label: string;
	token: ChartToken;
	/** One value per column, same length as `columns`. */
	values: number[];
}

/** A line across the whole plot at one value on the value axis.
 *
 * A rule and never a third series: a threshold is a fact about the scale, and a
 * series drawn at a constant invites a reader to compare its shape against the
 * lines that carry data. It only ships where somebody already agreed the
 * number elsewhere - the caller passes it in, so this file never holds one.
 */
export interface StackRule {
	/** Where on the value axis it sits, in the same unit the series are in. */
	at: number;
	/** What crossing it means, in the reader's words. Drawn beside the line. */
	label: string;
	token: ChartToken;
}

/** What a caller may fix about the plot where the data cannot settle it.
 *
 * Every field is optional, and passing none leaves the chart exactly as it was
 * before this shape existed. That is what lets every caller that wants a plain
 * composition keep passing three arguments and get the same picture.
 */
export interface StackOptions {
	/** The value axis floor. Absent lets the engine fit one to the data. */
	min?: number;
	/** The value axis ceiling. Absent lets the engine fit one. */
	max?: number;
	rules?: readonly StackRule[];
	/** One line per column, printed under the series in the tooltip at that
	 * column. What else is true of that column and no series carries - a sample
	 * size, most often, which is the difference between a figure and a figure
	 * somebody should act on. */
	columnNotes?: readonly string[];
	/** Printed straight after every value in the tooltip. The axis labels carry
	 * the unit already, and a tooltip floating over the plot does not, so a
	 * percentage reads there as a bare count of something. */
	unit?: string;
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
	shape: StackShape = 'bars',
	options: StackOptions = {}
): Stacked {
	const drawn = series.filter((s) => s.values.some((v) => v > 0));
	if (columns.length === 0 || drawn.length === 0) {
		return { option: {}, totals: [], empty: true };
	}

	const totals = columns.map((_, i) => drawn.reduce((sum, s) => sum + (s.values[i] ?? 0), 0));
	const notes = options.columnNotes;
	const unit = options.unit ?? '';
	const rules = options.rules ?? [];
	const told = notes !== undefined || unit !== '';

	return {
		totals,
		empty: false,
		option: {
			animation: false,
			grid: { left: 48, right: 12, top: 8, bottom: 26, containLabel: false },
			// One pointer position, every series at that column. Asking about one
			// band at a time is what makes a stack hard to read.
			tooltip: {
				trigger: 'axis',
				axisPointer: { type: 'shadow' },
				// Only where the caller has something to add - a note, or a unit the
				// engine has no way to know. Writing the formatter unconditionally
				// would replace the engine's own with a copy of it, and a copy drifts.
				...(told
					? {
							formatter: (params: unknown) => {
								const rows = params as {
									dataIndex: number;
									seriesName?: string;
									marker?: string;
									value?: number;
								}[];
								const index = rows[0]?.dataIndex ?? 0;
								const lines = rows.map(
									(row) =>
										`${row.marker ?? ''}${row.seriesName ?? ''} ${row.value === undefined || row.value === null ? '' : `${row.value}${unit}`}`
								);
								const note = notes?.[index];
								return [columns[index] ?? '', ...lines, ...(note === undefined ? [] : [note])].join(
									'<br/>'
								);
							}
						}
					: {})
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
				...(options.min === undefined ? {} : { min: options.min }),
				...(options.max === undefined ? {} : { max: options.max }),
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
				splitLine: { lineStyle: { color: paint('--chart-grid') } }
			},
			series: drawn.map((s, index) => ({
				name: s.label,
				...(shape === 'bars'
					? { type: 'bar' as const, stack: 'total', barMaxWidth: 26 }
					: { type: 'line' as const, symbolSize: 5, lineStyle: { width: 1.5 } }),
				itemStyle: { color: paint(s.token) },
				data: columns.map((_, i) => s.values[i] ?? 0),
				// On the first series only. A rule hung on each of them would be drawn
				// once per series at the same height, which reads as a thicker line
				// and prints its caption on top of itself.
				...(index === 0 && rules.length > 0
					? {
							markLine: {
								silent: true,
								symbol: 'none',
								data: rules.map((rule) => ({
									yAxis: rule.at,
									lineStyle: { color: paint(rule.token), width: 1.5, type: 'solid' as const },
									label: {
										formatter: rule.label,
										position: 'insideEndTop' as const,
										color: paint('--color-text-tertiary'),
										fontSize: 11
									}
								}))
							}
						}
					: {})
			}))
		}
	};
}
