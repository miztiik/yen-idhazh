/** Where items go between the router looking at one and a chart being published.
 *
 * The counts were already on the page, as four columns of a table with a
 * paragraph explaining what each one meant. Four numbers a reader has to divide
 * in their head to learn the only thing they wanted: where the drop is. A
 * funnel says it by shape, and the table underneath still holds the exact
 * numbers per day.
 *
 * Totals across the open window, not one day: a single day's four numbers are
 * already legible in the table, and the question "where do items go" is a
 * question about the window.
 */

import type { EChartsOption } from 'echarts';
import { paint } from './theme';

export interface FunnelDay {
	reached: number;
	asked: number;
	drafted: number;
	published: number;
}

const STEPS = [
	{ key: 'reached', label: 'Reached', token: '--chart-1' },
	{ key: 'asked', label: 'Asked the model', token: '--chart-2' },
	{ key: 'drafted', label: 'Drafted', token: '--chart-3' },
	{ key: 'published', label: 'Published', token: '--chart-4' }
] as const;

export interface ChartFunnel {
	option: EChartsOption;
	empty: boolean;
}

function grouped(value: number): string {
	return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

export function chartFunnel(days: readonly FunnelDay[]): ChartFunnel {
	const total = STEPS.map((step) => ({
		...step,
		value: days.reduce((sum, day) => sum + day[step.key], 0)
	}));
	// Nothing reached means nothing committed says what the router did. A funnel
	// of four zeros draws a rectangle and reads as a working stage.
	if (total[0].value === 0) return { option: {}, empty: true };

	const reached = total[0].value;
	const smallest = Math.min(...total.map((step) => step.value));

	return {
		option: {
			animation: false,
			tooltip: {
				trigger: 'item',
				formatter: (params: unknown) => {
					const item = params as { name: string; value: number };
					const share = ((item.value / reached) * 100).toFixed(1);
					return `${item.name}<br/>${grouped(item.value)} items, ${share}% of reached`;
				}
			},
			series: [
				{
					type: 'funnel',
					// Width is the count, not the rank. An evenly-stepped funnel is a
					// decoration: it draws the same shape whatever the numbers are.
					//
					// Anchoring the scale on the data's own smallest value, and giving
					// that value its true share as the minimum width, keeps every band
					// exactly proportional and squares off the bottom. Left to taper to
					// zero it drew a point, which says a fifth stage loses everything -
					// and there is no fifth stage.
					min: smallest,
					max: reached,
					minSize: `${(smallest / reached) * 100}%`,
					maxSize: '100%',
					sort: 'none',
					gap: 2,
					// The drop from asked to drafted is about fifteen to one, so the
					// last two bands are slivers. Their width has to stay honest, so
					// the label moves out beside the funnel instead of being squeezed
					// into a band too narrow to hold it. Measured 2026-08-29 on the
					// committed ledger: inside labels overflowed their band at 134 and
					// 116 items and printed over the panel behind.
					left: '3%',
					right: '34%',
					top: 10,
					bottom: 10,
					label: {
						position: 'right',
						color: paint('--color-text'),
						fontSize: 13,
						formatter: (params: unknown) => {
							const item = params as { name: string; value: number };
							const share = Math.round((item.value / reached) * 100);
							return `${item.name}  ${grouped(item.value)}  (${share}%)`;
						}
					},
					labelLine: {
						length: 18,
						lineStyle: { color: paint('--chart-axis'), width: 1 }
					},
					itemStyle: { borderWidth: 0 },
					data: total.map((step) => ({
						name: step.label,
						value: step.value,
						itemStyle: { color: paint(step.token) }
					}))
				}
			]
		},
		empty: false
	};
}
