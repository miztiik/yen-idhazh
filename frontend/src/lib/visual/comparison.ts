/** Place horizontal story comparisons, including their measurements and value axis. */
import { scaleLinear } from 'd3-scale';
import { DEFAULT_CHART_LABELS, labelGutter, labelWidth, thinLabels, tickAnchor, type ChartLabels } from '../charts/frame';
import { PALETTE } from '../charts/theme';
import { numberFormatter, type NumberFormatConfig, type NumberFormatter } from '../number-format';
import type { VisualData } from '../payload/types';
import type { StoryChartGeometryConfig } from '../server/config';
import type { DrawingBase } from './bar';
import { displayUnitSymbol } from './unit-symbol';

interface ComparisonRow {
	name: string;
	stated: string;
	sourceText: string | null;
	displayed: string;
	color: (typeof PALETTE)[number];
	lines: string[];
	label: number;
	center: number;
	plotTop: number;
	plotBottom: number;
}

interface ComparisonDrawing extends DrawingBase {
	unit: string | null;
	inset: number;
	leading: number;
	valueX: number;
	baseline: number;
	axis: {
		left: number;
		right: number;
		ticks: { value: number; x: number; text: string; anchor: ReturnType<typeof tickAnchor> }[];
		label: string[];
		description: string;
		labelY: number;
		tickY: number;
	};
}

interface Bar extends ComparisonRow {
	x: number;
	y: number;
	width: number;
	height: number;
}

interface Dot extends ComparisonRow {
	x: number;
	y: number;
	radius: number;
}

export interface BarDrawing extends ComparisonDrawing {
	type: 'bar';
	bars: Bar[];
}

export interface DotDrawing extends ComparisonDrawing {
	type: 'dot';
	dots: Dot[];
}

interface ComparisonOptions {
	numberFormat: NumberFormatConfig;
	tickDensity: number;
	narrowBelow?: number;
	labels?: ChartLabels;
}

/** English names for the powers of a thousand used on the reading surface. */
const MAGNITUDE_WORDS: Readonly<Record<number, string>> = {
	0: '', 3: 'thousand', 6: 'million', 9: 'billion', 12: 'trillion'
};

function comparisonFormat(
	values: number[],
	formatNumber: NumberFormatter,
	config?: NumberFormatConfig
) {
	const magnitude = Math.max(...values.map(Math.abs));
	const exponent = config && magnitude >= config.si_prefix_from
		? Math.max(0, Math.floor(Math.log10(magnitude) / 3) * 3) : 0;
	const divisor = 10 ** exponent;
	return {
		magnitude: MAGNITUDE_WORDS[exponent] ?? `x 10^${exponent}`,
		format: (value: number) => {
			// Preserve the decimal precision of the reading, not floating-point
			// digits introduced by division into the shared unit.
			const digits = value.toExponential().split('e')[0].replace(/[-.]/g, '').length;
			const formatter = config && digits > config.significant_digits
				? numberFormatter({ ...config, significant_digits: digits }) : formatNumber;
			return formatter(value / divisor, { si: false });
		}
	};
}

function wrapText(text: string, width: number, labels: ChartLabels): string[] {
	if (!text) return [];
	const fits = (line: string) => labelWidth(line, labels) <= width;
	if (fits(text)) return [text];
	const lines: string[] = [];
	let line = '';
	for (const word of text.split(/\s+/)) {
		const next = line ? `${line} ${word}` : word;
		if (fits(next)) {
			line = next;
			continue;
		}
		if (line) lines.push(line);
		line = '';
		for (const character of word) {
			if (line && !fits(line + character)) {
				lines.push(line);
				line = '';
			}
			line += character;
		}
	}
	if (line) lines.push(line);
	return lines;
}

function drawComparison(
	type: 'bar' | 'dot',
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig,
	options?: ComparisonOptions
) {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const rows = data.encoding.quantity.map((id, index) => {
		const quantity = held.get(id)!;
		const category = held.get(data.encoding.category[index])!.text ?? '';
		const series = held.get(data.encoding.series[index])?.text;
		return {
			name: series && series !== category ? `${category} (${series})` : category,
			series,
			value: Number(quantity.value),
			stated: quantity.value ?? '',
			sourceText: quantity.source_text,
			unit: quantity.unit
		};
	});
	const series = [...new Set(rows.map((row) => row.series))];
	if (type === 'bar') rows.sort((a, b) => b.value - a.value);

	const values = rows.map((row) => row.value);
	const unit = rows[0].unit;
	const labels = options?.labels ?? DEFAULT_CHART_LABELS;
	const leading = labels.leading;
	const gap = geometry.value_gap_px;
	const width = Math.max(0, Math.floor(room));
	const inset = gap;
	const valueX = width - inset;
	const ticks = options?.tickDensity ?? rows.length;
	const low = type === 'bar' ? Math.min(...values, 0) : Math.min(...values);
	const high = type === 'bar' ? Math.max(...values, 0) : Math.max(...values);
	const scale = scaleLinear()
		.domain(type === 'bar' && low === high ? [0, 1] : [low, high])
		.nice(ticks);
	const [minimum, maximum] = scale.domain();
	const stops = [...new Set([minimum, ...scale.ticks(ticks), maximum])];
	const scaled = comparisonFormat([...values, ...stops], formatNumber, options?.numberFormat);
	const displayed = rows.map((row) => scaled.format(row.value));
	const valueWidth = Math.ceil(Math.max(...displayed.map((text) => labelWidth(text, labels))));
	const gutter = width < (options?.narrowBelow ?? 0)
		? null : labelGutter(rows.map((row) => row.name), labels, gap, width - 2 * inset);
	const radius = type === 'dot' ? geometry.dot_radius_px : 0;
	const left = inset + (gutter ?? 0) + radius;
	const right = Math.max(left, valueX - valueWidth - gap - radius);
	scale.range([left, right]);

	const rowBand = geometry.row_height_px * (1 - geometry.row_padding_share);
	const barHeight = Math.round(rowBand * geometry.bar_height_share);
	const halfMark = Math.max(leading / 2, radius, type === 'bar' ? barHeight / 2 : 0);
	const band = Math.max(geometry.row_height_px, 2 * halfMark + gap);
	let baseline = 0;
	const placed = rows.map((row, index) => {
		const lines = gutter === null ? wrapText(row.name, width - 2 * inset, labels) : [row.name];
		const plotTop = baseline + (gutter === null ? leading * lines.length : 0);
		const center = plotTop + (gutter === null ? halfMark : band / 2);
		const label = gutter === null ? baseline + leading / 2 : center;
		baseline = plotTop + band;
		return {
			...row,
			lines,
			label,
			center,
			plotTop,
			plotBottom: baseline,
			color: PALETTE[series.indexOf(row.series)],
			displayed: displayed[index],
			at: scale(row.value)
		};
	});
	const tickLabels = stops.map((value, index) => ({
		value, x: scale(value), text: scaled.format(value), anchor: tickAnchor(index, stops.length)
	}));
	const shown = new Set(thinLabels(tickLabels, labels, gap).map(({ value }) => value));
	const unitText = [scaled.magnitude, unit ? displayUnitSymbol(unit) : ''].filter(Boolean).join(' ');
	const tight = type === 'dot' && (minimum > 0 || maximum < 0);
	const axisName = [unitText, tight ? 'zero not shown' : ''].filter(Boolean).join('; ');
	const axisLabel = axisName ? `Scale: ${axisName}` : '';
	const axisLines = wrapText(axisLabel, width - 2 * inset, labels);
	const tickOffset = Math.max(geometry.axis_label_offset_px, leading / 2 + geometry.axis_line_width_px);
	const tickBand = Math.max(geometry.axis_band_px, tickOffset + leading / 2);
	const drawing: ComparisonDrawing = {
		title: data.title,
		caption: data.caption,
		width,
		height: baseline + tickBand + leading * axisLines.length,
		unit,
		inset,
		leading,
		valueX,
		baseline,
		axis: {
			left: scale(minimum), right: scale(maximum),
			ticks: tickLabels.map((tick) => shown.has(tick.value) ? tick : { ...tick, text: '' }),
			label: axisLines,
			description: `${axisName ? `Scale (${axisName})` : 'Scale'}: ${
				tickLabels[0].text}${stops.length > 1 ? ` to ${tickLabels[tickLabels.length - 1].text}` : ''}.`,
			labelY: baseline + tickBand + leading / 2,
			tickY: baseline + tickOffset
		}
	};
	return { drawing, placed, barHeight, zero: scale(0), radius };
}

export function drawBars(
	data: VisualData, room: number, formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig, options?: ComparisonOptions
): BarDrawing {
	const { drawing, placed, barHeight, zero } = drawComparison('bar', data, room, formatNumber, geometry, options);
	return {
		...drawing, type: 'bar',
		bars: placed.map(({ at, ...row }) => ({
			...row,
			x: Math.min(zero, at),
			y: row.center - barHeight / 2,
			width: Math.abs(at - zero),
			height: barHeight
		}))
	};
}

export function drawDots(
	data: VisualData, room: number, formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig, options?: ComparisonOptions
): DotDrawing {
	const { drawing, placed, radius } = drawComparison('dot', data, room, formatNumber, geometry, options);
	return {
		...drawing, type: 'dot',
		dots: placed.map(({ at, ...row }) => ({ ...row, x: at, y: row.center, radius }))
	};
}

export function statedComparisonRow(row: ComparisonRow, unit: string | null): string {
	return `${row.name} ${row.stated}${unit ? ` ${unit}` : ''}` +
		(row.sourceText ? ` (source: ${row.sourceText})` : '');
}

function statedComparison(drawing: BarDrawing | DotDrawing): string {
	const rows = drawing.type === 'bar' ? drawing.bars : drawing.dots;
	const kind = drawing.type === 'bar' ? 'Bar' : 'Dot';
	return [
		drawing.title, `${kind} chart.`, drawing.axis.description,
		`${rows.map((row) => statedComparisonRow(row, drawing.unit)).join('; ')}.`, drawing.caption
	].filter(Boolean).join(' ');
}

export const statedBars = statedComparison;
export const statedDots = statedComparison;
