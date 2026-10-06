import { expect, test, type Page } from './support/browser';
import { chooseExplorerQuestion, openExplorer, runExplorer } from './support/explorer-answer';

/**
 * Where the Data explorer's regions stand: the workbench fills the window, Run
 * stands in one group with Save and Copy link, and the two copy buttons stand
 * on the answer's own heading line. Every expected value is a literal edge, a
 * literal order or a literal the test typed; nothing the canary holds decides
 * one.
 */

type Box = { left: number; top: number; right: number; bottom: number };

/** The window's own edges and the boxes of the named regions, in one frame. */
async function measure(page: Page, regions: readonly string[]) {
	return page.evaluate((names) => {
		const read = (node: Element | null): Box => {
			if (node === null) throw new Error('a region the layout needs is missing');
			const rect = node.getBoundingClientRect();
			return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom };
		};
		const root = document.documentElement;
		return {
			width: root.clientWidth,
			height: root.clientHeight,
			scrollWidth: root.scrollWidth,
			scrollHeight: root.scrollHeight,
			workbench: read(document.querySelector('.workbench')),
			regions: Object.fromEntries(names.map((name) => [name, read(document.querySelector(`[data-workbench-region="${name}"]`))]))
		};
	}, regions);
}

for (const view of [
	{ width: 1024, height: 768 },
	{ width: 1440, height: 900 },
	{ width: 1920, height: 1080 }
] as const) {
	test(`the workbench reaches the window's right and bottom edges at ${view.width} x ${view.height}`, async ({ page }) => {
		await page.setViewportSize(view);
		await openExplorer(page);
		const at = await measure(page, []);
		expect(at.width, 'the window is not the width this test asked for').toBe(view.width);
		expect(at.height, 'the window is not the height this test asked for').toBe(view.height);
		expect(at.workbench.left).toBeCloseTo(0, 0);
		expect(at.workbench.right).toBeCloseTo(view.width, 0);
		expect(at.workbench.bottom).toBeCloseTo(view.height, 0);
		expect(at.scrollWidth, 'the page scrolls sideways').toBe(view.width);
	});
}

for (const view of [
	{ width: 1440, height: 900 },
	{ width: 1920, height: 1080 }
] as const) {
	test(`the regions tile a window that holds them, and the page does not scroll, at ${view.width} x ${view.height}`, async ({ page }) => {
		await page.setViewportSize(view);
		await openExplorer(page);
		const at = await measure(page, ['ledgers', 'columns', 'answer', 'chart']);
		expect(at.scrollHeight, 'the page scrolls under a workbench that fits the window').toBe(view.height);

		// A rail at each side, and the answer and the chart side by side along the window's foot.
		const { ledgers, columns, answer, chart } = at.regions;
		expect(ledgers.left).toBeCloseTo(0, 0);
		expect(columns.right).toBeCloseTo(view.width, 0);
		expect(answer.left).toBeCloseTo(0, 0);
		expect(answer.right).toBeCloseTo(chart.left, 0);
		expect(chart.right).toBeCloseTo(view.width, 0);
		expect(answer.top).toBeCloseTo(chart.top, 0);
		expect(answer.bottom).toBeCloseTo(view.height, 0);
		expect(chart.bottom).toBeCloseTo(view.height, 0);
	});
}

test('a long answer and a long question scroll inside their own regions, and the page does not grow', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page);
	await chooseExplorerQuestion(page, ['published'], 'SELECT i AS row_number FROM range(0, 1200) AS t(i)');
	await runExplorer(page);
	await expect(page.locator('[data-explorer-answer] tbody tr').first()).toBeVisible();
	await page.locator('#explorer-sql').fill(Array.from({ length: 40 }, (_, index) => `SELECT ${index}`).join('\n'));
	const at = await page.evaluate(() => {
		const table = document.querySelector('[data-chart="answer-table"]') as HTMLElement;
		const editor = document.querySelector('[data-workbench-region="editor"] .frame') as HTMLElement;
		const root = document.documentElement;
		return {
			pageScrolls: root.scrollHeight > root.clientHeight,
			tableScrolls: table.scrollHeight > table.clientHeight,
			editorScrolls: editor.scrollHeight > editor.clientHeight,
			bottom: (document.querySelector('.workbench') as HTMLElement).getBoundingClientRect().bottom
		};
	});
	expect(at.pageScrolls).toBe(false);
	expect(at.tableScrolls, 'the answer grew its region instead of scrolling inside it').toBe(true);
	expect(at.editorScrolls, 'the question grew its region instead of scrolling inside it').toBe(true);
	expect(at.bottom).toBeCloseTo(900, 0);
});

for (const view of [
	{ width: 390, height: 844 },
	{ width: 768, height: 1024 }
] as const) {
	test(`below the wide breakpoint the workbench runs edge to edge and the answer is one window tall, at ${view.width}`, async ({ page }) => {
		await page.setViewportSize(view);
		await openExplorer(page);
		const at = await measure(page, ['answer']);
		expect(at.workbench.left).toBeCloseTo(0, 0);
		expect(at.workbench.right).toBeCloseTo(at.width, 0);
		expect(at.scrollWidth, 'the page scrolls sideways').toBe(at.width);
		expect(at.regions.answer.bottom - at.regions.answer.top).toBeCloseTo(view.height, 0);
	});
}

test('only the Data explorer lifts the width cap and leaves the footer out', async ({ page }) => {
	await page.setViewportSize({ width: 1920, height: 1080 });
	await page.goto('/console/', { waitUntil: 'domcontentloaded' });
	await expect(page.locator('.frame > footer')).toBeVisible();
	const capped = await page.locator('.frame').evaluate((node) => node.getBoundingClientRect().width);
	expect(capped, 'the Pipelines route lost its width cap').toBeLessThan(1920);

	await openExplorer(page);
	await expect(page.locator('.frame > footer')).toBeHidden();
	const lifted = await page.locator('.frame').evaluate((node) => node.getBoundingClientRect().width);
	expect(lifted).toBeCloseTo(1920, 0);
});

for (const view of [
	{ width: 1440, height: 900 },
	{ width: 390, height: 844 }
] as const) {
	test(`Run, Save and Copy link stand next to each other in one group, at ${view.width}`, async ({ page }) => {
		await page.setViewportSize(view);
		await openExplorer(page);
		const group = page.locator('[data-explorer-actions]');
		await expect(group).toHaveCount(1);
		await expect(page.locator('[data-workbench-region="toolbar"] .run-button')).toHaveCount(0);

		const read = () => group.evaluate((node) => {
			const region = (node.closest('[data-workbench-region="editor"]') as HTMLElement).getBoundingClientRect();
			const root = document.documentElement;
			const children = [...node.children] as HTMLElement[];
			const middles = children.map((child) => child.getBoundingClientRect().top + child.getBoundingClientRect().height / 2);
			return {
				names: children.map((child) => child.getAttribute('aria-label') ?? (child.textContent ?? '').replace(/\s+/g, ' ').trim()),
				spread: Math.max(...middles) - Math.min(...middles),
				inside: region.left >= -0.5 && region.right <= root.clientWidth + 0.5 && root.scrollWidth <= root.clientWidth && children.every((child) => {
					const box = child.getBoundingClientRect();
					return box.left >= region.left - 0.5 && box.right <= region.right + 0.5;
				})
			};
		});

		const standing = await read();
		expect(standing.names).toEqual(['Save', 'Copy link', 'Run']);
		expect(standing.spread, 'the three buttons are not on one line').toBeLessThanOrEqual(1);
		expect(standing.inside).toBe(true);

		// Naming a question changes the buttons to Run's left; Run stays the group's last button.
		await group.getByRole('button', { name: /^Save$/ }).click();
		const naming = await read();
		expect(naming.names).toEqual(['Name', 'Keep', 'Cancel', 'Run']);
		expect(naming.spread, 'the naming field and its buttons are not on one line').toBeLessThanOrEqual(1);
		expect(naming.inside).toBe(true);
	});
}

test('Ctrl+Enter in the editor runs the question', async ({ page }) => {
	await openExplorer(page);
	await chooseExplorerQuestion(page, ['published'], 'SELECT 42 AS answer');
	await page.locator('#explorer-sql').press('Control+Enter');
	await expect(page.locator('[data-explorer-answer] tbody td').first()).toHaveText('42', { timeout: 60_000 });
});

for (const view of [
	{ width: 390, height: 844 },
	{ width: 1024, height: 768 },
	{ width: 1440, height: 900 },
	{ width: 1920, height: 1080 }
] as const) {
	test(`the copy buttons stand on the answer's heading line and overlap no other region, at ${view.width}`, async ({ page }) => {
		await page.setViewportSize(view);
		await openExplorer(page);
		await chooseExplorerQuestion(page, ['published'], 'SELECT 1 AS one');
		await runExplorer(page);
		const head = page.locator('[data-workbench-region="answer"] [data-explorer-answer-head]');
		await expect(head.getByRole('button', { name: /^Copy as JSON$/ })).toBeVisible();
		await expect(head.getByRole('button', { name: /^Copy as table$/ })).toBeVisible();
		const found = await head.evaluate((line) => {
			const box = (node: Element) => node.getBoundingClientRect();
			const inside = (inner: DOMRect, outer: DOMRect) =>
				inner.left >= outer.left - 0.5 && inner.right <= outer.right + 0.5 && inner.top >= outer.top - 0.5 && inner.bottom <= outer.bottom + 0.5;
			const meets = (one: DOMRect, other: DOMRect) =>
				one.left < other.right - 0.5 && one.right > other.left + 0.5 && one.top < other.bottom - 0.5 && one.bottom > other.top + 0.5;
			const buttons = [...line.querySelectorAll('button')].map(box);
			const answer = line.closest('[data-workbench-region="answer"]') as Element;
			const others = [...document.querySelectorAll('[data-workbench-region]')].filter((region) => region !== answer);
			const note = answer.querySelector('.answer-note');
			return {
				count: buttons.length,
				onTheLine: buttons.every((button) => inside(button, box(line))),
				lineInAnswer: inside(box(line), box(answer)),
				overlaps: others.flatMap((region) => buttons.some((button) => meets(button, box(region))) ? [region.getAttribute('data-workbench-region')] : []),
				aboveTheNote: note === null || buttons.every((button) => button.bottom <= box(note).top + 0.5)
			};
		});
		expect(found.count).toBe(2);
		expect(found.onTheLine, 'a copy button stands outside the heading line').toBe(true);
		expect(found.lineInAnswer, 'the heading line stands outside the answer').toBe(true);
		expect(found.overlaps, 'a copy button lies over another region').toEqual([]);
		expect(found.aboveTheNote, 'a copy button lies over the line under it').toBe(true);
	});
}
