/** Does the shard board put every work-or-host fact on the row, in the DOM?
 *
 * The question a unit test cannot answer. `console-machine.spec.ts` drives the
 * builder over a fixture and proves the arithmetic; this one proves the values
 * reach the page as attributes an operator's browser can render, on the run the
 * canary really built.
 *
 * That covers the three clocks as well - the time no named step claimed, the
 * time an item waited, and the time the shard paid opening the weights. The
 * first is the one to watch: it is the stored column added up and nothing else,
 * so an implementation that worked it out from the step clocks would draw a
 * different number here.
 *
 * Every expectation below is recomputed from the canary ledgers on disk, never
 * read back off the page. An oracle that reads the module it is testing proves
 * only that the module agrees with itself.
 *
 * `frontend/scripts/build-canary.mjs` writes both ledgers this reads.
 */

import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const REPO = resolve(process.cwd(), '..');

/** Every row of one canary ledger, read straight off its day tree. */
function canaryRows(ledger: string): Record<string, string>[] {
	const root = join(REPO, 'backend', 'var', 'canary', 'state', ledger);
	const rows: Record<string, string>[] = [];
	for (const relative of readdirSync(root, { recursive: true }) as string[]) {
		if (!relative.endsWith('.csv')) continue;
		const text = readFileSync(join(root, relative), 'utf8').trim();
		if (text === '') continue;
		const [header, ...lines] = text.split('\n');
		const columns = header.split(',');
		for (const line of lines) {
			const cells = line.split(',');
			rows.push(Object.fromEntries(columns.map((name, index) => [name, cells[index] ?? ''])));
		}
	}
	return rows;
}

function measured(cell: string | null | undefined): number | null {
	const text = (cell ?? '').trim();
	if (text === '') return null;
	const value = Number(text);
	return Number.isFinite(value) ? value : null;
}

/** The middle reading, interpolated between the two nearest ranks. The same
 * rule the reader uses, restated here so the two cannot quietly be one. */
function median(values: number[]): number | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((left, right) => left - right);
	const position = (sorted.length - 1) / 2;
	const low = Math.floor(position);
	const high = Math.ceil(position);
	return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

interface Expected {
	items: number;
	writeRate: number | null;
	memoryMedian: number | null;
	memoryMax: number | null;
	cpuMedian: number | null;
	cpuMax: number | null;
	loadMax: number | null;
	swapFree: number | null;
	swapTotal: number | null;
	/** `stage_gap_ms` added over the shard's rows, in seconds, sign kept. */
	unclaimedSeconds: number | null;
	/** How many of those rows carried a figure below zero. */
	disagreed: number;
	/** How many carried one at all. */
	clocked: number;
	queueMedianSeconds: number | null;
	queueMaxSeconds: number | null;
}

/** One shard of one run, folded off the item ledger by hand. */
function foldShard(runId: string, shard: string): Expected {
	let items = 0;
	let written = 0;
	let writeMs = 0;
	const rss: number[] = [];
	const busy: number[] = [];
	let busyMax: number | null = null;
	let loadMax: number | null = null;
	let swapFree: number | null = null;
	let swapTotal: number | null = null;
	// The three clocks, folded by hand off the columns themselves. Added for the
	// unclaimed figure because each item's gap is a slice of that item's own
	// clock; never added for the queue, because each item's wait covers the queue
	// ahead of it and a sum would count that queue once per item.
	let unclaimedMs: number | null = null;
	let disagreed = 0;
	let clocked = 0;
	const waits: number[] = [];
	for (const row of canaryRows('item-health')) {
		if (row.run_id !== runId || row.shard !== shard) continue;
		const input = measured(row.input_tokens);
		const cached = measured(row.cached_tokens);
		if (input !== null && cached !== null) items += 1;
		const out = measured(row.output_tokens);
		if (out !== null) written += out;
		const decode = measured(row.decode_ms);
		if (decode !== null) writeMs += decode;
		const peak = measured(row.llama_rss_peak_bytes);
		if (peak !== null) rss.push(peak);
		const cpu = measured(row.cpu_busy_pct);
		if (cpu !== null) busy.push(cpu);
		const cpuTop = measured(row.cpu_busy_max);
		if (cpuTop !== null) busyMax = Math.max(busyMax ?? cpuTop, cpuTop);
		const load = measured(row.load_1m);
		if (load !== null) loadMax = Math.max(loadMax ?? load, load);
		const free = measured(row.os_swap_free_bytes);
		if (free !== null) swapFree = Math.min(swapFree ?? free, free);
		const total = measured(row.os_swap_total_bytes);
		if (total !== null) swapTotal = total;
		const unclaimed = measured(row.stage_gap_ms);
		if (unclaimed !== null) {
			unclaimedMs = (unclaimedMs ?? 0) + unclaimed;
			clocked += 1;
			if (unclaimed < 0) disagreed += 1;
		}
		const queued = measured(row.queue_wait_ms);
		if (queued !== null) waits.push(queued);
	}
	return {
		items,
		writeRate: writeMs > 0 ? written / (writeMs / 1000) : null,
		memoryMedian: median(rss),
		memoryMax: rss.length === 0 ? null : Math.max(...rss),
		cpuMedian: median(busy),
		cpuMax: busyMax,
		loadMax,
		swapFree,
		swapTotal,
		unclaimedSeconds: unclaimedMs === null ? null : unclaimedMs / 1000,
		disagreed,
		clocked,
		queueMedianSeconds: waits.length === 0 ? null : (median(waits) as number) / 1000,
		queueMaxSeconds: waits.length === 0 ? null : Math.max(...waits) / 1000
	};
}

/** The machine record's cells for one shard of one run, merged by hand. */
function hostOf(runId: string, shard: string): Record<string, string> {
	const held: Record<string, string> = {};
	for (const row of canaryRows('host-fingerprint')) {
		if (row.run_id !== runId || row.shard !== shard) continue;
		if ((row.job ?? '') !== '' && row.job !== 'work') continue;
		for (const [name, value] of Object.entries(row)) {
			if ((value ?? '').trim() !== '' && held[name] === undefined) held[name] = value.trim();
		}
	}
	return held;
}

/** A number on the page against the number the ledger carries, to six places.
 * Null on both sides is a match: an absent cell must reach the page as an empty
 * attribute rather than as a zero. */
function sameNumber(attribute: string | null, expected: number | null, what: string): void {
	if (expected === null) {
		expect(attribute ?? '', `${what} was drawn from nothing`).toBe('');
		return;
	}
	expect(attribute, `${what} is missing from the row`).not.toBeNull();
	expect(Number(attribute), what).toBeCloseTo(expected, 6);
}

test.describe('the shard board carries the work-or-host answer on the row', () => {
	test('every host figure on a row recomputes from the canary ledgers', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-shard-board]');
		await expect(board).toBeVisible();

		// A break panel, and it says so rather than leaving the reader to infer it
		// from the shape.
		await expect(board).toHaveAttribute('data-panel-question', 'what is broken');

		const runId = await board.getAttribute('data-shard-board');
		expect(runId, 'the board drew no run').not.toBe('empty');

		const rows = board.locator('[data-shard-row]');
		const count = await rows.count();
		expect(count, 'the canary run must draw more than one shard').toBeGreaterThan(1);

		for (let index = 0; index < count; index += 1) {
			const row = rows.nth(index);
			const shard = (await row.getAttribute('data-shard-row')) ?? '';
			const fold = foldShard(runId ?? '', shard);
			const host = hostOf(runId ?? '', shard);
			const where = `shard ${shard}`;

			expect(Number(await row.getAttribute('data-shard-items')), `${where} item count`).toBe(
				fold.items
			);
			sameNumber(
				await row.getAttribute('data-shard-write-tps'),
				fold.writeRate,
				`${where} write rate`
			);
			sameNumber(
				await row.getAttribute('data-shard-mem-median'),
				fold.memoryMedian,
				`${where} typical memory`
			);
			sameNumber(
				await row.getAttribute('data-shard-mem-max'),
				fold.memoryMax,
				`${where} worst memory`
			);
			sameNumber(
				await row.getAttribute('data-shard-cpu-median'),
				fold.cpuMedian,
				`${where} typical processor busy`
			);
			sameNumber(
				await row.getAttribute('data-shard-cpu-max'),
				fold.cpuMax,
				`${where} worst processor busy`
			);
			sameNumber(await row.getAttribute('data-shard-load'), fold.loadMax, `${where} load`);
			sameNumber(
				await row.getAttribute('data-shard-cores'),
				measured(host.cores),
				`${where} core count`
			);
			sameNumber(
				await row.getAttribute('data-shard-model-load-ms'),
				measured(host.model_load_ms),
				`${where} weights load`
			);

			// The swap pair is a named state rather than a number, because zero free
			// means "no swap on this box" and "swap consumed" equally, and only the
			// second is an emergency.
			const swapState = await row.getAttribute('data-shard-swap-state');
			const expectedState =
				fold.swapTotal === null ? 'unrecorded' : fold.swapTotal > 0 ? 'measured' : 'none';
			expect(swapState, `${where} swap state`).toBe(expectedState);
			sameNumber(await row.getAttribute('data-shard-swap-free'), fold.swapFree, `${where} free swap`);

			// The three clocks, against the ledger's own columns. The unclaimed one
			// is the column added up and nothing else: these rows carry stage clocks
			// the page never reads, so a figure worked out on the page from them
			// would not be this number.
			sameNumber(
				await row.getAttribute('data-shard-unclaimed-seconds'),
				fold.unclaimedSeconds,
				`${where} unclaimed time`
			);
			expect(
				Number(await row.getAttribute('data-shard-clocks-disagreed')),
				`${where} items whose clocks disagree`
			).toBe(fold.disagreed);
			sameNumber(
				await row.getAttribute('data-shard-queue-median-seconds'),
				fold.queueMedianSeconds,
				`${where} typical queue wait`
			);
			sameNumber(
				await row.getAttribute('data-shard-queue-max-seconds'),
				fold.queueMaxSeconds,
				`${where} worst queue wait`
			);
		}
	});

	test('THE ORACLE: a shard whose clocks disagree says so, and never draws a zero', async ({
		page
	}) => {
		// The canary writes one row with an unclaimed time below zero, which no
		// committed day has ever held. It says the named steps claim more time than
		// the item took - two clocks disagreeing - and clamping it to zero would
		// hide the only fault the signed column exists to show.
		await page.goto('/console/machine/');
		const board = page.locator('[data-shard-board]');
		await expect(board).toBeVisible();

		const runId = (await board.getAttribute('data-shard-board')) ?? '';
		const rows = board.locator('[data-shard-row]');
		const count = await rows.count();

		let below = 0;
		for (let index = 0; index < count; index += 1) {
			const row = rows.nth(index);
			const shard = (await row.getAttribute('data-shard-row')) ?? '';
			const fold = foldShard(runId, shard);
			const printed = (await row.locator('[data-shard-figure="unclaimed"]').innerText()).trim();

			if (fold.unclaimedSeconds === null) {
				expect(printed, `shard ${shard} drew a figure from no clock at all`).toContain(
					'No item clock'
				);
				continue;
			}
			// Every shard prints the count beside the sum, because a shard whose
			// items cancel each other out reads as healthy on the sum alone.
			if (fold.unclaimedSeconds < 0 || fold.disagreed > 0) {
				below += 1;
				expect(printed, `shard ${shard} drew a disagreement without saying so`).toContain(
					'two clocks disagree'
				);
				expect(printed, `shard ${shard} named the wrong number of items`).toContain(
					`${fold.disagreed} of ${fold.clocked} items`
				);
				expect(printed, `shard ${shard} rounded a disagreement away to nothing`).not.toBe(
					'0.0 s no named step claimed.'
				);
			} else {
				expect(printed, `shard ${shard} did not say what its unclaimed time was`).toContain(
					'no named step claimed'
				);
			}
		}

		expect(below, 'no canary shard carries an unclaimed time below zero to draw').toBeGreaterThan(
			0
		);
	});

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

		// The domain is the largest rate the board drew, so a shard at a quarter of
		// its neighbour draws a quarter-length bar. A fixed ceiling would put both
		// against a number nobody measured.
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
