import { expect, test, type Page } from './support/browser';
import { chooseExplorerQuestion, expectAnswer, openExplorer, runExplorer, serveBuilt, type AnswerState } from './support/explorer-answer';
import { everyDay } from './support/ledger-lifecycle';
import { explorerConfig } from '../src/lib/server/config';
import { statusSentence, statusWithHeld } from '../src/lib/console/explorer/status';

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
			['toolbar', '[data-workbench-region="toolbar"]'],
			['questions', '[data-workbench-region="questions"]'],
			['ledgers', '[data-workbench-region="ledgers"]'],
			['editor', '[data-workbench-region="editor"]'],
			['status', '[data-workbench-region="status"]'],
			['columns', '[data-workbench-region="columns"]'],
			['answer', '[data-workbench-region="answer"]'],
			['chart', '[data-workbench-region="chart"]'],
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
		const lede = page.locator('[data-console-panel-id="data-explorer-rows"] [data-lede]');
		const cases: { sql: string; state: AnswerState; rows: string | null }[] = [
			{ sql: 'SELECT count(*) AS rows FROM "published"', state: 'table', rows: '1 row' },
			{ sql: 'SELECT i AS row_number FROM range(0, 1200) AS t(i)', state: 'table', rows: 'The first 1000 rows' },
			{ sql: 'SELECT * FROM "published" WHERE false', state: 'quiet', rows: null },
			{ sql: 'SELECT 1; SELECT 2', state: 'refused', rows: null }
		];
		for (const { sql, state, rows } of cases) {
			await chooseExplorerQuestion(page, ['published'], sql);
			// Run is pressed where a person sees it, so the press itself scrolls nothing.
			await page.locator('.run-button').scrollIntoViewIfNeeded();
			await startShiftObserver(page);
			const before = await snapshot(page);
			await runExplorer(page);
			await expectAnswer(page, state);
			if (rows !== null) await expect(lede).toHaveText(rows);
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
	await expect(link).toHaveAttribute('href', /#data-explorer-rows$/);
	const overlap = await page.locator('[data-workbench-region="status"]').evaluate((status) => {
		const text = status.querySelector('.status-copy')?.getBoundingClientRect();
		const answer = status.querySelector('.status-link-box')?.getBoundingClientRect();
		if (!text || !answer) return true;
		return text.right > answer.left && text.left < answer.right && text.bottom > answer.top && text.top < answer.bottom;
	});
	expect(overlap).toBe(false);
	expect(await page.locator('[data-workbench-region="status"]').evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);

	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['published'], 'SELECT * FROM "published" WHERE false');
	await runExplorer(page);
	await expectAnswer(page, 'quiet');
	await expect(page.getByRole('link', { name: 'See the answer' })).toHaveCount(0);
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
	if (await page.locator('[data-shape-choice]').count()) await measure(() => page.locator('[data-shape-choice]').last().click());
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

test('M11: status words stay in the reserved lines and never scroll sideways', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	expect(statusSentence({ state: 'idle', files: 123, bytes: 67_108_864, ledgers: 4, days: 90, firstRun: true })).toBe('Run reads 123 files, 64.0 MB from 4 ledgers over 90 UTC days. It also starts the query engine.');
	expect(statusSentence({ state: 'costing' })).toBe('Choosing a ledger fetches one day of it to list its columns.');
	expect(statusSentence({ state: 'running-fetch', files: 123, bytes: 67_108_864 })).toBe('Fetching 123 files, 64.0 MB.');
	expect(statusSentence({ state: 'running-query' })).toBe('Running the question.');
	expect(statusSentence({ state: 'answered', ms: 99999, read: { files: 123, bytes: 67_108_864, alreadyHeld: 45, ms: 99999 } })).toBe('Answered in 100.0 s. Fetched 123 files, 64.0 MB; 45 more were already in this page.');
	expect(statusSentence({ state: 'quiet', ms: 99999, read: { files: 123, bytes: 67_108_864, alreadyHeld: 45, ms: 99999 } })).toBe('Ran in 100.0 s and matched no rows. Fetched 123 files, 64.0 MB.');
	expect(statusSentence({ state: 'refused' })).toBe('Did not run. The reason is where the answer would be.');
	expect(statusSentence({ state: 'missing', ledger: 'published' })).toBe('Did not run. published is not on this site yet.');
	expect(statusSentence({ state: 'unreachable-engine' })).toBe('Did not run. The query engine did not start.');
	expect(statusSentence({ state: 'unreachable-files' })).toBe('Did not run. The ledger files could not be fetched.');
	const longest = statusWithHeld(statusSentence({ state: 'answered', ms: 99999, read: { files: 123, bytes: 67_108_864, alreadyHeld: 123, ms: 99999 } }), 67_108_864);
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

test('M13: B2 column rail text flips without changing either rail box', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'),
		{ ledger: 'host-fingerprint', pinned: PINNED, days: everyDay(0, 0) },
		{ ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await page.setViewportSize({ width: 1440, height: 900 });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['host-fingerprint'], 'SELECT * FROM "host-fingerprint" LIMIT 1');
	const rail = '[data-workbench-region="columns"]';
	const outer = await box(page, rail);
	const inner = await box(page, '[data-explorer-column-box]');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	await expect(page.locator('[data-explorer-columns] h3')).toHaveText('Answer columns');
	closeBox(outer, await box(page, rail));
	closeBox(inner, await box(page, '[data-explorer-column-box]'));
	await page.locator('[data-ledger-name="published"] input').check();
	await expect(page.locator('[data-explorer-columns] h3')).toHaveText('Ledger columns');
	closeBox(outer, await box(page, rail));
	closeBox(inner, await box(page, '[data-explorer-column-box]'));
});

test('M15: panel ids stay ordered, headed and joined into one workbench surface', async ({ page }) => {
	await openExplorer(page, PINNED);
	const ids = await page.locator('[data-console-panel-id]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-console-panel-id')));
	expect(ids.slice(0, 3)).toEqual(['data-explorer-ask', 'data-explorer-rows', 'data-explorer-shape']);
	for (const id of ['data-explorer-ask', 'data-explorer-rows', 'data-explorer-shape']) {
		await expect(page.locator(`[data-console-panel-id="${id}"] h2`)).toHaveCount(1);
	}
	// Each panel touches the one before it, under it or, where the answer and the chart share a row, beside it.
	const joins = await page.locator('[data-console-panel-id]').evaluateAll((nodes) => nodes.slice(0, 3).map((node, index, all) => {
		if (index === 0) return 'first';
		const box = node.getBoundingClientRect();
		const before = all[index - 1].getBoundingClientRect();
		const under = Math.abs(box.top - before.bottom) < 0.5;
		const beside = Math.abs(box.left - before.right) < 0.5 && Math.abs(box.top - before.top) < 0.5;
		return under || beside ? 'joined' : `${box.top - before.bottom}px under and ${box.left - before.right}px beside the panel before it`;
	}));
	expect(joins).toEqual(['first', 'joined', 'joined']);
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
			const cut = await page.evaluate(() => {
				// These regions never scroll, so a control outside them, or content past their
				// height, is cut off. The rails scroll by design, so they are held only sideways.
				const whole = ['toolbar', 'questions', 'editor'];
				const sideways = ['ledgers', 'columns'];
				const offenders: string[] = [];
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
						if (rect.width === 0 || rect.height === 0 || !control.checkVisibility() || getComputedStyle(control).visibility === 'hidden') continue;
						const across = rect.left >= box.left - 0.5 && rect.right <= box.right + 0.5;
						const down = rect.top >= box.top - 0.5 && rect.bottom <= box.bottom + 0.5;
						if (!across || (both && !down)) {
							offenders.push(`${name}: ${control.tagName.toLowerCase()} "${(control.textContent ?? '').trim().slice(0, 40)}" at ${Math.round(rect.left)},${Math.round(rect.top)}-${Math.round(rect.right)},${Math.round(rect.bottom)} outside ${Math.round(box.left)},${Math.round(box.top)}-${Math.round(box.right)},${Math.round(box.bottom)}`);
						}
					}
				}
				return offenders;
			});
			expect(cut, `${view.width}px, ${phase}`).toEqual([]);
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
