import type { VisualData } from '$lib/payload/types';
import {
	MAX_SIGNIFICANT_DIGITS,
	numberFormatter,
	type NumberFormatConfig,
	type NumberFormatter
} from '$lib/number-format';
import type { StoryChartGeometryConfig } from '$lib/server/config';
import type { DrawingBase } from './bar';
import { displayUnitSymbol } from './unit-symbol';

export interface HistogramBin {
	emphasized: boolean;
	range: string;
	rangeY: number;
	displayed: string;
	x: number;
	y: number;
	height: number;
	width: number;
	figure: number;
}

export interface HistogramDrawing extends DrawingBase {
	type: 'histogram';
	unit: string | null;
	valueHeading: string;
	bins: HistogramBin[];
}

/** Place recorded equal-width bins in increasing order, with a count for each. */
export function drawHistogram(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	numberFormat: NumberFormatConfig,
	geometry: StoryChartGeometryConfig
): HistogramDrawing {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const bins = data.encoding.bins.map((id, index) => {
		const mark = held.get(id);
		if (
			mark === undefined || mark.derived === null || mark.derived === undefined ||
			typeof mark.derived !== 'object' || !('bin_lower' in mark.derived) ||
			!('bin_upper' in mark.derived)
		) {
			throw new Error(`histogram bin ${id} has no recorded edges`);
		}
		const lower = Number(mark.derived.bin_lower);
		const upper = Number(mark.derived.bin_upper);
		const value = Number(mark.value);
		if (!Number.isFinite(lower) || !Number.isFinite(upper) || !Number.isFinite(value)) {
			throw new Error(`histogram bin ${id} has non-finite geometry`);
		}
		return { mark, value, lower, upper, last: index === data.encoding.bins.length - 1 };
	});
	const distinctEdges = [...new Set(bins.flatMap(({ lower, upper }) => [lower, upper]))];
	let edgeFormatter = formatNumber;
	for (
		let digits = numberFormat.significant_digits;
		digits <= MAX_SIGNIFICANT_DIGITS;
		digits += 1
	) {
		const candidate = digits === numberFormat.significant_digits
			? formatNumber
			: numberFormatter({ ...numberFormat, significant_digits: digits });
		const labels = distinctEdges.map((edge) => candidate(edge, { si: true }));
		if (new Set(labels).size === distinctEdges.length) {
			edgeFormatter = candidate;
			break;
		}
		if (digits === MAX_SIGNIFICANT_DIGITS) {
			throw new RangeError('Histogram range edges cannot be distinguished.');
		}
	}
	const rangeUnit = data.histogram_unit
		? ` ${displayUnitSymbol(data.histogram_unit)}`
		: '';
	const rangedBins = bins.map(({ mark, value, lower, upper, last }) => ({
		mark,
		value,
		range: `${edgeFormatter(lower, { si: true })} ${
			last ? 'through' : 'to less than'
		} ${edgeFormatter(upper, { si: true })}${rangeUnit}`
	}));
	const width = Math.max(0, Math.floor(room));
	const countWidth = Math.round(width * geometry.value_gutter_share);
	const plotWidth = Math.max(
		0,
		width - countWidth - geometry.value_gap_px
	);
	const plotX = 0;
	const maximum = Math.max(...bins.map((bin) => bin.value));
	const headingHeight = geometry.axis_band_px;
	const rowHeight = geometry.row_height_px;
	const binHeight = headingHeight + rowHeight;
	const barHeight = Math.round(rowHeight * geometry.bar_height_share);
	const unit = data.histogram_unit
		? displayUnitSymbol(data.histogram_unit)
		: null;
	return {
		title: data.title,
		caption: data.caption,
		width,
		type: 'histogram',
		height: headingHeight + bins.length * binHeight,
		unit,
		valueHeading: 'Number of values',
		bins: rangedBins.map(({ mark, value, range }, index) => {
			const barWidth = maximum > 0 ? Math.round((value / maximum) * plotWidth) : 0;
			const binY = headingHeight + index * binHeight;
			const y = binY + headingHeight + (rowHeight - barHeight) / 2;
			return {
				emphasized: mark.mark_id === data.emphasized_mark_id,
				range,
				rangeY: binY + geometry.axis_label_offset_px,
				displayed: formatNumber(value, { exact: true }),
				x: plotX,
				y,
				height: barHeight,
				width: barWidth,
				figure: plotX + barWidth + geometry.value_gap_px
			};
		})
	};
}

/** Read every recorded range and count in the same order as the drawing. */
export function statedHistogram(drawing: HistogramDrawing): string {
	const facts = drawing.bins.map((bin) =>
		`${bin.range}: ${bin.displayed} values${bin.emphasized ? ' (highlighted)' : ''}`
	);
	return [
		drawing.title,
		`Histogram. ${drawing.valueHeading}. ${facts.join('; ')}.`,
		drawing.caption
	].filter(Boolean).join(' ');
}
