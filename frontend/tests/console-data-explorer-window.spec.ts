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

/** A question whose answer has `count` columns, each named under a ledger, so the column rail lists them as that ledger's. */
function prefixedColumns(count: number): string {
	return `SELECT ${Array.from({ length: count }, (_, index) => `${index + 1} AS "published.c${String(index + 1).padStart(2, '0')}"`).join(', ')}`;
}

for (const view of [
	{ width: 1440, height: 900 },
	{ width: 1920, height: 1080 }
] as const) {
	test(`a long list of a ledger's columns scrolls inside the column rail and never stretches the page, at ${view.width} x ${view.height}`, async ({ page }) => {
		await page.setViewportSize(view);
		await openExplorer(page);
		await chooseExplorerQuestion(page, ['published'], prefixedColumns(80));
		await runExplorer(page);
		await expect(page.locator('[data-explorer-columns] li')).toHaveCount(80);
		const at = await page.evaluate(() => {
			const list = document.querySelector('[data-explorer-column-box]') as HTMLElement;
			const root = document.documentElement;
			return { scrollHeight: root.scrollHeight, listScrolls: list.scrollHeight > list.clientHeight };
		});
		expect(at.listScrolls, 'the 80 columns did not scroll inside the rail').toBe(true);
		expect(at.scrollHeight, 'the column list stretched the page').toBe(view.height);
	});
}

/** Eight questions saved in this browser, each with a name the test wrote, near the 40-character cap. */
const SAVED = Array.from({ length: 8 }, (_, index) => ({
	id: `strip-${index + 1}`,
	name: `Saved question number ${index + 1} with a long name`,
	statement: `SELECT ${index + 1} AS one`,
	ledgers: ['published'],
	days: 14,
	updatedAt: `2026-08-20T0${index}:00:00Z`
}));

for (const view of [
	{ width: 768, height: 1024 },
	{ width: 1440, height: 900 },
	{ width: 1920, height: 1080 }
] as const) {
	test(`the question strip stays one line, folds the rest into "{n} more" and keeps every title whole, at ${view.width}`, async ({ page }) => {
		await page.addInitScript((saved) => localStorage.setItem('yen-idhazh:data-explorer:saved', JSON.stringify(saved)), SAVED);
		await page.setViewportSize(view);
		await openExplorer(page);
		const strip = page.locator('[data-workbench-region="questions"] .question-strip');
		const fold = strip.locator(':scope > details > summary');
		await expect(fold).toBeVisible();
		const read = () => strip.evaluate((node) => {
			const box = node.getBoundingClientRect();
			const shown = [...node.querySelectorAll(':scope > .run-label, :scope > .example, :scope > .saved-chip, :scope > details > summary')] as HTMLElement[];
			const middles = shown.map((part) => part.getBoundingClientRect().top + part.getBoundingClientRect().height / 2);
			const titles = [...node.querySelectorAll(':scope > .example, :scope > .saved-chip .example')] as HTMLElement[];
			return {
				height: box.height,
				spread: Math.max(...middles) - Math.min(...middles),
				whole: titles.every((title) => {
					const part = title.getBoundingClientRect();
					return title.scrollWidth <= title.clientWidth && part.left >= box.left - 0.5 && part.right <= box.right + 0.5;
				}),
				more: Number((node.querySelector(':scope > details > summary')?.textContent ?? '').trim().split(' ')[0]),
				listed: node.querySelectorAll(':scope > details .folded .example').length
			};
		});
		const before = await read();
		expect(before.spread, 'the strip is not one line').toBeLessThanOrEqual(1);
		expect(before.whole, 'a chip on the line is cut short').toBe(true);
		expect(before.more, 'the fold names a different count from the chips it holds').toBe(before.listed);

		// The folded chips open in view, each title whole.
		await fold.click();
		const list = strip.locator('.folded');
		await expect(list).toBeVisible();
		const opened = await list.evaluate((node) => [...node.querySelectorAll('.example')].every((chip) => {
			const box = chip.getBoundingClientRect();
			const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
			return hit !== null && chip.contains(hit) && chip.scrollWidth <= chip.clientWidth;
		}));
		expect(opened, 'a folded chip is hidden or cut short').toBe(true);
		await fold.click();

		// Saving one more question folds a chip away; the strip keeps its height.
		await page.getByRole('button', { name: /^Save$/ }).click();
		await page.getByLabel('Name', { exact: true }).fill('One more saved question');
		await page.getByRole('button', { name: /^Keep$/ }).click();
		await expect(strip.locator(':scope > .saved-chip .example').first()).toContainText('One more saved question');
		const after = await read();
		expect(after.spread, 'the strip is not one line after a save').toBeLessThanOrEqual(1);
		expect(after.height).toBeCloseTo(before.height, 0);
		expect(after.more).toBe(after.listed);
	});
}

test('the chart heading line holds still and the drawing scrolls in its own box beneath it', async ({ page }) => {
	await page.setViewportSize({ width: 1024, height: 768 });
	await openExplorer(page);
	await chooseExplorerQuestion(page, ['published'], "SELECT * FROM (VALUES (DATE '2026-08-18', 3, 5), (DATE '2026-08-19', 5, 4), (DATE '2026-08-20', 8, 9)) AS t(date, a, b)");
	await runExplorer(page);
	const chart = page.locator('[data-workbench-region="chart"]');
	await expect(chart.locator('[data-shape-choice]').first()).toBeVisible();
	const body = chart.locator('.chart-body');
	const line = chart.locator(':scope > .region-bar');
	const before = await line.boundingBox();
	await body.evaluate((node) => node.scrollTo({ top: node.scrollHeight }));
	const found = await chart.evaluate((region) => {
		const bar = region.querySelector(':scope > .region-bar') as HTMLElement;
		const drawing = region.querySelector('.chart-body') as HTMLElement;
		const tiles = [...bar.querySelectorAll('[data-shape-choice]')] as HTMLElement[];
		return {
			scrolled: drawing.scrollTop > 0,
			below: drawing.getBoundingClientRect().top >= bar.getBoundingClientRect().bottom - 0.5,
			tilesOnTop: tiles.every((tile) => {
				const box = tile.getBoundingClientRect();
				const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
				return hit !== null && tile.contains(hit);
			}),
			tilesInLine: tiles.every((tile) => {
				const box = tile.getBoundingClientRect();
				const edge = bar.getBoundingClientRect();
				return box.top >= edge.top - 0.5 && box.bottom <= edge.bottom + 0.5;
			})
		};
	});
	expect(found.scrolled, 'the drawing did not need to scroll, so this proves nothing').toBe(true);
	expect(found.below, 'the drawing starts above the heading line').toBe(true);
	expect(found.tilesInLine, 'a shape tile stands outside the heading line').toBe(true);
	expect(found.tilesOnTop, 'something is drawn over a shape tile').toBe(true);
	const after = await line.boundingBox();
	expect(after?.y).toBeCloseTo(before?.y ?? -1, 0);
});

test('a long answer and a long question scroll inside their own regions, and the page does not grow', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page);
	await chooseExplorerQuestion(page, ['published'], 'SELECT i AS row_number FROM range(0, 1200) AS t(i)');
	await runExplorer(page);
	await expect(page.locator('[data-explorer-answer] tbody tr').first()).toBeVisible();
	await page.locator('#explorer-sql').fill(Array.from({ length: 40 }, (_, index) => `SELECT ${index}`).join('\n'));
	const at = await page.evaluate(() => {
		const table = document.querySelector('[data-chart="answer-table"]') as HTMLElement;
		const editor = document.querySelector('[data-workbench-region="editor"] .editor-frame') as HTMLElement;
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
	await expect(page.locator('.frame:has(> main) > footer')).toBeVisible();
	const capped = await page.locator('.frame:has(> main)').evaluate((node) => node.getBoundingClientRect().width);
	expect(capped, 'the Pipelines route lost its width cap').toBeLessThan(1920);

	await openExplorer(page);
	await expect(page.locator('.frame:has(> main) > footer')).toBeHidden();
	const lifted = await page.locator('.frame:has(> main)').evaluate((node) => node.getBoundingClientRect().width);
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
