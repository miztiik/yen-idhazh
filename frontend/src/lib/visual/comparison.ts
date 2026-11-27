/** Fit a story comparison's exact readings and place its marks on one shared scale. */
import { scaleLinear } from 'd3-scale';
import { DEFAULT_CHART_LABELS, labelGutter, labelWidth, thinLabels, tickAnchor, type ChartLabels, type TickAnchor } from '../charts/frame';
import { PALETTE, type ChartPaletteToken } from '../charts/theme';
import { numberFormatter, type NumberFormatConfig, type NumberFormatter } from '../number-format';
import type { VisualData } from '../payload/types';
import type { StoryChartGeometryConfig } from '../server/config';
import type { DrawingBase } from './bar';
import { COMPARISON_COLORS, type ComparisonColorToken } from './comparison-colors';

export interface ComparisonText {
	x: number;
	y: number;
	anchor: TickAnchor;
	lines: string[];
}

interface ComparisonFact {
	id: string;
	name: string;
	stated: string;
	sourceText: string | null;
	displayed: string;
	color: ChartPaletteToken | ComparisonColorToken;
}

interface ComparisonRow extends ComparisonFact {
	label: ComparisonText;
	reading: ComparisonText;
}

interface Rule {
	x1: number;
	y1: number;
	x2: number;
	y2: number;
}

interface ComparisonDrawing extends DrawingBase {
	orientation: 'horizontal' | 'vertical';
	leading: number;
	axis: {
		line: Rule;
		ticks: { value: number; line: Rule; guides: Rule[]; label: ComparisonText | null }[];
		note: ComparisonText;
		description: string;
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
	labels?: ChartLabels;
}

interface LayoutOptions {
	rows: { name: string; displayed: string; nameWidth: number; readingWidth: number }[];
	width: number;
	radius: number;
	ticks: string[];
	labels: ChartLabels;
	geometry: StoryChartGeometryConfig;
}

interface ComparisonLayout {
	orientation: ComparisonDrawing['orientation'];
	range: [number, number];
	axisAt: number;
	tickAt: number;
	noteTop: number;
	guides: [number, number][];
	rows: { center: number; thickness: number; label: ComparisonText; reading: ComparisonText }[];
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
			// Preserve the precision of the tick, not floating-point
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

function placeColumns({ rows, width, radius, ticks, labels, geometry }: LayoutOptions): ComparisonLayout | null {
	const gap = geometry.value_gap_px;
	const { leading } = labels;
	const tickWidth = Math.ceil(Math.max(...ticks.map((tick) => labelWidth(tick, labels))));
	const left = tickWidth + 2 * gap;
	const right = width - gap;
	const column = (right - left) / rows.length;
	if (rows.some((row) => row.nameWidth + row.readingWidth + 2 * gap > column) ||
		2 * radius + gap > column) return null;

	const top = gap + Math.max(radius, leading / 2);
	const tickPitch = Math.ceil(leading + gap + geometry.axis_line_width_px);
	const bottom = top + Math.max(geometry.row_height_px, (ticks.length - 1) * tickPitch);
	const labelY = bottom + radius + gap + leading / 2;
	const thickness = column * (1 - geometry.row_padding_share) * geometry.bar_height_share;
	return {
		orientation: 'vertical',
		range: [bottom, top],
		axisAt: left,
		tickAt: left - gap,
		noteTop: labelY + leading / 2 + gap,
		guides: [[left, right]],
		rows: rows.map((row, index) => {
			const center = left + column * (index + 0.5);
			const start = center - (row.nameWidth + gap + row.readingWidth) / 2;
			return {
				center, thickness,
				label: { x: start, y: labelY, anchor: 'start', lines: [row.name] },
				reading: { x: start + row.nameWidth + gap, y: labelY, anchor: 'start', lines: [row.displayed] }
			};
		})
	};
}

function placeRows({ rows, width, radius, labels, geometry }: LayoutOptions): ComparisonLayout {
	const gap = geometry.value_gap_px;
	const { leading } = labels;
	const available = width - 2 * gap;
	const gutter = labelGutter(rows.map((row) => row.name), labels, gap, available);
	const readingWidth = Math.ceil(Math.max(...rows.map((row) => row.readingWidth)));
	const beside = gutter !== null &&
		available - gutter - readingWidth - gap - 2 * radius >= geometry.row_height_px;
	const left = gap + (beside ? gutter : 0) + radius;
	const right = Math.max(left, width - gap - (beside ? readingWidth + gap : 0) - radius);
	const thickness = Math.round(geometry.row_height_px * (1 - geometry.row_padding_share) * geometry.bar_height_share);
	const band = Math.max(geometry.row_height_px, Math.max(leading, 2 * radius, thickness) + gap);
	const guides: ComparisonLayout['guides'] = [];
	let bottom = 0;
	const placed: ComparisonLayout['rows'] = rows.map((row) => {
		const top = bottom;
		const paired = !beside && row.nameWidth + gap + row.readingWidth <= available;
		const names = beside || paired ? [row.name] : wrapText(row.name, available, labels);
		const readings = beside || paired ? [row.displayed] : wrapText(row.displayed, available, labels);
		const plotTop = beside ? top : top + leading * (paired ? 1 : names.length + readings.length);
		bottom = plotTop + band;
		guides.push([plotTop, bottom]);
		const center = plotTop + band / 2;
		const labelY = beside ? center : top + leading / 2;
		return {
			center, thickness,
			label: { x: gap, y: labelY, anchor: 'start', lines: names },
			reading: {
				x: beside ? width - gap : paired ? gap + row.nameWidth + gap : gap,
				y: beside || paired ? labelY : labelY + names.length * leading,
				anchor: beside ? 'end' : 'start',
				lines: readings
			}
		};
	});
	const tickOffset = Math.max(geometry.axis_label_offset_px, leading / 2 + geometry.axis_line_width_px);
	return {
		orientation: 'horizontal',
		range: [left, right],
		axisAt: bottom,
		tickAt: bottom + tickOffset,
		noteTop: bottom + Math.max(geometry.axis_band_px, tickOffset + leading / 2),
		guides,
		rows: placed
	};
}

function drawComparison(
	type: 'bar' | 'dot',
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig,
	options?: ComparisonOptions
) {
	const labels = options?.labels ?? DEFAULT_CHART_LABELS;
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const rows = data.encoding.quantity.map((id, index) => {
		const quantity = held.get(id)!;
		const category = held.get(data.encoding.category[index])!.text!;
		const series = held.get(data.encoding.series[index])?.text ?? '';
		const name = series && series !== category ? `${category} (${series})` : category;
		const unit = quantity.unit?.trim() || null;
		const stated = quantity.value!;
		// The stored decimal is exact; only the position and tick notation use numbers.
		const displayed = unit ? `${stated} ${unit}` : stated;
		return {
			id, name, series, unit, stated, displayed,
			value: Number(stated),
			sourceText: quantity.source_text,
			nameWidth: labelWidth(name, labels),
			readingWidth: labelWidth(displayed, labels)
		};
	});
	const series = [...new Set(rows.map((row) => row.series))];
	if (type === 'bar') rows.sort((a, b) => b.value - a.value);

	const values = rows.map((row) => row.value);
	const unit = rows.every((row) => row.unit === rows[0].unit) ? rows[0].unit : null;
	const signed = type === 'bar' && unit !== null
		&& values.some((value) => value > 0) && values.some((value) => value < 0);
	function fillFor(group: string, value: number): ComparisonFact['color'] {
		if (series.length > 1) return PALETTE[series.indexOf(group)];
		if (signed && value > 0) return COMPARISON_COLORS.above_zero;
		if (signed && value < 0) return COMPARISON_COLORS.below_zero;
		return COMPARISON_COLORS.measure;
	}
	const width = Math.max(0, Math.floor(room));
	const ticks = options?.tickDensity ?? rows.length;
	const low = type === 'bar' ? Math.min(...values, 0) : Math.min(...values);
	const high = type === 'bar' ? Math.max(...values, 0) : Math.max(...values);
	const scale = scaleLinear()
		.domain(type === 'bar' && low === high ? [0, 1] : [low, high])
		.nice(ticks);
	const [minimum, maximum] = scale.domain();
	const stops = [...new Set([minimum, ...scale.ticks(ticks), maximum])];
	const scaled = comparisonFormat(stops, formatNumber, options?.numberFormat);
	const tickTexts = stops.map(scaled.format);
	const radius = type === 'dot' ? geometry.dot_radius_px : 0;
	const layoutOptions = { rows, width, radius, labels, geometry, ticks: tickTexts };
	const layout = placeColumns(layoutOptions) ?? placeRows(layoutOptions);
	const vertical = layout.orientation === 'vertical';
	const direction = vertical ? -1 : 1;
	const gap = geometry.value_gap_px;
	const { leading } = labels;
	scale.range(layout.range);
	const point = (along: number, across: number) => vertical ? { x: across, y: along } : { x: along, y: across };
	function rule(along: number, across: number, toAlong: number, toAcross: number): Rule {
		const start = point(along, across);
		const end = point(toAlong, toAcross);
		return { x1: start.x, y1: start.y, x2: end.x, y2: end.y };
	}
	const placed = rows.map(({ id, name, stated, sourceText, displayed, value, series: group }, index) => ({
		id, name, stated, sourceText, displayed,
		...layout.rows[index],
		color: fillFor(group, value),
		at: scale(value)
	}));
	const tickLabels = stops.map((value, index) => ({
		value, x: direction * scale(value), text: tickTexts[index],
		anchor: vertical ? 'middle' as const : tickAnchor(index, stops.length)
	}));
	const tickMetrics = vertical ? { ...labels, measure: () => leading, tracking: 0 } : labels;
	const shown = new Set(thinLabels(tickLabels, tickMetrics, gap).map(({ value }) => value));
	const unitText = [scaled.magnitude, unit].filter(Boolean).join(' ');
	const tight = type === 'dot' && (minimum > 0 || maximum < 0);
	const axisName = [unitText, tight ? 'zero not shown' : ''].filter(Boolean).join('; ');
	const axisLabel = axisName ? `Scale: ${axisName}` : '';
	const note = {
		x: gap, y: layout.noteTop + leading / 2, anchor: 'start' as const,
		lines: wrapText(axisLabel, width - 2 * gap, labels)
	};
	const drawing: ComparisonDrawing = {
		title: data.title,
		caption: data.caption,
		width,
		height: Math.ceil(layout.noteTop + leading * note.lines.length),
		orientation: layout.orientation,
		leading,
		axis: {
			line: rule(scale(minimum), layout.axisAt, scale(maximum), layout.axisAt),
			ticks: tickLabels.map(({ value, x, text, anchor }) => {
				const at = direction * x;
				return {
					value,
					line: rule(at, layout.axisAt, at, layout.axisAt + direction * geometry.axis_label_offset_px / 4),
					guides: layout.guides.map(([from, to]) => rule(at, from, at, to)),
					label: shown.has(value)
						? { ...point(at, layout.tickAt), anchor: vertical ? 'end' : anchor, lines: [text] }
						: null
				};
			}),
			note,
			description: `${axisName ? `Scale (${axisName})` : 'Scale'}: ${
				tickTexts[0]}${stops.length > 1 ? ` to ${tickTexts[tickTexts.length - 1]}` : ''}.`
		}
	};
	return { drawing, placed, point, zero: scale(0), radius };
}

export function drawBars(
	data: VisualData, room: number, formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig, options?: ComparisonOptions
): BarDrawing {
	const { drawing, placed, point, zero } = drawComparison('bar', data, room, formatNumber, geometry, options);
	const vertical = drawing.orientation === 'vertical';
	return {
		...drawing, type: 'bar',
		bars: placed.map(({ at, center, thickness, ...row }) => {
			const length = Math.abs(at - zero);
			return {
				...row, ...point(Math.min(zero, at), center - thickness / 2),
				width: vertical ? thickness : length,
				height: vertical ? length : thickness
			};
		})
	};
}

export function drawDots(
	data: VisualData, room: number, formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig, options?: ComparisonOptions
): DotDrawing {
	const { drawing, placed, point, radius } = drawComparison('dot', data, room, formatNumber, geometry, options);
	return {
		...drawing, type: 'dot',
		dots: placed.map(({ at, center, thickness, ...row }) => ({ ...row, ...point(at, center), radius }))
	};
}

export function statedComparisonRow(row: ComparisonFact): string {
	return `${row.name} ${row.displayed}` +
		(row.sourceText ? ` (source: ${row.sourceText})` : '');
}

function statedComparison(drawing: BarDrawing | DotDrawing): string {
	const rows = drawing.type === 'bar' ? drawing.bars : drawing.dots;
	const kind = drawing.type === 'bar' ? 'Bar' : 'Dot';
	return [
		drawing.title, `${kind} chart.`, drawing.axis.description,
		`${rows.map(statedComparisonRow).join('; ')}.`, drawing.caption
	].filter(Boolean).join(' ');
}

export const statedBars = statedComparison;
export const statedDots = statedComparison;
