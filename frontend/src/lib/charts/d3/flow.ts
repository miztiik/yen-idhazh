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
 * d3-sankey lays the flow out, and two of the funnel's own rules are put back
 * on it. Every node sits in the column of its own depth (`sankeyLeft`): the
 * library's default sends each node with nothing leaving it to the last
 * column, which would put every drop at the far edge. And the library spreads
 * each column's spare height between the nodes in it, which moves the main
 * line off the shared top edge, so each column is stacked again from the top
 * before the library attaches the ribbons where the nodes now stand. The
 * ribbons are filled shapes on `curveBumpX`, the curve d3's own link generator
 * uses, so two ribbons meeting at a bend never overlap as stroked lines do.
 */
import { sankey, sankeyLeft, type SankeyLink, type SankeyNode } from 'd3-sankey';
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
	/** Include the shared count verdict on a stepped result, for a caller's headline. */
	includeCountsStatus?: boolean;
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
	/** Present only when requested: all stage totals and adjacent counts match. */
	countsConsistent?: boolean;
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

/** A stage or a drop, as the layout sees it. `layer` is the column the library
 * drew it in, which the library writes and its type definitions leave out. */
type Stop = { id: string; label: string; drop: boolean; layer?: number };

/** What carries on to the next stage, or what one stage lost. */
type Carry = { drop: boolean };

function diagram(stages: readonly FlowStageInput[], opts: FlowOptions): FlowGeometry | SteppedGeometry {
	const box = opts.frame;
	const last = stages.length - 1;
	const lostAt = (index: number) => stages[index].drops.filter((drop) => drop.count > 0);
	const columns = stages.length + (lostAt(last).length > 0 ? 1 : 0);
	const pitch = columns > 1 ? (box.innerWidth - opts.nodeWidth) / (columns - 1) : 0;
	if (columns > 1 && pitch <= opts.nodeWidth) {
		return stepped(stages, 'This panel is too narrow to hold a column for every stage, so the stages are listed.');
	}

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
	if (columns === 1) {
		// One stage that lost nothing is one bar: there is nothing to lay out.
		const only = stages[0];
		const bar: FlowNode = {
			label: only.label,
			value: only.arrived,
			column: 0,
			x: box.left,
			y: box.top,
			width: opts.nodeWidth,
			height: only.arrived * perItem,
			drop: false
		};
		return { kind: 'diagram', frame: box, columns, nodes: [bar], ribbons: [] };
	}

	// Stages first, so every column lists its own stage above the drops that land in it.
	const stops: SankeyNode<Stop, Carry>[] = stages.map((stage, index) => ({
		id: `stage-${index}`,
		label: stage.label,
		drop: false,
		fixedValue: stage.arrived
	}));
	const carries: SankeyLink<Stop, Carry>[] = [];
	stages.forEach((stage, index) => {
		// A carry of zero stays in the graph, so every later stage keeps the column of its own depth.
		if (index < last) carries.push({ source: `stage-${index}`, target: `stage-${index + 1}`, value: stage.left, drop: false });
		lostAt(index).forEach((drop, order) => {
			const id = `drop-${index}-${order}`;
			stops.push({ id, label: drop.label, drop: true });
			carries.push({ source: `stage-${index}`, target: id, value: drop.count, drop: true });
		});
	});

	const layout = sankey<Stop, Carry>()
		.nodeId((stop) => stop.id)
		.nodeAlign(sankeyLeft)
		.nodeSort(null)
		.linkSort(null)
		.iterations(0)
		.nodeWidth(opts.nodeWidth)
		.nodePadding(opts.nodeGap)
		.extent([
			[box.left, box.top],
			[box.left + box.innerWidth, box.top + box.innerHeight]
		]);
	const graph = layout({ nodes: stops, links: carries });
	const below = new Map<number, number>();
	for (const node of graph.nodes) {
		const column = node.layer ?? 0;
		const height = (node.y1 ?? 0) - (node.y0 ?? 0);
		node.y0 = below.get(column) ?? box.top;
		node.y1 = node.y0 + height;
		below.set(column, node.y1 + opts.nodeGap);
	}
	layout.update(graph);

	const nodes: FlowNode[] = graph.nodes.map((node) => ({
		label: node.label,
		value: node.value ?? 0,
		column: node.layer ?? 0,
		x: node.x0 ?? 0,
		y: node.y0 ?? 0,
		width: (node.x1 ?? 0) - (node.x0 ?? 0),
		height: (node.y1 ?? 0) - (node.y0 ?? 0),
		drop: node.drop
	}));
	const ribbons: FlowRibbon[] = graph.links
		.filter((link) => link.value > 0)
		.map((link) => {
			const from = link.source as SankeyNode<Stop, Carry>;
			const to = link.target as SankeyNode<Stop, Carry>;
			const half = (link.width ?? 0) / 2;
			const leaves = link.y0 ?? 0;
			const lands = link.y1 ?? 0;
			return {
				from: from.label,
				to: to.label,
				value: link.value,
				drop: link.drop,
				path:
					ribbon([
						{ x: from.x1 ?? 0, y0: leaves - half, y1: leaves + half },
						{ x: to.x0 ?? 0, y0: lands - half, y1: lands + half }
					]) ?? ''
			};
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
	const geometry = note !== null ? stepped(stages, note) : opts.narrow ? stepped(stages, null) : diagram(stages, opts);
	return opts.includeCountsStatus && geometry.kind === 'stepped'
		? { ...geometry, countsConsistent: note === null }
		: geometry;
}
