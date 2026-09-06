import { expect, test } from '@playwright/test';
import { chartFlow, type FlowDay } from '../src/lib/charts/chart-flow';

/**
 * The chart-arm flow, at a width that can hold it and one that cannot.
 *
 * A Sankey label does not scale with the SVG: the font is fixed while the chart
 * redraws at container width, and the label column is a fixed 170 pixels. So a
 * diagram that is comfortable at 1440 is unreadable at 390, and no font size
 * fixes it - measured 2026-09-01 in Chromium on the built console, three pairs
 * of labels collided at 390 and the worst overlapped by 56.2 pixels.
 *
 * Below `48rem` the same numbers are a stepped list. Both shapes come from one
 * `chartFlow` call, and the oracle below is what stops them ever reporting two
 * different flows.
 */

const DESKTOP = { width: 1440, height: 1000 };
const PHONE = { width: 390, height: 844 };
const NARROW = { width: 360, height: 780 };

/** The breakpoint the page stacks at, in CSS pixels. */
const BREAKPOINT = 768;

/** A flow whose four stages fall and whose three losses are all non-zero. */
const DAYS: FlowDay[] = [
	{ reached: 1000, asked: 700, drafted: 100, published: 80 },
	{ reached: 500, asked: 300, drafted: 50, published: 40 }
];

test('the stepped list is the same flow the diagram draws', () => {
	// One call, two shapes. Two functions over one ledger is how two pictures of
	// it drift, and the drift is invisible because each looks right alone.
	const { steps } = chartFlow(DAYS);
	expect(steps.map((step) => step.label)).toEqual([
		'Reached',
		'Asked the model',
		'Drafted',
		'Published'
	]);
	expect(steps.map((step) => step.value)).toEqual([1500, 1000, 150, 120]);
	// Shares are of everything that reached the arm, which is what the diagram's
	// own labels print.
	expect(steps.map((step) => step.share)).toEqual([100, 67, 10, 8]);
	expect(steps.map((step) => step.lost?.label ?? null)).toEqual([
		'Answered without a visual',
		'The model drew nothing',
		'Did not survive the checks',
		null
	]);

	// What leaves a stage is what arrived at it. The list has to conserve for
	// the same reason the diagram does: a branch that does not is a shape, not
	// the data.
	for (const [index, step] of steps.entries()) {
		const next = steps[index + 1];
		if (next === undefined) {
			expect(step.lost, 'the last stage is where items stop').toBeNull();
			continue;
		}
		expect(next.value + (step.lost?.value ?? 0), `${step.label} does not conserve`).toBe(step.value);
	}
});

test('a branch of zero is no branch in the list either', () => {
	// A loss too small to see and no loss at all are two different facts, and a
	// row reading `0 (0%)` is the first one.
	const { steps } = chartFlow([{ reached: 10, asked: 10, drafted: 4, published: 4 }]);
	expect(steps.map((step) => step.lost?.label ?? null)).toEqual([
		null,
		'The model drew nothing',
		null,
		null
	]);
});

test('a window with no flow to draw has no list to draw either', () => {
	// Both empty states, so a narrow column gets the sentence rather than an
	// empty list where the diagram would have said why.
	const nothing = chartFlow([{ reached: 0, asked: 0, drafted: 0, published: 0 }]);
	expect(nothing.empty).toBe(true);
	expect(nothing.steps).toEqual([]);

	const gained = chartFlow([{ reached: 100, asked: 60, drafted: 5, published: 9 }]);
	expect(gained.empty).toBe(true);
	expect(gained.steps).toEqual([]);
});

/** Every label's box in the flow diagram, with the two lines of one label
 * folded into one box.
 *
 * echarts draws a two-line label as two `<text>` nodes sharing a left edge one
 * line height apart, and their line boxes touch by a pixel at every width. That
 * is line spacing. Comparing raw text nodes reports it as a collision on a
 * diagram that is perfectly readable, which is the wrong answer at every width.
 *
 * The gap that counts as line spacing is measured off the label rather than
 * fixed, because the diagram is not always drawn at the size it is shown at.
 * Before a reader comes to it the server's SVG is on screen, drawn 760 wide and
 * stretched to the column - 1,076px at a 1440px window, which is every distance
 * in it multiplied by 1.416. Measured 2026-09-06 on the canary build: the two
 * lines of one label sit 21px apart there and 15px apart once the engine has
 * redrawn at the column's own width, so a fixed 20px tolerance folded the live
 * chart and split the server's, and reported seven collisions on a diagram
 * nobody could fault. Two lines of one label are within one and a half line
 * boxes of each other at any scale; two different nodes are 100px apart at the
 * smaller of these two.
 */
async function flowLabels(page: import('@playwright/test').Page) {
	return page.evaluate(() => {
		const flow = document.querySelector('[data-flow="chart"]');
		if (flow === null) return null;
		const svg = flow.querySelector('svg');
		const raw = [...flow.querySelectorAll('svg text')].map((node) => {
			const rect = node.getBoundingClientRect();
			return {
				text: node.textContent?.trim() ?? '',
				left: rect.left,
				right: rect.right,
				top: rect.top,
				bottom: rect.bottom
			};
		});
		const labels: typeof raw = [];
		for (const box of raw) {
			const line = Math.max(box.bottom - box.top, 1) * 1.5;
			const owner = labels.find(
				(one) => Math.abs(one.left - box.left) <= 1.5 && Math.abs(one.top - box.top) <= line
			);
			if (owner === undefined) labels.push({ ...box });
			else {
				owner.text = `${owner.text} / ${box.text}`;
				owner.left = Math.min(owner.left, box.left);
				owner.right = Math.max(owner.right, box.right);
				owner.top = Math.min(owner.top, box.top);
				owner.bottom = Math.max(owner.bottom, box.bottom);
			}
		}
		const frame = svg === null ? null : svg.getBoundingClientRect();
		return {
			labels,
			frame: frame === null ? null : { left: frame.left, right: frame.right, width: frame.width }
		};
	});
}

test('THE ORACLE: at 390 the flow is a list, and it carries what the diagram drew', async ({
	page
}) => {
	// The numbers the diagram draws at a width that can hold it.
	await page.setViewportSize(DESKTOP);
	await page.goto('/console/');
	await page.waitForTimeout(1200);

	const wide = await flowLabels(page);
	expect(wide, 'the console drew no flow at all, so nothing here is tested').not.toBeNull();
	const drawn = (wide?.labels ?? []).map((label) => label.text);
	expect(drawn.length, 'the diagram drew no labels').toBeGreaterThan(0);

	// The diagram is readable at this width: every label inside the frame, and
	// no two of them touching.
	for (const label of wide?.labels ?? []) {
		expect(
			label.left >= (wide?.frame?.left ?? 0) - 0.5 &&
				label.right <= (wide?.frame?.right ?? 0) + 0.5,
			`${label.text} is drawn outside the diagram`
		).toBe(true);
	}
	const collisions: string[] = [];
	const labels = wide?.labels ?? [];
	for (let i = 0; i < labels.length; i += 1) {
		for (let j = i + 1; j < labels.length; j += 1) {
			const x = Math.min(labels[i].right, labels[j].right) - Math.max(labels[i].left, labels[j].left);
			const y = Math.min(labels[i].bottom, labels[j].bottom) - Math.max(labels[i].top, labels[j].top);
			if (x > 0 && y > 0) collisions.push(`${labels[i].text} over ${labels[j].text} by ${x.toFixed(1)}px`);
		}
	}
	expect(collisions, 'two labels overlap at 1440').toEqual([]);

	// Every value the diagram printed, as a number, so the two shapes can be
	// compared rather than eyeballed.
	const fromDiagram = drawn
		.flatMap((text) => text.match(/[\d,]+\s+\(\d+%\)/g) ?? [])
		.map((one) => Number(one.split(/\s+/)[0].replace(/,/g, '')))
		.sort((a, b) => a - b);
	expect(fromDiagram.length, 'no diagram label carried a count').toBeGreaterThan(0);

	// Now the phone. The diagram is gone and the list is there.
	await page.setViewportSize(PHONE);
	await page.waitForTimeout(600);

	await expect(page.locator('[data-flow="chart"]')).toBeHidden();
	const list = page.locator('[data-flow-steps]');
	await expect(list).toBeVisible();
	await expect(list.locator('[data-flow-step]')).toHaveCount(4);

	const fromList = await page
		.locator('[data-flow-step-value], [data-flow-lost-value]')
		.evaluateAll((nodes) =>
			nodes.map((node) =>
				Number(
					node.getAttribute('data-flow-step-value') ?? node.getAttribute('data-flow-lost-value')
				)
			)
		);
	expect(
		[...fromList].sort((a, b) => a - b),
		'the list and the diagram report different flows'
	).toEqual(fromDiagram);

	// And the branch values still add back to the inflow, read off the page.
	const stages = await page
		.locator('[data-flow-step]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				value: Number(node.querySelector('[data-flow-step-value]')?.getAttribute('data-flow-step-value')),
				lost: Number(
					node.querySelector('[data-flow-lost-value]')?.getAttribute('data-flow-lost-value') ?? 0
				)
			}))
		);
	for (const [index, stage] of stages.entries()) {
		const next = stages[index + 1];
		if (next === undefined) continue;
		expect(next.value + stage.lost, `stage ${index} does not conserve on the page`).toBe(stage.value);
	}
});

for (const size of [PHONE, NARROW]) {
	test(`the list fits a ${size.width}px column and every value keeps its name`, async ({
		page
	}) => {
		await page.setViewportSize(size);
		await page.goto('/console/');
		await page.waitForTimeout(800);

		const list = page.locator('[data-flow-steps]');
		await expect(list).toBeVisible();

		// Nothing runs past the column it is in, and no two lines of the list sit
		// on top of each other. That is the whole of "it survives a phone".
		const bad = await page.evaluate(() => {
			const root = document.querySelector('[data-flow-steps]');
			if (root === null) return ['no list'];
			const frame = root.getBoundingClientRect();
			const problems: string[] = [];
			const rows = [...root.querySelectorAll('p')];
			for (const row of rows) {
				const rect = row.getBoundingClientRect();
				if (rect.right > frame.right + 0.5 || rect.left < frame.left - 0.5) {
					problems.push(`${row.textContent?.trim()} runs outside the list`);
				}
			}
			for (let i = 0; i < rows.length; i += 1) {
				for (let j = i + 1; j < rows.length; j += 1) {
					const a = rows[i].getBoundingClientRect();
					const b = rows[j].getBoundingClientRect();
					const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
					const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
					if (x > 0 && y > 0) {
						problems.push(`${rows[i].textContent?.trim()} over ${rows[j].textContent?.trim()}`);
					}
				}
			}
			return problems;
		});
		expect(bad).toEqual([]);

		// Every count is beside the name of what it counts. A number on its own
		// line is the defect the diagram had, in a different shape.
		const named = await list
			.locator('[data-flow-step], [data-flow-lost]')
			.evaluateAll((nodes) => nodes.map((node) => (node.textContent ?? '').trim()));
		expect(named.length).toBeGreaterThan(0);
		for (const text of named) {
			expect(text, `${text} carries no count`).toMatch(/[\d,]+\s+\(\d+%\)/);
		}
	});
}

test('the diagram comes back above the breakpoint', async ({ page }) => {
	// The pair is a swap, not a deletion. A width that can hold the diagram gets
	// it, and the list is not drawn beside it - two shapes of one flow on one
	// screen is two answers to one question.
	await page.setViewportSize({ width: BREAKPOINT + 2, height: 900 });
	await page.goto('/console/');
	await page.waitForTimeout(800);

	await expect(page.locator('[data-flow="chart"]')).toBeVisible();
	await expect(page.locator('[data-flow-steps]')).toBeHidden();
});
