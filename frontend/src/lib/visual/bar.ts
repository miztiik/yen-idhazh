/** Turn validated story-chart data into geometry and exact readings. */

import { scaleLinear } from 'd3-scale';
import { frame, type ChartLabels, type Frame } from '../charts/frame';
import { dateSeries, type PlacedPoint } from '../charts/d3/dateSeries';
import { LEGACY_MODEL_RULE } from '../charts/d3/model-rule';
import { PALETTE, type ChartPaletteToken } from '../charts/theme';
import { UNRECORDED_STOP } from '../charts/machine-colour';
import { factsOf, type ReadoutFacts } from '../charts/readout';
import { partsOfOne, pieOfOne, type PartsGeometry, type PieGeometry } from '../charts/d3/partsOfOne';
import type { VisualData, VisualMark } from '$lib/payload/types';
import type { NumberFormatConfig, NumberFormatter } from '$lib/number-format';
import type { StoryChartGeometryConfig } from '$lib/server/config';
import { drawScatter, statedScatter, type ScatterDrawing } from './scatter';
import { drawBubble, statedBubble, type BubbleDrawing } from './bubble';
import { drawHistogram, statedHistogram, type HistogramDrawing } from './histogram';
import { displayUnitSymbol } from './unit-symbol';
import { drawBars, drawDots, statedBars, statedDots, type BarDrawing, type DotDrawing } from './comparison';

export { drawBars, drawDots, statedBars, statedDots } from './comparison';

/** A whole chart, placed. */
export interface DrawingBase {
	title: string | null;
	caption: string | null;
	/** The room the caller measured, which every mark below is placed inside. */
	width: number;
	height: number;
}

export interface Slope {
	name: string;
	color: number;
	left: { x: number; y: number; stated: string; displayed: string; emphasized: boolean };
	right: { x: number; y: number; stated: string; displayed: string; emphasized: boolean };
}

export interface SlopeDrawing extends DrawingBase {
	type: 'slope';
	unit: string | null;
	leftLabel: string;
	rightLabel: string;
	leftX: number;
	rightX: number;
	slopes: Slope[];
}

export interface LinePoint extends PlacedPoint {
	timeLabel: string;
	stated: string;
	displayed: string;
	sourceText: string | null;
	emphasized: boolean;
}

export interface Line {
	name: string;
	color: number;
	dasharray: string;
	path: string;
	points: LinePoint[];
}

export interface LineDrawing extends DrawingBase {
	type: 'line';
	frame: Frame;
	columns: number[];
	ticks: { index: number; date: string; text: string; anchor: 'start' | 'middle' | 'end' }[];
	axis: { ticks: { value: number; at: number; text: string }[] };
	unit: string | null;
	lines: Line[];
}

export interface StackedBarDrawing {
	type: 'stacked_bar';
	title: string | null;
	caption: string | null;
	width: number;
	geometry: PartsGeometry;
	readout: ReadoutFacts;
}

export interface PieDrawing extends DrawingBase {
	type: 'pie';
	whole: string;
	geometry: PieGeometry;
	parts: { label: string; value: number; displayed: string; emphasized: boolean }[];
}

export type Drawing =
	| BarDrawing
	| DotDrawing
	| SlopeDrawing
	| LineDrawing
	| ScatterDrawing
	| BubbleDrawing
	| StackedBarDrawing
	| PieDrawing
	| HistogramDrawing;

function figureOf(mark: VisualMark): number {
	// The compiler pins `value` to the characters the article wrote, so this is
	// a decimal string and never a formatted one. A figure that will not parse
	// is a compiler defect, and `Number` gives NaN rather than a wrong bar.
	return Number(mark.value);
}

/** Place paired measurements as two labelled columns and connecting lines. */
export function drawSlopes(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig
): SlopeDrawing {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const mark = (id: string): VisualMark => {
		const found = held.get(id);
		if (found === undefined) throw new Error(`visual data draws a mark it does not carry: ${id}`);
		return found;
	};
	const quantities = data.encoding.quantity.map(mark);
	const times = data.encoding.time.map(mark);
	const entities = data.encoding.entity.map(mark);
	const series = data.encoding.series.map(mark);
	const values = quantities.map(figureOf);
	const finite = values.filter(Number.isFinite);
	const minimum = Math.min(...finite);
	const maximum = Math.max(...finite);
	const count = quantities.length / 2;
	const width = Math.max(0, Math.floor(room));
	const height = geometry.slope_min_height_px;
	const top = geometry.slope_header_band_px;
	const bottom = height - geometry.slope_footer_band_px;
	const y = scaleLinear()
		.domain(minimum === maximum ? [minimum - 1, maximum + 1] : [minimum, maximum])
		.range([bottom, top]);
	const leftX = Math.round(width * geometry.slope_column_share);
	const rightX = Math.round(width * (1 - geometry.slope_column_share));
	const emphasizedIndex = quantities.findIndex((quantity) => quantity.mark_id === data.emphasized_mark_id);
	const slopes = Array.from({ length: count }, (_, index): Slope => {
		const left = quantities[index * 2];
		const right = quantities[index * 2 + 1];
		const leftValue = values[index * 2];
		const rightValue = values[index * 2 + 1];
		return {
			name: entities[index]?.text ?? series[index]?.text ?? '',
			color: index + 1,
			left: {
				x: leftX,
				y: Number.isFinite(leftValue) ? y(leftValue) : top,
				stated: left.value ?? '',
				displayed: formatNumber(leftValue, { si: true }),
				emphasized: emphasizedIndex === index * 2
			},
			right: {
				x: rightX,
				y: Number.isFinite(rightValue) ? y(rightValue) : top,
				stated: right.value ?? '',
				displayed: formatNumber(rightValue, { si: true }),
				emphasized: emphasizedIndex === index * 2 + 1
			}
		};
	});
	return {
		type: 'slope',
		title: data.title,
		caption: data.caption,
		width,
		height,
		unit: quantities[0]?.unit ?? null,
		leftLabel: times[0]?.text ?? '',
		rightLabel: times[1]?.text ?? '',
		leftX,
		rightX,
		slopes
	};
}

/** Place source-backed date/quantity pairs with the shared D3 date-series builder. */
export function drawLines(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	numberFormat: NumberFormatConfig,
	tickDensity: number,
	geometry: StoryChartGeometryConfig
): LineDrawing {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const mark = (id: string): VisualMark => {
		const found = held.get(id);
		if (found === undefined) throw new Error(`visual data draws a mark it does not carry: ${id}`);
		return found;
	};
	const quantities = data.encoding.quantity.map(mark);
	const times = data.encoding.time.map(mark);
	const labels = data.encoding.series.map(mark);
	const inputs = new Map<
		string,
		{ label: string; token: ChartPaletteToken; points: { date: string; value: number }[] }
	>();
	const sourcePoints = new Map<string, Map<string, LinePoint>>();
	for (const [index, quantity] of quantities.entries()) {
		const time = times[index];
		if (time?.time === null || time?.time === undefined || time.text === null) {
			throw new Error('line data has no canonical date and source label');
		}
		const name = labels[index]?.text ?? '';
		let input = inputs.get(name);
		if (input === undefined) {
			const token = PALETTE[inputs.size];
			if (token === undefined) throw new Error('line data exceeds the chart colour palette');
			input = { label: name, token, points: [] };
			inputs.set(name, input);
			sourcePoints.set(name, new Map());
		}
		if (quantity.value === null) throw new Error('line data has no measured value');
		const value = figureOf(quantity);
		const point: LinePoint = {
			date: time.time,
			value,
			timeLabel: time.text,
			stated: quantity.value,
			displayed: formatNumber(value, { si: true }),
			sourceText: quantity.source_text,
			emphasized: quantity.mark_id === data.emphasized_mark_id,
			x: 0,
			y: 0,
			alone: false
		};
		input.points.push({ date: time.time, value });
		const source = sourcePoints.get(name);
		if (source === undefined) throw new Error(`line source points are absent for series: ${name}`);
		source.set(time.time, point);
	}

	const width = Math.max(0, Math.floor(room));
	const chartFrame = frame(width, geometry.line_min_height_px, {
		top: geometry.line_axis_margin_top_px,
		right: geometry.dot_radius_px,
		bottom: geometry.axis_band_px,
		left: geometry.line_axis_margin_left_px
	});
	const series = dateSeries([...inputs.values()], {
		frame: chartFrame,
		density: tickDensity,
		valueTicks: tickDensity,
		number_format: numberFormat,
		padding: geometry.row_padding_share,
		rule: LEGACY_MODEL_RULE
	});
	if (series === null) throw new Error('line data has no finite readings');
	const lines = series.lines.map((line, index): Line => {
		const dasharray = geometry.line_series_dash_arrays[index];
		if (dasharray === undefined) throw new Error('line data exceeds the configured series patterns');
		const source = sourcePoints.get(line.label);
		if (source === undefined) throw new Error(`line geometry names an absent series: ${line.label}`);
		return {
			name: line.label,
			color: index + 1,
			dasharray,
			path: line.path,
			points: line.points.map((placed) => {
				const original = source.get(placed.date);
				if (original === undefined) throw new Error(`line geometry has no source point for ${placed.date}`);
				return { ...original, ...placed };
			})
		};
	});
	return {
		type: 'line',
		title: data.title,
		caption: data.caption,
		width,
		height: chartFrame.height,
		frame: chartFrame,
		columns: series.columns,
		ticks: series.ticks,
		axis: series.axis,
		unit: quantities[0]?.unit ?? null,
		lines
	};
}

/** Place one source-declared whole and its measured parts on the shared stack. */
export function drawStackedBars(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter
): StackedBarDrawing {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const mark = (id: string): VisualMark => {
		const found = held.get(id);
		if (found === undefined) throw new Error(`visual data draws a mark it does not carry: ${id}`);
		return found;
	};
	const whole = mark(data.encoding.category[0]);
	const quantities = data.encoding.quantity.map(mark);
	const labels = data.encoding.series.map(mark);
	const values = quantities.map(figureOf);
	const parts = labels.map((label, index) => ({
		label: label.text ?? '',
		value: values[index],
		emphasized: quantities[index].mark_id === data.emphasized_mark_id
	}));
	const hues = UNRECORDED_STOP - 1;
	const geometry = partsOfOne(
		[{ label: whole.text ?? '', parts }],
		{
			order: labels.map((label) => label.text ?? ''),
			tokens: labels.map((_, index) => PALETTE[index % hues])
		}
	);
	if (geometry === null) throw new Error('a validated stacked bar has no measurable parts');
	const unit = quantities[0]?.unit;
	const unitSuffix = unit ? ` ${displayUnitSymbol(unit)}` : '';
	const readout = factsOf(
		whole.text ?? '',
		parts.map((part, index) => ({
			label: part.label,
			value: [
				`${formatNumber(values[index], { si: true })}${unitSuffix}`,
				quantities[index].source_text
					? `(source: ${quantities[index].source_text})`
					: ''
			].filter(Boolean).join(' '),
			swatch: `var(${geometry.key[index].token})`
		})),
		'Not measured'
	);
	return {
		type: 'stacked_bar',
		title: data.title,
		caption: data.caption,
		width: Math.max(0, Math.floor(room)),
		geometry,
		readout
	};
}

/** Draw source-linked shares against the separately stated whole. */
export function drawPie(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	availableHeight: number,
	geometry: StoryChartGeometryConfig
): PieDrawing {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const labels = data.encoding.category.map((id) => held.get(id)!);
	const quantities = data.encoding.quantity.map((id) => held.get(id)!);
	if (
		data.declared_whole === null || labels.length < 2 ||
		labels.length !== quantities.length
	) throw new Error('pie data has no declared whole or does not pair each part');
	const parts = labels.map((label, index) => {
		const quantity = quantities[index]!;
		const value = figureOf(quantity);
		return {
			label: label.text ?? '',
			value,
			emphasized: quantity.mark_id === data.emphasized_mark_id
		};
	});
	const width = Math.max(0, Math.floor(room));
	const height = Math.max(
		geometry.line_min_height_px,
		Math.floor(Math.min(width, availableHeight))
	);
	const pieGeometry = pieOfOne(parts, Math.min(width, height));
	if (pieGeometry === null) throw new Error('a validated pie has no measurable parts');
	return {
		type: 'pie',
		title: data.title,
		caption: data.caption,
		width,
		height,
		whole: data.declared_whole.text,
		geometry: pieGeometry,
		parts: parts.map((part) => ({
			...part,
			displayed: formatNumber(part.value, { si: false })
		}))
	};
}

export function drawVisual(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	numberFormat: NumberFormatConfig,
	tickDensity: number,
	geometry: StoryChartGeometryConfig,
	availableHeight: number = geometry.line_min_height_px,
	comparison?: { narrowBelow: number; labels?: ChartLabels }
): Drawing {
	switch (data.type) {
		case 'bar':
			return drawBars(data, room, formatNumber, geometry, { numberFormat, tickDensity, ...comparison });
		case 'dot':
			return drawDots(data, room, formatNumber, geometry, { numberFormat, tickDensity, ...comparison });
		case 'slope':
			return drawSlopes(data, room, formatNumber, geometry);
		case 'line':
			return drawLines(data, room, formatNumber, numberFormat, tickDensity, geometry);
		case 'scatter':
			return drawScatter(data, room, formatNumber, numberFormat, tickDensity, geometry);
		case 'bubble':
			return drawBubble(data, room, formatNumber, numberFormat, tickDensity, geometry);
		case 'stacked_bar':
			return drawStackedBars(data, room, formatNumber);
		case 'pie':
			return drawPie(data, room, formatNumber, availableHeight, geometry);
		case 'histogram':
			return drawHistogram(data, room, formatNumber, numberFormat, geometry);
		default:
			throw new Error(`visual type is not drawn: ${data.type}`);
	}
}

export function statedSlopes(drawing: SlopeDrawing): string {
	const tail = drawing.unit ? ` ${drawing.unit}` : '';
	const facts = drawing.slopes.map((slope) =>
		`${slope.name}: ${drawing.leftLabel} ${slope.left.stated}${tail}` +
		`${slope.left.emphasized ? ' (highlighted)' : ''}; ` +
		`${drawing.rightLabel} ${slope.right.stated}${tail}` +
		`${slope.right.emphasized ? ' (highlighted)' : ''}`
	);
	return [drawing.title, `Slope chart. ${facts.join('; ')}.`, drawing.caption]
		.filter(Boolean).join(' ');
}

export function statedLines(drawing: LineDrawing): string {
	const tail = drawing.unit ? ` ${drawing.unit}` : '';
	const facts = drawing.lines.flatMap((line) => line.points.map((point) =>
		`${line.name ? `${line.name}: ` : ''}${point.timeLabel} ${point.stated}${tail}` +
		`${point.emphasized ? ' (highlighted)' : ''}` +
		`${point.sourceText ? ` (source: ${point.sourceText})` : ''}`
	));
	return [drawing.title, `Line chart. ${facts.join('; ')}.`, drawing.caption]
		.filter(Boolean).join(' ');
}

export function statedDrawing(drawing: Drawing): string {
	switch (drawing.type) {
		case 'bar':
			return statedBars(drawing);
		case 'dot':
			return statedDots(drawing);
		case 'slope':
			return statedSlopes(drawing);
		case 'line':
			return statedLines(drawing);
		case 'scatter':
			return statedScatter(drawing);
		case 'bubble':
			return statedBubble(drawing);
		case 'stacked_bar': {
			const facts = drawing.readout.facts.map((fact) =>
				`${fact.label} ${fact.value ?? drawing.readout.notMeasured}` +
				`${drawing.geometry.rows[0].segments.find((segment) =>
					segment.label === fact.label
				)?.emphasized ? ' (highlighted)' : ''}`
			);
			return [
				drawing.title,
				`Stacked bar chart. ${drawing.geometry.rows[0].label}: ${facts.join('; ')}.`,
				drawing.caption
			].filter(Boolean).join(' ');
		}
		case 'pie': {
			const facts = drawing.parts.map((part) =>
				`${part.label} ${part.displayed}%${part.emphasized ? ' (highlighted)' : ''}`
			);
			return [
				drawing.title,
				`Pie chart. Declared total: ${drawing.whole}. Shares: ${facts.join('; ')}.`,
				drawing.caption
			].filter(Boolean).join(' ');
		}
		case 'histogram': {
			return statedHistogram(drawing);
		}
	}
}
