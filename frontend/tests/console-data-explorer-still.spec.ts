import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from './support/browser';
import { chooseExplorerQuestion, expectAnswer, openExplorer, runExplorer, serveBuilt, type AnswerState } from './support/explorer-answer';
import { everyDay, serveToPage } from './support/ledger-lifecycle';
import { consolePanels } from './support/console-panels';
import { judgeFill, readPanel } from './support/panel-gates';
import { explorerConfig } from '../src/lib/server/config';
import { statusSentence } from '../src/lib/console/explorer/status';

/** The UTC day every test here pins as the page's today. A built ledger's days count back from it. */
const PINNED = '2030-06-15';

type Box = { x: number; y: number; width: number; height: number };
type ShiftSource = {
	nodeName: string;
	text: string;
	closest: {
		tag: string;
		className: string;
		data: Record<string, string>;
	} | null;
	previousRect: Box;
	currentRect: Box;
};
type Snapshot = { boxes: Record<string, Box>; scrollY: number; scrollHeight: number; shift: number; sources: ShiftSource[] };

const VIEWS = [
	{ width: 1440, height: 900 },
	{ width: 1024, height: 768 },
	{ width: 768, height: 1024 },
	{ width: 390, height: 844 }
] as const;
async function startShiftObserver(page: Page) {
	await page.evaluate(() => {
		const rectOf = (rect: DOMRectReadOnly) => ({
			x: rect.x,
			y: rect.y,
			width: rect.width,
			height: rect.height
		});
		const held = window as typeof window & { __explorerShift?: number; __explorerSources?: ShiftSource[]; __explorerObserver?: PerformanceObserver };
		held.__explorerObserver?.disconnect();
		held.__explorerShift = 0;
		held.__explorerSources = [];
		held.__explorerObserver = new PerformanceObserver((list) => {
			for (const entry of list.getEntries()) {
				held.__explorerShift =
					(held.__explorerShift ?? 0) +
					(entry as PerformanceEntry & { value?: number }).value!;
				for (const source of ((entry as PerformanceEntry & { sources?: { node?: Node; previousRect?: DOMRectReadOnly; currentRect?: DOMRectReadOnly }[] }).sources ?? [])) {
					const node = source.node;
					const element = node instanceof HTMLElement ? node : node?.parentElement;
					const data = Object.fromEntries(
						[...(element?.attributes ?? [])]
							.filter((attribute) => attribute.name.startsWith('data-'))
							.map((attribute) => [attribute.name, attribute.value])
					);
					held.__explorerSources?.push({
						nodeName: node?.nodeName ?? 'unknown',
						text: (node?.textContent ?? '').slice(0, 60),
						closest: element === undefined || element === null ? null : {
							tag: element.tagName.toLowerCase(),
							className: element.getAttribute('class') ?? '',
							data
						},
						previousRect: rectOf(source.previousRect ?? new DOMRect()),
						currentRect: rectOf(source.currentRect ?? new DOMRect())
					});
				}

			}
		});
		held.__explorerObserver.observe({ type: 'layout-shift', buffered: false });
	});
}

async function snapshot(page: Page): Promise<Snapshot> {
	return page.evaluate(() => {
		const read = (selector: string) => {
			const node = document.querySelector(selector);
			if (!(node instanceof HTMLElement)) throw new Error(`${selector} was not found`);
			const box = node.getBoundingClientRect();
			return { x: box.x, y: box.y, width: box.width, height: box.height };
		};
		const selectors = [
			['strip', '[data-console-strip]'],
			['editorHead', '[data-workbench-region="editor"] .editor-head'],
			['questions', '[data-workbench-region="questions"]'],
			['ledgers', '[data-workbench-region="ledgers"]'],
			['editor', '[data-workbench-region="editor"]'],
			['status', '[data-workbench-region="status"]'],
			['columns', '[data-workbench-region="columns"]'],
			['answer', '[data-workbench-region="answer"]'],
			['run', '.run-button'],
			['editorFrame', '[data-workbench-region="editor"] .editor-frame']
		] as const;
		return {
			boxes: Object.fromEntries(selectors.map(([name, selector]) => [name, read(selector)])),
			scrollY: window.scrollY,
			scrollHeight: document.documentElement.scrollHeight,
			shift: (window as typeof window & { __explorerShift?: number }).__explorerShift ?? 0,
			sources: (window as typeof window & { __explorerSources?: ShiftSource[] }).__explorerSources ?? []
		};
	});
}

async function box(page: Page, selector: string): Promise<Box> {
	return page.locator(selector).evaluate((node) => {
		const rect = node.getBoundingClientRect();
		return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
	});
}

function closeBox(left: Box, right: Box) {
	expect(right.x).toBeCloseTo(left.x, 0);
	expect(right.y).toBeCloseTo(left.y, 0);
	expect(right.width).toBeCloseTo(left.width, 0);
	expect(right.height).toBeCloseTo(left.height, 0);
}

function closeInlineBox(left: Box, right: Box) {
	expect(right.x).toBeCloseTo(left.x, 0);
	expect(right.y).toBeCloseTo(left.y, 0);
	expect(right.width).toBeCloseTo(left.width, 0);
}

async function tileBoxes(page: Page, selector: string, attribute: string): Promise<Record<string, Box>> {
	return page.locator(selector).evaluateAll((nodes, key) => Object.fromEntries(nodes.map((node) => {
		const element = node as HTMLElement;
		const rect = element.getBoundingClientRect();
		return [element.getAttribute(key as string) ?? '', { x: rect.x, y: rect.y, width: rect.width, height: rect.height }];
	})), attribute);
}

function expectTileBoxesStable(before: Record<string, Box>, after: Record<string, Box>, label: string) {
	expect(Object.keys(after).sort(), `${label} tile set`).toEqual(Object.keys(before).sort());
	for (const [name, box] of Object.entries(before)) {
		closeBox(box, after[name]);
	}
}

function expectStable(before: Snapshot, after: Snapshot) {
	expect(after.shift, `layout shift sources: ${JSON.stringify(after.sources, null, 2)}`).toBe(0);
	expect(after.scrollY).toBe(before.scrollY);
	expect(after.scrollHeight).toBe(before.scrollHeight);
	for (const [name, box] of Object.entries(before.boxes)) {
		const next = after.boxes[name];
		expect(next.x, `${name} x`).toBeCloseTo(box.x, 0);
		expect(next.y, `${name} y`).toBeCloseTo(box.y, 0);
		expect(next.width, `${name} width`).toBeCloseTo(box.width, 0);
		expect(next.height, `${name} height`).toBeCloseTo(box.height, 0);
	}
}

for (const view of VIEWS) {
	test(`Run moves nothing in answered, capped, quiet and refused states at ${view.width}px`, async ({ page, context }) => {
		await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(1, 0) });
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		await page.evaluate(() => window.scrollTo(0, 0));
		const cases: { sql: string; state: AnswerState }[] = [
			{ sql: 'SELECT count(*) AS rows FROM "published"', state: 'table' },
			{ sql: 'SELECT i AS row_number FROM range(0, 1200) AS t(i)', state: 'table' },
			{ sql: 'SELECT * FROM "published" WHERE false', state: 'quiet' },
			{ sql: 'SELECT 1; SELECT 2', state: 'refused' }
		];
		for (const { sql, state } of cases) {
			await chooseExplorerQuestion(page, ['published'], sql);
			// Run is pressed where a person sees it, so the press itself scrolls nothing.
			await page.locator('.run-button').scrollIntoViewIfNeeded();
			await startShiftObserver(page);
			const before = await snapshot(page);
			await runExplorer(page);
			await expectAnswer(page, state);
			await page.waitForTimeout(1000);
			expectStable(before, await snapshot(page));
		}
	});
}

test('Copy link notice is fixed and moves no region', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	await page.setViewportSize({ width: 390, height: 844 });
	await openExplorer(page, PINNED);
	await page.getByRole('button', { name: /^Copy link$/ }).scrollIntoViewIfNeeded();
	await startShiftObserver(page);
	const before = await snapshot(page);
	await page.getByRole('button', { name: /^Copy link$/ }).click();
	await expect(page.locator('[data-notice]')).toHaveCSS('position', 'fixed');
	await expect(page.locator('[data-notice]')).toHaveAttribute('role', 'status');
	expectStable(before, await snapshot(page));
});

test('status text never overlaps the reserved answer link box', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 390, height: 844 });
	await openExplorer(page, PINNED);
	await expect(page.getByRole('link', { name: 'See the answer' })).toHaveCount(0);
	await chooseExplorerQuestion(page, ['published'], 'SELECT * FROM "published" WHERE false');
	await runExplorer(page);
	await expectAnswer(page, 'quiet');
	const link = page.getByRole('link', { name: 'See the answer' });
	if (await link.count() > 0) {
		await expect(link).toHaveAttribute('href', /#data-explorer-rows$/);
		const overlap = await page.locator('[data-workbench-region="status"]').evaluate((status) => {
			const text = status.querySelector('.status-copy')?.getBoundingClientRect();
			const answer = status.querySelector('.status-link-box')?.getBoundingClientRect();
			if (!text || !answer) return true;
			return text.right > answer.left && text.left < answer.right && text.bottom > answer.top && text.top < answer.bottom;
		});
		expect(overlap).toBe(false);
	}
	expect(await page.locator('[data-workbench-region="status"]').evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);

	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['published'], 'SELECT * FROM "published" WHERE false');
	await runExplorer(page);
	await expectAnswer(page, 'quiet');
	await expect(page.getByRole('link', { name: 'See the answer' })).toHaveCount(0);
});

test('M8: editor head, questions and narrow rails keep their density heights', async ({ page }) => {
	for (const view of VIEWS) {
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		const sizes = await page.evaluate(() => {
			const css = getComputedStyle(document.documentElement);
			const rem = parseFloat(css.fontSize);
			const control = parseFloat(css.getPropertyValue('--workbench-control')) * rem;
			const space1 = parseFloat(css.getPropertyValue('--space-1')) * rem;
			const space2 = parseFloat(css.getPropertyValue('--space-2')) * rem;
			const space3 = parseFloat(css.getPropertyValue('--space-3')) * rem;
			const questions = document.querySelector<HTMLElement>('[data-workbench-region="questions"]');
			const questionStyle = questions === null ? null : getComputedStyle(questions);
			const questionGap = questionStyle === null ? 0 : parseFloat(questionStyle.rowGap) || 0;
			// The region's own edge and padding, which its box holds beside its two lines.
			const questionEdges = questionStyle === null ? 0 : ['border-top-width', 'border-bottom-width', 'padding-top', 'padding-bottom'].reduce((sum, property) => sum + (parseFloat(questionStyle.getPropertyValue(property)) || 0), 0);
			const regions = Object.fromEntries(
				[...document.querySelectorAll('[data-workbench-region]')].map((node) => {
					const rect = node.getBoundingClientRect();
					return [node.getAttribute('data-workbench-region') ?? '', rect.height];
				})
			);
			return { control, space1, space2, space3, questionGap, questionEdges, regions };
		});
		const oneControlRow = sizes.control + 2 * sizes.space1;
		expect(await page.locator('[data-workbench-region="editor"] .editor-head').evaluate((node) => node.getBoundingClientRect().height), `${view.width} editor head`).toBeGreaterThanOrEqual(oneControlRow - 1);
		if (view.width < 640) {
			expect(sizes.regions.questions, `${view.width} questions`).toBeCloseTo(2 * sizes.control + sizes.questionGap + sizes.questionEdges, 0);
		} else {
			expect(sizes.regions.questions, `${view.width} questions`).toBeCloseTo(oneControlRow, 0);
		}
		if (view.width < 1024) {
			expect(sizes.regions.ledgers, `${view.width} ledgers summary`).toBeCloseTo(sizes.control, 0);
			expect(sizes.regions.columns, `${view.width} columns summary`).toBeCloseTo(sizes.control, 0);
		}
	}
});

test('M7: the editor frame starts in the top third on desktop and tablet', async ({ page }) => {
	for (const view of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }] as const) {
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		const top = await page.locator('[data-workbench-region="editor"] .editor-frame').evaluate((node) => node.getBoundingClientRect().top);
		expect(top, `${view.width} editor frame top`).toBeLessThanOrEqual(300);
	}
});

test('M14: the chart draws at the region content width and keeps its height on resize', async ({ page, context }, testInfo) => {
	await serveBuilt(context, testInfo.outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['published'], "SELECT * FROM (VALUES (DATE '2026-08-18', 3), (DATE '2026-08-19', 5), (DATE '2026-08-20', 8)) AS t(date, rows)");
	await runExplorer(page);
	await page.getByRole('tab', { name: 'Chart' }).click();
	await page.locator('[data-workbench-region="chart"]').evaluate((node) => node.scrollIntoView({ block: 'center', behavior: 'instant' }));
	await page.locator('[data-workbench-region="chart"] svg[data-chart-type]').waitFor({ state: 'visible', timeout: 60_000 });
	const reading = async () => page.evaluate(() => {
		const plot = document.querySelector('[data-workbench-region="chart"] svg[data-chart-type]') as SVGElement | null;
		const region = (document.querySelector('[data-workbench-region="chart"] .chart-body') ?? plot?.parentElement) as HTMLElement | null;
		if (region === null || plot === null) throw new Error('chart body was not drawn');
		const style = getComputedStyle(region);
		const contentWidth = Math.floor(region.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight));
		const plotBox = plot.getBoundingClientRect();
		const regionBox = region.getBoundingClientRect();
		return { contentWidth, plotWidth: Math.floor(plotBox.width), regionHeight: regionBox.height };
	});
	const wide = await reading();
	expect(wide.plotWidth).toBe(wide.contentWidth);
	await page.setViewportSize({ width: 1024, height: 768 });
	const narrow = await reading();
	expect(narrow.plotWidth).toBe(narrow.contentWidth);
	expect(narrow.plotWidth).not.toBe(wide.plotWidth);
	expect(narrow.regionHeight).toBeGreaterThan(0);
});

test('M19: workbench text stays on the declared type scale', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	const offScale = await page.locator('.workbench').evaluate((root) => {
		const css = getComputedStyle(document.documentElement);
		const rem = parseFloat(css.fontSize);
		const allowed = ['--text-xs', '--text-sm', '--text-base', '--text-xl']
			.map((size) => parseFloat(css.getPropertyValue(size)) * rem);
		allowed.push(parseFloat(css.getPropertyValue('--text-xs')) * rem * 0.8);
		const failures: string[] = [];
		const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
		for (let text = walker.nextNode(); text; text = walker.nextNode()) {
			if ((text.textContent ?? '').trim() === '') continue;
			const element = text.parentElement;
			if (element === null) continue;
			const style = getComputedStyle(element);
			if (style.visibility === 'hidden' || style.display === 'none') continue;
			if (element.closest('.sr-only')) continue;
			if (element.closest('h2')) continue;
			const box = element.getBoundingClientRect();
			if (box.width <= 1 && box.height <= 1) continue;
			const size = parseFloat(style.fontSize);
			if (!allowed.some((allowedSize) => Math.abs(allowedSize - size) < 0.2)) {
				failures.push(`${(text.textContent ?? '').trim().slice(0, 32)}: ${size}`);
			}
		}
		return failures;
	});
	expect(offScale).toEqual([]);
});

test('R1: column headers stay on one line and the answer box scrolls sideways', async ({ page }) => {
	for (const view of [{ width: 1440, height: 900 }, { width: 390, height: 844 }] as const) {
		await page.setViewportSize(view);
		await openExplorer(page, '2026-08-20');
		await chooseExplorerQuestion(page, ['item-health'], 'SELECT * FROM "item-health"');
		await runExplorer(page);
		await expectAnswer(page, 'table');
		const reading = await page.locator('[data-explorer-answer]').evaluate((table) => {
			const box = table.closest('.table-box') as HTMLElement;
			const headers = [...table.querySelectorAll('thead th:not(.row-number) span')].map((header) => {
				const rect = header.getBoundingClientRect();
				const line = parseFloat(getComputedStyle(header).lineHeight);
				return { text: header.textContent ?? '', height: rect.height, line };
			});
			return { scrolls: box.scrollWidth > box.clientWidth, headers };
		});
		expect(reading.scrolls, `${view.width} table did not scroll sideways`).toBe(true);
		for (const header of reading.headers) {
			expect(header.height, `${view.width} ${header.text} broke across lines`).toBeLessThanOrEqual(header.line + 1);
		}
	}
});

test('M10: non-run interactions keep every region box fixed', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['published'], 'SELECT i AS row_number FROM range(0, 120) AS t(i)');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	await page.evaluate(() => window.scrollTo(0, 0));
	const measure = async (act: () => Promise<void>) => {
		const before = await snapshot(page);
		await act();
		expectStable(before, await snapshot(page));
	};
	await measure(() => page.locator('[data-explorer-answer] th button').first().click());
	await page.getByRole('button', { name: /^Show 50 more rows$/ }).scrollIntoViewIfNeeded();
	await measure(() => page.getByRole('button', { name: /^Show 50 more rows$/ }).click());
	await measure(() => page.getByRole('tab', { name: 'Chart' }).click());
	await measure(() => page.getByRole('tab', { name: 'Table' }).click());
	await page.getByRole('tab', { name: 'Chart' }).click();
	if (await page.locator('[data-shape-choice]').count()) await measure(() => page.locator('[data-shape-choice]').last().click());
	await page.getByRole('tab', { name: 'Table' }).click();
	if (await page.locator('summary').filter({ hasText: 'more' }).count()) {
		await measure(() => page.locator('summary').filter({ hasText: 'more' }).first().click());
		// The open list lies over the regions below it; a person closes it before pressing what it covers.
		await measure(() => page.keyboard.press('Escape'));
	}
	await page.locator('.history-list summary').scrollIntoViewIfNeeded();
	await measure(() => page.locator('.history-list summary').click());
	await page.getByRole('button', { name: /^Copy as JSON$/ }).scrollIntoViewIfNeeded();
	await measure(() => page.getByRole('button', { name: /^Copy as JSON$/ }).click());
	await measure(() => page.getByRole('button', { name: /^Copy as table$/ }).click());
	await page.getByRole('button', { name: /^Copy link$/ }).scrollIntoViewIfNeeded();
	await measure(() => page.getByRole('button', { name: /^Copy link$/ }).click());
	await measure(() => page.getByRole('button', { name: /^Save$/ }).click());
	await page.getByLabel('Name').fill('Long question');
	await measure(() => page.getByRole('button', { name: /^Keep$/ }).click());
	await measure(() => page.locator('#explorer-sql').fill(Array.from({ length: 40 }, (_, index) => `SELECT ${index}`).join('\n')));
});

test('Susan 2026-10-07: checked choice tiles keep their bold-word width in every caller', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);

	const assertPressesDoNotMoveTiles = async (selector: string, attribute: string, name: string) => {
		const count = await page.locator(selector).count();
		expect(count, `${name} has no tiles to press`).toBeGreaterThan(0);
		for (let index = 0; index < count; index += 1) {
			const before = await tileBoxes(page, selector, attribute);
			await page.locator(selector).nth(index).click();
			const after = await tileBoxes(page, selector, attribute);
			expectTileBoxesStable(before, after, `${name} ${index}`);
		}
	};

	await assertPressesDoNotMoveTiles('[data-window-preset]', 'data-window-preset', 'day');

	await chooseExplorerQuestion(page, ['published'], "SELECT * FROM (VALUES (DATE '2026-08-18', 3), (DATE '2026-08-19', 5), (DATE '2026-08-20', 8)) AS t(date, rows)");
	await runExplorer(page);
	await expectAnswer(page, 'table');
	await page.getByRole('tab', { name: 'Chart' }).click();
	await assertPressesDoNotMoveTiles('[data-shape-choice]', 'data-shape-choice', 'Draw it as');
});

test('M11: status words stay in the reserved lines and never scroll sideways', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	expect(statusSentence({ state: 'idle', files: 123, bytes: 67_108_864, ledgers: 4, days: 90, firstRun: true })).toBe('Run reads 123 files, 64.0 MB from 4 ledgers over 90 UTC days. It also starts the query engine.');
	expect(statusSentence({ state: 'costing' })).toBe('Choosing a ledger fetches one day of it to list its columns.');
	expect(statusSentence({ state: 'running-fetch', files: 123, bytes: 67_108_864 })).toBe('Fetching 123 files, 64.0 MB.');
	expect(statusSentence({ state: 'running-query' })).toBe('Running the question.');
	expect(statusSentence({ state: 'answered', ms: 99999, read: { files: 123, bytes: 67_108_864, alreadyHeld: 45, ms: 99999 } })).toBe('Answered in 100.0 s. Read 123 files, 64.0 MB.');
	expect(statusSentence({ state: 'answered', ms: 99999, read: { files: 0, bytes: 0, alreadyHeld: 45, ms: 99999 } })).toBe('Answered in 100.0 s.');
	expect(statusSentence({ state: 'quiet', ms: 99999, read: { files: 123, bytes: 67_108_864, alreadyHeld: 45, ms: 99999 } })).toBe('Ran in 100.0 s and matched no rows. Read 123 files, 64.0 MB.');
	expect(statusSentence({ state: 'quiet', ms: 99999, read: { files: 0, bytes: 0, alreadyHeld: 45, ms: 99999 } })).toBe('Ran in 100.0 s and matched no rows.');
	expect(statusSentence({ state: 'refused' })).toBe('Did not run. The reason is where the answer would be.');
	expect(statusSentence({ state: 'missing', ledger: 'published' })).toBe('Did not run. published is not on this site yet.');
	expect(statusSentence({ state: 'unreachable-engine' })).toBe('Did not run. The query engine did not start.');
	expect(statusSentence({ state: 'unreachable-files' })).toBe('Did not run. The ledger files could not be fetched.');
	const longest = statusSentence({ state: 'answered', ms: 99999, read: { files: 123, bytes: 67_108_864, alreadyHeld: 123, ms: 99999 } });
	for (const view of VIEWS) {
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		const status = page.locator('[data-workbench-region="status"]');
		await expect(status).toContainText('Run reads');
		await chooseExplorerQuestion(page, ['published'], 'SELECT * FROM "published" WHERE false');
		await runExplorer(page);
		await expectAnswer(page, 'quiet');
		await expect(status).toContainText('Ran in');
		await status.locator('.status-copy').evaluate((node, value) => {
			node.textContent = value;
		}, longest);
		const fit = await status.evaluate((node) => ({
			noHorizontalScroll: node.scrollWidth <= node.clientWidth,
			verticalFits: node.scrollHeight <= node.clientHeight
		}));
		expect(fit.noHorizontalScroll, `${view.width} no horizontal scroll`).toBe(true);
		expect(fit.verticalFits, `${view.width} reserved lines`).toBe(true);
	}
});

test('M12: notices time out, pause on hover or focus, and close on the button', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	await page.setViewportSize({ width: 390, height: 844 });
	await openExplorer(page, PINNED);
	await page.clock.install();
	await page.getByRole('button', { name: /^Copy link$/ }).scrollIntoViewIfNeeded();
	await page.getByRole('button', { name: /^Copy link$/ }).click();
	const notice = page.locator('[data-notice]');
	await expect(notice).toBeVisible();
	await page.clock.fastForward(explorerConfig().notice_ms + 100);
	await expect(notice).toHaveCount(0);
	await page.getByRole('button', { name: /^Copy link$/ }).click();
	await expect(notice).toBeVisible();
	await notice.hover();
	await page.clock.fastForward(explorerConfig().notice_ms + 100);
	await expect(notice).toBeVisible();
	await notice.getByRole('button', { name: 'Close' }).focus();
	await page.mouse.move(1, 1);
	await page.clock.fastForward(explorerConfig().notice_ms + 100);
	await expect(notice).toBeVisible();
	await notice.getByRole('button', { name: 'Close' }).click();
	await expect(notice).toHaveCount(0);
});

test('storage notice dismissal does not re-enable storage-backed controls', async ({ page }) => {
	await openExplorer(page, PINNED);
	await page.evaluate(() => {
		Storage.prototype.setItem = () => {
			throw new Error('storage blocked');
		};
	});
	await page.getByRole('button', { name: /^Save$/ }).click();
	await page.getByLabel('Name').fill('Blocked');
	await page.getByRole('button', { name: /^Keep$/ }).click();
	const notice = page.locator('[data-notice]');
	await expect(notice).toContainText('This browser keeps nothing.');
	await notice.getByRole('button', { name: 'Close' }).click();
	await expect(notice).toHaveCount(0);
	await expect(page.getByRole('button', { name: /^Save$/ })).toBeDisabled();
	await page.locator('.history-list summary').click();
	await expect(page.locator('.history-list')).toContainText('Nothing asked in this browser yet.');
});

test('M13: B1 column rail text is identical before and after Run', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'host-fingerprint', pinned: PINNED, days: everyDay(0, 0) });
	for (const view of [{ width: 1440, height: 900 }, { width: 390, height: 844 }] as const) {
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		await chooseExplorerQuestion(page, ['host-fingerprint'], 'SELECT * FROM "host-fingerprint" LIMIT 1');
		const rail = '[data-workbench-region="columns"]';
		if (await page.locator(`${rail}:not([open]) summary`).count()) await page.locator(`${rail} summary`).click();
		await expect(page.locator('[data-explorer-columns] h3')).toHaveText('Ledger columns');
		await expect(page.locator('[data-explorer-columns] li code')).toHaveText(['host-fingerprint.covers', 'host-fingerprint.date', 'host-fingerprint.n']);
		const beforeText = await page.locator('[data-explorer-columns]').innerText();
		const outer = await box(page, rail);
		const inner = await box(page, '[data-explorer-column-box]');
		await runExplorer(page);
		await expectAnswer(page, 'table');
		await expect(page.locator('[data-explorer-columns] h3')).toHaveText('Ledger columns');
		expect(await page.locator('[data-explorer-columns]').innerText()).toBe(beforeText);
		closeBox(outer, await box(page, rail));
		closeBox(inner, await box(page, '[data-explorer-column-box]'));
	}
});

test('M15: panel ids stay ordered, headed and joined into one workbench surface', async ({ page }) => {
	await openExplorer(page, PINNED);
	const ids = await page.locator('[data-console-panel-id]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-console-panel-id')));
	expect(ids.slice(0, 3)).toEqual(['data-explorer-ask', 'data-explorer-rows', 'data-explorer-shape']);
	for (const id of ['data-explorer-ask', 'data-explorer-rows', 'data-explorer-shape']) {
		await expect(page.locator(`[data-console-panel-id="${id}"] h2`)).toHaveCount(1);
	}
	await expect(page.getByRole('tablist', { name: 'Answer view' })).toHaveCount(1);
	await expect(page.getByRole('tab', { name: 'Table' })).toHaveAttribute('aria-controls', 'data-explorer-rows');
	await expect(page.getByRole('tab', { name: 'Table' })).toHaveAttribute('aria-selected', 'true');
	await expect(page.getByRole('tab', { name: 'Table' })).toHaveAttribute('tabindex', '0');
	await expect(page.getByRole('tab', { name: 'Chart' })).toHaveAttribute('aria-controls', 'data-explorer-shape');
	await expect(page.getByRole('tab', { name: 'Chart' })).toHaveAttribute('aria-selected', 'false');
	await expect(page.getByRole('tab', { name: 'Chart' })).toHaveAttribute('tabindex', '-1');
	await expect(page.locator('#data-explorer-rows')).toHaveAttribute('role', 'tabpanel');
	await expect(page.locator('#data-explorer-rows')).toHaveAttribute('aria-labelledby', 'explorer-tab-table');
	await expect(page.locator('#data-explorer-shape')).toHaveAttribute('role', 'tabpanel');
	await expect(page.locator('#data-explorer-shape')).toHaveAttribute('aria-labelledby', 'explorer-tab-chart');
	await page.getByRole('tab', { name: 'Table' }).focus();
	await page.keyboard.press('ArrowRight');
	await expect(page.getByRole('tab', { name: 'Chart' })).toBeFocused();
	await expect(page.getByRole('tab', { name: 'Chart' })).toHaveAttribute('aria-selected', 'true');
	await expect(page.getByRole('tab', { name: 'Chart' })).toHaveAttribute('tabindex', '0');
	await expect(page.getByRole('tab', { name: 'Table' })).toHaveAttribute('tabindex', '-1');
	await page.keyboard.press('ArrowLeft');
	await expect(page.getByRole('tab', { name: 'Table' })).toBeFocused();
	await page.getByRole('tab', { name: 'Chart' }).click();
	await chooseExplorerQuestion(page, ['published'], 'SELECT count(*) AS rows FROM "published"');
	await runExplorer(page);
	await expectAnswer(page, 'quiet');
	await expect(page.getByRole('tab', { name: 'Chart' })).toHaveAttribute('aria-selected', 'true');
	const colours = await page.evaluate(() => ({
		page: getComputedStyle(document.body).backgroundColor,
		workbench: getComputedStyle(document.querySelector('.workbench') as HTMLElement).backgroundColor
	}));
	expect(colours.workbench).not.toBe(colours.page);
});

test('M16: phone width has no document overflow and controls stay inside their regions', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await openExplorer(page, PINNED);
	const overflow = await page.evaluate(() => {
		const regions = [...document.querySelectorAll('[data-workbench-region="toolbar"], [data-workbench-region="questions"]')];
		const offenders: string[] = [];
		return {
			documentFits: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
			controlsFit: regions.every((region) => {
				const box = region.getBoundingClientRect();
				return [...region.querySelectorAll('button, input, a, summary')].every((node) => {
					const rect = node.getBoundingClientRect();
					if (rect.width === 0 || rect.height === 0 || getComputedStyle(node).visibility === 'hidden') return true;
					const fits = rect.left >= box.left - 0.5 && rect.right <= box.right + 0.5;
					if (!fits) offenders.push(`${region.getAttribute('data-workbench-region')}: ${node.tagName} ${node.textContent?.trim()} ${rect.left}-${rect.right} outside ${box.left}-${box.right}`);
					return fits;
				});
			}),
			offenders
		};
	});
	expect(overflow.documentFits).toBe(true);
	expect(overflow.controlsFit, overflow.offenders.join('\n')).toBe(true);
});

/** Every control the named regions cut off: one outside a region that never scrolls, or past its
 *  height; one outside a clipping box it sits in; and one whose own text is cut. A region in
 *  `whole` never scrolls; a region in `sideways` scrolls by design, so it is held only sideways.
 *  `openList` names a floating list that is open: the list itself lies inside the window and inside
 *  its region's side edges, and its lines, which scroll inside it, are held sideways. */
async function cutOffControls(page: Page, whole: readonly string[], sideways: readonly string[], openList: string | null = null): Promise<string[]> {
	return page.evaluate(({ whole, sideways, openList }) => {
		const list = openList === null ? null : document.querySelector<HTMLElement>(openList);
		const offenders: string[] = openList !== null && list === null ? [`${openList}: the open list is missing`] : [];
		if (list !== null) {
			const at = list.getBoundingClientRect();
			const windowWidth = document.documentElement.clientWidth;
			const windowHeight = document.documentElement.clientHeight;
			if (at.left < -0.5 || at.top < -0.5 || at.right > windowWidth + 0.5 || at.bottom > windowHeight + 0.5) offenders.push(`the open list at ${Math.round(at.left)},${Math.round(at.top)}-${Math.round(at.right)},${Math.round(at.bottom)} passes the window`);
			const region = list.closest('[data-workbench-region]')?.getBoundingClientRect();
			if (region !== undefined && (at.left < region.left - 0.5 || at.right > region.right + 0.5)) offenders.push('the open list passes its region\'s side edges');
		}
		const overflows = (node: HTMLElement) => {
			const style = getComputedStyle(node);
			return style.overflowX !== 'visible' || style.overflowY !== 'visible';
		};
		const scrolls = (node: HTMLElement) => {
			const style = getComputedStyle(node);
			return style.overflowX === 'auto' || style.overflowX === 'scroll' || style.overflowY === 'auto' || style.overflowY === 'scroll';
		};
		const visible = (node: HTMLElement) => {
			const rect = node.getBoundingClientRect();
			return rect.width > 0 && rect.height > 0 && node.checkVisibility() && getComputedStyle(node).visibility !== 'hidden';
		};
		const label = (node: HTMLElement) => `${node.tagName.toLowerCase()} "${(node.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 50)}"`;
		const fitsInside = (inner: DOMRect, outer: DOMRect, bothAxes: boolean) => inner.left >= outer.left - 0.5 && inner.right <= outer.right + 0.5 && (!bothAxes || (inner.top >= outer.top - 0.5 && inner.bottom <= outer.bottom + 0.5));
		const intersects = (inner: DOMRect, outer: DOMRect) => inner.right > outer.left && inner.left < outer.right && inner.bottom > outer.top && inner.top < outer.bottom;
		const canScrollIntoView = (control: HTMLElement, rect: DOMRect, bothAxes: boolean) => {
			for (let ancestor = control.parentElement; ancestor !== null && !ancestor.classList.contains('workbench'); ancestor = ancestor.parentElement) {
				if (!visible(ancestor) || !overflows(ancestor)) continue;
				const ancestorBox = ancestor.getBoundingClientRect();
				if (fitsInside(rect, ancestorBox, bothAxes)) continue;
				return scrolls(ancestor) && (bothAxes ? !intersects(rect, ancestorBox) : rect.right <= ancestorBox.left || rect.left >= ancestorBox.right || rect.bottom <= ancestorBox.top || rect.top >= ancestorBox.bottom);
			}
			return false;
		};
		for (const name of [...whole, ...sideways]) {
			const region = document.querySelector<HTMLElement>(`[data-workbench-region="${name}"]`);
			if (region === null) {
				offenders.push(`${name}: the region is missing`);
				continue;
			}
			const regionBoth = whole.includes(name);
			const box = region.getBoundingClientRect();
			// A list that floats over the page - the folded questions, History's list - is
			// a box placed out of the flow that reaches past its region. Its controls are
			// held to the window, and the region is measured without it.
			const floats = (node: Element, itself = false) => {
				for (let ancestor: Element | null = itself ? node : node.parentElement; ancestor !== null && ancestor !== region; ancestor = ancestor.parentElement) {
					const position = getComputedStyle(ancestor).position;
					if ((position === 'absolute' || position === 'fixed') && !fitsInside(ancestor.getBoundingClientRect(), box, true)) return true;
				}
				return false;
			};
			const scrolledInside = (node: Element) => {
				for (let ancestor = node.parentElement; ancestor !== null && ancestor !== region; ancestor = ancestor.parentElement) {
					if (scrolls(ancestor)) return true;
				}
				return false;
			};
			if (regionBoth) {
				// Content in the flow below the region's foot lies over the region under it,
				// whether or not this region clips.
				let foot = box.top;
				for (const node of region.querySelectorAll<HTMLElement>('*')) {
					if (!visible(node) || floats(node, true) || scrolledInside(node)) continue;
					foot = Math.max(foot, node.getBoundingClientRect().bottom);
				}
				if (foot > box.bottom + 0.5) offenders.push(`${name}: ${Math.round(foot - box.bottom)}px of its content lies below it`);
			}
			const windowBox = new DOMRect(0, 0, document.documentElement.clientWidth, document.documentElement.clientHeight);
			for (const control of region.querySelectorAll<HTMLElement>('button, input, select, textarea, a[href], summary')) {
				const rect = control.getBoundingClientRect();
				// A line of an open list scrolls inside the list by design, so it is held sideways, as a rail's row is.
				const both = list !== null && list.contains(control) ? false : regionBoth;
				// checkVisibility() is false for a chip in a closed fold, which the page lays out but never draws.
				if (!visible(control)) continue;
				if (canScrollIntoView(control, rect, both)) continue;
				const floating = floats(control);
				const frame = floating ? windowBox : box;
				const across = rect.left >= frame.left - 0.5 && rect.right <= frame.right + 0.5;
				const down = rect.top >= frame.top - 0.5 && rect.bottom <= frame.bottom + 0.5;
				if (!across || ((both || floating) && !down)) {
					offenders.push(`${name}: ${label(control)} at ${Math.round(rect.left)},${Math.round(rect.top)}-${Math.round(rect.right)},${Math.round(rect.bottom)} outside ${floating ? 'the window' : 'its region'} ${Math.round(frame.left)},${Math.round(frame.top)}-${Math.round(frame.right)},${Math.round(frame.bottom)}`);
				}
				if ((control.matches('button, a[href], summary') || control.classList.contains('example')) && control.scrollWidth > control.clientWidth + 1) {
					offenders.push(`${name}: ${label(control)} cuts its text by ${control.scrollWidth - control.clientWidth}px`);
				}
				for (let ancestor = control.parentElement; ancestor !== null && !ancestor.classList.contains('workbench'); ancestor = ancestor.parentElement) {
					if (!visible(ancestor) || !overflows(ancestor)) continue;
					const ancestorBox = ancestor.getBoundingClientRect();
					if (!fitsInside(rect, ancestorBox, both)) {
						offenders.push(`${name}: ${label(control)} is outside clipping ancestor ${ancestor.tagName.toLowerCase()}.${ancestor.className} at ${Math.round(ancestorBox.left)},${Math.round(ancestorBox.top)}-${Math.round(ancestorBox.right)},${Math.round(ancestorBox.bottom)}`);
					}
				}
			}
		}
		return offenders;
	}, { whole, sideways, openList });
}

test('no workbench control is cut off, idle or after a run, at any width', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	for (const view of VIEWS) {
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		for (const phase of ['idle', 'after a run'] as const) {
			if (phase === 'after a run') {
				await chooseExplorerQuestion(page, ['published'], 'SELECT count(*) AS rows FROM "published"');
				await runExplorer(page);
				await expectAnswer(page, 'table');
			}
			for (const disclosure of ['closed', 'questions open'] as const) {
				const summary = page.locator('[data-workbench-region="questions"] .question-strip summary');
				if (disclosure === 'questions open' && await summary.count()) await summary.click();
				// These regions never scroll, so a control outside them, or content past their
				// height, is cut off. The rails scroll by design, so they are held only sideways.
				const cut = await cutOffControls(page, ['questions', 'editor'], ['ledgers', 'columns']);
				expect(cut, `${view.width}px, ${phase}, ${disclosure}`).toEqual([]);
				if (disclosure === 'questions open' && await summary.count()) await summary.click();
			}
		}
	}
});

test('M17: keyboard order follows the visual order at desktop and phone widths', async ({ page }) => {
	for (const view of [{ width: 1440, height: 900 }, { width: 390, height: 844 }] as const) {
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		const order = await page.evaluate(() => {
			const regionOrder = ['strip', 'toolbar', 'questions', 'ledgers', 'editor', 'status', 'columns', 'answer', 'chart'];
			return [...document.querySelectorAll<HTMLElement>('a[href], button, input, summary, textarea')]
				.filter((node) => {
					const rect = node.getBoundingClientRect();
					return rect.width > 0 && rect.height > 0 && getComputedStyle(node).visibility !== 'hidden';
				})
				.map((node, index) => {
					const region = node.closest('[data-workbench-region]')?.getAttribute('data-workbench-region') ?? (node.closest('[data-console-strip]') ? 'strip' : '');
					return { index, region, rank: regionOrder.indexOf(region) };
				});
		});
		const ranks = order.filter((entry) => entry.rank >= 0).map((entry) => entry.rank);
		expect(ranks).toEqual([...ranks].sort((left, right) => left - right));
	}
});

// --- The Chart tab: the reader chooses the chart and its columns (plan 55 row 19) ----------------

/** Two date columns, a name a row and four number columns, one of them too flat to draw: every
 *  role of every chart has a column to pick and another to change to. Two date columns pick no
 *  chart of their own, so the tiles start with none checked. */
const CHART_SQL = "SELECT DATE '2026-01-01' + i::INTEGER AS day, TIMESTAMP '2026-01-01 06:00:00' + INTERVAL (i) DAY AS stamp, 'n' || i::VARCHAR AS name, i AS across, 200 - i AS up, 2 * i AS other, 0 AS tiny FROM range(0, 170) AS t(i)";
const CHART_TYPES = ['dateSeries', 'rankedList', 'pairedScatter', 'distribution', 'partsOfOne', 'tileStrip', 'flow'] as const;
/** The lines the role row reserves, with Flow's four roles, even when another chart is drawn. */
const ROLE_LINES: Record<number, number> = { 1440: 1, 1024: 2, 768: 2, 390: 4 };

for (const view of VIEWS) {
	test.describe(`row20 role band ${view.width}`, () => {
	test.use({ hasTouch: view.width < 1024 });
	test(`row20 I1: Flow uses four roles without moving Spread's boxes at ${view.width}px`, async ({ page, context }) => {
		await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		await openChart(page, "SELECT 's' || i AS stage, 170-i AS arrived, 169-i AS went, 1 AS dropped FROM range(0, 170) AS t(i)");
		await page.locator('[data-shape-choice="flow"]').click();
		await settle(page);
		const read = () => page.locator('[data-chart-roles]').evaluate((node) => ({
			height: node.getBoundingClientRect().height,
			tops: [...node.querySelectorAll('summary')].map((pill) => Math.round(pill.getBoundingClientRect().top))
		}));
		const flowRow = await read();
		expect(new Set(flowRow.tops).size).toBe(ROLE_LINES[view.width]);
		expect(flowRow.height).toBe({ 390: 196, 768: 100, 1024: 76, 1440: 40 }[view.width]);
		const sizes = await tokens(page);
		expect(flowRow.height).toBeCloseTo(ROLE_LINES[view.width] * sizes.control + (ROLE_LINES[view.width] - 1) * sizes.space1 + 2 * sizes.space1, 0);
		await page.locator('[data-shape-choice="distribution"]').click();
		await settle(page);
		expect(Math.abs((await read()).height - flowRow.height)).toBeLessThanOrEqual(0.5);
	});
	});
}

test('row20 I7, I9 and I10: Flow keeps long names, its floating Dropped list and one readout tab stop', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await openExplorer(page, PINNED);
	await openChart(page, "SELECT 's' || i AS stage, 170-i AS summary_prefill_tokens_per_s, 169-i AS went, 1 AS dropped FROM range(0, 170) AS t(i)");
	await page.locator('[data-shape-choice="flow"]').click();
	for (const width of [390, 768, 1024, 1399, 1400, 1440]) {
		await page.setViewportSize({ width, height: 900 });
		await settle(page);
		await expect(pill(page, 'arrived').locator('summary')).toHaveAttribute('aria-label', 'Arrived: summary_prefill_tokens_per_s');
		const name = await pill(page, 'arrived').locator('[data-pill-name]').evaluate((node) => ({ width: node.clientWidth, content: node.scrollWidth }));
		if (width !== 1399) expect(name.content).toBeLessThanOrEqual(name.width);
		if (width === 1399 || width === 1400) {
			const tops = await page.locator('[data-chart-roles] summary').evaluateAll((nodes) => nodes.map((node) => Math.round(node.getBoundingClientRect().top)));
			expect(new Set(tops).size).toBe(width === 1399 ? 2 : 1);
		}
	}
	await page.setViewportSize({ width: 390, height: 844 });
	await page.locator('[data-workbench-region="answer"]').evaluate((node) => node.scrollIntoView({ block: 'start' }));
	const before = await page.evaluate(() => window.scrollY);
	await pill(page, 'dropped').locator('summary').click();
	const list = await pill(page, 'dropped').locator('[data-pill-list]').boundingBox();
	expect(list!.y).toBeGreaterThanOrEqual(0);
	expect(list!.y + list!.height).toBeLessThanOrEqual(844);
	expect(await page.evaluate(() => window.scrollY)).toBe(before);
	await page.keyboard.press('Escape');
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.getByRole('tab', { name: 'Chart' }).focus();
	for (const next of [
		page.locator('[data-shape-choice="flow"] input'),
		pill(page, 'stage').locator('summary'),
		pill(page, 'arrived').locator('summary'),
		pill(page, 'wentOn').locator('summary'),
		pill(page, 'dropped').locator('summary'),
		page.locator('[data-chart-type="flow"][tabindex], [data-chart-type="flow"] ol[tabindex]')
	]) {
		await page.keyboard.press('Tab');
		await expect(next).toBeFocused();
	}
	await page.locator('[data-shape-choice="distribution"]').click();
	await page.getByRole('tab', { name: 'Chart' }).focus();
	for (const next of [page.locator('[data-shape-choice="distribution"] input'), pill(page, 'values').locator('summary'), page.locator('[data-chart-type="distribution"][tabindex]')]) {
		await page.keyboard.press('Tab');
		await expect(next).toBeFocused();
	}
});

/** Wait two frames, so a layout shift the last action caused has been reported. */
async function settle(page: Page) {
	await page.evaluate(() => new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(done, 50)))));
}

type ChartReading = { boxes: Record<string, Box>; starts: Record<string, { x: number; y: number }>; pills: (Box | null)[]; scrollY: number; shift: number; sources: ShiftSource[] };

/** Every box on the Chart tab that a choice must not move, where each tile's word starts, and the
 *  pill each slot holds. A word's start is read on its own, because a browser reports a moved
 *  start of under 3 px as no shift at all, so a narrow face hides what a wider one shows. */
async function chartReading(page: Page): Promise<ChartReading> {
	return page.evaluate(() => {
		const read = (node: Element) => {
			const rect = node.getBoundingClientRect();
			return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
		};
		const boxes: Record<string, Box> = {};
		for (const [name, selector] of [['region', '[data-workbench-region="answer"]'], ['strip', '.result-tabs'], ['roles', '[data-chart-roles]'], ['drawing', '[data-chart-drawing]'], ['foot', '[data-chart-foot]']]) {
			const node = document.querySelector(selector);
			if (node === null) throw new Error(`${selector} was not found`);
			boxes[name] = read(node);
		}
		document.querySelectorAll('[role="tab"]').forEach((tab) => (boxes[`tab ${tab.textContent?.trim()}`] = read(tab)));
		document.querySelectorAll('[data-shape-choice]').forEach((tile) => (boxes[`tile ${tile.getAttribute('data-shape-choice')}`] = read(tile)));
		const starts: Record<string, { x: number; y: number }> = {};
		document.querySelectorAll('[data-shape-choice] .choice-shown').forEach((word) => {
			const { x, y } = word.getBoundingClientRect();
			starts[`word ${word.closest('[data-shape-choice]')?.getAttribute('data-shape-choice')}`] = { x, y };
		});
		const slots = [...document.querySelectorAll('[data-role-slot]')];
		slots.forEach((slot) => (boxes[`slot ${slot.getAttribute('data-role-slot')}`] = read(slot)));
		const held = window as typeof window & { __explorerShift?: number; __explorerSources?: ShiftSource[] };
		return {
			boxes,
			starts,
			pills: slots.map((slot) => {
				const pill = slot.querySelector('summary');
				return pill === null ? null : read(pill);
			}),
			scrollY: window.scrollY,
			shift: held.__explorerShift ?? 0,
			sources: held.__explorerSources ?? []
		};
	});
}

/** Nothing outside the drawing moved: no layout shift, no scroll, every box where it was, every
 *  tile's word starting where it started, and each pill exactly filling its slot. */
function expectChartStill(before: ChartReading, after: ChartReading, label: string) {
	expect(after.shift, `${label}: layout shift sources ${JSON.stringify(after.sources, null, 2)}`).toBe(0);
	expect(after.scrollY, `${label}: the page scrolled`).toBe(before.scrollY);
	expect(Object.keys(after.boxes).sort(), `${label}: the parts on the tab`).toEqual(Object.keys(before.boxes).sort());
	for (const [name, box] of Object.entries(before.boxes)) {
		for (const side of ['x', 'y', 'width', 'height'] as const) expect(after.boxes[name][side], `${label}: ${name} ${side}`).toBeCloseTo(box[side], 0);
	}
	expect(Object.keys(after.starts).sort(), `${label}: the tiles' words`).toEqual(Object.keys(before.starts).sort());
	for (const [name, start] of Object.entries(before.starts)) {
		for (const side of ['x', 'y'] as const) expect(after.starts[name][side], `${label}: ${name} starts at another ${side}`).toBeCloseTo(start[side], 0);
	}
	after.pills.forEach((pill, index) => {
		if (pill === null) return;
		const slot = after.boxes[`slot ${index}`];
		for (const side of ['x', 'y', 'width', 'height'] as const) expect(pill[side], `${label}: pill ${index} ${side} against its slot`).toBeCloseTo(slot[side], 0);
	});
}

/** The page's own sizes, in pixels, so a check is computed from the tokens and never from a constant. */
async function tokens(page: Page) {
	return page.evaluate(() => {
		const css = getComputedStyle(document.documentElement);
		const rem = parseFloat(css.fontSize);
		const px = (name: string, from: CSSStyleDeclaration = css) => {
			const value = from.getPropertyValue(name).trim();
			return value.endsWith('rem') ? parseFloat(value) * rem : parseFloat(value);
		};
		const workbench = getComputedStyle(document.querySelector('.workbench')!);
		return {
			control: px('--workbench-control'),
			space1: px('--space-1'),
			space2: px('--space-2'),
			space3: px('--space-3'),
			textXs: px('--text-xs'),
			leadingSm: px('--leading-sm'),
			leadingBase: px('--leading-base'),
			leadingXl: px('--leading-xl'),
			// The line a chart's readout takes, which sets no line height of its own: the page's.
			lineShare: css.lineHeight.endsWith('px') ? parseFloat(css.lineHeight) / parseFloat(css.fontSize) : parseFloat(css.lineHeight),
			// `console.chart_height`, as the page hands it to the chart.
			chartHeight: px('--idle-height', workbench)
		};
	});
}

/** The band each of the four widths in `VIEWS` falls in, cut at `frame.breakpoints_px`. */
const BAND: Record<number, number> = { 390: 0, 768: 1, 1024: 2, 1440: 3 };

type Sizes = Awaited<ReturnType<typeof tokens>>;

/** The result region's floor at `width`, from the page's tokens (row 26 rule 5): the strip, the role
 *  row, and the drawing's floor - the main figure's line, the plot, the date chart's readout, the
 *  comparison's line and the space between them. */
function resultFloor(sizes: Sizes, width: number): number {
	const stripLines = width < 640 ? 2 : 1;
	const strip = stripLines * sizes.control + (stripLines + 1) * sizes.space1;
	const roleLines = ROLE_LINES[width];
	const roles = roleLines * sizes.control + (roleLines - 1) * sizes.space1 + 2 * sizes.space1;
	const readout = sizes.space3 + sizes.space1 + sizes.space2 + 3 * sizes.lineShare * sizes.textXs;
	return strip + roles + sizes.leadingXl + sizes.space3 + sizes.chartHeight + readout + sizes.leadingBase + sizes.space3;
}

/** How tall the foot is for an answer that can give `notes` notes, at `width` (row 26 rule 2). */
function footRoom(sizes: Sizes, notes: number, width: number): number {
	return notes === 0 ? 0 : notes * explorerConfig().chart_note_lines[BAND[width]] * sizes.leadingSm + 2 * sizes.space1;
}

async function openChart(page: Page, sql = CHART_SQL) {
	await chooseExplorerQuestion(page, ['published'], sql);
	await runExplorer(page);
	await expectAnswer(page, 'table');
	await page.getByRole('tab', { name: 'Chart' }).click();
	await page.locator('[data-workbench-region="answer"]').evaluate((node) => node.scrollIntoView({ block: 'start', behavior: 'instant' }));
	await settle(page);
}

function pill(page: Page, role: string) {
	return page.locator(`[data-chart-roles] .column-picker[data-role="${role}"]`);
}

for (const view of VIEWS) {
	test(`I1, I2, I13 and I15: the role row stands between the strip and the drawing, the lists float and nothing is cut off, at ${view.width}px`, async ({ page, context }) => {
		await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		const sizes = await tokens(page);
		// In the page's own coordinates, because the test scrolls the answer into view between readings.
		const strip = async () => page.locator('.result-tabs').evaluate((node) => {
			const rect = node.getBoundingClientRect();
			return { x: rect.x + window.scrollX, y: rect.y + window.scrollY, width: rect.width, height: rect.height };
		});
		// I2: the strip is the same box with either tab open, two lines below 640 px and one above.
		const tableStrip = await strip();
		const lines = view.width < 640 ? 2 : 1;
		expect(tableStrip.height, 'the strip is not its lines tall').toBeCloseTo(lines * sizes.control + (lines + 1) * sizes.space1, 0);
		await page.getByRole('tab', { name: 'Chart' }).click();
		closeBox(tableStrip, await strip());
		await page.getByRole('tab', { name: 'Table' }).click();
		await openChart(page);
		await expect(page.locator('.result-tabs [data-shape-choice]')).toHaveCount(7);
		await expect(page.locator('.result-tabs').getByRole('button', { name: /^Copy as/ })).toHaveCount(0);
		await page.locator('[data-shape-choice="pairedScatter"]').click();
		await settle(page);
		// I1: the role row is the chart panel's first row, from the strip's foot to the drawing's top.
		const placed = await page.evaluate(() => {
			const panel = document.querySelector('#data-explorer-shape')!.getBoundingClientRect();
			const roles = document.querySelector('[data-chart-roles]')!;
			const at = roles.getBoundingClientRect();
			return {
				panelTop: panel.top,
				stripBottom: document.querySelector('.result-tabs')!.getBoundingClientRect().bottom,
				top: at.top,
				bottom: at.bottom,
				height: at.height,
				drawingTop: document.querySelector('[data-chart-drawing]')!.getBoundingClientRect().top,
				pillTops: [...roles.querySelectorAll('summary')].map((summary) => Math.round(summary.getBoundingClientRect().top))
			};
		});
		expect(placed.pillTops, 'Paired does not show its three pills').toHaveLength(3);
		expect(Math.abs(placed.top - placed.panelTop), 'the role row is not the panel\'s first row').toBeLessThanOrEqual(0.5);
		expect(Math.abs(placed.top - placed.stripBottom), 'the role row does not start at the strip\'s foot').toBeLessThanOrEqual(0.5);
		expect(Math.abs(placed.bottom - placed.drawingTop), 'the role row does not end at the drawing\'s top').toBeLessThanOrEqual(0.5);
		expect(new Set(placed.pillTops).size, 'the pills stand on the wrong number of lines').toBe(Math.ceil(3 / (view.width >= 1400 ? 4 : view.width >= 1024 ? 3 : view.width >= 640 ? 2 : 1)));
		const rows = ROLE_LINES[view.width];
		expect(placed.height).toBeCloseTo(rows * sizes.control + (rows - 1) * sizes.space1 + 2 * sizes.space1, 0);
		// I15: the role row takes height, not width, so the plot still covers the panel's width.
		if (view.width !== 1024) {
			const fill = judgeFill(await readPanel(page.locator('[data-console-panel-id="data-explorer-shape"]')), consolePanels().fillFloor);
			expect(fill.pass, fill.says).toBe(true);
		}
		// Nothing on the strip or the Chart tab is cut off, with every pill's list closed and open.
		expect(await cutOffControls(page, ['answer'], []), `${view.width}px, every list closed`).toEqual([]);
		for (const role of ['across', 'up', 'name']) {
			await startShiftObserver(page);
			const before = await chartReading(page);
			await pill(page, role).locator('summary').click();
			await expect(pill(page, role).locator('[data-pill-list]')).toBeVisible();
			await settle(page);
			// I13: opening the list moves nothing; it floats over the drawing.
			expectChartStill(before, await chartReading(page), `${role} list opened`);
			expect(await cutOffControls(page, ['answer'], [], '.column-picker[open] [data-pill-list]'), `${view.width}px, ${role} open`).toEqual([]);
			// I13: it closes on Escape, with focus on its pill.
			await page.keyboard.press('Escape');
			await expect(pill(page, role).locator('[data-pill-list]')).toBeHidden();
			await expect(pill(page, role).locator('summary')).toBeFocused();
			await settle(page);
			expectChartStill(before, await chartReading(page), `${role} list closed`);
		}
		// I13: a press outside closes it, and a pick in a one-column list closes it with focus on its pill.
		// The press lands on the open tab, which the list never covers at any width and which does nothing more.
		await pill(page, 'across').locator('summary').click();
		await page.getByRole('tab', { name: 'Chart' }).click();
		await expect(pill(page, 'across').locator('[data-pill-list]')).toBeHidden();
		await expect(page.getByRole('tab', { name: 'Chart' })).toHaveAttribute('aria-selected', 'true');
		await pill(page, 'across').locator('summary').click();
		await pill(page, 'across').locator('[data-column="other"] input').click();
		await expect(pill(page, 'across').locator('[data-pill-list]')).toBeHidden();
		await expect(pill(page, 'across').locator('summary')).toBeFocused();
		await expect(pill(page, 'across').locator('[data-pill-name]')).toHaveText('other');
		// I2, after an answer as before one: the strip's box is the same with either tab open, the copy
		// buttons stand on it only while Table is open, and the tiles only while Chart is.
		const answeredStrip = await strip();
		expect(answeredStrip.height, 'the strip is not its lines tall').toBeCloseTo(tableStrip.height, 0);
		await page.getByRole('tab', { name: 'Table' }).click();
		await expect(page.locator('.result-tabs [data-shape-choice]')).toHaveCount(0);
		await expect(page.locator('.result-tabs').getByRole('button', { name: /^Copy as/ })).toHaveCount(2);
		closeBox(answeredStrip, await strip());
	});

	test(`I3, I4 and T9: a change of chart or of column moves nothing outside the drawing, at ${view.width}px`, async ({ page, context }) => {
		await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		await openChart(page);
		for (const tile of await page.locator('[data-shape-choice] input').all()) await expect(tile, 'two date columns picked a chart').not.toBeChecked();
		// The answer gives a note: the page's own lines leave `tiny` out as flat. So the foot that
		// must hold still is a real box, one note's room under every chart (row 26's I3).
		const sizes = await tokens(page);
		const foot = page.locator('[data-chart-foot]');
		expect(Math.abs((await foot.evaluate((node) => node.getBoundingClientRect().height)) - footRoom(sizes, 1, view.width)), 'the foot is not one note\'s room').toBeLessThanOrEqual(0.5);
		// I3 by a press, from every tile to every other.
		for (const from of CHART_TYPES) {
			for (const to of CHART_TYPES) {
				if (from === to) continue;
				await page.locator(`[data-shape-choice="${from}"]`).click();
				await settle(page);
				await startShiftObserver(page);
				const before = await chartReading(page);
				await page.locator(`[data-shape-choice="${to}"]`).click();
				await settle(page);
				expectChartStill(before, await chartReading(page), `${from} to ${to}`);
				await expect(page.locator(`[data-shape-choice="${to}"] input`)).toBeFocused();
			}
		}
		// Over time names the flat line in the foot; Ranked, where that note and the one for rows with
		// no day do not show, keeps their room empty.
		await page.locator('[data-shape-choice="dateSeries"]').click();
		await expect(foot.locator('[data-shape-foot]')).toHaveText(['"tiny" is left out: it is under 5% of "other", so it would draw flat.']);
		await page.locator('[data-shape-choice="rankedList"]').click();
		await expect(foot.locator('[data-shape-foot]')).toHaveCount(0);
		expect(Math.abs((await foot.evaluate((node) => node.getBoundingClientRect().height)) - footRoom(sizes, 1, view.width)), 'Ranked gave the foot\'s room away').toBeLessThanOrEqual(0.5);
		// I3 by an arrow key, along the tiles and back.
		await page.locator('[data-shape-choice="dateSeries"]').click();
		for (const [key, to] of [['ArrowRight', 'rankedList'], ['ArrowRight', 'pairedScatter'], ['ArrowRight', 'distribution'], ['ArrowLeft', 'pairedScatter'], ['ArrowLeft', 'rankedList'], ['ArrowLeft', 'dateSeries']] as const) {
			await settle(page);
			await startShiftObserver(page);
			const before = await chartReading(page);
			await page.keyboard.press(key);
			await settle(page);
			expectChartStill(before, await chartReading(page), `${key} to ${to}`);
			await expect(page.locator(`[data-shape-choice="${to}"] input`)).toBeFocused();
			await expect(page.locator(`[data-shape-choice="${to}"] input`)).toBeChecked();
		}
		// I4: for each pill, open it and pick another column; in the several-column list check one and uncheck it.
		const picks: { type: (typeof CHART_TYPES)[number]; role: string; column: string }[] = [
			{ type: 'dateSeries', role: 'date', column: 'stamp' },
			{ type: 'rankedList', role: 'name', column: 'across' },
			{ type: 'rankedList', role: 'rankBy', column: 'up' },
			{ type: 'pairedScatter', role: 'across', column: 'other' },
			{ type: 'pairedScatter', role: 'up', column: 'across' },
			{ type: 'pairedScatter', role: 'name', column: '' },
			{ type: 'distribution', role: 'values', column: 'up' }
		];
		for (const { type, role, column } of picks) {
			await page.locator(`[data-shape-choice="${type}"]`).click();
			await settle(page);
			await startShiftObserver(page);
			const before = await chartReading(page);
			await pill(page, role).locator('summary').click();
			await pill(page, role).locator(`[data-column="${column}"] input`).click();
			await expect(pill(page, role).locator('[data-pill-list]')).toBeHidden();
			await settle(page);
			expectChartStill(before, await chartReading(page), `${type} ${role} to ${column || 'Row number'}`);
			await expect(pill(page, role).locator('summary')).toBeFocused();
		}
		await page.locator('[data-shape-choice="dateSeries"]').click();
		await settle(page);
		await startShiftObserver(page);
		const before = await chartReading(page);
		await pill(page, 'lines').locator('summary').click();
		const tiny = pill(page, 'lines').locator('[data-column="tiny"] input');
		await expect(tiny, 'the flat column was checked by default').not.toBeChecked();
		await tiny.click();
		await expect(tiny).toBeChecked();
		await tiny.click();
		await expect(tiny).not.toBeChecked();
		await page.keyboard.press('Escape');
		await expect(pill(page, 'lines').locator('[data-pill-list]')).toBeHidden();
		await settle(page);
		expectChartStill(before, await chartReading(page), 'Lines checked and unchecked');
		await expect(pill(page, 'lines').locator('summary')).toBeFocused();
		// I4 for the foot (row 26): an answer that can give two notes, a flat line and a row with no
		// day in `gappy`. Picking `gappy`, then `day`, then unchecking a line while the flat line is
		// named changes the foot's text and never its box. A fresh page, so no earlier pick holds.
		await openExplorer(page, PINNED);
		await openChart(page, GAPPY_SQL);
		await page.locator('[data-shape-choice="dateSeries"]').click();
		await settle(page);
		await expect(foot.locator('[data-shape-foot]')).toHaveText([FLAT_TINY]);
		expect(Math.abs((await foot.evaluate((node) => node.getBoundingClientRect().height)) - footRoom(sizes, 2, view.width)), 'the foot is not two notes\' room').toBeLessThanOrEqual(0.5);
		await startShiftObserver(page);
		const held = await chartReading(page);
		await pill(page, 'date').locator('summary').click();
		await pill(page, 'date').locator('[data-column="gappy"] input').click();
		await settle(page);
		await expect(foot.locator('[data-shape-foot]')).toHaveText([FLAT_TINY, '1 row holds null in the column "gappy", so the chart does not draw it. It is in the table.']);
		expectChartStill(held, await chartReading(page), 'Date to a column with a null day');
		await pill(page, 'date').locator('summary').click();
		await pill(page, 'date').locator('[data-column="day"] input').click();
		await settle(page);
		await expect(foot.locator('[data-shape-foot]')).toHaveText([FLAT_TINY]);
		expectChartStill(held, await chartReading(page), 'Date back to a column with every day');
		await pill(page, 'lines').locator('summary').click();
		await pill(page, 'lines').locator('[data-column="up"] input').click();
		await page.keyboard.press('Escape');
		await settle(page);
		await expect(foot.locator('[data-shape-foot]')).toHaveCount(0);
		expectChartStill(held, await chartReading(page), 'a line unchecked while the flat line was named');
	});
}

/** Two date columns, `gappy` with no day on one row, and a column too flat to draw beside two that
 *  are not: an answer that can give two notes under Over time, whichever of them shows. */
const GAPPY_SQL = "SELECT DATE '2026-01-01' + i::INTEGER AS day, CASE WHEN i = 3 THEN NULL ELSE DATE '2026-01-01' + i::INTEGER END AS gappy, 100 + i AS across, 200 - i AS up, 0 AS tiny FROM range(0, 30) AS t(i)";
const FLAT_TINY = '"tiny" is left out: it is under 5% of "up", so it would draw flat.';

/** Three answers and the notes each can give: an Over time chart whose page lines leave `tiny` out
 *  as flat, the same chart with nothing to leave out, and a paired chart, whose readout is shorter. */
const FLOOR_ANSWERS = [
	{ sql: "SELECT DATE '2026-01-01' + i::INTEGER AS day, 100 + i AS a, 0 AS tiny FROM range(0, 30) AS t(i)", notes: 1, said: ['"tiny" is left out: it is under 5% of "a", so it would draw flat.'] },
	{ sql: "SELECT DATE '2026-01-01' + i::INTEGER AS day, 100 + i AS a FROM range(0, 30) AS t(i)", notes: 0, said: [] },
	{ sql: 'SELECT i AS a, 200 - i AS b FROM range(0, 170) AS t(i)', notes: 0, said: [] }
] as const;

for (const view of VIEWS) {
	test(`I1: the result region keeps its floor, the foot holds only the notes the answer can give, and no plot scrolls inside the drawing, at ${view.width}px`, async ({ page, context }) => {
		await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		const sizes = await tokens(page);
		const floor = resultFloor(sizes, view.width);
		for (const { sql, notes, said } of FLOOR_ANSWERS) {
			await openChart(page, sql);
			await page.locator('[data-chart-drawing] svg[data-chart-type]').waitFor({ state: 'visible', timeout: 60_000 });
			await settle(page);
			await expect(page.locator('[data-chart-foot] [data-shape-foot]')).toHaveText([...said]);
			const at = await page.evaluate(() => {
				const box = (selector: string) => document.querySelector(selector)!.getBoundingClientRect();
				const drawing = document.querySelector('[data-chart-drawing]') as HTMLElement;
				const root = document.documentElement;
				return {
					region: box('[data-workbench-region="answer"]').height,
					foot: box('[data-chart-foot]').height,
					drawingBottom: box('[data-chart-drawing]').bottom,
					panelBottom: box('#data-explorer-shape').bottom,
					drawingScrolls: drawing.scrollHeight > drawing.clientHeight,
					plot: box('[data-chart-drawing] svg[data-chart-type]').height,
					pageScrolls: root.scrollHeight > root.clientHeight
				};
			});
			const label = `${view.width}px, ${notes} note(s)`;
			expect(at.region, `${label}: the region is under its floor`).toBeGreaterThanOrEqual(floor - 0.5);
			expect(Math.abs(at.foot - footRoom(sizes, notes, view.width)), `${label}: the foot is ${at.foot} px tall`).toBeLessThanOrEqual(0.5);
			if (notes === 0) expect(Math.abs(at.drawingBottom - at.panelBottom), `${label}: the drawing does not reach the panel's foot`).toBeLessThanOrEqual(0.5);
			expect(at.drawingScrolls, `${label}: the drawing scrolls a plot`).toBe(false);
			expect(at.plot + at.foot, `${label}: the plot and the foot share less than the chart's height`).toBeGreaterThanOrEqual(sizes.chartHeight - 0.5);
			if (view.width === 1440) expect(at.pageScrolls, `${label}: the page scrolls`).toBe(false);
			if (view.width === 1024) {
				expect(Math.abs(at.region - floor), `${label}: the region is ${at.region} px, not its floor, ${floor} px`).toBeLessThanOrEqual(0.5);
				// The page's last scroll position shows the whole drawing, down to its comparison.
				await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' }));
				const comparison = await page.locator('[data-chart-drawing] [data-comparison]').evaluate((node) => {
					const rect = node.getBoundingClientRect();
					return { top: rect.top, bottom: rect.bottom, window: document.documentElement.clientHeight };
				});
				expect(comparison.top, `${label}: the comparison is above the window`).toBeGreaterThanOrEqual(-0.5);
				expect(comparison.bottom, `${label}: the comparison is below the window`).toBeLessThanOrEqual(comparison.window + 0.5);
			}
		}
	});
}

test('I6: across runs of one answer, and through a busy and a failed run, the drawing and the foot hold their boxes', async ({ page, context }) => {
	const root = test.info().outputPath('state');
	// item-health is fetched by no run until the busy one, so that run can be held on its fetch.
	await serveBuilt(context, root, { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) }, { ledger: 'item-health', pinned: PINNED, days: everyDay(1, 0) });
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	const sizes = await tokens(page);
	const boxes = () => page.evaluate(() => Object.fromEntries(['[data-chart-drawing]', '[data-chart-foot]'].map((selector) => {
		const rect = document.querySelector(selector)!.getBoundingClientRect();
		return [selector, { x: rect.x, y: rect.y, width: rect.width, height: rect.height }];
	})) as Record<string, Box>);
	const same = (first: Record<string, Box>, now: Record<string, Box>, label: string) => {
		for (const [name, box] of Object.entries(first)) {
			for (const side of ['x', 'y', 'width', 'height'] as const) expect(Math.abs(now[name][side] - box[side]), `${label}: ${name} ${side}`).toBeLessThanOrEqual(0.5);
		}
	};
	// Before the first answer the foot has no room.
	await page.getByRole('tab', { name: 'Chart' }).click();
	expect((await boxes())['[data-chart-foot]'].height, 'the foot has room before any answer').toBeLessThanOrEqual(0.5);
	await openChart(page);
	const first = await boxes();
	expect(Math.abs(first['[data-chart-foot]'].height - footRoom(sizes, 1, 1440)), 'the foot is not one note\'s room').toBeLessThanOrEqual(0.5);
	for (const run of [1, 2]) {
		await runExplorer(page);
		await expectAnswer(page, 'table');
		await settle(page);
		same(first, await boxes(), `run ${run} of the same answer`);
	}
	await chooseExplorerQuestion(page, ['published'], 'SELECT 1; SELECT 2');
	await runExplorer(page);
	await expectAnswer(page, 'refused');
	await settle(page);
	same(first, await boxes(), 'a refused run');
	await expect(page.locator('[data-chart-foot] [data-shape-foot]')).toHaveCount(0);
	// A run held on its fetch is busy until the test lets it fail, so the page answers unreachable.
	await chooseExplorerQuestion(page, ['item-health'], 'SELECT count(*) AS rows FROM "item-health"', false);
	let release!: () => void;
	const held = new Promise<void>((resolve) => { release = resolve; });
	await page.route('**/state/**/*.parquet*', async (route) => {
		await held;
		await route.abort();
	});
	await page.getByRole('button', { name: /^Run$/ }).click();
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-state="loading"]')).toHaveCount(1);
	await settle(page);
	same(first, await boxes(), 'a busy run');
	release();
	await expectAnswer(page, 'unreachable');
	await settle(page);
	same(first, await boxes(), 'a failed run');
});

for (const view of [{ width: 1440, height: 900 }, { width: 390, height: 844 }] as const) {
	test(`I5: switching between Table and Chart moves nothing in every state, with the role row in place, at ${view.width}px`, async ({ page, context }) => {
		const root = test.info().outputPath('state');
		// item-health holds two days, so a run reads one that choosing the ledger did not.
		await serveBuilt(context, root, { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) }, { ledger: 'item-health', pinned: PINNED, days: everyDay(1, 0) });
		await serveToPage(context, root, 'feed-health');
		const switchesStill = async (one: Page, state: string) => {
			await one.getByRole('tab', { name: 'Table' }).click();
			// The tabs are pressed where a person sees them, so the press itself scrolls nothing.
			await one.getByRole('tab', { name: 'Chart' }).scrollIntoViewIfNeeded();
			await startShiftObserver(one);
			const before = await snapshot(one);
			await one.getByRole('tab', { name: 'Chart' }).click();
			await expect(one.locator('[data-chart-roles]'), `${state}: no role row`).toBeVisible();
			expectStable(before, await snapshot(one));
			await one.getByRole('tab', { name: 'Table' }).click();
			expectStable(before, await snapshot(one));
		};
		await page.setViewportSize(view);
		await openExplorer(page, PINNED);
		await switchesStill(page, 'idle');
		await chooseExplorerQuestion(page, ['published'], CHART_SQL);
		await runExplorer(page);
		await switchesStill(page, 'answered');
		await page.getByRole('tab', { name: 'Chart' }).click();
		await page.locator('[data-shape-choice="dateSeries"]').click();
		await chooseExplorerQuestion(page, ['published'], "SELECT 'n' || i::VARCHAR AS name, i AS a FROM range(0, 5) AS t(i)");
		await runExplorer(page);
		await page.getByRole('tab', { name: 'Chart' }).click();
		await expect(page.locator('[data-shape-none]'), 'the chosen chart is not drawn with no date column').toHaveCount(1);
		await switchesStill(page, 'a needed role with no column');
		for (const [state, sql] of [['quiet', 'SELECT * FROM "published" WHERE false'], ['refused', 'SELECT 1; SELECT 2']] as const) {
			await chooseExplorerQuestion(page, ['published'], sql);
			await runExplorer(page);
			await expectAnswer(page, state);
			await switchesStill(page, state);
		}
		await chooseExplorerQuestion(page, ['feed-health'], 'SELECT count(*) AS rows FROM "feed-health"', false);
		await runExplorer(page);
		await expectAnswer(page, 'missing');
		await switchesStill(page, 'missing');
		// A page that already holds a file fetches nothing for it again, so a failed fetch and a held
		// one each start on a page of their own.
		const failing = await context.newPage();
		await failing.setViewportSize(view);
		await failing.route('**/state/**/*.parquet*', (route) => route.abort());
		await openExplorer(failing, PINNED);
		await chooseExplorerQuestion(failing, ['published'], 'SELECT count(*) AS rows FROM "published"', false);
		await runExplorer(failing);
		await expectAnswer(failing, 'unreachable');
		await switchesStill(failing, 'unreachable');
		await failing.close();
		const waiting = await context.newPage();
		await waiting.setViewportSize(view);
		await openExplorer(waiting, PINNED);
		await chooseExplorerQuestion(waiting, ['item-health'], 'SELECT count(*) AS rows FROM "item-health"');
		let release!: () => void;
		const held = new Promise<void>((resolve) => { release = resolve; });
		await waiting.route('**/state/**/*.parquet*', async (route) => {
			await held;
			await route.abort();
		});
		await waiting.getByRole('button', { name: /^Run$/ }).click();
		await expect(waiting.locator('[data-console-panel-id="data-explorer-rows"] [data-state="loading"]')).toHaveCount(1);
		await switchesStill(waiting, 'running');
		release();
		await waiting.close();
	});
}

test('I6: across four runs, each drawn by a different chart, the tiles keep their count, order and boxes, checked or not', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	const answers = [
		{ opens: 'dateSeries', sql: "SELECT * FROM (VALUES (DATE '2026-08-18', 3), (DATE '2026-08-19', 5), (DATE '2026-08-20', 8)) AS t(date, rows)" },
		{ opens: 'rankedList', sql: "SELECT * FROM (VALUES ('a', 9), ('b', 4), ('c', 2)) AS t(name, rows)" },
		{ opens: 'pairedScatter', sql: "SELECT 'row-' || i::VARCHAR AS name, i AS x, 170 - i AS y FROM range(0, 170) AS t(i)" },
		{ opens: 'distribution', sql: 'SELECT * FROM range(0, 170) AS t(rows)' }
	] as const;
	let first: Record<string, Box> | null = null;
	for (const { opens, sql } of answers) {
		await chooseExplorerQuestion(page, ['published'], sql);
		await runExplorer(page);
		await page.getByRole('tab', { name: 'Chart' }).click();
		await expect(page.locator(`[data-shape-choice="${opens}"] input`), `${opens} did not open`).toBeChecked();
		const tiles = await tileBoxes(page, '[data-shape-choice]', 'data-shape-choice');
		expect(Object.keys(tiles)).toEqual([...CHART_TYPES]);
		if (first === null) first = tiles;
		else expectTileBoxesStable(first, tiles, `after ${opens} opened`);
		await page.getByRole('tab', { name: 'Table' }).click();
	}
});

test.describe('on a phone, with touch', () => {
	test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });

	test('I7: a role over 128 columns, 88 of them numbers, lists exactly the numbers in the window and scrolls inside itself', async ({ page, context }) => {
		await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
		await openExplorer(page, PINNED);
		const wide = wideAnswer();
		await openChart(page, wide.sql);
		await page.locator('[data-shape-choice="distribution"]').tap();
		const values = pill(page, 'values');
		await values.locator('summary').tap();
		const list = values.locator('[data-pill-list]');
		await expect(list).toBeVisible();
		// A touch puts focus on the checked line, so the phone's keyboard does not rise until the filter is tapped.
		await expect(values.locator(`[data-column="${wide.numbers[0]}"] input`)).toBeFocused();
		expect(await list.locator('[data-column]').evaluateAll((lines) => lines.map((line) => line.getAttribute('data-column')))).toEqual(wide.numbers);
		const sizes = await tokens(page);
		const placed = await list.evaluate((node) => {
			const at = node.getBoundingClientRect();
			const region = node.closest('[data-workbench-region="chart"]')!.getBoundingClientRect();
			return {
				at: { left: at.left, top: at.top, right: at.right, bottom: at.bottom },
				region: { left: region.left, right: region.right },
				window: { width: document.documentElement.clientWidth, height: document.documentElement.clientHeight },
				pageWidth: { scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth },
				lines: [...node.querySelectorAll('.pill-line')].map((line) => line.getBoundingClientRect().height),
				scrolls: node.scrollHeight > node.clientHeight
			};
		});
		expect(placed.at.left).toBeGreaterThanOrEqual(-0.5);
		expect(placed.at.top).toBeGreaterThanOrEqual(-0.5);
		expect(placed.at.right).toBeLessThanOrEqual(placed.window.width + 0.5);
		expect(placed.at.bottom).toBeLessThanOrEqual(placed.window.height + 0.5);
		expect(placed.at.left).toBeGreaterThanOrEqual(placed.region.left - 0.5);
		expect(placed.at.right).toBeLessThanOrEqual(placed.region.right + 0.5);
		expect(placed.pageWidth.scroll).toBeLessThanOrEqual(placed.pageWidth.client);
		expect(Math.min(...placed.lines)).toBeGreaterThanOrEqual(sizes.control - 0.5);
		// Scrolled to its end with the wheel, the list takes the scroll and the page does not.
		expect(placed.scrolls, 'the list does not scroll, so this proves nothing').toBe(true);
		const scrollY = await page.evaluate(() => window.scrollY);
		const listBox = (await list.boundingBox())!;
		await page.mouse.move(listBox.x + listBox.width / 2, listBox.y + listBox.height / 2);
		for (let turn = 0; turn < 40 && !(await list.evaluate((node) => node.scrollTop + node.clientHeight >= node.scrollHeight - 1)); turn += 1) {
			await page.mouse.wheel(0, 600);
		}
		expect(await list.evaluate((node) => node.scrollTop + node.clientHeight >= node.scrollHeight - 1), 'the list did not reach its end').toBe(true);
		await page.mouse.wheel(0, 600);
		await settle(page);
		expect(await page.evaluate(() => window.scrollY)).toBe(scrollY);
	});
});

test('I8: the filter keeps the names that hold the typed text anywhere, in their order, and clearing it shows every one again', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	const wide = wideAnswer();
	await openChart(page, wide.sql);
	await page.locator('[data-shape-choice="distribution"]').click();
	const values = pill(page, 'values');
	await values.locator('summary').click();
	const filter = values.getByRole('searchbox', { name: 'Find a column' });
	await expect(filter, 'a mouse did not put focus in the filter').toBeFocused();
	const listed = () => values.locator('[data-column]').evaluateAll((lines) => lines.map((line) => line.getAttribute('data-column')));
	await page.keyboard.type('decode');
	expect(await listed()).toEqual(wide.numbers.filter((name) => name.includes('decode')));
	expect(await listed()).toHaveLength(5);
	await filter.fill('');
	expect(await listed()).toEqual(wide.numbers);
	await filter.fill('no-such-name');
	await expect(values.locator('.pill-note')).toHaveText('No column here has "no-such-name" in its name.');
});

test('I7 and I13: a pill near the window\'s foot opens its list over itself, inside the window, with every line reachable, and moves nothing', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 390, height: 844 });
	await openExplorer(page, PINNED);
	await openChart(page);
	await page.locator('[data-shape-choice="dateSeries"]').click();
	const lines = pill(page, 'lines');
	// Scroll the page until the pill stands just above the window's foot, as a reader may leave it.
	const before = (await lines.locator('summary').boundingBox())!;
	await page.evaluate((by) => window.scrollBy({ top: by, behavior: 'instant' }), before.y + before.height - (844 - 8));
	const near = (await lines.locator('summary').boundingBox())!;
	expect(844 - (near.y + near.height), 'the pill is not near the window\'s foot, so this proves nothing').toBeLessThan(near.height);
	await settle(page);
	await startShiftObserver(page);
	const still = await chartReading(page);
	await lines.locator('summary').click();
	const list = lines.locator('[data-pill-list]');
	await expect(list).toBeVisible();
	await settle(page);
	expectChartStill(still, await chartReading(page), 'Lines list opened near the foot');
	const at = (await list.boundingBox())!;
	expect(at.y + at.height, 'the list does not hang over its pill').toBeLessThanOrEqual(near.y + 0.5);
	expect(at.y).toBeGreaterThanOrEqual(-0.5);
	expect(await list.evaluate((node) => node.scrollHeight <= node.clientHeight), 'the list has room for every line').toBe(true);
	const tiny = lines.locator('[data-column="tiny"] input');
	await tiny.click();
	await expect(tiny).toBeChecked();
	await page.keyboard.press('Escape');
	await expect(list).toBeHidden();
});

/** 128 columns as `SELECT * FROM "item-health"` returns them: 88 numbers that share a few starts,
 *  five of them about decoding, among 40 text columns. */
function wideAnswer(): { sql: string; numbers: string[] } {
	const decode = ['label_decode_tokens_per_s', 'summary_decode_tokens_per_s', 'label_decode_ms', 'summary_decode_ms', 'os_mem_decode_peak_bytes'];
	const starts = ['label', 'summary', 'os_mem'];
	const numbers: string[] = [];
	const parts: string[] = [];
	for (let index = 0; index < 128; index += 1) {
		if (index % 16 < 11) {
			const name = numbers.length % 17 === 3 && decode.length > 0 ? (decode.shift() as string) : `${starts[numbers.length % 3]}_reading_${numbers.length}`;
			numbers.push(name);
			parts.push(`${numbers.length} AS ${name}`);
		} else {
			parts.push(`'v' AS text_${index}`);
		}
	}
	return { sql: `SELECT ${parts.join(', ')}`, numbers };
}

test('I9: a 28-character name stands whole beside the longest role word, and a 60-character alias is cut on the pill alone', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await openExplorer(page, PINNED);
	for (const view of VIEWS) {
		await page.setViewportSize(view);
		await openChart(page, "SELECT * FROM (VALUES ('a', 5), ('b', 3)) AS t(name, summary_prefill_tokens_per_s)");
		const name = pill(page, 'rankBy').locator('[data-pill-name]');
		await expect(name).toHaveText('summary_prefill_tokens_per_s');
		expect(await name.evaluate((node) => node.scrollWidth <= node.clientWidth), `${view.width}px cut the name`).toBe(true);
	}
	const alias = 'a_sixty_character_alias_that_an_operator_typed_in_a_question';
	expect(alias).toHaveLength(60);
	for (const view of [{ width: 1440, height: 900 }, { width: 390, height: 844 }] as const) {
		await page.setViewportSize(view);
		await openChart(page, `SELECT i AS ${alias} FROM range(0, 170) AS t(i)`);
		const name = pill(page, 'values').locator('[data-pill-name]');
		expect(await name.evaluate((node) => node.scrollWidth > node.clientWidth && getComputedStyle(node).textOverflow === 'ellipsis'), `${view.width}px did not end the alias in an ellipsis`).toBe(true);
		await expect(pill(page, 'values').locator('summary')).toHaveAttribute('aria-label', `Values: ${alias}`);
		await expect(page.locator('[data-console-panel-id="data-explorer-shape"] svg[data-chart-type="distribution"]')).toHaveAttribute('aria-label', `Spread: ${alias}`);
		await pill(page, 'values').locator('summary').click();
		await expect(pill(page, 'values').locator(`[data-column="${alias}"] code`)).toHaveText(alias);
		await page.keyboard.press('Escape');
	}
});

test('I10: Tab runs from the tab to the checked tile, each pill and the readout, and back; a list closes on Escape and when Tab leaves it', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	await openChart(page, "SELECT DATE '2026-01-01' + i::INTEGER AS day, 'n' || i::VARCHAR AS name, i AS across, 200 - i AS up FROM range(0, 170) AS t(i)");
	const chartTab = page.getByRole('tab', { name: 'Chart' });
	const stops = [
		chartTab,
		page.locator('[data-shape-choice="dateSeries"] input'),
		pill(page, 'date').locator('summary'),
		pill(page, 'lines').locator('summary'),
		page.locator('[data-console-panel-id="data-explorer-shape"] svg[data-chart-type="dateSeries"]')
	];
	await chartTab.focus();
	await page.keyboard.press('Shift+Tab');
	for (const stop of stops) {
		await page.keyboard.press('Tab');
		await expect(stop).toBeFocused();
	}
	for (const stop of [...stops].reverse().slice(1)) {
		await page.keyboard.press('Shift+Tab');
		await expect(stop).toBeFocused();
	}
	// Left and Right on a tab move between the two tabs, never to a tile.
	await page.keyboard.press('ArrowRight');
	await expect(page.getByRole('tab', { name: 'Table' })).toBeFocused();
	await page.keyboard.press('ArrowLeft');
	await expect(chartTab).toBeFocused();
	// With Paired, the three pills follow the tile in order.
	await page.locator('[data-shape-choice="pairedScatter"]').click();
	for (const role of ['across', 'up', 'name']) {
		await page.keyboard.press('Tab');
		await expect(pill(page, role).locator('summary')).toBeFocused();
	}
	// A list opened from the keyboard closes on Escape with focus on its pill.
	await pill(page, 'across').locator('summary').focus();
	await page.keyboard.press('Enter');
	await expect(pill(page, 'across').locator('[data-pill-list]')).toBeVisible();
	await page.keyboard.press('Escape');
	await expect(pill(page, 'across').locator('[data-pill-list]')).toBeHidden();
	await expect(pill(page, 'across').locator('summary')).toBeFocused();
	// Down opens it too; Tab moves from the filter to the lines, then out to the next pill and closes it.
	await page.keyboard.press('ArrowDown');
	await expect(pill(page, 'across').getByRole('searchbox', { name: 'Find a column' })).toBeFocused();
	await page.keyboard.press('Tab');
	await expect(pill(page, 'across').locator('[data-column="across"] input')).toBeFocused();
	await page.keyboard.press('Tab');
	await expect(pill(page, 'up').locator('summary')).toBeFocused();
	await expect(pill(page, 'across').locator('[data-pill-list]')).toBeHidden();
	// Up and Down move between lines without picking; Enter picks one and closes the list.
	await page.keyboard.press('Shift+Tab');
	await page.keyboard.press('Enter');
	await page.keyboard.press('ArrowDown');
	await page.keyboard.press('ArrowDown');
	await expect(pill(page, 'across').locator('[data-column="up"] input')).toBeFocused();
	await expect(pill(page, 'across').locator('[data-pill-name]')).toHaveText('across');
	await page.keyboard.press('Enter');
	await expect(pill(page, 'across').locator('[data-pill-list]')).toBeHidden();
	await expect(pill(page, 'across').locator('[data-pill-name]')).toHaveText('up');
	await expect(pill(page, 'across').locator('summary')).toBeFocused();
});

test('I11 and I12: a role the chart needs with no column keeps a quiet pill and the box says why; one it can do without draws without it', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	await openChart(page, "SELECT 'n' || i::VARCHAR AS name, i AS a FROM range(0, 5) AS t(i)");
	await expect(page.locator('[data-shape-choice="rankedList"] input')).toBeChecked();
	await startShiftObserver(page);
	const drawn = await chartReading(page);
	await page.locator('[data-shape-choice="dateSeries"]').click();
	await settle(page);
	expectChartStill(drawn, await chartReading(page), 'Ranked to Over time with no date column');
	const date = pill(page, 'date');
	await expect(date.locator('summary')).toHaveAttribute('aria-disabled', 'true');
	await expect(date.locator('[data-pill-name]')).toHaveText('None');
	await expect(date.locator('.pill-mark'), 'the empty pill shows a chevron').toHaveCount(0);
	await expect(date.locator('summary')).not.toHaveAttribute('disabled');
	await page.keyboard.press('Tab');
	await expect(date.locator('summary'), 'the empty pill is not a Tab stop').toBeFocused();
	await page.keyboard.press('Enter');
	await expect(date.locator('[data-pill-list]'), 'the empty pill opened its list').toBeHidden();
	await expect(date).not.toHaveAttribute('open');
	const box = page.locator('[data-chart-drawing]');
	await expect(box.locator('[data-shape-none]')).toHaveCount(1);
	await expect(box.locator('[data-shape-none]')).toHaveText('Nothing here to draw: Over time needs a date or timestamp column for Date, and a number column for Lines. The ledgers keep their dates as text: CAST(date AS DATE) in the question makes a date column.');
	const said = await page.locator('[data-chart-roles]').evaluate((row) => ({
		row: (row as HTMLElement).innerText.replace(/\s+/g, ' ').trim(),
		pills: [...row.querySelectorAll('summary')].map((summary) => (summary as HTMLElement).innerText.replace(/\s+/g, ' ').trim()).join(' ')
	}));
	expect(said.row, 'the role row says something besides its pills').toBe(said.pills);
	await startShiftObserver(page);
	const empty = await chartReading(page);
	await page.locator('[data-shape-choice="rankedList"]').click();
	await settle(page);
	expectChartStill(empty, await chartReading(page), 'Over time back to Ranked');
	// I12: two numbers and no text column draw Paired with each row its own point (Susan's A7).
	await openChart(page, 'SELECT i AS a, 200 - i AS b FROM range(0, 170) AS t(i)');
	await page.locator('[data-shape-choice="pairedScatter"]').click();
	await expect(pill(page, 'name').locator('[data-pill-name]')).toHaveText('Row number');
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] svg[data-chart-type="pairedScatter"]')).toHaveCount(1);
	await expect(page.locator('[data-shape-none]')).toHaveCount(0);
});

test('I14: the column picker borrows the page\'s floating list and type label, and no other explorer file closes a list itself', () => {
	const folder = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'lib', 'console', 'explorer');
	const picker = readFileSync(path.join(folder, 'ColumnPicker.svelte'), 'utf8');
	expect(picker).toMatch(/from '\$lib\/console\/explorer\/floating-list'/);
	expect(picker).toMatch(/import ColumnType from '\$lib\/console\/explorer\/ColumnType\.svelte'/);
	// A file closes a list itself when it sets a list's `open` to false or reads the Escape key. A
	// press listener alone closes nothing: the ledger list's stops following the chosen ledger.
	const handlers = readdirSync(folder)
		.filter((name) => name !== 'floating-list.ts')
		.filter((name) => /open\s*=\s*false|removeAttribute\(\s*['"]open['"]|['"]Escape['"]/i.test(readFileSync(path.join(folder, name), 'utf8')));
	expect(handlers).toEqual([]);
});
