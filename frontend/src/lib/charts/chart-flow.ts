/** Where items go between the visual planner looking at one and a visual being
 * published.
 *
 * This was a funnel until 2026-08-30. A funnel draws a monotonic sequence as a
 * taper, so it says how much is left at each step and nothing about where the
 * rest went - and the three drops here have three different causes. An item can
 * be answered without the model being asked at all, the model can be asked and
 * draw nothing, and a drafted chart can fail the checks that run after it.
 * Those are three different things to go and fix, and a taper shows them as one
 * slope.
 *
 * So every loss leaves the flow as its own branch carrying its own count, and
 * the widths add up: what leaves a stage is what arrived at it. That is the one
 * property this picture has to have, and `charts.spec.ts` asserts it rather
 * than trusting it.
 *
 * Totals across the open window, not one day: a single day's four numbers are
 * already legible in the table under it, and the question "where do items go"
 * is a question about the window.
 */

import type { EChartsOption } from 'echarts';
import type { ChartToken } from './theme';
import { paint } from './theme';

export interface FlowDay {
	reached: number;
	asked: number;
	drafted: number;
	published: number;
}

/** The four stages, left to right, in the order the pipeline runs them. */
const STAGES = [
	{ key: 'reached', label: 'Reached', token: '--chart-1' },
	{ key: 'asked', label: 'Asked the model', token: '--chart-2' },
	{ key: 'drafted', label: 'Drafted', token: '--chart-3' },
	{ key: 'published', label: 'Published', token: '--chart-4' }
] as const satisfies readonly { key: keyof FlowDay; label: string; token: ChartToken }[];

/** What each drop actually was. Three causes, three sentences - the whole
 * reason this stopped being a funnel. */
const LOSSES = ['Answered without a visual', 'The model drew nothing', 'Did not survive the checks'];

/** Fixed here so the server that draws the SVG and the page that hydrates it
 * cannot disagree about it. */
export const FLOW_HEIGHT = 260;

/** A loss branch takes the hue of the stage it left, at a lower opacity. A
 * second hue would say a loss is a different kind of thing; it is the same
 * items, going a different way. Both are low enough that a label crossing a
 * branch still reads, which is unavoidable: a label to the right of a node sits
 * over the links leaving it. */
const LOSS_OPACITY = 0.28;
const FLOW_OPACITY = 0.55;

/** Room to the right of the last column for a label to sit beside its node.
 *
 * Pixels, not a percentage. A label does not shrink with the frame, so a share
 * of the width leaves too little on a narrow screen and too much on a wide one.
 * Measured 2026-08-30 in the browser at 12px: the widest name is `Did not
 * survive the checks` at 151px, and the label starts 5px past the node. */
const LABEL_MARGIN = 170;

/** Two nodes in one column are this far apart, which is what stops their two
 * labels overlapping. Measured 2026-08-30: `Published` and `Did not survive the
 * checks` are 13.8px and 2.2px tall over the committed ledger, so at the
 * engine's default 14px gap their labels shared 9 pixels of one line. A
 * two-line label is 31px, and the gap has to carry it. */
const NODE_GAP = 34;

/** One stage of the flow, and the branch that left it, as words and numbers.
 *
 * The same four stages the diagram draws, in the same order, from the same
 * totals - so the stepped list a narrow column gets and the diagram a wide one
 * gets cannot report two different flows. `chartFlow` returns both, because two
 * functions over one ledger is how two pictures of it drift.
 */
export interface FlowStep {
	label: string;
	value: number;
	/** Whole percent of everything that reached the arm. */
	share: number;
	token: ChartToken;
	/** What left the flow at this stage, or null at the last one. Null is also
	 * what a stage that lost nothing gets: a branch of zero is not a branch. */
	lost: { label: string; value: number; share: number } | null;
}

export interface ChartFlow {
	option: EChartsOption;
	empty: boolean;
	/** Why there is no diagram, in words the page prints. Null when there is
	 * one. An empty panel says nothing; this says which nothing it is. */
	reason: string | null;
	/** The same flow as a stepped list, for a column too narrow to hold the
	 * diagram. Empty wherever `empty` is true. */
	steps: FlowStep[];
}

function grouped(value: number): string {
	return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

export function chartFlow(days: readonly FlowDay[]): ChartFlow {
	const total = STAGES.map((stage) => ({
		...stage,
		value: days.reduce((sum, day) => sum + day[stage.key], 0)
	}));
	const reached = total[0].value;
	// Nothing reached means nothing committed says what the visual planner did. A
	// flow of four zeros draws nothing and reads as a chart that failed to load.
	if (reached === 0) {
		return {
			option: {},
			empty: true,
			steps: [],
			reason:
				'Nothing committed says what the visual planner did over this window, so there is ' +
				'no flow to draw.'
		};
	}

	// A stage counting more than the one before it is not a flow, and drawing it
	// as one needs a branch of negative width. It happens: a visual published
	// inside the window can have been drafted before the window opened. Say that
	// and leave the table to hold the numbers, rather than draw a picture the
	// counts do not support.
	const gained = total.findIndex((stage, i) => i > 0 && stage.value > total[i - 1].value);
	if (gained > 0) {
		return {
			option: {},
			empty: true,
			steps: [],
			reason:
				`This window counts more items at ${total[gained].label.toLowerCase()} than at ` +
				`${total[gained - 1].label.toLowerCase()}, so the counts are not one flow. A visual ` +
				'published inside the window can have been drafted before it opened. The table ' +
				'below holds the numbers.'
		};
	}

	const share = (value: number) => Math.round((value / reached) * 100);
	// The stepped list a narrow column gets, built from the same totals the
	// diagram is. Measured 2026-09-01 in Chromium on the built console, the
	// diagram needs 700px of viewport before its labels stop overlapping: at
	// 390 three pairs collided, worst 56.2px, and at 360 the widest was 59.1px.
	// The label column is a fixed 170px, so at 360 it is 52 percent of a 328px
	// SVG and the four stages share what is left.
	const steps: FlowStep[] = total.map((stage, i) => {
		const dropped = i === total.length - 1 ? 0 : stage.value - total[i + 1].value;
		return {
			label: stage.label,
			value: stage.value,
			share: share(stage.value),
			token: stage.token,
			// A branch of zero is not a branch, here for the same reason it draws
			// none in the diagram: a loss too small to see and no loss at all are
			// two different facts.
			lost:
				dropped > 0
					? { label: LOSSES[i], value: dropped, share: share(dropped) }
					: null
		};
	});
	// Two lines: the name, then the count. On one line the four columns cannot
	// hold them - measured 2026-08-30, `Answered without a chart  696  (33%)` ran
	// 280px into a 246px column pitch and printed over the next stage's label.
	const label = (name: string, value: number) =>
		`${name}\n${grouped(value)}  (${share(value)}%)`;
	// Every node carries its column, rather than letting the layout infer one. A
	// loss branch is a dead end, and an inferred layout justifies dead ends to
	// the far edge - which would draw the first stage's loss beside the last
	// stage's.
	const nodes = [
		...total.map((stage, depth) => ({
			name: stage.label,
			value: stage.value,
			depth,
			itemStyle: { color: paint(stage.token), opacity: FLOW_OPACITY, borderWidth: 0 }
		})),
		...LOSSES.map((name, i) => ({
			name,
			value: total[i].value - total[i + 1].value,
			depth: i + 1,
			itemStyle: { color: paint(total[i].token), opacity: LOSS_OPACITY, borderWidth: 0 }
		})).filter((node) => node.value > 0)
	];
	const drawn = new Set(nodes.map((node) => node.name));
	const links = [
		...total.slice(1).map((stage, i) => ({
			source: total[i].label,
			target: stage.label,
			value: stage.value,
			lineStyle: { color: paint(total[i].token), opacity: FLOW_OPACITY }
		})),
		...LOSSES.map((name, i) => ({
			source: total[i].label,
			target: name,
			value: total[i].value - total[i + 1].value,
			lineStyle: { color: paint(total[i].token), opacity: LOSS_OPACITY }
		}))
	].filter((link) => link.value > 0 && drawn.has(link.target));

	return {
		option: {
			animation: false,
			tooltip: {
				trigger: 'item',
				formatter: (params: unknown) => {
					const item = params as {
						dataType?: string;
						name: string;
						value: number;
						data?: { source?: string; target?: string };
					};
					const of = `${grouped(item.value)} items, ${share(item.value)}% of everything reached`;
					if (item.dataType === 'edge') {
						return `${item.data?.source} to ${item.data?.target}<br/>${of}`;
					}
					return `${item.name}<br/>${of}`;
				}
			},
			series: [
				{
					type: 'sankey',
					// Left to right, the direction the page reads and the order the
					// pipeline runs its stages in.
					orient: 'horizontal',
					nodeAlign: 'left',
					left: 8,
					// Room for a label beside the last column instead of inside it. The
					// narrowest node here is under three pixels tall on the committed
					// ledger, so a label inside it would be unreadable - the defect the
					// funnel already had to fix once.
					right: LABEL_MARGIN,
					top: 12,
					bottom: 12,
					nodeWidth: 12,
					nodeGap: NODE_GAP,
					draggable: false,
					emphasis: { focus: 'adjacency' },
					label: {
						position: 'right',
						color: paint('--color-text'),
						fontSize: 12,
						lineHeight: 15,
						formatter: (params: unknown) => {
							const item = params as { name: string; value: number };
							return label(item.name, item.value);
						}
					},
					lineStyle: { curveness: 0.5 },
					data: nodes,
					links
				}
			]
		},
		empty: false,
		reason: null,
		steps
	};
}
