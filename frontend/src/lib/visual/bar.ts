/** Where story-chart geometry comes from, and it is the only place it does.
 *
 * **The reader's browser draws the chart and the pipeline never draws one**
 * (maintainer ruling, 2026-09-13,
 * `docs/architecture/publishing/visuals.md`). This module is the half of that
 * which decides where every mark sits. `ItemVisual.svelte` is the half that
 * writes them into the document.
 *
 * The split is not decoration. Geometry with no DOM in it can be checked by
 * calling it twice and comparing, which is this row's oracle - and a function
 * that also wrote to a document could only be checked by rendering one.
 *
 * **d3 computes and Svelte emits, and that is the whole engine** (Carmack,
 * 2026-09-13). `scaleBand` is real arithmetic - step, bandwidth, padding,
 * rounding - and it is imported. `scaleLinear` is not, because a bar anchored
 * at zero is a multiply, and because calling it drags `d3-format` and
 * `d3-interpolate` onto a reading page that named neither. `d3-selection` and
 * `d3-axis` are not installed at all: nothing here joins, enters or exits, and
 * `d3-axis` writes a 10px axis font, which is below `--text-xs` at every root
 * size the site uses - it would be imported in order to be undone.
 *
 * It reads a `VisualData` document that `refusedVisualData` has already passed,
 * so every lookup below resolves and every channel pairs. A caller that skipped
 * that check would get an exception rather than a wrong picture, which is the
 * right way round.
 */

import { scaleBand, scaleLinear } from 'd3-scale';
import type { VisualData, VisualMark } from '$lib/payload/types';
import type { NumberFormatter } from '$lib/number-format';
import type { StoryChartGeometryConfig } from '$lib/server/config';

/** One bar, placed. Every number here is a CSS pixel on the reader's screen. */
export interface Bar {
	emphasized: boolean;
	sourceText: string | null;
	/** The element's own characters, cut and sanitized by the compiler. */
	name: string;
	/** The figure as the article states it, which is what a reader reads. */
	stated: string;
	/** The same quantity in the configured display notation. */
	displayed: string;
	/** Where the name sits, on the line above the bar and with the width to itself. */
	label: number;
	y: number;
	height: number;
	/** Bar length. Zero-length where the figure is zero, and never negative. */
	width: number;
	/** Where the stated figure sits, just past the end of its own bar. */
	figure: number;
}

/** A whole chart, placed. */
interface DrawingBase {
	title: string | null;
	caption: string | null;
	/** The room the caller measured, which every mark below is placed inside. */
	width: number;
	height: number;
}

export interface BarDrawing extends DrawingBase {
	type: 'bar';
	baseline: number;
	unit: string | null;
	bars: Bar[];
}

export interface Dot {
	emphasized: boolean;
	name: string;
	stated: string;
	displayed: string;
	x: number;
	valueX: number;
	y: number;
	radius: number;
	labelY: number;
}

export interface DotDrawing extends DrawingBase {
	type: 'dot';
	baseline: number;
	axisEnd: number;
	unit: string | null;
	dots: Dot[];
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

export type Drawing = BarDrawing | DotDrawing | SlopeDrawing;

function figureOf(mark: VisualMark): number {
	// The compiler pins `value` to the characters the article wrote, so this is
	// a decimal string and never a formatted one. A figure that will not parse
	// is a compiler defect, and `Number` gives NaN rather than a wrong bar.
	return Number(mark.value);
}

/**
 * Place every bar of one published visual.
 *
 * **Category `i` names quantity `i`**, which is the plan's own order carried
 * through the compiler. Re-ranking here would be the drawing code deciding what
 * the comparison says.
 *
 * **The measured axis is anchored at zero and scaled to the longest bar.** A
 * bar chart whose axis starts anywhere else exaggerates every difference on it,
 * which is the one way a chart drawn from true figures can still lie. A
 * negative figure draws no bar rather than a bar pointing the wrong way: the
 * compiler can publish one, and nothing has ruled on what it should
 * look like, so nothing is drawn until something does.
 *
 * **`room` is the width the caller measured, in CSS pixels, and every number
 * this returns is placed inside it.** There is no canvas: the name sits on its
 * own line with the whole width to itself, and the bar runs under it with all
 * of that width but the sixteenth kept for the figure beside it - so the
 * comparison the chart exists to make gets every pixel left once the number it
 * compares has somewhere to stand. A name column beside the bars is what a
 * fixed canvas could afford and a phone cannot
 * - the compiler allows 40 of the article's own characters, about 250 CSS
 * pixels at `--text-xs`, and a 360 px phone has roughly 300 pixels of card to
 * spend. Side by side, a column that fits the names leaves nothing to draw a
 * bar in, and the old drawing hid that by scaling the type down until the names
 * fitted. What a reader gives up is the tidy left-hand column a desktop had
 * room for, and one text line of height per bar.
 *
 * Throws where the data does not fit - see the module note: `refusedVisualData`
 * is the check, and this is the code that trusts it.
 */
export function drawBars(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig
): BarDrawing {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const mark = (id: string): VisualMark => {
		const found = held.get(id);
		// Unreachable through the page, which runs `refusedVisualData` first. It
		// throws rather than drawing a gap, because a bar with no mark behind it
		// is a length nobody can explain.
		if (found === undefined) throw new Error(`visual data draws a mark it does not carry: ${id}`);
		return found;
	};
	const names = data.encoding.category.map(mark);
	const figures = data.encoding.quantity.map(mark);

	const band = scaleBand<string>()
		.domain(names.map((_, index) => String(index)))
		.range([0, names.length * geometry.row_height_px])
		.paddingInner(geometry.row_padding_share)
		.paddingOuter(geometry.row_padding_share / 2)
		.round(true);

	const values = figures.map(figureOf);
	const longest = Math.max(...values.map((value) => (Number.isFinite(value) ? value : 0)), 0);
	const width = Math.max(0, Math.floor(room));
	// What a bar may run to, so the figure beside the longest one has somewhere
	// to sit inside the width rather than past its right edge.
	const span = Math.max(0, width - Math.round(width * geometry.value_gutter_share));

	const bars: Bar[] = names.map((named, index) => {
		const value = values[index];
		const share = longest > 0 && Number.isFinite(value) && value > 0 ? value / longest : 0;
		const top = band(String(index)) ?? 0;
		const height = Math.round(band.bandwidth() * geometry.bar_height_share);
		const drawn = Math.round(share * span);
		return {
			emphasized: figures[index].mark_id === data.emphasized_mark_id,
			sourceText: figures[index].source_text,
			name: named.text ?? '',
			stated: figures[index].value ?? '',
			displayed: formatNumber(value, { si: true }),
			// The name has the line above the bar to itself, centred in the room the
			// bar leaves, so a long name never meets the figure beside the bar.
			label: top + (band.bandwidth() - height) / 2,
			y: top + band.bandwidth() - height,
			height,
			width: drawn,
			figure: drawn + geometry.value_gap_px
		};
	});

	return {
		title: data.title,
		caption: data.caption,
		width,
		type: 'bar',
		height: names.length * geometry.row_height_px + geometry.axis_band_px,
		baseline: names.length * geometry.row_height_px,
		unit: figures[0]?.unit ?? null,
		bars
	};
}

/** Place dots on one shared value scale, with labels kept outside the plot. */
export function drawDots(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig
): DotDrawing {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const mark = (id: string): VisualMark => {
		const found = held.get(id);
		if (found === undefined) throw new Error(`visual data draws a mark it does not carry: ${id}`);
		return found;
	};
	const names = data.encoding.category.map(mark);
	const series = data.encoding.series.map(mark);
	const figures = data.encoding.quantity.map(mark);
	const values = figures.map(figureOf);
	const finite = values.filter(Number.isFinite);
	const minimum = Math.min(...finite);
	const maximum = Math.max(...finite);
	const width = Math.max(0, Math.floor(room));
	const plotStart = geometry.dot_radius_px;
	const valueX = Math.max(plotStart, width - Math.round(width * geometry.value_gutter_share));
	const plotEnd = Math.max(plotStart, valueX - geometry.value_gap_px);
	const scale = scaleLinear()
		.domain(minimum === maximum ? [minimum - 1, maximum + 1] : [minimum, maximum])
		.range([plotStart, plotEnd]);
	const band = scaleBand<string>()
		.domain(names.map((_, index) => String(index)))
		.range([0, names.length * geometry.row_height_px])
		.paddingInner(geometry.row_padding_share)
		.paddingOuter(geometry.row_padding_share / 2)
		.round(true);
	const dots = names.map((name, index): Dot => {
		const top = band(String(index)) ?? 0;
		const figure = figures[index];
		const seriesLabel = series[index]?.text;
		return {
			emphasized: figure.mark_id === data.emphasized_mark_id,
			name: `${name.text ?? ''}${seriesLabel ? ` (${seriesLabel})` : ''}`,
			stated: figure.value ?? '',
			displayed: formatNumber(values[index], { si: true }),
			x: Number.isFinite(values[index]) ? scale(values[index]) : plotStart,
			valueX,
			y: top + band.bandwidth() / 2,
			radius: geometry.dot_radius_px,
			labelY: top + band.bandwidth() * geometry.dot_category_label_share
		};
	});
	return {
		type: 'dot',
		title: data.title,
		caption: data.caption,
		width,
		height: names.length * geometry.row_height_px + geometry.axis_band_px,
		baseline: names.length * geometry.row_height_px,
		axisEnd: plotEnd,
		unit: figures[0]?.unit ?? null,
		dots
	};
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
	const height = Math.max(
		geometry.slope_min_height_px,
		geometry.slope_header_band_px + count * geometry.row_height_px + geometry.slope_footer_band_px
	);
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

export function drawVisual(
	data: VisualData,
	room: number,
	formatNumber: NumberFormatter,
	geometry: StoryChartGeometryConfig
): Drawing {
	switch (data.type) {
		case 'bar':
			return drawBars(data, room, formatNumber, geometry);
		case 'dot':
			return drawDots(data, room, formatNumber, geometry);
		case 'slope':
			return drawSlopes(data, room, formatNumber, geometry);
		default:
			throw new Error(`visual type is not drawn: ${data.type}`);
	}
}

/**
 * What the drawing says, as one sentence, read off the marks it just placed.
 *
 * **The sentence and the picture come out of one `Drawing`, so they cannot
 * disagree.** Every string the drawing paints is in here and nothing else is:
 * each bar's name, each bar's stated figure, and the unit the axis counts. That
 * is the property `ItemVisual.svelte` hands to a keyboard, and
 * `frontend/tests/item-visual.spec.ts` compares the two sets on a real page
 * rather than taking this sentence's word for it.
 *
 * **The compiler writes a sentence too, and this replaces it on the page.**
 * `alt_text` on the day payload is a second derivation of the same figures, and
 * measured on the canary day 2026-09-14 it had already drifted from them two
 * ways. It re-groups the article's own `1200` as `1,200`, so the reader who
 * hears the chart and the reader who sees it are given different characters.
 * And it is cut to 300 characters, which an eight-bar chart - the ceiling
 * `visuals.max_chart_points` allows - goes past on names of 25 characters, so
 * the last bar is drawn and never spoken. A fact a reader can see and cannot
 * hear is the whole defect here, and one source is the only fix that stays
 * fixed. The compiler still writes `alt_text` and `backend/tests/test_render.py`
 * still holds it to the element table; what changed is that the reading page no
 * longer carries it.
 */
export function statedBars(drawing: BarDrawing): string {
	const tail = drawing.unit ? ` ${drawing.unit}` : '';
	const facts = drawing.bars.map((bar) =>
		`${bar.name} ${bar.stated}${tail}${bar.emphasized ? ' (highlighted)' : ''}` +
		(bar.sourceText ? ` (source: ${bar.sourceText})` : '')
	);
	return [drawing.title, `Bar chart. ${facts.join('; ')}.`, drawing.caption]
		.filter(Boolean).join(' ');
}

export function statedDots(drawing: DotDrawing): string {
	const tail = drawing.unit ? ` ${drawing.unit}` : '';
	const facts = drawing.dots.map((dot) =>
		`${dot.name} ${dot.stated}${tail}${dot.emphasized ? ' (highlighted)' : ''}`
	);
	return [drawing.title, `Dot chart. ${facts.join('; ')}.`, drawing.caption]
		.filter(Boolean).join(' ');
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

export function statedDrawing(drawing: Drawing): string {
	switch (drawing.type) {
		case 'bar':
			return statedBars(drawing);
		case 'dot':
			return statedDots(drawing);
		case 'slope':
			return statedSlopes(drawing);
	}
}
