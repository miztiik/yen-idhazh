/** Render a chart to finished SVG at build time.
 *
 * Under `$lib/server/` on purpose: SvelteKit fails the build if a client module
 * imports anything here, which is a stronger guard than a runtime check. The
 * browser must never pull the engine in to draw something the server already
 * drew.
 *
 * This is what keeps the console complete before any script runs, and what
 * leaves every mark on screen for a reader with JavaScript off.
 */

import type { EChartsOption } from 'echarts';
import { toCssVariables } from '$lib/charts/theme';

export interface ChartSize {
	width: number;
	height: number;
}

export async function renderToSvg(option: EChartsOption, size: ChartSize): Promise<string> {
	const { echarts } = await import('$lib/charts/core');
	const chart = echarts.init(null, null, {
		renderer: 'svg',
		ssr: true,
		width: size.width,
		height: size.height
	});
	chart.setOption(option);
	const svg = chart.renderToSVGString();
	chart.dispose();
	// Colour leaves as a custom-property reference, so CSS owns it from here and
	// a theme change costs nothing.
	return toCssVariables(svg);
}
