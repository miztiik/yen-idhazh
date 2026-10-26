/** Size a story plot from viewport room and its readable content, not mark density. */
import type { VisualData } from '../payload/types';
import type { StoryChartGeometryConfig } from '../server/config';
import { roomIn } from './width';

export interface ChartRoom {
	width: number;
	height: number;
	textHeight: number;
}

/** Axis guides need text clearance too; thinning guides never removes source marks. */
export function fitChartTicks(
	data: VisualData,
	geometry: StoryChartGeometryConfig,
	textHeight: number,
	maximum: number
): number {
	const span = data.type === 'scatter' || data.type === 'bubble'
		? geometry.scatter_height_px - geometry.scatter_margin_top_px - geometry.scatter_margin_bottom_px
		: geometry.line_min_height_px - geometry.line_axis_margin_top_px - geometry.axis_band_px;
	return Math.max(1, Math.min(maximum, Math.floor(span / (textHeight + geometry.value_gap_px))));
}

export function fitChartGeometry(
	data: VisualData,
	geometry: StoryChartGeometryConfig,
	room: Pick<ChartRoom, 'height' | 'textHeight'>
): StoryChartGeometryConfig {
	const clearance = Math.max(
		room.textHeight + geometry.value_gap_px,
		geometry.dot_radius_px * 2 + geometry.mark_outline_width_px
	);
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const values = data.encoding.quantity.map((id) => Number(held.get(id)!.value));
	let slopeSpan = clearance;
	if (data.type === 'slope') {
		const span = Math.max(...values) - Math.min(...values);
		for (const side of [0, 1]) {
			const column = values.filter((_, index) => index % 2 === side).sort((a, b) => a - b);
			for (let index = 1; index < column.length; index++) {
				const gap = column[index] - column[index - 1];
				// Coincident readings are data, not a reason for infinite height.
				if (gap > 0) slopeSpan = Math.max(slopeSpan, clearance * span / gap);
			}
		}
	}
	return {
		...geometry,
		row_height_px: Math.max(
			geometry.row_height_px,
			room.textHeight / ((1 - geometry.bar_height_share) * (1 - geometry.row_padding_share))
		),
		line_min_height_px: Math.ceil(Math.max(
			room.height,
			geometry.line_axis_margin_top_px + geometry.axis_band_px + clearance
		)),
		scatter_height_px: Math.ceil(Math.max(
			room.height,
			geometry.scatter_margin_top_px + geometry.scatter_margin_bottom_px + clearance
		)),
		slope_min_height_px: Math.ceil(Math.max(
			room.height,
			geometry.slope_header_band_px + geometry.slope_footer_band_px + slopeSpan
		))
	};
}

type Measured = (room: ChartRoom) => void;
const figures = new Map<Element, Measured>();
let observer: ResizeObserver | null = null;

function measure(node: Element, run: Measured): void {
	const plot = node.querySelector<SVGSVGElement>(':scope > svg');
	const text = plot?.querySelector<SVGTextElement>('text');
	const style = getComputedStyle(node);
	const shell = document.querySelector('[data-filter-bar]');
	const shellStyle = shell ? getComputedStyle(shell) : null;
	const occlusion = shell && shellStyle?.position === 'sticky'
		? shell.getBoundingClientRect().height + (parseFloat(shellStyle.top) || 0) : 0;
	const furniture = node.getBoundingClientRect().height -
		(plot?.getBoundingClientRect().height ?? 0) +
		parseFloat(style.marginTop) + parseFloat(style.marginBottom);
	const textHeight = text ? text.getBBox().height : parseFloat(style.fontSize);
	run({
		width: roomIn(node),
		height: Math.max(0, (window.visualViewport?.height ?? window.innerHeight) - occlusion - furniture),
		textHeight
	});
}

function measureAll(): void {
	for (const [node, run] of figures) measure(node, run);
}

/** One observer and viewport subscription serve every mounted story figure. */
export function whenChartFits(node: Element, run: Measured): () => void {
	if (figures.size === 0) {
		window.addEventListener('resize', measureAll);
		window.visualViewport?.addEventListener('resize', measureAll);
		document.fonts.addEventListener('loadingdone', measureAll);
	}
	observer ??= new ResizeObserver(measureAll);
	figures.set(node, run);
	observer.observe(node);
	for (const child of node.children) observer.observe(child);
	measure(node, run);
	return () => {
		observer?.unobserve(node);
		for (const child of node.children) observer?.unobserve(child);
		figures.delete(node);
		if (figures.size === 0) {
			window.removeEventListener('resize', measureAll);
			window.visualViewport?.removeEventListener('resize', measureAll);
			document.fonts.removeEventListener('loadingdone', measureAll);
		}
	};
}
