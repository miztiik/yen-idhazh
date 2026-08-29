/** How a total was built from ordered contributions.
 *
 * The question: where did the growth come from. A line of the running total
 * says it went up; a waterfall says which days did it. The floating bar is the
 * point - each one starts where the last one ended, so the reader reads a
 * contribution as a length and the total as the place they end up.
 *
 * A rise and a fall take different colours because the sign is the first thing
 * read and a length cannot carry it.
 */

import type { EChartsOption } from 'echarts';
import { paint } from './theme';

export interface WaterfallStep {
	label: string;
	delta: number;
}

export interface Waterfall {
	option: EChartsOption;
	/** Running totals after each step, opening balance first. The oracle checks
	 * the last one equals the opening plus the sum of the deltas. */
	cumulative: number[];
	empty: boolean;
}

export function waterfall(opening: number, steps: readonly WaterfallStep[]): Waterfall {
	if (steps.length === 0) return { option: {}, cumulative: [opening], empty: true };

	const cumulative = [opening];
	for (const step of steps) cumulative.push(cumulative[cumulative.length - 1] + step.delta);

	// The invisible base each floating bar sits on: the lower of the two ends,
	// so a fall hangs from where it started rather than growing from zero.
	const base = steps.map((step, i) => Math.min(cumulative[i], cumulative[i + 1]));
	const span = steps.map((step) => Math.abs(step.delta));

	const floor = Math.min(...cumulative);
	const ceiling = Math.max(...cumulative);
	const pad = (ceiling - floor) * 0.08 || 1;

	return {
		cumulative,
		empty: false,
		option: {
			animation: false,
			grid: { left: 56, right: 12, top: 16, bottom: 26, containLabel: false },
			tooltip: {
				trigger: 'axis',
				axisPointer: { type: 'shadow' },
				formatter: (params: unknown) => {
					const rows = params as { dataIndex: number }[];
					const i = rows[0]?.dataIndex ?? 0;
					const step = steps[i];
					const sign = step.delta >= 0 ? '+' : '';
					return `${step.label}<br/>${sign}${step.delta}<br/>running total ${cumulative[i + 1]}`;
				}
			},
			xAxis: {
				type: 'category',
				data: steps.map((s) => s.label),
				axisLine: { lineStyle: { color: paint('--chart-axis') } },
				axisTick: { show: false },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11, hideOverlap: true }
			},
			yAxis: {
				type: 'value',
				min: Math.floor(floor - pad),
				max: Math.ceil(ceiling + pad),
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
				splitLine: { lineStyle: { color: paint('--chart-grid') } }
			},
			series: [
				{
					type: 'bar',
					stack: 'run',
					// The spacer carries no meaning and must never be pointable.
					itemStyle: { color: 'transparent' },
					emphasis: { itemStyle: { color: 'transparent' } },
					tooltip: { show: false },
					silent: true,
					data: base
				},
				{
					type: 'bar',
					stack: 'run',
					data: span.map((value, i) => ({
						value,
						itemStyle: { color: paint(steps[i].delta >= 0 ? '--chart-1' : '--chart-4') }
					}))
				}
			]
		}
	};
}
