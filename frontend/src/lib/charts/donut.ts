/** One share against a whole, with the count beside it.
 *
 * The question: how much of something got through. A donut answers it in one
 * glance because the reader compares an arc to a ring rather than a number to a
 * remembered number - and unlike a bar, the whole is drawn, so "82 percent" and
 * "82 of 100" are the same picture.
 *
 * A ring, not a pie: the hole is where the count goes, and a count next to a
 * share is what stops a reader doing the arithmetic themselves.
 */

import type { EChartsOption } from 'echarts';
import { paint, type ChartToken } from './theme';

export interface DonutSlice {
	label: string;
	value: number;
	token: ChartToken;
}

export interface Donut {
	option: EChartsOption;
	/** The share the first slice holds, 0 to 1. Exported because the geometry
	 * oracle recomputes the arc from it rather than trusting the drawing. */
	share: number;
	total: number;
	empty: boolean;
}

export function donut(slices: readonly DonutSlice[], centreLabel: string): Donut {
	const total = slices.reduce((sum, s) => sum + s.value, 0);
	// Nothing measured is not zero percent. A full ring of one colour reads as a
	// working system that scored zero, which is a different and much worse claim.
	if (total <= 0 || slices.length === 0) {
		return { option: {}, share: 0, total: 0, empty: true };
	}

	const share = slices[0].value / total;

	return {
		share,
		total,
		empty: false,
		option: {
			animation: false,
			tooltip: {
				trigger: 'item',
				formatter: (params: unknown) => {
					const p = params as { name: string; value: number };
					return `${p.name}<br/>${p.value} of ${total}, ${((p.value / total) * 100).toFixed(1)}%`;
				}
			},
			series: [
				{
					type: 'pie',
					radius: ['62%', '86%'],
					center: ['50%', '52%'],
					// A pie draws in data order and never re-sorts, so the order in the
					// argument is the order on screen. That is load-bearing: the first
					// slice is the one the centre label is about.
					avoidLabelOverlap: false,
					label: {
						show: true,
						position: 'center',
						formatter: `{a|${Math.round(share * 100)}%}\n{b|${centreLabel}}`,
						rich: {
							a: { fontSize: 26, fontWeight: 600, color: paint('--color-text'), lineHeight: 32 },
							b: { fontSize: 11, color: paint('--color-text-tertiary'), lineHeight: 16 }
						}
					},
					labelLine: { show: false },
					itemStyle: { borderWidth: 0 },
					data: slices.map((s) => ({
						name: s.label,
						value: s.value,
						itemStyle: { color: paint(s.token) }
					}))
				}
			]
		}
	};
}
