/** Send typed chart readings to the console's single pointer-hover surface. */
import type { Readout, ReadoutFacts } from './readout';
import { readoutView, type ReadoutView } from './readout-view';

/** A local DOM event, not a persisted payload or an outbound message. */
export const CHART_HOVER_EVENT = 'console-chart-hover';

export type HoverSource = Readout | ReadoutFacts | readonly (ReadoutFacts | null)[];
export interface HoverReadout {
	name: string;
	readout: HoverSource | null;
	offset?: number;
	/** Optional compact projections of the same readings, keyed by an actual mark. */
	byMark?: ReadonlyMap<string, HoverSource>;
	footnote?: boolean;
}
export type ChartHover =
	| { source: Element; reading: ReadoutView; name: string; x: number; y: number; footnote?: boolean }
	| { source: Element; reading: null };

export function hoverReading(source: HoverReadout, index: number, markKey: string | null = null): ReadoutView | null {
	const readout = (markKey === null ? undefined : source.byMark?.get(markKey)) ?? source.readout;
	if (readout === null) return null;
	const at = index + (source.offset ?? 0);
	if ('columns' in readout) return readoutView(readout, at);
	if ('subject' in readout) return readoutView(readout);
	return readoutView(readout[at] ?? null);
}

export function hoverPosition(
	point: { x: number; y: number },
	box: { width: number; height: number },
	viewport: { width: number; height: number },
	gap: number
): { left: number; top: number } {
	const left = Math.max(gap, Math.min(point.x + gap, viewport.width - box.width - gap));
	const below = point.y + gap;
	const above = point.y - box.height - gap;
	return { left, top: Math.max(gap, below + box.height <= viewport.height - gap ? below : above) };
}

/** Selection actions call this after resolving the actual column or record. */
export function createHoverReadout(node: Element, initial: HoverReadout | undefined) {
	let source = initial;
	let shown = false;
	const publish = (detail: ChartHover) =>
		node.dispatchEvent(new CustomEvent<ChartHover>(CHART_HOVER_EVENT, { detail, bubbles: true }));
	const hide = () => {
		if (shown) publish({ source: node, reading: null });
		shown = false;
	};
	const declare = () => {
		if (source?.readout !== null && source !== undefined) node.setAttribute('data-chart-hover', source.name);
		else node.removeAttribute('data-chart-hover');
	};
	declare();
	return {
		show(event: PointerEvent, index: number | null) {
			if (source === undefined || index === null || event.type !== 'pointermove' ||
				(event.pointerType !== 'mouse' && event.pointerType !== 'pen') ||
				event.buttons !== 0 || !node.closest('[data-surface="operator"]')) {
				hide();
				return;
			}
			if (event.target instanceof Element && event.target.closest('[data-chart-hover]') !== node) return;
			const mark = event.target instanceof Element ? event.target.closest('[data-readout-key]') : null;
			const key = mark !== null && node.contains(mark) ? mark.getAttribute('data-readout-key') : null;
			const reading = hoverReading(source, index, key);
			if (reading === null) { hide(); return; }
			shown = true;
			publish({ source: node, reading, name: source.name, x: event.clientX, y: event.clientY, footnote: source.footnote });
		},
		update(next: HoverReadout | undefined) {
			if (next?.readout !== source?.readout || next?.offset !== source?.offset || next?.name !== source?.name ||
				next?.byMark !== source?.byMark || next?.footnote !== source?.footnote) hide();
			source = next;
			declare();
		},
		hide,
		destroy() { hide(); node.removeAttribute('data-chart-hover'); }
	};
}

/** Printed tracks retain their printed facts; they need no second standing strip. */
export function hoverReadout(node: Element, source: HoverReadout) {
	let current = source;
	const hover = createHoverReadout(node, source);
	const move = (event: Event) => {
		if (!(event instanceof PointerEvent)) return;
		const mark = event.target instanceof Element ? event.target.closest('[data-readout-at]') : null;
		if (current.readout !== null && !('columns' in current.readout) && !('subject' in current.readout) && mark === null) {
			hover.hide();
			return;
		}
		const index = mark !== null && node.contains(mark) ? Number(mark.getAttribute('data-readout-at')) : 0;
		if (Number.isInteger(index) && index >= 0) hover.show(event, index);
	};
	const hide = () => hover.hide();
	node.addEventListener('pointermove', move);
	node.addEventListener('pointerleave', hide);
	node.addEventListener('pointerdown', hide);
	return {
		update(next: HoverReadout) { current = next; hover.update(current); },
		destroy() {
			node.removeEventListener('pointermove', move);
			node.removeEventListener('pointerleave', hide);
			node.removeEventListener('pointerdown', hide);
			hover.destroy();
		}
	};
}
