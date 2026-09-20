/** Where one reading falls inside the span its window measured.
 *
 * One figure, one track: the band is what the window read, the upright is what
 * the newest run read, and the reader compares them by looking. The same figure
 * written as a sentence - "95.47% this run, 94.10% to 96.88% over these days" -
 * can be read but not compared, and a panel of such sentences is a pile rather
 * than a system.
 *
 * The domain is the data drawn, widened by a ceiling where the figure has one.
 * A ceiling joins the readings rather than capping them, so a run that breaks
 * its ceiling draws past the band instead of sitting on the end of it.
 */
import { percentOf } from './rank';

/** A window's low-to-high reading of one figure, and how many runs answered.
 *
 * The loader derives this once per preset, so a track never re-derives a figure
 * the page was already handed.
 */
export interface FigureSpan {
	low: number | null;
	high: number | null;
	from: number;
	outOf: number;
}

/** No run in the window recorded the figure, so there is no band to draw.
 *
 * Distinct from a run that recorded nothing: this run may hold a reading the
 * window cannot place, and the two absences read differently.
 */
export interface SpanUnread {
	spanned: false;
	/** The newest run's own reading. Null where the run recorded none. */
	value: number | null;
	low: null;
	high: null;
	from: number;
	outOf: number;
}

/** The window holds both ends, so the band is a length the reader can see. */
export interface SpanRead {
	spanned: true;
	/** The newest run's own reading. Null where the run recorded none. */
	value: number | null;
	low: number;
	high: number;
	from: number;
	outOf: number;
	/** What the whole track stands for, printed beside it. */
	scale: number;
	/** The band's near end, as a CSS length. */
	start: string;
	/** The band's length, as a CSS length. */
	length: string;
	/** Where the newest run's upright stands, as a CSS length. */
	at: string;
	/** False where the band would draw under one pixel. A span every run agreed
	 * on is a printed figure and a mark, never a line too thin to see. */
	drawn: boolean;
}

export type SpanTrack = SpanUnread | SpanRead;

/** One figure as a value inside its span.
 *
 * `ceiling` is the number the figure is read against where it has one - a share
 * runs to 100 whatever the readings did. Where it has none the track ends at the
 * largest thing drawn on it. `width` is the drawing width in pixels, which is
 * what decides whether a band is a length or a mark.
 */
export function spanTrack(
	value: number | null,
	span: FigureSpan,
	limits: { ceiling?: number | null; width: number }
): SpanTrack {
	if (span.low === null || span.high === null) {
		return { spanned: false, value, low: null, high: null, from: span.from, outOf: span.outOf };
	}
	const ends = [span.low, span.high, value, limits.ceiling ?? null].filter(
		(end): end is number => end !== null && Number.isFinite(end)
	);
	const scale = Math.max(...ends);
	const along = (end: number | null) => (scale <= 0 || end === null ? 0 : end / scale);
	const length = Math.max(0, along(span.high) - along(span.low));
	return {
		spanned: true,
		value,
		low: span.low,
		high: span.high,
		from: span.from,
		outOf: span.outOf,
		scale,
		start: percentOf(along(span.low)),
		length: percentOf(length),
		at: percentOf(along(value)),
		drawn: length * limits.width >= 1
	};
}
