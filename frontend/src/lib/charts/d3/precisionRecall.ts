/** Place observed cutoff readings on a common zero-to-one precision and recall frame. */
import { linearAxis, type Frame } from '../frame';

interface Coordinates {
	readonly precision: number | null;
	readonly recall: number | null;
}

export type CutoffShape = 'lower' | 'upper' | 'reporting' | 'target';

export function precisionRecall(
	points: readonly Coordinates[], cutoffs: readonly (Coordinates & { shape: CutoffShape })[], box: Frame, density: number
) {
	const x = linearAxis([0, 1], [box.left, box.right], { nice: false, tickCount: density });
	const y = linearAxis([0, 1], [box.bottom, box.top], { nice: false, tickCount: density });
	const place = ({ precision, recall }: Coordinates, index: number) => precision === null || recall === null
		? [] : [{ x: x.scale(recall), y: y.scale(precision), index }];
	const dots = points.flatMap(place);
	if (!dots.length || !box.innerWidth || !box.innerHeight) return null;
	const markers = cutoffs.flatMap((cutoff, index) => place(cutoff, index).map((mark) => ({ ...mark, shape: cutoff.shape })));
	return { box, x, y, dots, markers };
}
