/** Whether the extractor's yield is falling, one point a day.
 *
 * The four cards on the Extraction panel carry levels. This carries the
 * direction they tell the reader to look for: the articles the reading found
 * enough figures in, against the published ones that ended up carrying a chart.
 * Two counts of articles, so one linear domain holds both.
 *
 * A pure reduction plus one engine option, so a spec re-derives every point
 * without a browser.
 */

import type { EChartsOption } from 'echarts';
import { dayMonth } from '../format';
import { paint } from './theme';

/** One measured day, in the two counts the trend draws. */
export interface ExtractionDay {
	date: string;
	/** Articles the reading found enough figures of one kind in. */
	chartable: number;
	/** Published articles that could carry a chart and do. */
	charted: number;
}

export interface ExtractionTrend {
	option: EChartsOption;
	days: ExtractionDay[];
	/** The taller series' peak over the shorter's, which is the measurement the
	 * shared-axis rule asks for before two series are drawn on one domain. Null
	 * where the shorter series never left zero, which no ratio describes. */
	ratio: number | null;
	/** True where no day in the window measured anything. The panel prints its
	 * own sentence rather than an empty plot. */
	empty: boolean;
	/** One measured day. Still a chart, still a point, and never an empty plot -
	 * a single day has a level and no direction, and the panel says so. */
	single: boolean;
}

/** Both series share this domain. Named once so the axis, the readout and the
 * accessible description cannot disagree about what is being counted. */
const UNIT = 'Articles';

const SERIES = [
	{ name: 'Enough figures to draw', token: '--chart-1' as const, of: (day: ExtractionDay) => day.chartable },
	{ name: 'Published carrying a chart', token: '--chart-3' as const, of: (day: ExtractionDay) => day.charted }
];

/** The trend, over the days handed in.
 *
 * The value domain comes from the data drawn and is niced by the engine. There
 * is no ceiling here to measure distance from: the counts are articles a day
 * happened to publish, and a fixed maximum would waste the plot on every quiet
 * day.
 */
export function extractionTrend(days: readonly ExtractionDay[]): ExtractionTrend {
	const ordered = [...days].sort((a, b) => a.date.localeCompare(b.date));
	if (ordered.length === 0) {
		return { option: {}, days: [], ratio: null, empty: true, single: false };
	}

	const peak = (of: (day: ExtractionDay) => number) => Math.max(...ordered.map(of));
	const taller = peak((day) => day.chartable);
	const shorter = peak((day) => day.charted);

	return {
		days: ordered,
		// A series flat on zero has no peak to divide by. Reported absent rather
		// than as a huge number, because the two are different findings: one says
		// the shorter series is dwarfed, the other says it never happened.
		ratio: shorter > 0 ? taller / shorter : null,
		empty: false,
		single: ordered.length === 1,
		option: {
			animation: false,
			grid: { left: 48, right: 14, top: 34, bottom: 26, containLabel: false },
			tooltip: { trigger: 'axis' },
			xAxis: {
				type: 'category',
				// The same date grammar every other axis on this console prints.
				data: ordered.map((day) => dayMonth(day.date)),
				axisLine: { lineStyle: { color: paint('--chart-axis') } },
				axisTick: { show: false },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11, hideOverlap: true }
			},
			yAxis: {
				type: 'value',
				name: UNIT,
				nameLocation: 'end',
				nameGap: 12,
				nameTextStyle: { color: paint('--color-text-tertiary'), fontSize: 11, align: 'left' },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
				splitLine: { lineStyle: { color: paint('--chart-grid') } }
			},
			series: SERIES.map((series) => ({
				name: series.name,
				type: 'line' as const,
				// One day is a point and not a line, so the symbol is what draws it.
				showSymbol: true,
				symbolSize: 5,
				data: ordered.map(series.of),
				lineStyle: { width: 1.75, color: paint(series.token) },
				itemStyle: { color: paint(series.token) }
			}))
		}
	};
}

/** Both series at one day, for the strip under the plot. */
export function extractionTrendColumns(days: readonly ExtractionDay[]) {
	return SERIES.map((series) => ({
		label: series.name,
		colour: `var(${series.token})`,
		value: (index: number) => {
			const day = days[index];
			return day === undefined ? '-' : String(series.of(day));
		}
	}));
}
