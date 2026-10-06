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
		// Saved questions come first; whether it fits the line depends on the face, so it is either there or in the fold.
		await expect(strip.locator('.saved-chip .example', { hasText: 'One more saved question' })).toHaveCount(1);
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

/** A question the test wrote that is too long for a link: 5,000 scattered CJK characters deflate to far more than the link may carry. */
const UNLINKABLE = (() => {
	let state = 7;
	let out = '';
	for (let index = 0; index < 5000; index += 1) {
		state = (1664525 * state + 1013904223) >>> 0;
		out += String.fromCharCode(0x4e00 + ((state >>> 8) % 0x5000));
	}
	return out;
})();

for (const view of [
	{ width: 1440, height: 900 },
	{ width: 390, height: 844 }
] as const) {
	test(`Run, Save and Copy link stand next to each other in one group, and Run holds still in every state of it, at ${view.width}`, async ({ page, context }) => {
		await context.grantPermissions(['clipboard-read', 'clipboard-write']);
		await page.setViewportSize(view);
		await openExplorer(page);
		const group = page.locator('[data-explorer-actions]');
		await expect(group).toHaveCount(1);
		await expect(page.locator('[data-workbench-region="toolbar"] .run-button')).toHaveCount(0);
		await page.locator('#explorer-sql').fill('SELECT 1 AS one');

		const read = () => group.evaluate((node) => {
			const box = (part: Element) => {
				const rect = part.getBoundingClientRect();
				return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom };
			};
			const region = box(node.closest('[data-workbench-region="editor"]') as HTMLElement);
			const root = document.documentElement;
			const children = [...node.children] as HTMLElement[];
			return {
				names: children.map((child) => child.getAttribute('aria-label') ?? (child.textContent ?? '').replace(/\s+/g, ' ').trim()),
				boxes: children.map(box),
				group: box(node),
				region,
				sideways: root.scrollWidth > root.clientWidth
			};
		});
		type Read = Awaited<ReturnType<typeof read>>;
		const spread = (boxes: Read['boxes']) => {
			const middles = boxes.map((one) => (one.top + one.bottom) / 2);
			return Math.max(...middles) - Math.min(...middles);
		};
		const apart = (boxes: Read['boxes']) => boxes.every((a, index) => boxes.slice(index + 1).every((b) =>
			a.right <= b.left + 0.5 || b.right <= a.left + 0.5 || a.bottom <= b.top + 0.5 || b.bottom <= a.top + 0.5));
		const inside = (state: Read) => !state.sideways && state.boxes.every((one) => one.left >= state.region.left - 0.5 && one.right <= state.region.right + 0.5);
		const run = (state: Read) => state.boxes[state.names.indexOf('Run')];

		const standing = await read();
		expect(standing.names).toEqual(['Save', 'Copy link', 'Run']);
		expect(spread(standing.boxes), 'the three buttons are not on one line').toBeLessThanOrEqual(1);
		expect(inside(standing)).toBe(true);

		// Save hands focus to the name field with the suggestion selected. Keep, Cancel
		// and Run take the line Save, Copy link and Run stood on; Run does not move.
		await group.getByRole('button', { name: /^Save$/ }).click();
		const field = group.getByLabel('Name', { exact: true });
		await expect(field).toBeFocused();
		await expect(field).toHaveValue('SELECT 1 AS one');
		expect(await field.evaluate((node: HTMLInputElement) => node.selectionStart === 0 && node.selectionEnd === node.value.length)).toBe(true);
		const naming = await read();
		expect(naming.names).toEqual(['Name', 'Keep', 'Cancel', 'Run']);
		expect(run(naming), 'Run moved when the naming state opened').toEqual(run(standing));
		expect(spread(naming.boxes.slice(1)), 'Keep, Cancel and Run are not on one line').toBeLessThanOrEqual(1);
		expect(apart(naming.boxes), 'two of the naming controls overlap').toBe(true);
		expect(inside(naming)).toBe(true);
		if (view.width >= 640) {
			expect(spread(naming.boxes), 'the name field is not on the buttons\' line').toBeLessThanOrEqual(1);
		} else {
			// On a phone the name field takes a whole line of its own beneath the buttons.
			expect(naming.boxes[0].top, 'the name field is not beneath the buttons').toBeGreaterThanOrEqual(run(naming).bottom - 0.5);
			expect(naming.boxes[0].left).toBeCloseTo(naming.group.left, 0);
			expect(naming.boxes[0].right).toBeCloseTo(naming.group.right, 0);
		}

		// Cancel and Keep both hand focus back to Save.
		await group.getByRole('button', { name: /^Cancel$/ }).click();
		await expect(group.getByRole('button', { name: /^Save$/ })).toBeFocused();
		await group.getByRole('button', { name: /^Save$/ }).click();
		await group.getByRole('button', { name: /^Keep$/ }).click();
		await expect(group.getByRole('button', { name: /^Save$/ })).toBeFocused();
		expect(run(await read())).toEqual(run(standing));

		// A question too long for a link brings Copy question into the group; Run does not move.
		await page.locator('#explorer-sql').fill(UNLINKABLE);
		await group.getByRole('button', { name: /^Copy link$/ }).click();
		await expect(group.getByRole('button', { name: /^Copy question$/ })).toBeVisible();
		const linked = await read();
		expect(linked.names).toEqual(['Save', 'Copy link', 'Copy question', 'Run']);
		expect(run(linked), 'Run moved when Copy question appeared').toEqual(run(standing));
		expect(apart(linked.boxes), 'two of the buttons overlap').toBe(true);
		expect(inside(linked)).toBe(true);
	});
}

test('the folded list closes on a press outside it, on Escape and after a pick, and stays open after Forget', async ({ page }) => {
	await page.addInitScript((saved) => localStorage.setItem('yen-idhazh:data-explorer:saved', JSON.stringify(saved)), SAVED);
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page);
	const strip = page.locator('[data-workbench-region="questions"] .question-strip');
	const summary = strip.locator(':scope > details > summary');
	const list = strip.locator(':scope > details .folded');

	// A press outside the list closes it and still does what it pressed.
	await summary.click();
	await expect(list).toBeVisible();
	await page.locator('.history-list summary').click();
	await expect(list).toBeHidden();
	await expect(page.locator('.history-list')).toHaveAttribute('open', '');

	// Escape closes it and hands focus back to its summary.
	await summary.click();
	await expect(list).toBeVisible();
	await list.locator('.example').first().focus();
	await page.keyboard.press('Escape');
	await expect(list).toBeHidden();
	await expect(summary).toBeFocused();

	// Forget leaves it open and moves focus to the nearest x left in it.
	await summary.click();
	const forgets = list.locator('.forget');
	expect(await forgets.count(), 'eight long saved names leave more than one in the fold').toBeGreaterThan(1);
	const gone = ((await list.locator('.saved-chip .example').first().textContent()) ?? '').trim();
	await forgets.first().click();
	await expect(list).toBeVisible();
	await expect(strip.locator('.example', { hasText: gone })).toHaveCount(0);
	await expect(forgets.first()).toBeFocused();

	// A pick loads the question, closes the list and leaves focus on its summary, not in the editor.
	const picked = list.locator('.saved-chip .example').first();
	const number = /number (\d+) /.exec(((await picked.textContent()) ?? '').trim())?.[1];
	expect(number).toBeDefined();
	await picked.click();
	await expect(list).toBeHidden();
	await expect(summary).toBeFocused();
	await expect(page.locator('#explorer-sql')).toHaveValue(`SELECT ${number} AS one`);
});

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
