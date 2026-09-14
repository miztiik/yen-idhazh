/** Where a bar chart's geometry comes from, and it is the only place it does.
 *
 * **The reader's browser draws the chart and the pipeline never draws one**
 * (owner ruling, 2026-09-13,
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

import { scaleBand } from 'd3-scale';
import type { VisualData, VisualMark } from '$lib/payload/types';

/** The drawing's own coordinate space.
 *
 * The chart is laid out at this width and scaled to the reader's screen by the
 * `viewBox`, so the page reserves the right box from markup and nothing shifts
 * while a story is read. Row #2 takes the width the screen actually has; until
 * then this is one number in one place rather than a canvas the backend baked.
 */
export const VIEW_WIDTH = 720;

/** How much of the width the names take before a bar starts. */
const NAME_GUTTER = 168;
/** Room under the bars for the axis line and its ticks. */
const AXIS_BAND = 34;
/** Room to the right of the longest bar, so its figure has somewhere to sit. */
const FIGURE_GUTTER = 72;

/** How tall one band is, before padding. */
const BAND_HEIGHT = 34;
/** The share of a band that is space rather than bar. */
const BAND_PADDING = 0.28;

/** One bar, placed. Every number here is a coordinate in the view box above. */
export interface Bar {
	/** The element's own characters, cut and sanitized by the compiler. */
	name: string;
	/** The figure as the article states it, which is what a reader reads. */
	stated: string;
	y: number;
	height: number;
	/** Bar length. Zero-length where the figure is zero, and never negative. */
	width: number;
}

/** A whole chart, placed. */
export interface Drawing {
	width: number;
	height: number;
	/** Where the bars start, which is also where the axis line starts. */
	left: number;
	/** The baseline the bars sit on. */
	baseline: number;
	/** What the measured axis counts, or null where the article named no unit. */
	unit: string | null;
	bars: Bar[];
}

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
 * compiler can publish one, and plan 12 has no row that says what it should
 * look like, so nothing is drawn until one does.
 *
 * Throws where the data does not fit - see the module note: `refusedVisualData`
 * is the check, and this is the code that trusts it.
 */
export function drawBars(data: VisualData): Drawing {
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
		.range([0, names.length * BAND_HEIGHT])
		.paddingInner(BAND_PADDING)
		.paddingOuter(BAND_PADDING / 2)
		.round(true);

	const values = figures.map(figureOf);
	const longest = Math.max(...values.map((value) => (Number.isFinite(value) ? value : 0)), 0);
	const span = VIEW_WIDTH - NAME_GUTTER - FIGURE_GUTTER;

	const bars: Bar[] = names.map((named, index) => {
		const value = values[index];
		const share = longest > 0 && Number.isFinite(value) && value > 0 ? value / longest : 0;
		return {
			name: named.text ?? '',
			stated: figures[index].value ?? '',
			y: band(String(index)) ?? 0,
			height: band.bandwidth(),
			width: Math.round(share * span)
		};
	});

	return {
		width: VIEW_WIDTH,
		height: names.length * BAND_HEIGHT + AXIS_BAND,
		left: NAME_GUTTER,
		baseline: names.length * BAND_HEIGHT,
		unit: figures[0]?.unit ?? null,
		bars
	};
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
export function statedBars(drawing: Drawing): string {
	const tail = drawing.unit ? ` ${drawing.unit}` : '';
	const facts = drawing.bars.map((bar) => `${bar.name} ${bar.stated}${tail}`);
	return `Bar chart. ${facts.join('; ')}.`;
}
