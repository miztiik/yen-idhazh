/** The shape of a chart that has no numbers yet.
 *
 * A panel that draws nothing while it waits collapses, and everything below it
 * moves when the payload lands. A panel that draws a plain grey rectangle keeps
 * the room but says nothing about what will be in it. So an empty chart here
 * draws the two things that are already true before any row arrives: **where
 * the axes are and where the ticks fall.** Both come out of the same `frame()`
 * and the same `MARGIN` the real charts use, so the frame a reader watches is
 * the frame they get.
 *
 * **No numbers.** A tick label needs a value and there is no value, so a number
 * printed here would be invented. The mark is drawn and the label is not.
 *
 * The axis frame is an SVG and the marks that shimmer are elements over it,
 * because a CSS gradient animation cannot be put on an SVG `rect`. Both are
 * placed from the same margins as a share of the box, so they scale together
 * and cannot drift apart at any width.
 */
import { frame, MARGIN, type Frame } from './frame';

/** How many ticks a waiting plot draws on each axis.
 *
 * Six each way is enough to read as a frame and few enough that the marks stay
 * apart in the narrowest column the console has - 328 CSS px on a 360px screen.
 */
export const SKELETON_TICKS = 6;

/** How many marks stand where the data will be. */
export const SKELETON_BARS = 12;

/** The heights the marks cycle through, as a share of the plot.
 *
 * Fixed rather than random: a skeleton that redrew differently on each render
 * would ripple, and a ripple is motion the reader did not ask for and cannot
 * read. Four steps say "something varies here" and claim no value.
 */
const STEPS = [0.55, 0.8, 0.4, 0.68];

/** The plot's edges as a share of the whole box, ready for a CSS `inset`. */
export interface PlotInset {
	top: string;
	right: string;
	bottom: string;
	left: string;
}

export interface SkeletonFrame {
	box: Frame;
	/** Tick positions along the bottom axis, in the SVG's own pixels. */
	xTicks: number[];
	/** Tick positions up the left axis, in the SVG's own pixels. */
	yTicks: number[];
	/** Where the plot sits inside the box, as percentages. */
	inset: PlotInset;
	/** One height per mark, as a share of the plot. */
	bars: number[];
}

/** Evenly spaced positions across a span, ends included. */
function spread(from: number, to: number, count: number): number[] {
	if (count < 2) return [from];
	const step = (to - from) / (count - 1);
	return Array.from({ length: count }, (_, index) => from + step * index);
}

function share(value: number, of: number): string {
	return `${((value / Math.max(1, of)) * 100).toFixed(4)}%`;
}

export function skeletonFrame(
	width: number,
	height: number,
	bars: number = SKELETON_BARS,
	ticks: number = SKELETON_TICKS
): SkeletonFrame {
	const box = frame(width, height, MARGIN);
	const count = Math.max(1, bars);
	return {
		box,
		xTicks: spread(box.left, box.right, ticks),
		yTicks: spread(box.top, box.bottom, ticks),
		inset: {
			top: share(box.top, height),
			right: share(width - box.right, width),
			bottom: share(height - box.bottom, height),
			left: share(box.left, width)
		},
		bars: Array.from({ length: count }, (_, index) => STEPS[index % STEPS.length] as number)
	};
}
