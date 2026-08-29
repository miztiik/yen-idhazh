/** The engine, cut down to the parts a chart on this site actually uses.
 *
 * Importing `echarts` whole pulls every chart type, every component and both
 * renderers: measured 2026-08-29 on this tree, 1,044,275 B raw and 345,959 B
 * gzipped for a page that draws one funnel. Registering only what is used cuts
 * that to 451,227 B raw and 153,204 B gzipped, a 56 percent saving, and it is
 * the difference between a lazy chunk worth having and one that is
 * indefensible on any route.
 *
 * Adding a chart type means adding its import here, and the number in
 * `docs/concepts/design-system.md` is re-measured in the same commit. That is
 * the whole cost-control mechanism, so it is deliberately a file somebody has
 * to edit.
 */

import * as echarts from 'echarts/core';
import { FunnelChart } from 'echarts/charts';
import { TooltipComponent } from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';

// SVG, never canvas: the server renders to a string at build time, and an SVG
// carries a custom-property reference, so CSS keeps owning colour.
echarts.use([FunnelChart, TooltipComponent, SVGRenderer]);

export { echarts };
