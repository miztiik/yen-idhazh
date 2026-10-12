import { expect, test } from './support/door-page';

function measured(value: string | null): number | null {
	const parsed = value === null || value === '' ? NaN : Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

test.describe('the shard board carries the work-or-host answer on the row', () => {
	test('the rate domain is the rates drawn, and the board prints the ratio it measured', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-shard-board]');
		const rows = board.locator('[data-shard-row]');
		const count = await rows.count();

		const reads: number[] = [];
		const writes: number[] = [];
		for (let index = 0; index < count; index += 1) {
			const read = measured(await rows.nth(index).getAttribute('data-shard-read-tps'));
			const write = measured(await rows.nth(index).getAttribute('data-shard-write-tps'));
			if (read !== null) reads.push(read);
			if (write !== null) writes.push(write);
		}
		expect(reads.length + writes.length, 'no rate reached the board').toBeGreaterThan(0);

		const readTop = reads.length === 0 ? 0 : Math.max(...reads);
		const writeTop = writes.length === 0 ? 0 : Math.max(...writes);
		const larger = Math.max(readTop, writeTop);
		const smaller = Math.min(readTop, writeTop);
		expect(Number(await board.getAttribute('data-shard-board-rate-scale'))).toBeCloseTo(larger, 6);

		const shares = (await board.getAttribute('data-shard-board-rates-share-axis')) === 'true';
		expect(shares, 'the axis choice must follow the measured ratio').toBe(
			smaller <= 0 || larger / smaller < 20
		);
		expect(Number(await board.getAttribute('data-shard-board-write-rate-scale'))).toBeCloseTo(
			shares ? larger : writeTop,
			6
		);
	});

	test('the memory domain takes the runner ceiling in rather than capping at it', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-shard-board]');
		const rows = board.locator('[data-shard-row]');
		const count = await rows.count();

		const marks: number[] = [];
		for (let index = 0; index < count; index += 1) {
			for (const name of ['data-shard-mem-median', 'data-shard-mem-max']) {
				const value = measured(await rows.nth(index).getAttribute(name));
				if (value !== null) marks.push(value);
			}
		}
		const ceiling = 16 * 1024 * 1024 * 1024;
		expect(Number(await board.getAttribute('data-shard-board-memory-scale'))).toBe(
			Math.max(ceiling, ...marks)
		);
	});
});
