/** Do these two move together: one dot a reading, one quantity along each axis, and no line through them.
 *
 * **No trend line, ever.** A fitted line is a verdict nobody agreed to: it
 * says the two move together by some rule and by how much, and the reader
 * learns the line rather than the dots. The geometry has nowhere to put one.
 *
 * **Two floors, and missing either draws nothing.** Two points define a line,
 * so a scatter of two is a claim, and a scatter of many readings from one or
 * two subjects is those subjects, not a relation. Under `minRows` readings or
 * `minSubjects` distinct labels the geometry is null and
 * `pairedScatterShortfall` names the floor it missed. Both floors are the
 * caller's, from config.
 *
 * Neither axis is anchored at zero: these are two measurements set against
 * each other, not bars, and a zero nobody is near squeezes every dot into a
 * corner.
 */
import type { Frame } from '../frame';
import { tooFewSentence } from '../../console/waiting';
import { valueAxis, type ValueAxis } from './axis';

export interface ScatterInput {
	/** The subject the reading is of - a machine kind, a source. */
	label: string;
	x: number;
	y: number;
}

export interface ScatterOptions {
	frame: Frame;
	/** The fewest readings drawn - `console.fleet_min_rows`. */
	minRows: number;
	/** The fewest distinct subjects drawn - `console.bandwidth_min_kinds`. */
	minSubjects: number;
	/** How many ticks each axis aims for. */
	valueTicks: number;
}

export interface ScatterMark extends ScatterInput {
	/** The dot's centre, in the chart's own pixels. */
	cx: number;
	cy: number;
}

export interface ScatterGeometry {
	frame: Frame;
	x: ValueAxis;
	y: ValueAxis;
	marks: ScatterMark[];
	/** Every distinct subject, sorted, for the key. */
	subjects: string[];
}

function readingsOf(points: readonly ScatterInput[]): ScatterInput[] {
	return points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
}

/** Why there is no scatter, in words, or null where there is one or there is
 * nothing at all. */
export function pairedScatterShortfall(
	points: readonly ScatterInput[],
	opts: Pick<ScatterOptions, 'minRows' | 'minSubjects'>
): string | null {
	const readings = readingsOf(points);
	if (readings.length === 0) return null;
	if (readings.length < opts.minRows) return tooFewSentence(readings.length, opts.minRows, 'readings');
	const subjects = new Set(readings.map((point) => point.label)).size;
	if (subjects < opts.minSubjects) return tooFewSentence(subjects, opts.minSubjects, 'subjects');
	return null;
}

/** The dots, or null where either floor is missed. */
export function pairedScatter(points: readonly ScatterInput[], opts: ScatterOptions): ScatterGeometry | null {
	const readings = readingsOf(points);
	const subjects = [...new Set(readings.map((point) => point.label))].sort();
	if (readings.length === 0 || readings.length < opts.minRows || subjects.length < opts.minSubjects) {
		return null;
	}
	const box = opts.frame;
	const x = valueAxis(
		readings.map((point) => point.x),
		box,
		{ along: 'x', ticks: opts.valueTicks, zero: false }
	);
	const y = valueAxis(
		readings.map((point) => point.y),
		box,
		{ along: 'y', ticks: opts.valueTicks, zero: false }
	);
	return {
		frame: box,
		x,
		y,
		marks: readings.map((point) => ({ ...point, cx: x.scale(point.x), cy: y.scale(point.y) })),
		subjects
	};
}
