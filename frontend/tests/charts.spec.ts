/** The private drawing counts conserve their losses through the actual native layout. */
import { expect, test } from '@playwright/test';
import { frame } from '../src/lib/charts/frame';
import { flow, type FlowGeometry } from '../src/lib/charts/d3/flow';
import { chartFlow, type FlowDay } from '../src/lib/console/pipelines/drawing-flow';

const DAYS = [
	{ reached: 1000, asked: 700, drafted: 100, published: 80 },
	{ reached: 500, asked: 300, drafted: 50, published: 40 }
];
const TOTAL = { reached: 1500, asked: 1000, drafted: 150, published: 120 };
const OPTIONS = { narrow: false, frame: frame(900, 300), nodeWidth: 12, nodeGap: 34 };

function nativeFlow(days: readonly FlowDay[], narrow = false) {
	const drawing = chartFlow(days);
	return flow(drawing.steps.map((step, index) => ({
		label: step.label,
		arrived: step.value,
		left: drawing.steps[index + 1]?.value ?? step.value,
		drops: step.lost === null ? [] : [{ label: step.lost.label, count: step.lost.value }]
	})), { ...OPTIONS, narrow });
}

function diagram(days: readonly FlowDay[]): FlowGeometry {
	const geometry = nativeFlow(days);
	expect(geometry?.kind).toBe('diagram');
	if (geometry?.kind !== 'diagram') throw new Error('Expected the measured flow to draw a diagram.');
	return geometry;
}

test('what leaves a stage is what arrived at it', () => {
	const { nodes, ribbons } = diagram(DAYS);
	const out = (name: string) => ribbons.filter((link) => link.from === name).reduce((sum, link) => sum + link.value, 0);
	const value = (name: string) => nodes.find((node) => node.label === name)?.value;
	const stages = [
		['Reached', TOTAL.reached, TOTAL.asked],
		['Asked the model', TOTAL.asked, TOTAL.drafted],
		['Drafted', TOTAL.drafted, TOTAL.published]
	] as const;
	for (const [name, arrived, onward] of stages) {
		expect(value(name), `${name} draws its own count`).toBe(arrived);
		expect(out(name), `${name} sends on everything it took in`).toBe(arrived);
		expect(ribbons.find((link) => link.from === name && !link.drop)?.value).toBe(onward);
		expect(ribbons.find((link) => link.from === name && link.drop)?.value).toBe(arrived - onward);
	}
	expect(value('Published')).toBe(TOTAL.published);
	expect(out('Published')).toBe(0);
	for (const loss of ['Answered without a visual', 'The model drew nothing', 'Did not survive the checks']) {
		expect(out(loss)).toBe(0);
		expect(ribbons.filter((link) => link.to === loss).reduce((sum, link) => sum + link.value, 0)).toBe(value(loss));
	}
});

test('a loss sits beside the stage it left on the same count scale', () => {
	const { nodes } = diagram(DAYS);
	const node = (name: string) => {
		const found = nodes.find((entry) => entry.label === name);
		if (found === undefined) throw new Error(`The diagram lost "${name}".`);
		return found;
	};
	for (const [loss, next] of [
		['Answered without a visual', 'Asked the model'],
		['The model drew nothing', 'Drafted'],
		['Did not survive the checks', 'Published']
	]) {
		expect(node(loss).column).toBe(node(next).column);
	}
	const perItem = node('Reached').height / TOTAL.reached;
	for (const entry of nodes) expect(entry.height).toBeCloseTo(entry.value * perItem, 10);
});

test('the narrow list carries the same counts and independently expected shares', () => {
	const geometry = nativeFlow(DAYS, true);
	expect(geometry?.kind).toBe('stepped');
	if (geometry?.kind !== 'stepped') throw new Error('Expected a stepped flow at a narrow width.');
	expect(geometry.stages.map((step) => [step.arrived, step.left, step.share])).toEqual([
		[1500, 1000, 100], [1000, 150, 67], [150, 120, 10], [120, 120, 8]
	]);
	expect(geometry.stages.map((step) => step.drops.map((drop) => [drop.count, drop.share]))).toEqual([
		[[500, 33]], [[850, 57]], [[30, 2]], []
	]);
});

test('nothing reached says so and draws no zeros', () => {
	const days = [{ reached: 0, asked: 0, drafted: 0, published: 0 }];
	expect(chartFlow(days)).toMatchObject({ empty: true, steps: [] });
	expect(chartFlow(days).reason).toContain('Nothing committed says what the visual planner did');
	expect(nativeFlow(days)).toBeNull();
});

test('a gained stage is refused in words rather than drawing a negative branch', () => {
	const days = [{ reached: 100, asked: 60, drafted: 5, published: 9 }];
	const drawing = chartFlow(days);
	expect(drawing.empty).toBe(true);
	expect(drawing.steps).toEqual([]);
	expect(drawing.reason).toContain('published');
	expect(drawing.reason).toContain('drafted');
	expect(nativeFlow(days)).toBeNull();
});

test('a drop of zero has no branch or loss label', () => {
	const { nodes, ribbons } = diagram([{ reached: 10, asked: 10, drafted: 4, published: 4 }]);
	expect(nodes.map((node) => node.label)).not.toContain('Answered without a visual');
	expect(nodes.map((node) => node.label)).not.toContain('Did not survive the checks');
	expect(ribbons.every((link) => link.value > 0)).toBe(true);
	expect(ribbons.filter((link) => link.drop).map((link) => link.value)).toEqual([6]);
});
