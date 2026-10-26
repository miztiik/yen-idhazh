/** Place complete relationship points and encode size with proportional area. */
import type { NumberFormatConfig, NumberFormatter } from '../number-format';
import type { VisualData, VisualMark } from '../payload/types';
import type { StoryChartGeometryConfig } from '../server/config';
import { drawScatter, type ScatterDrawing, type StoryScatterPoint } from './scatter';

export interface BubblePoint extends StoryScatterPoint {
	size: number;
	statedSize: string;
	displayedSize: string;
	sourceSize: string | null;
	radius: number;
}

export interface BubbleDrawing extends Omit<ScatterDrawing, 'type' | 'points'> {
	type: 'bubble';
	sizeUnit: string | null;
	maxRadius: number;
	sizeRange: {
		min: number;
		max: number;
		minRadius: number;
	};
	points: BubblePoint[];
}

export function drawBubble(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	numberFormat: NumberFormatConfig,
	tickDensity: number,
	geometry: StoryChartGeometryConfig
): BubbleDrawing {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const mark = (id: string): VisualMark => {
		const found = held.get(id);
		if (found === undefined) throw new Error(`bubble names an absent mark: ${id}`);
		return found;
	};
	const sizes = data.encoding.size.map(mark);
	const values = sizes.map((size) => Number(size.value));
	if (
		values.length === 0 || values.length !== data.encoding.quantity.length ||
		values.some((value) => !Number.isFinite(value) || value <= 0)
	) throw new Error('bubble data has a non-positive or non-finite size');

	const base = drawScatter(data, room, formatNumber, numberFormat, tickDensity, geometry);
	const maxRadius = Math.max(
		0,
		Math.min(base.frame.innerWidth, base.frame.innerHeight) *
			geometry.bubble_max_radius_share - geometry.mark_outline_width_px / 2
	);
	const inset = maxRadius + geometry.mark_outline_width_px / 2;
	const placed = drawScatter(data, room, formatNumber, numberFormat, tickDensity, {
		...geometry,
		scatter_margin_left_px: geometry.scatter_margin_left_px + inset,
		scatter_margin_right_px: geometry.scatter_margin_right_px + inset,
		scatter_margin_top_px: geometry.scatter_margin_top_px + inset,
		scatter_margin_bottom_px: geometry.scatter_margin_bottom_px + inset
	});
	const largest = Math.max(...values);
	const smallest = Math.min(...values);
	const radiusFor = (value: number) => maxRadius * Math.sqrt(value / largest);
	const sizeRange = {
		min: smallest,
		max: largest,
		minRadius: radiusFor(smallest)
	};

	return {
		...placed,
		type: 'bubble',
		sizeUnit: sizes[0]?.unit ?? null,
		maxRadius,
		sizeRange,
		points: placed.points.map((point, index) => {
			const size = sizes[index]!;
			const value = values[index]!;
			return {
				...point,
				size: value,
				statedSize: size.value!,
				displayedSize: formatNumber(value, { si: true }),
				sourceSize: size.source_text,
				radius: radiusFor(value)
			};
		})
	};
}

export function statedBubble(drawing: BubbleDrawing): string {
	const facts = drawing.points.map((point) =>
		`${point.label}: x ${point.statedX}${drawing.xUnit ? ` ${drawing.xUnit}` : ''}` +
		`${point.sourceX ? ` (source: ${point.sourceX})` : ''}, ` +
		`y ${point.statedY}${drawing.yUnit ? ` ${drawing.yUnit}` : ''}` +
		`${point.sourceY ? ` (source: ${point.sourceY})` : ''}, ` +
		`area ${point.statedSize}${drawing.sizeUnit ? ` ${drawing.sizeUnit}` : ''}` +
		`${point.sourceSize ? ` (source: ${point.sourceSize})` : ''}` +
		`${point.emphasized ? ' (highlighted)' : ''}`
	);
	return [
		drawing.title,
		`Bubble chart. Circle area represents ${drawing.sizeUnit ?? 'size'}. ${facts.join('; ')}.`,
		drawing.caption
	].filter(Boolean).join(' ');
}
