/** Place every validated story pair with the shared D3 scatter builder. */
import { frame, type Frame } from '../charts/frame';
import { pairedScatter, type ScatterMark } from '../charts/d3/pairedScatter';
import type { ValueAxis } from '../charts/d3/axis';
import type { VisualData, VisualMark } from '../payload/types';
import type { NumberFormatConfig, NumberFormatter } from '../number-format';
import type { StoryChartGeometryConfig } from '../server/config';
import type { DrawingBase } from './bar';

export interface StoryScatterPoint extends ScatterMark {
	emphasized: boolean;
	statedX: string;
	statedY: string;
	displayedX: string;
	displayedY: string;
	sourceX: string | null;
	sourceY: string | null;
}

export interface ScatterDrawing extends DrawingBase {
	type: 'scatter';
	frame: Frame;
	x: ValueAxis;
	y: ValueAxis;
	xUnit: string | null;
	yUnit: string | null;
	points: StoryScatterPoint[];
}

export function drawScatter(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	numberFormat: NumberFormatConfig,
	tickDensity: number,
	geometry: StoryChartGeometryConfig
): ScatterDrawing {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const mark = (id: string): VisualMark => {
		const found = held.get(id);
		if (found === undefined) throw new Error(`scatter names an absent mark: ${id}`);
		return found;
	};
	const entities = data.encoding.entity.map(mark);
	const horizontal = data.encoding.quantity_x.map(mark);
	const vertical = data.encoding.quantity.map(mark);
	const series = data.encoding.series.map(mark);
	if (
		entities.length === 0 || horizontal.length !== entities.length ||
		vertical.length !== entities.length || (series.length !== 0 && series.length !== entities.length)
	) throw new Error('scatter data has an incomplete source pair');
	const inputs = entities.map((entity, index) => {
		const x = horizontal[index];
		const y = vertical[index];
		if (entity.text === null || x?.value == null || y?.value == null) {
			throw new Error('scatter data has an incomplete source pair');
		}
		const values = { x: Number(x.value), y: Number(y.value) };
		if (!Number.isFinite(values.x) || !Number.isFinite(values.y)) {
			throw new Error('scatter data has a non-finite source pair');
		}
		return {
			...values,
			label: entity.text,
			name: `${entity.text}${series[index]?.text ? ` (${series[index].text})` : ''}`,
			emphasized: y.mark_id === data.emphasized_mark_id,
			statedX: x.value,
			statedY: y.value,
			displayedX: formatNumber(values.x, { si: true }),
			displayedY: formatNumber(values.y, { si: true }),
			sourceX: x.source_text,
			sourceY: y.source_text
		};
	});
	const width = Math.max(0, Math.floor(room));
	const chartFrame = frame(width, geometry.scatter_height_px, {
		left: geometry.scatter_margin_left_px,
		right: geometry.scatter_margin_right_px,
		top: geometry.scatter_margin_top_px,
		bottom: geometry.scatter_margin_bottom_px
	});
	const placed = pairedScatter(inputs, {
		frame: chartFrame,
		// The producer applies the configured evidence floor. The story must keep
		// its entire validated set, not the explorer's finite-pair subset.
		minRows: inputs.length,
		minSubjects: inputs.length,
		valueTicks: tickDensity,
		number_format: numberFormat
	});
	if (placed === null || placed.marks.length !== inputs.length) {
		throw new Error('scatter geometry did not preserve the complete entity set');
	}
	return {
		type: 'scatter',
		title: data.title,
		caption: data.caption,
		width,
		height: chartFrame.height,
		frame: chartFrame,
		x: placed.x,
		y: placed.y,
		xUnit: horizontal[0]?.unit ?? null,
		yUnit: vertical[0]?.unit ?? null,
		points: placed.marks.map((point, index) => ({
			...inputs[index], ...point, label: inputs[index].name
		}))
	};
}

export function statedScatter(drawing: ScatterDrawing): string {
	const facts = drawing.points.map((point) =>
		`${point.label}: x ${point.statedX}${drawing.xUnit ? ` ${drawing.xUnit}` : ''}` +
		`${point.sourceX ? ` (source: ${point.sourceX})` : ''}, ` +
		`y ${point.statedY}${drawing.yUnit ? ` ${drawing.yUnit}` : ''}` +
		`${point.sourceY ? ` (source: ${point.sourceY})` : ''}` +
		`${point.emphasized ? ' (highlighted)' : ''}`
	);
	return [drawing.title, `Scatter chart. ${facts.join('; ')}.`, drawing.caption]
		.filter(Boolean).join(' ');
}
