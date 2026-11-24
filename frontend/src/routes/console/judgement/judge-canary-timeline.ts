/** Place the canary match line and returned-answer blocks on the same UTC date bands. */
import { line } from 'd3-shape';
import { bandScale, linearScale } from '../../../lib/charts/d3/scale';
import { dayTicks, type Frame } from '../../../lib/charts/frame';
import { CANARY_BANDS, CANARY_CATEGORIES, type CanaryDay } from '../../../lib/console/judge-canaries';

type Point = [x: number, y: number];

export function judgeCanaryTimeline(days: readonly CanaryDay[], box: Frame, density: number) {
	const dates = days.map(({ date }) => date);
	const bands = bandScale(dates, box, 'x', 0.25);
	const half = bands.bandwidth() / 2;
	const centers = dates.map((date) => bands(date)! + half);
	const blockHeight = (box.innerHeight - box.labels.leading) / 2;
	const blockTop = box.bottom - blockHeight;
	const stripBottom = blockTop - box.labels.leading;
	const y = linearScale([0, 1], { ...box, bottom: stripBottom }, 'y');
	const blockWidth = Math.min(blockHeight, bands.bandwidth());
	const ticks = dayTicks(dates, { density, columns: centers, bounds: [box.left, box.right], labels: box.labels });
	const changes = days.flatMap(({ date, setChanged }, index) => !setChanged || index === 0 ? [] : [
		{ date, x: (centers[index - 1] + centers[index]) / 2 }
	]);
	const drawLine = line<Point>();
	const timelines = CANARY_CATEGORIES.map(({ expected, label }) => {
		let run: Point[] = [];
		let version: string | null = null;
		const runs: Point[][] = [];
		const columns = days.map(({ date, record }, index) => {
			const x = centers[index];
			const group = record?.groups[expected];
			if (group === undefined || group.expected === 0) {
				version = null;
				return { date, x, point: null, segments: [] };
			}
			const incomplete = group.counts.invalid > 0 || group.counts.missing > 0;
			const point = { y: y(group.matched / group.expected), incomplete };
			const current = record?.setVersion ?? null;
			if (incomplete || current === null) {
				version = null;
			} else {
				if (current !== version) {
					run = [];
					runs.push(run);
				}
				run.push([x, point.y]);
				version = current;
			}
			let count = 0;
			const segments = CANARY_BANDS.flatMap((band) => {
				const value = group.counts[band];
				if (value === 0) return [];
				const top = blockTop + blockHeight * count / group.expected;
				count += value;
				return [{ band, top, height: blockTop + blockHeight * count / group.expected - top }];
			});
			return { date, x, point, segments };
		});
		const path = runs.filter((points) => points.length > 1).map(drawLine).join(' ');
		return { expected, label, columns, path };
	});
	return { centers, ticks, changes, timelines, stripBottom, blockTop, blockWidth };
}
