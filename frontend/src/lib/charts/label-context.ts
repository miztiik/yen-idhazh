/** Give console drawings the same measured type that their labels render in. */
import { getContext, setContext } from 'svelte';
import { DEFAULT_CHART_LABELS, frame, labelsFromStyle, type ChartLabels, type Margin } from './frame';
import type { ChartConfig } from '../server/config';

const LABELS = Symbol('console-chart-labels');

export function provideChartLabels(read: () => ChartLabels | null): void {
	setContext(LABELS, read);
}

export function useChartLabels(): () => ChartLabels {
	const read = getContext<(() => ChartLabels | null) | undefined>(LABELS);
	return () => read?.() ?? DEFAULT_CHART_LABELS;
}

export function useChartFrame(config?: () => Pick<ChartConfig, 'label_style'>) {
	const read = getContext<(() => ChartLabels | null) | undefined>(LABELS);
	return (width: number, height: number, margin?: Margin) => {
		const measured = read?.();
		const style = config?.().label_style;
		const rootSize = typeof document === 'undefined'
			? null : Number.parseFloat(getComputedStyle(document.documentElement).fontSize);
		const labels = measured ?? (style && rootSize !== null
			? labelsFromStyle(style, rootSize) : DEFAULT_CHART_LABELS);
		return frame(width, height, margin, labels);
	};
}

/** The node uses the configured small type; ResizeObserver follows text zoom. */
export function measureChartLabels(
	node: HTMLElement,
	show: (labels: ChartLabels) => void
): { destroy(): void } {
	const canvas = document.createElement('canvas');
	const found = canvas.getContext('2d');
	if (found === null) throw new Error('Console labels need the browser text measurement context.');
	const context: CanvasRenderingContext2D = found;
	function measure(): void {
		const style = getComputedStyle(node);
		const fontSize = Number.parseFloat(style.fontSize);
		const leading = Number.parseFloat(style.lineHeight);
		const tracking = style.letterSpacing === 'normal' ? 0 : Number.parseFloat(style.letterSpacing);
		if (![fontSize, leading, tracking].every(Number.isFinite)) {
			throw new Error('Console label size, leading and tracking must resolve to CSS pixels.');
		}
		context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
		show({ fontSize, leading, tracking, measure: (text) => context.measureText(text).width });
	}
	const observer = new ResizeObserver(measure);
	observer.observe(node);
	measure();
	let mounted = true;
	void document.fonts.ready.then(() => { if (mounted) measure(); });
	return { destroy() { mounted = false; observer.disconnect(); } };
}
