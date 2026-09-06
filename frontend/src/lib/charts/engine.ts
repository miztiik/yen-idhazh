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
 *
 * A chart here has an explicit lifetime with four moments and no others:
 * `hydrate` hands back a handle at once, the handle draws when the chart is
 * near enough to be worth drawing, `update` hands it a new option, and
 * `destroy` releases it. That one call releases everything the engine holds -
 * the instance, the theme subscription, the visibility watch - and each of the
 * other three is a no-op after it. What the chart library does inside its own
 * repaint is its business and is not measured here; this file only bounds what
 * we hand it.
 *
 * The state a test needs is published on the page rather than kept private:
 * `data-chart` on the host says `waiting` or `live`, `data-chart-options`
 * counts full option applications and `data-chart-colours` counts the
 * colour-only ones, and `data-charts-live` on the document element says how
 * many instances the engine holds right now. A test that cannot see which path
 * ran cannot tell a cheap repaint from an expensive one.
 */

import type { EChartsOption } from 'echarts';
import { readTokens, resolveSentinels, SENTINEL_PATTERN } from './theme';

type Instance = ReturnType<(typeof import('./core'))['echarts']['init']>;

export interface ChartSize {
	width: number;
	height: number;
}

export interface LiveChart {
	/** Hand the chart a new option. Without this a live chart keeps the option
	 * it was born with for ever, and a control that changes one is ignored. */
	update(option: EChartsOption): void;
	resize(size: ChartSize): void;
	destroy(): void;
}

/** How close a chart has to be before it is worth drawing: one screen ahead,
 * the same reach `ItemVisual.svelte` gives a drawing. A chart nine screens down
 * costs nothing until a reader comes near it, and one hidden by CSS has no box
 * at all so it never comes near. Both still draw the moment they are approached
 * or revealed - offscreen means "not yet", never "never". */
const REACH = '100% 0px';

/** A colour the server left for the client to resolve. `SENTINEL_PATTERN` is
 * unanchored because it also scans SVG text; a whole value is seven
 * characters. */
function isSentinel(value: string): boolean {
	return value.length === 7 && SENTINEL_PATTERN.test(value);
}

/** The branches of an option that name a colour, and nothing else.
 *
 * The chart library merges a partial option into a live chart, so a theme
 * change can hand over the few branches that carry a colour instead of the
 * whole option and its data again. Two shapes have to travel complete anyway,
 * and they are the honest limit of this: a `data` array, because the library
 * replaces a series' data wholesale rather than matching it item by item, and
 * an array of plain values such as the top-level palette, because an item of it
 * cannot carry a "leave this one alone" placeholder. Where a chart keeps its
 * colours inside its points - a pie's slices, a flow's nodes - that array is
 * copied, and only that array. Where it does not, no data moves at all.
 */
function paintedParts(node: unknown, whole: boolean): { part: unknown; painted: boolean } {
	if (typeof node === 'string') {
		return isSentinel(node) ? { part: node, painted: true } : { part: undefined, painted: false };
	}
	if (Array.isArray(node)) {
		const parts = node.map((item) => paintedParts(item, whole));
		if (!parts.some((one) => one.painted)) return { part: undefined, painted: false };
		const mergeable =
			!whole &&
			node.every((item) => item !== null && typeof item === 'object' && !Array.isArray(item));
		if (!mergeable) return { part: node, painted: true };
		return { part: parts.map((one) => one.part ?? {}), painted: true };
	}
	if (node !== null && typeof node === 'object') {
		const kept: Record<string, unknown> = {};
		let painted = false;
		for (const [key, value] of Object.entries(node)) {
			const one = paintedParts(value, whole || key === 'data');
			if (!one.painted) continue;
			kept[key] = one.part;
			painted = true;
		}
		return painted ? { part: kept, painted: true } : { part: undefined, painted: false };
	}
	return { part: undefined, painted: false };
}

/** What a tooltip needs, which is the one part of a chart CSS cannot reach.
 *
 * The server's SVG names a custom property and follows a theme for free. A live
 * chart cannot: the engine paints a tooltip's own background itself, so those
 * few values are read out of the document here, and re-read whenever the theme
 * changes.
 */
function tooltipStyle(): Record<string, unknown> {
	const tokens = readTokens();
	return {
		backgroundColor: tokens['--color-surface'],
		borderColor: tokens['--chart-grid'],
		textStyle: { color: tokens['--color-text'], fontSize: 13 }
	};
}

function givenTooltip(option: EChartsOption): Record<string, unknown> {
	return typeof option.tooltip === 'object' && !Array.isArray(option.tooltip)
		? (option.tooltip as Record<string, unknown>)
		: {};
}

/** The whole option, painted for the theme in the document right now. */
function fullOption(option: EChartsOption): EChartsOption {
	return resolveSentinels({
		...option,
		tooltip: { trigger: 'item', ...tooltipStyle(), ...givenTooltip(option) }
	});
}

/** The colours alone, painted for the theme in the document right now. */
function colourOption(template: EChartsOption): EChartsOption {
	const painted = resolveSentinels(template);
	return { ...painted, tooltip: { ...tooltipStyle(), ...givenTooltip(painted) } };
}

/** Every live chart's repaint, and one watch between them.
 *
 * One observer per chart meant the number of observers grew with the number of
 * charts, and every one of them read the theme out of the document again on
 * every flip. This reads it once and tells the charts, and it refuses a repaint
 * when the attribute moved but no value under it did.
 */
const repainters = new Set<() => void>();
let themed: MutationObserver | null = null;
let lastTokens = '';

function tokenPrint(): string {
	return Object.values(readTokens()).join('|');
}

function watchTheme(repaint: () => void): () => void {
	repainters.add(repaint);
	if (themed === null) {
		lastTokens = tokenPrint();
		themed = new MutationObserver(() => {
			const print = tokenPrint();
			if (print === lastTokens) return;
			lastTokens = print;
			for (const one of [...repainters]) one();
		});
		themed.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['data-theme']
		});
	}
	return () => {
		repainters.delete(repaint);
		if (repainters.size === 0) {
			themed?.disconnect();
			themed = null;
		}
	};
}

/** How many instances the engine holds, published where a test can read it. A
 * chart that is unmounted and not released shows up here as a number that only
 * ever goes up. */
let held = 0;

function countHeld(step: number): void {
	held += step;
	document.documentElement.setAttribute('data-charts-live', String(held));
}

export function hydrate(node: HTMLElement, option: EChartsOption, size: ChartSize): LiveChart {
	let current = option;
	let template = (paintedParts(option, false).part ?? {}) as EChartsOption;
	let at: ChartSize = { ...size };
	let chart: Instance | null = null;
	let gone = false;
	let started = false;
	let unwatch: (() => void) | null = null;
	let near: IntersectionObserver | null = null;
	let options = 0;
	let colours = 0;

	node.setAttribute('data-chart', 'waiting');

	const publish = (): void => {
		node.setAttribute('data-chart-options', String(options));
		node.setAttribute('data-chart-colours', String(colours));
	};

	const applyOption = (): void => {
		if (chart === null) return;
		options += 1;
		// A new option replaces the old one outright. Merging would leave a
		// property the new option dropped - a stack, a mark line - alive on a
		// chart that no longer asks for it.
		chart.setOption(fullOption(current), { notMerge: true });
		publish();
	};

	const repaint = (): void => {
		if (chart === null) return;
		colours += 1;
		chart.setOption(colourOption(template));
		publish();
	};

	const start = (): void => {
		if (gone || started) return;
		started = true;
		void (async () => {
			// The library is a network fetch of its own and it can fail. The server
			// already drew this chart, so a failure costs the tooltip and nothing
			// else - said once in the console rather than thrown at a reader who
			// can do nothing with it.
			const loaded = await import('./core').catch((reason: unknown) => {
				console.warn('a chart engine did not load, so the chart stays as drawn', reason);
				return null;
			});
			// The chunk is a network fetch, so a chart can be unmounted while it is
			// in flight. Drawing into a detached node then leaks an instance nothing
			// is left holding to dispose.
			if (loaded === null || gone || !node.isConnected) return;
			node.replaceChildren();
			chart = loaded.echarts.init(node, null, {
				renderer: 'svg',
				// The container decides, not the server's authored width. The
				// prerendered SVG stretches to fill; a live chart drawn at the
				// authored width would shrink the moment it hydrated.
				width: node.clientWidth || at.width,
				height: at.height
			});
			countHeld(1);
			node.setAttribute('data-chart', 'live');
			applyOption();
			unwatch = watchTheme(repaint);
		})();
	};

	if (typeof IntersectionObserver === 'undefined') start();
	else {
		near = new IntersectionObserver(
			(entries) => {
				if (!entries.some((entry) => entry.isIntersecting)) return;
				near?.disconnect();
				near = null;
				start();
			},
			{ rootMargin: REACH }
		);
		near.observe(node);
	}

	return {
		update: (next) => {
			if (gone) return;
			current = next;
			template = (paintedParts(next, false).part ?? {}) as EChartsOption;
			applyOption();
		},
		resize: (next) => {
			if (gone) return;
			if (next.width === at.width && next.height === at.height) return;
			at = { ...next };
			// A chart that has not been drawn yet keeps the size for when it is.
			chart?.resize({ width: next.width, height: next.height });
		},
		destroy: () => {
			if (gone) return;
			gone = true;
			near?.disconnect();
			near = null;
			unwatch?.();
			unwatch = null;
			if (chart !== null) {
				chart.dispose();
				chart = null;
				countHeld(-1);
			}
		}
	};
}
