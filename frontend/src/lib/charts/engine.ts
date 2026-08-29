/** The client half of the chart engine.
 *
 * Imported dynamically by `Chart.svelte`, so the engine lands in its own chunk
 * and is fetched only when a chart hydrates. Measured 2026-08-30 on this tree
 * it is 197,561 B gzipped, and it costs the console route none of that - the
 * route's first load carries the component, the option builders and the token
 * bridge, and nothing else. Nothing downloads the engine unless a chart comes
 * alive, and no other route references it at all. `charts.spec.ts` asserts
 * both.
 *
 * The build-time half is `$lib/server/chart-render`, where SvelteKit fails the
 * build if a client module imports it.
 */

import type { EChartsOption } from 'echarts';
import { readTokens, resolveSentinels } from './theme';

export interface ChartSize {
	width: number;
	height: number;
}

export interface LiveChart {
	resize(size: ChartSize): void;
	destroy(): void;
}

/** The option a live chart needs beyond what the server drew.
 *
 * The server's SVG names a custom property and follows a theme for free. A live
 * chart cannot: the engine paints a tooltip's own background itself, so those
 * few values are read out of the document here, and re-read whenever the theme
 * attribute changes.
 */
function liveTheme(option: EChartsOption): EChartsOption {
	const tokens = readTokens();
	const given =
		typeof option.tooltip === 'object' && !Array.isArray(option.tooltip) ? option.tooltip : {};
	return resolveSentinels({
		...option,
		tooltip: {
			trigger: 'item',
			backgroundColor: tokens['--color-surface'],
			borderColor: tokens['--chart-grid'],
			textStyle: { color: tokens['--color-text'], fontSize: 13 },
			...given
		}
	});
}

export async function hydrate(
	node: HTMLElement,
	option: EChartsOption,
	size: ChartSize
): Promise<LiveChart> {
	const { echarts } = await import('./core');
	node.replaceChildren();
	const chart = echarts.init(node, null, {
		renderer: 'svg',
		// The container decides, not the server's authored width. The prerendered
		// SVG stretches to fill; a live chart drawn at the authored width would
		// shrink the moment it hydrated.
		width: node.clientWidth || size.width,
		height: size.height
	});
	chart.setOption(liveTheme(option));

	// A theme change repaints the parts CSS cannot reach. The SVG marks follow
	// their own custom properties without being told.
	const themed = new MutationObserver(() => chart.setOption(liveTheme(option)));
	themed.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

	return {
		resize: (next) => chart.resize({ width: next.width, height: next.height }),
		destroy: () => {
			themed.disconnect();
			chart.dispose();
		}
	};
}
