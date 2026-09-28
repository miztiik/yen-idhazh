/** Where did they go, and where did they leave: a funnel of stages in which every loss is its own branch.
 *
 * What leaves a stage is what arrived at it, so the widths add up - the one
 * property this picture has to have. The stages share one top edge, so their
 * heights compare by eye along it, and each stage's drops fall below the flow
 * that carried on, into the very next column: a loss sits beside the stage
 * that lost it, never at the far edge of the page.
 *
 * **One call, two shapes.** Where the panel is narrower than
 * `frame.breakpoints_px[0]` it passes `narrow` and gets the stepped list - the
 * same stages and drops as words and numbers - from this same call, so a phone
 * and a desk cannot be shown two different flows. The panel measures; this
 * module never reads a width it was not given.
 *
 * **Counts that are not one flow are listed, never drawn.** A stage that lets
 * more through than the next one counts arriving - a visual published inside
 * the window can have been drafted before it opened - would need a branch of
 * negative width. The stepped list prints each stage's own numbers and says
 * why there is no diagram.
 *
 * The layout is written here rather than taken from d3-sankey: a straight
 * funnel has no crossings, merges or loops, which are the only cases a general
 * layout solves, and d3-sankey's layout spreads each column's spare height
 * between its nodes, which moves the main line off the shared top edge. The
 * ribbons are filled shapes on `curveBumpX`, the curve d3's own link generator
 * uses, so two ribbons meeting at a bend never overlap as stroked lines do.
 */
import { area, curveBumpX } from 'd3-shape';

import type { Frame } from '../frame';
import { grouped } from '../series';

export interface FlowDrop {
	label: string;
	count: number;
}

export interface FlowStageInput {
	label: string;
	arrived: number;
	/** What carried on to the next stage - or, at the last stage, what came
	 * out of the far end. */
	left: number;
	drops: readonly FlowDrop[];
}

export interface FlowOptions {
	/** True below `frame.breakpoints_px[0]`. The panel decides; the type obeys. */
	narrow: boolean;
	frame: Frame;
	/** How wide a stage's bar is, in CSS pixels. */
	nodeWidth: number;
	/** Clear pixels between two things in one column. */
	nodeGap: number;
}

export interface FlowNode {
	label: string;
	value: number;
	/** 0-based, left to right. A drop sits in the column after its stage. */
	column: number;
	x: number;
	y: number;
	width: number;
	height: number;
	drop: boolean;
}

export interface FlowRibbon {
	from: string;
	to: string;
	value: number;
	drop: boolean;
	/** A filled shape, as an SVG path. */
	path: string;
}

export interface FlowGeometry {
	kind: 'diagram';
	frame: Frame;
	columns: number;
	nodes: FlowNode[];
	ribbons: FlowRibbon[];
}

export interface SteppedDrop extends FlowDrop {
	/** Whole percent of everything that arrived at the first stage. */
	share: number;
}

export interface SteppedStage {
	label: string;
	arrived: number;
	left: number;
	share: number;
	/** Only the drops that took something: a branch of zero is not a branch. */
	drops: SteppedDrop[];
}

export interface SteppedGeometry {
	kind: 'stepped';
	stages: SteppedStage[];
	/** Why this is a list where a diagram was asked for, or null where the
	 * list is what the panel asked for. */
	note: string | null;
}

function checked(stages: readonly FlowStageInput[]): void {
	const counts = (stage: FlowStageInput) => [stage.arrived, stage.left, ...stage.drops.map((drop) => drop.count)];
	for (const stage of stages) {
		if (counts(stage).some((count) => !Number.isFinite(count) || count < 0)) {
			throw new RangeError(`"${stage.label}" carries a count that is not a count of anything.`);
		}
	}
}

/** Where the counts stop being one flow, in words, or null where they are one. */
function imbalance(stages: readonly FlowStageInput[]): string | null {
	const listed = 'so the counts are not one flow and the stages are listed rather than drawn.';
	for (const [index, stage] of stages.entries()) {
		const out = stage.left + stage.drops.reduce((sum, drop) => sum + drop.count, 0);
		if (out !== stage.arrived) {
			return `${stage.label} counts ${grouped(stage.arrived)} arriving and ${grouped(out)} leaving, ${listed}`;
		}
		const next = stages[index + 1];
		if (next !== undefined && next.arrived !== stage.left) {
			return `${stage.label} lets ${grouped(stage.left)} through and ${next.label} counts ${grouped(next.arrived)} arriving, ${listed}`;
		}
	}
	return null;
}

function stepped(stages: readonly FlowStageInput[], note: string | null): SteppedGeometry {
	const first = stages[0].arrived;
	const share = (value: number) => Math.round((value / first) * 100);
	return {
		kind: 'stepped',
		note,
		stages: stages.map((stage) => ({
			label: stage.label,
			arrived: stage.arrived,
			left: stage.left,
			share: share(stage.arrived),
			drops: stage.drops
				.filter((drop) => drop.count > 0)
				.map((drop) => ({ label: drop.label, count: drop.count, share: share(drop.count) }))
		}))
	};
}

interface Edge {
	x: number;
	y0: number;
	y1: number;
}

const ribbon = area<Edge>()
	.x((edge) => edge.x)
	.y0((edge) => edge.y0)
	.y1((edge) => edge.y1)
	.curve(curveBumpX);

function diagram(stages: readonly FlowStageInput[], opts: FlowOptions): FlowGeometry | SteppedGeometry {
	const box = opts.frame;
	const last = stages.length - 1;
	const lostAt = (index: number) => stages[index].drops.filter((drop) => drop.count > 0);
	const columns = stages.length + (lostAt(last).length > 0 ? 1 : 0);
	const pitch = columns > 1 ? (box.innerWidth - opts.nodeWidth) / (columns - 1) : 0;
	if (columns > 1 && pitch <= opts.nodeWidth) {
		return stepped(stages, 'This panel is too narrow to hold a column for every stage, so the stages are listed.');
	}
	const columnX = (column: number) => box.left + column * pitch;

	// A column holds its own stage and the drops of the stage before it, and
	// in a balanced flow those add up to what arrived at that earlier stage.
	let perItem = Number.POSITIVE_INFINITY;
	for (let column = 0; column < columns; column += 1) {
		const things = (column <= last ? 1 : 0) + (column > 0 ? lostAt(column - 1).length : 0);
		const total = column === 0 ? stages[0].arrived : stages[column - 1].arrived;
		if (total > 0) perItem = Math.min(perItem, (box.innerHeight - (things - 1) * opts.nodeGap) / total);
	}
	if (!(perItem > 0) || !Number.isFinite(perItem)) {
		return stepped(stages, 'This panel is too short to draw every branch with room between them, so the stages are listed.');
	}

	const nodes: FlowNode[] = stages.map((stage, index) => ({
		label: stage.label,
		value: stage.arrived,
		column: index,
		x: columnX(index),
		y: box.top,
		width: opts.nodeWidth,
		height: stage.arrived * perItem,
		drop: false
	}));
	const ribbons: FlowRibbon[] = [];
	stages.forEach((stage, index) => {
		const from = columnX(index) + opts.nodeWidth;
		const to = columnX(index + 1);
		const carried = box.top + stage.left * perItem;
		if (index < last && stage.left > 0) {
			ribbons.push({
				from: stage.label,
				to: stages[index + 1].label,
				value: stage.left,
				drop: false,
				path:
					ribbon([
						{ x: from, y0: box.top, y1: carried },
						{ x: to, y0: box.top, y1: carried }
					]) ?? ''
			});
		}
		// Each drop leaves from under the flow that carried on, and lands in the
		// next column under the stage there, one gap below it.
		let source = carried;
		let target = index < last ? box.top + stages[index + 1].arrived * perItem + opts.nodeGap : box.top;
		for (const drop of lostAt(index)) {
			const height = drop.count * perItem;
			nodes.push({
				label: drop.label,
				value: drop.count,
				column: index + 1,
				x: to,
				y: target,
				width: opts.nodeWidth,
				height,
				drop: true
			});
			ribbons.push({
				from: stage.label,
				to: drop.label,
				value: drop.count,
				drop: true,
				path:
					ribbon([
						{ x: from, y0: source, y1: source + height },
						{ x: to, y0: target, y1: target + height }
					]) ?? ''
			});
			source += height;
			target += height + opts.nodeGap;
		}
	});
	return { kind: 'diagram', frame: box, columns, nodes, ribbons };
}

/** The flow, or null where nothing arrived at its first stage. */
export function flow(
	stages: readonly FlowStageInput[],
	opts: FlowOptions
): FlowGeometry | SteppedGeometry | null {
	checked(stages);
	if (stages.length === 0 || stages[0].arrived <= 0) return null;
	const note = imbalance(stages);
	if (note !== null) return stepped(stages, note);
	return opts.narrow ? stepped(stages, null) : diagram(stages, opts);
}
