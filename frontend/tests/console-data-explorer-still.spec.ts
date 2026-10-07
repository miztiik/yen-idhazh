import { expect, test, type Page } from './support/browser';
import { chooseExplorerQuestion, expectAnswer, openExplorer, runExplorer, serveBuilt, type AnswerState } from './support/explorer-answer';
import { everyDay } from './support/ledger-lifecycle';
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
			const regions = Object.fromEntries(
				[...document.querySelectorAll('[data-workbench-region]')].map((node) => {
					const rect = node.getBoundingClientRect();
					return [node.getAttribute('data-workbench-region') ?? '', rect.height];
				})
			);
			return { control, space1, space2, space3, regions };
		});
		const oneControlRow = sizes.control + 2 * sizes.space1;
		expect(await page.locator('[data-workbench-region="editor"] .editor-head').evaluate((node) => node.getBoundingClientRect().height), `${view.width} editor head`).toBeGreaterThanOrEqual(oneControlRow - 1);
		if (view.width < 640) {
			expect(sizes.regions.questions, `${view.width} questions`).toBeCloseTo(2 * sizes.control + sizes.space1, 0);
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
				const cut = await page.evaluate(() => {
				// These regions never scroll, so a control outside them, or content past their
				// height, is cut off. The rails scroll by design, so they are held only sideways.
				const whole = ['questions', 'editor'];
				const sideways = ['ledgers', 'columns'];
				const offenders: string[] = [];
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
					const both = whole.includes(name);
					if (both && region.scrollHeight > region.clientHeight + 0.5) {
						offenders.push(`${name}: ${region.scrollHeight - region.clientHeight}px of content is hidden`);
					}
					const box = region.getBoundingClientRect();
					for (const control of region.querySelectorAll<HTMLElement>('button, input, select, textarea, a[href], summary')) {
						const rect = control.getBoundingClientRect();
						// checkVisibility() is false for a chip in a closed fold, which the page lays out but never draws.
						if (!visible(control)) continue;
						if (canScrollIntoView(control, rect, both)) continue;
						const across = rect.left >= box.left - 0.5 && rect.right <= box.right + 0.5;
						const down = rect.top >= box.top - 0.5 && rect.bottom <= box.bottom + 0.5;
						if (!across || (both && !down)) {
							offenders.push(`${name}: ${label(control)} at ${Math.round(rect.left)},${Math.round(rect.top)}-${Math.round(rect.right)},${Math.round(rect.bottom)} outside ${Math.round(box.left)},${Math.round(box.top)}-${Math.round(box.right)},${Math.round(box.bottom)}`);
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
				});
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
