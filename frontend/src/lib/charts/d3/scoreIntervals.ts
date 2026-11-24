/** Draw observed score intervals at their exact edges, with a count-scaled composition tick. */
import { dayColumns, dayTicks, linearAxis, type Frame } from '../frame';

export interface IntervalDay {
	readonly date: string;
	readonly used: readonly (number | null)[];
	readonly decided: readonly (number | null)[];
	readonly slices: readonly { low: number; high: number; parts: readonly number[] }[];
}

interface ScoreContext {
	readonly focus: number;
	readonly share: number;
}

function intervalAxis(box: Frame, floor: number, ceiling: number, density: number, context: ScoreContext | null) {
	const options = { zero: false, nice: false, tickCount: density };
	if (!context || context.focus <= floor || context.focus >= ceiling ||
		context.share >= (context.focus - floor) / (ceiling - floor)) {
		return { ...linearAxis([floor, ceiling], [box.bottom, box.top], options), focus: null };
	}
	const { focus, share } = context;
	const join = box.bottom - share * box.innerHeight;
	const low = linearAxis([floor, focus], [box.bottom, join], options);
	const high = linearAxis([focus, ceiling], [join, box.top], options);
	return {
		domain: [floor, ceiling],
		scale: (score: number) => score < focus ? low.scale(score) : high.scale(score),
		ticks: [...new Set([floor, ...(floor < 0 && focus > 0 ? [0] : []), focus, ...high.ticks.filter((tick) => tick > focus), ceiling])],
		focus
	};
}

export function scoreIntervals(
	days: readonly IntervalDay[], box: Frame, floor: number, ceiling: number, density: number,
	context: ScoreContext | null = null
) {
	if (!days.length || !box.innerWidth || !box.innerHeight ||
		!days.some((day) => day.slices.length || day.used.some((value) => value !== null))) return null;
	const pitch = box.innerWidth / days.length;
	const xs = dayColumns(days.length, box, pitch / 2);
	const axis = intervalAxis(box, floor, ceiling, density, context);
	const max = Math.max(1, ...days.map(({ slices }) =>
		slices.reduce((largest, { parts }) => Math.max(largest, parts.reduce((total, n) => total + n, 0)), 0)));
	const guide = (side: number) => days.flatMap(({ used, decided }, at) => {
		const value = used[side], next = days[at + 1]?.used[side], after = decided[side];
		if (value == null) return [];
		const y = axis.scale(value), x = xs[at] - pitch / 2, end = xs[at] + pitch / 2;
		return [{
			x, end, y, next: next == null ? null : axis.scale(next),
			decision: after == null || after === value ? null : axis.scale(after)
		}];
	});
	const columns = days.map(({ slices, date }, at) => ({
		date,
		x: xs[at],
		marks: slices.map(({ low, high, parts }) => {
			const total = parts.reduce((sum, n) => sum + n, 0);
			// Leave room for the interval on the neighbouring date, even at the largest draw.
			const unit = pitch * 0.8 / max;
			let left = xs[at] - total * unit / 2;
			const middle = (low + high) / 2;
			return {
				low, high, y0: axis.scale(low), y1: axis.scale(high), y: axis.scale(middle),
				segments: parts.map((n) => {
					const start = left;
					left += n * unit;
					return { start, end: left };
				})
			};
		})
	}));
	return {
		box, xs, pitch, columns, axis, guides: [guide(0), guide(1)],
		dates: dayTicks(days.map(({ date }) => date), { columns: xs, bounds: [box.left, box.right], density, labels: box.labels })
	};
}
