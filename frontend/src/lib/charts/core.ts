/** The engine, cut down to the parts a chart on this site actually uses.
 *
 * Importing `echarts` whole pulls every chart type, every component and both
 * renderers. Registering only what is used is the whole cost-control mechanism,
 * and it is worth about half the download: measured 2026-08-29 on this tree,
 * 1,044,275 B raw whole against 451,227 B for the registered set of the day.
 *
 * Adding a chart type means adding its import here, and the chunk is
 * re-measured in the same commit - `docs/concepts/design-system.md` holds the
 * number. Measured 2026-08-30 on this tree, this list builds a lazy chunk of
 * 585,481 B raw and 197,561 B gzipped, against a 200,000 B line the console
 * plan draws. Two and a half kilobytes of room left is why this is deliberately
 * a file somebody has to edit.
 */

import * as echarts from 'echarts/core';
import { BarChart, LineChart, PieChart, SankeyChart } from 'echarts/charts';
import {
	GridComponent,
	LegendComponent,
	MarkLineComponent,
	TooltipComponent
} from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';

// SVG, never canvas: the server renders to a string at build time, and an SVG
// carries a custom-property reference, so CSS keeps owning colour.
echarts.use([
	BarChart,
	LineChart,
	PieChart,
	SankeyChart,
	GridComponent,
	LegendComponent,
	MarkLineComponent,
	TooltipComponent,
	SVGRenderer
]);

export { echarts };
