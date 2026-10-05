import { expect, test, type Page } from './support/browser';
import { chooseExplorerQuestion, openExplorer, runExplorer } from './support/explorer-answer';

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
			['editorFrame', '[data-workbench-region="editor"] .frame']
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
	test(`Run moves nothing in answered, capped, quiet and refused states at ${view.width}px`, async ({ page }) => {
		await page.setViewportSize(view);
		await openExplorer(page);
		await page.evaluate(() => window.scrollTo(0, 0));
		for (const sql of [
			'SELECT count(*) AS rows FROM "published"',
			'SELECT i AS row_number FROM range(0, 1200) AS t(i)',
			'SELECT * FROM "published" WHERE false',
			'SELECT 1; SELECT 2'
		]) {
			await chooseExplorerQuestion(page, ['published'], sql);
			await page.evaluate(() => window.scrollTo(0, 0));
			await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
			await startShiftObserver(page);
			const before = await snapshot(page);
			await runExplorer(page);
			await page.waitForTimeout(1000);
			expectStable(before, await snapshot(page));
		}
	});
}

test('Copy link notice is fixed and moves no region', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	await page.setViewportSize({ width: 390, height: 844 });
	await openExplorer(page);
	await page.getByRole('button', { name: /^Copy link$/ }).scrollIntoViewIfNeeded();
	await startShiftObserver(page);
	const before = await snapshot(page);
	await page.getByRole('button', { name: /^Copy link$/ }).click();
	await expect(page.locator('[data-notice]')).toHaveCSS('position', 'fixed');
	await expect(page.locator('[data-notice]')).toHaveAttribute('role', 'status');
	expectStable(before, await snapshot(page));
});
