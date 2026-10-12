import { expect, test } from './support/door-page';
import { RUNNER_MEMORY_BYTES } from '../src/lib/charts/machine';

function measuredAttribute(cell: string | null | undefined): number | null {
	const text = (cell ?? '').trim();
	if (text === '') return null;
	const value = Number(text);
	return Number.isFinite(value) ? value : null;
}

test.describe('the memory panel puts the item grain on the page', () => {
	test('the page names one tightest item, and the lead matches that item', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');
		await expect(board).toBeVisible();

		await expect(board).toHaveAttribute('data-panel-question', 'what is broken');
		const runId = await board.getAttribute('data-memory-board');
		expect(runId, 'the panel drew no run').not.toBe('empty');
		const floor = measuredAttribute(await board.getAttribute('data-memory-floor-low'));
		const ceiling = measuredAttribute(await board.getAttribute('data-memory-ceiling'));
		expect(floor, 'the panel names no lead floor').not.toBeNull();
		expect(ceiling, 'the panel names no memory ceiling').not.toBeNull();
		expect(floor, 'the floor is outside the ceiling it is drawn against').toBeLessThanOrEqual(
			ceiling ?? 0
		);
		const owner = await board.getAttribute('data-memory-floor-item');
		expect(owner, 'the minimum reached the page with no item owning it').not.toBe('');

		const tightest = board.locator('[data-memory-item-tightest="true"]');
		await expect(tightest).toHaveCount(1);
		expect(await tightest.getAttribute('data-memory-item')).toBe(owner);
		expect(measuredAttribute(await tightest.getAttribute('data-memory-item-floor'))).toBe(floor);

		const floors = (
			await board
				.locator('[data-memory-item]')
				.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-memory-item-floor') ?? ''))
		)
			.filter((cell) => cell !== '')
			.map(Number);
		expect(floors.length, 'no item mark carries a kernel floor').toBeGreaterThan(0);
		expect(floor, 'the lead floor is not the lowest floor the marks carry').toBe(Math.min(...floors));
	});

	test('the kernel gap sentence follows the skipped count and bounded dates', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');
		const skipped = Number(await board.getAttribute('data-memory-kernel-skipped'));
		const from = Number(await board.getAttribute('data-memory-kernel-from'));
		const total = Number(await board.getAttribute('data-memory-items'));
		expect(skipped + from, 'kernel coverage does not add to the items drawn').toBe(total);
		const gap = board.locator('[data-memory-kernel-gap]');
		if (skipped === 0) {
			await expect(gap).toHaveCount(0);
			return;
		}
		await expect(gap).toBeVisible();
		await expect(gap).toContainText('no kernel reading');
		for (const attribute of ['data-memory-kernel-begins', 'data-memory-read-from'] as const) {
			const date = await board.getAttribute(attribute);
			expect(date, `${attribute} is missing`).not.toBe('');
			await expect(gap).toContainText(date ?? '');
		}
	});

	test('the page says the disputed high-water mark is not drawn', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');
		const drawnValues = await board.evaluate((node) =>
			[...node.attributes]
				.filter((one) => one.name.startsWith('data-memory-'))
				.map((one) => one.name)
		);
		expect(drawnValues, 'the disputed maximum has a drawing attribute').not.toContain(
			'data-memory-peak'
		);
		await expect(board.locator('[data-memory-not-drawn]')).toBeVisible();
		await expect(board.locator('[data-memory-not-drawn]')).toContainText('not drawn here');
	});

	test('every item mark carries parseable figures, and absent cells stay empty', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');

		const marks = board.locator('[data-memory-item]');
		const count = await marks.count();
		expect(count, 'the panel drew no item marks').toBeGreaterThan(0);
		for (let index = 0; index < count; index += 1) {
			const mark = marks.nth(index);
			const id = (await mark.getAttribute('data-memory-item')) ?? '';
			expect(id, 'a memory mark has no item id').not.toBe('');
			for (const attribute of [
				'data-memory-item-server-end',
				'data-memory-item-worker',
				'data-memory-item-floor',
				'data-memory-item-end',
				'data-memory-item-load'
			] as const) {
				const drawn = await mark.getAttribute(attribute);
				if ((drawn ?? '') === '') continue;
				expect(Number.isFinite(Number(drawn)), `${id} ${attribute} is not a number`).toBe(true);
			}
		}
	});

	test('the brackets are labelled at most and drawn against the larger of themselves', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');

		const server = measuredAttribute(await board.getAttribute('data-memory-server-end-high-water'));
		const worker = measuredAttribute(await board.getAttribute('data-memory-worker-high-water'));
		const scale = Number(await board.getAttribute('data-memory-bracket-scale'));
		expect(server, 'the model server bracket has no figure').not.toBeNull();
		expect(worker, 'the worker bracket has no figure').not.toBeNull();
		expect(scale).toBe(Math.max(server!, worker!));
		expect(scale).not.toBe(Number(await board.getAttribute('data-memory-ceiling')));
		await expect(board.locator('[data-memory-figure="server-end"]')).toContainText('at most');
		await expect(board.locator('[data-memory-figure="worker-end"]')).toContainText('at most');
	});

	test('the panel names its denominator and says what it cannot separate', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');

		const ceiling = Number(await board.getAttribute('data-memory-ceiling'));
		expect(ceiling, 'the panel drew against no ceiling').toBeGreaterThan(0);
		const measuredTotal = measuredAttribute(await board.getAttribute('data-memory-total-measured'));
		expect(ceiling).toBe(measuredTotal ?? RUNNER_MEMORY_BYTES);

		await expect(board.locator('[data-memory-cannot-separate]')).toBeAttached();
		await expect(board.locator('[data-memory-denominator]')).toBeAttached();
	});
});
