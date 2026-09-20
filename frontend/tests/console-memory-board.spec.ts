/** Does the memory panel show the item a per-shard maximum hides?
 *
 * The panel exists because one measurement was asked two questions and only one
 * of them was built. A per-shard high-water mark is the verdict reading - how
 * near the ceiling the run got - and behind it sits the item that took the model
 * server there. On the committed ledger that item reached 83.1 percent of the
 * runner's 16 GiB and no panel drew it.
 *
 * Two halves, for the two things that can be wrong. The builder tests drive the
 * fold over fixture ledger rows and recompute every expectation from those rows,
 * so the module never checks itself. The browser tests prove the same figures
 * reach the page as attributes, on the run the canary really built.
 *
 * `frontend/scripts/build-canary.mjs` writes the ledgers the browser half reads.
 */

import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	memoryBoard,
	MEM_TOTAL_AGREES_WITHIN_PCT,
	RUNNER_MEMORY_BYTES
} from '../src/lib/charts/machine';
import {
	machineCounters,
	machineLimits,
	type MachineLimits,
	type MachineRun
} from '../src/lib/server/machine-counters';
import { ledgers, plan, type ShardReading } from './support/machine-rows';

const REPO = resolve(process.cwd(), '..');
const DATE = '2026-09-04';
const RUN = '2026-09-04-1';
// Whole bytes, because the ledger's cells are whole bytes and a fixture written
// in fractions of a gibibyte turns every subtraction below into a float compare.
const MIB = 1024 * 1024;
const GIB = 1024 * MIB;

/** `config/idhazh.json` off disk, so an expectation comes from the committed
 * file rather than from the reader it is checking. */
function limits(): MachineLimits {
	const idhazh = JSON.parse(
		readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')
	) as { run: { shard_timeout_minutes: number }; models_file: string };
	const models = JSON.parse(
		readFileSync(join(REPO, 'config', idhazh.models_file), 'utf8')
	) as { summarize: { inference: { n_ctx: number } } };
	return {
		contextWindow: models.summarize.inference.n_ctx,
		jobTimeoutSeconds: idhazh.run.shard_timeout_minutes * 60
	};
}

/** The fixture ledgers, and the run the reader folds them into. */
function fixture(readings: ShardReading[]): {
	run: MachineRun;
	health: Record<string, string>[];
} {
	const stamped = readings.map((reading) => ({ date: DATE, runId: RUN, ...reading }));
	const { hosts, health } = ledgers(stamped);
	const { runs, refused } = machineCounters(hosts, health, plan([RUN, 2]), limits());
	expect(refused, 'the fixture was refused').toEqual([]);
	expect(runs, 'the fixture folded into no run').toHaveLength(1);
	return { run: runs[0], health };
}

/** One item that filled every cell this panel reads. */
function item(over: ShardReading): ShardReading {
	return {
		shard: 0,
		cores: 4,
		cachedTokens: 0,
		writtenTokens: 100,
		writeSeconds: 20,
		longestSequence: 500,
		serverPromptTokens: 400,
		serverPromptSeconds: 40,
		jobSeconds: 600,
		cpuModel: 'AMD EPYC 7763 64-Core Processor',
		memTotal: 16 * GIB,
		shardItemCount: 3,
		...over
	};
}

/** Three items on one shard, chosen so every derived figure checks with a
 * pencil. The middle item is the one that took the machine furthest. */
const THREE_ITEMS: ShardReading[] = [
	item({
		itemId: 'item-a',
		startedAt: '2026-09-04T06:00:00Z',
		peakRssBytes: 11 * GIB,
		workerRssBytes: 1 * GIB,
		memAvailableMin: 4 * GIB,
		memAvailable: 5 * GIB,
		load: 2.5,
		cpuBusyMin: 90,
		cpuBusyMax: 99
	}),
	item({
		itemId: 'item-b',
		startedAt: '2026-09-04T06:10:00Z',
		peakRssBytes: 13 * GIB,
		workerRssBytes: 1229 * MIB,
		memAvailableMin: 2 * GIB,
		memAvailable: 2 * GIB + 205 * MIB,
		load: 6.5,
		cpuBusyMin: 96,
		cpuBusyMax: 100
	}),
	item({
		itemId: 'item-c',
		startedAt: '2026-09-04T06:20:00Z',
		peakRssBytes: 12 * GIB,
		workerRssBytes: 1536 * MIB,
		memAvailableMin: 3 * GIB,
		memAvailable: 3 * GIB + 410 * MIB,
		load: 3.1,
		cpuBusyMin: 88,
		cpuBusyMax: 97
	})
];

test.describe('memory and load, three grains', () => {
	test('THE ORACLE: the printed item maximum is the maximum over the item rows', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);

		// Recomputed from the fixture rows rather than read back off the view.
		const peaks = health
			.filter((row) => row.run_id === RUN && row.llama_rss_peak_bytes !== '')
			.map((row) => Number(row.llama_rss_peak_bytes));
		expect(peaks.length, 'the fixture recorded no item memory').toBe(3);
		expect(board.itemHighWater, 'the panel prints something other than the item maximum').toBe(
			Math.max(...peaks)
		);
		// And it names the item that owns it, which is the whole reason the grain
		// exists: a per-shard maximum is one number with no owner.
		expect(board.worstItemId).toBe('item-b');
		expect(board.items.filter((one) => one.worst).map((one) => one.itemId)).toEqual(['item-b']);
		// The shard grain of the same run reads the same maximum, so the two
		// grains cannot disagree about one measurement.
		expect(board.shard.highWater).toBe(Math.max(...peaks));
	});

	test('THE ORACLE: all three grains and the load series are built from one call', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);

		// Item grain: one entry an item, in run order off the item's own clock.
		expect(board.items.map((one) => one.itemId)).toEqual(['item-a', 'item-b', 'item-c']);
		// Shard grain: the per-shard bars, unchanged.
		expect(board.shard.empty).toBe(false);
		expect(board.shard.shards.map((one) => one.shard)).toEqual([0]);
		// The load series, which is the second series and not a second panel.
		expect(board.loadHigh).toBe(6.5);
		expect(board.cores).toBe(4);
		expect(board.load.empty, 'load has no core count to be read against').toBe(false);
		// Busy runs near 100 on every row, which is why load is drawn beside it.
		expect(board.busySpan.median).toBe(88);
		expect(board.busySpan.max).toBe(100);
		expect(board.loadEmpty).toBe(false);
	});

	test('THE ORACLE: null OS columns are an empty grain, never a flat line at zero', () => {
		// Same three items, every machine cell blank. This is a day older than the
		// cells, which is a missing reading rather than an item that used none.
		const blank = THREE_ITEMS.map((one) => ({
			...one,
			peakRssBytes: '' as const,
			workerRssBytes: '' as const,
			memAvailableMin: '' as const,
			memAvailable: '' as const,
			memTotal: '' as const,
			load: '' as const,
			cpuBusyMin: '' as const,
			cpuBusyMax: '' as const
		}));
		const { run, health } = fixture(blank);
		const board = memoryBoard(run, health);

		expect(board.itemsEmpty, 'a blank day drew item marks').toBe(true);
		expect(board.items).toEqual([]);
		expect(board.itemHighWater).toBeNull();
		expect(board.itemHighWater, 'absence was drawn as a measurement of zero').not.toBe(0);
		expect(board.loadHigh).toBeNull();
		expect(board.loadEmpty).toBe(true);
		expect(board.busySpan.empty).toBe(true);
		// The shard grain is empty for the same reason, so the whole panel is.
		expect(board.shard.empty).toBe(true);
		expect(board.empty).toBe(true);
	});

	test('the two maxima added are an upper bound unless one item held both', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);
		// item-b holds the largest model-server figure and item-c the largest
		// worker figure, so no moment of this run held both.
		expect(board.coPeak).toBe(false);
		expect(board.itemHighWater).toBe(13 * GIB);
		expect(board.workerHighWater).toBe(1536 * MIB);
		expect(board.bothHighWater).toBe(13 * GIB + 1536 * MIB);

		// Move the worker maximum onto the item that owns the memory maximum and
		// the same sum becomes a reading.
		const together = THREE_ITEMS.map((one) =>
			one.itemId === 'item-b' ? { ...one, workerRssBytes: 2 * GIB } : one
		);
		const co = fixture(together);
		expect(memoryBoard(co.run, co.health).coPeak).toBe(true);
	});

	test('the item mark runs floor to recovery, so a leak reads apart from hard work', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);

		const b = board.items.find((one) => one.itemId === 'item-b');
		expect(b?.headroom.floorBytes).toBe(2 * GIB);
		expect(b?.headroom.endBytes).toBe(2 * GIB + 205 * MIB);
		expect(b?.headroom.recoveredBytes, 'the second end of the mark is not drawn').toBe(
			205 * MIB
		);
		// An item that ends lower than its own floor gave nothing back, which is
		// the state the second end exists to separate from working hard.
		const leaking = fixture([
			item({
				itemId: 'item-leak',
				startedAt: '2026-09-04T07:00:00Z',
				peakRssBytes: 13 * GIB,
				memAvailableMin: 3 * GIB,
				memAvailable: 3 * GIB - 512 * MIB,
				load: 4
			})
		]);
		const mark = memoryBoard(leaking.run, leaking.health).items[0].headroom;
		expect(mark.recoveredBytes).toBe(-512 * MIB);
	});

	test('an item with no headroom cells keeps its memory bar and says the mark is absent', () => {
		const mixed = fixture([
			item({
				itemId: 'item-held-only',
				startedAt: '2026-09-04T08:00:00Z',
				peakRssBytes: 10 * GIB,
				load: 2
			})
		]);
		const one = memoryBoard(mixed.run, mixed.health).items[0];
		expect(one.peakBytes).toBe(10 * GIB);
		expect(one.headroom.empty, 'an unmeasured headroom mark was drawn').toBe(true);
		expect(one.headroom.floorBytes).toBeNull();
		expect(one.headroom.endBytes).toBeNull();
	});

	test('THE ORACLE: MemTotal is the denominator, and the tell that it is another machine', () => {
		// A container reports the HOST from /proc/meminfo, so a total that is not
		// the runner's is the one cell that can say the other five are about a
		// different box.
		const elsewhere = fixture(
			THREE_ITEMS.map((one) => ({ ...one, memTotal: 64 * GIB }))
		);
		const board = memoryBoard(elsewhere.run, elsewhere.health);
		expect(board.measuredTotalBytes).toBe(64 * GIB);
		expect(board.totalAgrees, 'a 64 GiB machine read as the 16 GiB runner').toBe(false);
		expect(board.ceilingBytes).toBe(64 * GIB);

		// The tolerance is a measurement rather than a taste, so a total inside it
		// reads as the runner it is.
		const nearly = Math.round(RUNNER_MEMORY_BYTES * (1 - MEM_TOTAL_AGREES_WITHIN_PCT / 200));
		const kernelReserved = fixture(THREE_ITEMS.map((one) => ({ ...one, memTotal: nearly })));
		expect(memoryBoard(kernelReserved.run, kernelReserved.health).totalAgrees).toBe(true);

		// No total at all is unknown, and the runner's own ceiling is what the
		// panel then draws against - never a total nobody measured.
		const silent = fixture(THREE_ITEMS.map((one) => ({ ...one, memTotal: '' as const })));
		const quiet = memoryBoard(silent.run, silent.health);
		expect(quiet.totalAgrees).toBeNull();
		expect(quiet.measuredTotalBytes).toBeNull();
		expect(quiet.ceilingBytes).toBe(RUNNER_MEMORY_BYTES);
	});

	test('two machine sizes in one run take the smaller, and both are carried', () => {
		const twoBoxes = fixture([
			...THREE_ITEMS,
			item({
				itemId: 'item-d',
				shard: 1,
				startedAt: '2026-09-04T06:30:00Z',
				memTotal: 8 * GIB,
				peakRssBytes: 7 * GIB,
				load: 1.5
			})
		]);
		const board = memoryBoard(twoBoxes.run, twoBoxes.health);
		expect(board.totalsSeen, 'a run that drew two machine sizes kept one').toEqual([
			8 * GIB,
			16 * GIB
		]);
		// The smaller, because the smaller is the one that could have run out.
		expect(board.ceilingBytes).toBe(8 * GIB);
	});

	test('coverage is the items that answered against the items the shards had', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);
		expect(board.from).toBe(3);
		// One count a shard, summed over the shards that recorded one - never the
		// largest, which would report one shard's work as the whole run's.
		expect(board.outOf).toBe(3);

		const silent = fixture(
			THREE_ITEMS.map((one) => ({ ...one, shardItemCount: '' as const }))
		);
		expect(memoryBoard(silent.run, silent.health).outOf, 'an unknown total was invented').toBeNull();
	});

	test('a run with no rows at all is empty rather than a run that used nothing', () => {
		const board = memoryBoard(null, []);
		expect(board.empty).toBe(true);
		expect(board.items).toEqual([]);
		expect(board.itemHighWater).toBeNull();
		expect(board.runId).toBe('');
	});
});

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

test.describe('the memory panel puts the item grain on the page', () => {
	test('THE ORACLE: the item maximum on the page recomputes from the canary ledger', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');
		await expect(board).toBeVisible();

		// A break panel, and it says so rather than leaving a reader to infer it.
		await expect(board).toHaveAttribute('data-panel-question', 'what is broken');
		const runId = await board.getAttribute('data-memory-board');
		expect(runId, 'the panel drew no run').not.toBe('empty');

		const peaks = canaryRows('item-health')
			.filter((row) => row.run_id === runId)
			.map((row) => measured(row.llama_rss_peak_bytes))
			.filter((value): value is number => value !== null);
		expect(peaks.length, 'the newest canary run records no item memory').toBeGreaterThan(0);

		// The figure the panel exists for, on an attribute rather than in prose:
		// a sentence can be renamed and a negative prose assertion then passes
		// while the page prints the wrong number.
		expect(Number(await board.getAttribute('data-memory-item-high-water'))).toBe(
			Math.max(...peaks)
		);
		const owner = await board.getAttribute('data-memory-worst-item');
		expect(owner, 'the maximum reached the page with no item owning it').not.toBe('');

		// And exactly one mark is flagged as the worst, whatever ties behind it:
		// "the item that owns the maximum" has to be an item a reader can go and
		// look at, so a tie is named once.
		const worst = board.locator('[data-memory-item-worst="true"]');
		await expect(worst).toHaveCount(1);
		expect(await worst.getAttribute('data-memory-item')).toBe(owner);
		expect(Number(await worst.getAttribute('data-memory-item-peak'))).toBe(Math.max(...peaks));
	});

	test('every item mark carries its own figures, recomputed from the ledger', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');
		const runId = await board.getAttribute('data-memory-board');

		const byItem = new Map<string, Record<string, string>>();
		for (const row of canaryRows('item-health')) {
			if (row.run_id !== runId) continue;
			byItem.set((row.item_id ?? '').trim(), row);
		}

		const marks = board.locator('[data-memory-item]');
		const count = await marks.count();
		expect(count, 'the panel drew no item marks').toBeGreaterThan(0);
		for (let index = 0; index < count; index += 1) {
			const mark = marks.nth(index);
			const id = (await mark.getAttribute('data-memory-item')) ?? '';
			const row = byItem.get(id);
			expect(row, `${id} is on the page and not in the ledger`).toBeTruthy();
			for (const [attribute, column] of [
				['data-memory-item-peak', 'llama_rss_peak_bytes'],
				['data-memory-item-worker', 'python_rss_bytes'],
				['data-memory-item-floor', 'os_mem_available_min_bytes'],
				['data-memory-item-end', 'os_mem_available_bytes'],
				['data-memory-item-load', 'load_1m']
			] as const) {
				const drawn = await mark.getAttribute(attribute);
				const expected = measured(row![column]);
				// An absent cell reaches the page as an empty attribute, never as a
				// zero: a zero-length bar claims a reading nobody took.
				if (expected === null) expect(drawn ?? '', `${id} ${column}`).toBe('');
				else expect(Number(drawn), `${id} ${column}`).toBeCloseTo(expected, 6);
			}
		}
	});

	test('THE ORACLE: the grain switch reaches all three grains from one payload', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');
		const control = board.locator('[data-shape-switch="memory-grain"]');

		// Top right of its own panel, and radio inputs rather than a verb.
		await expect(control).toBeVisible();
		await expect(board.locator('[data-memory-pane="item"]')).toBeVisible();

		await control.locator('[data-shape-option="shard"]').click();
		await expect(board.locator('[data-memory-pane="shard"]')).toBeVisible();
		// The shard grain is the panel that used to stand alone, and it still
		// reads the maximum and never the sum.
		const bars = board.locator('[data-memory-shard]');
		expect(await bars.count(), 'the shard grain drew no bars').toBeGreaterThan(0);
		const shardBytes: number[] = [];
		for (let index = 0; index < (await bars.count()); index += 1) {
			shardBytes.push(Number(await bars.nth(index).getAttribute('data-memory-bytes')));
		}
		const high = Number(
			await board.locator('[data-memory-high-water]').getAttribute('data-memory-high-water')
		);
		expect(high, 'the shard grain summed its shards').toBe(Math.max(...shardBytes));

		await control.locator('[data-shape-option="span"]').click();
		const track = board.locator('[data-memory-span-high]');
		await expect(track).toBeVisible();
		// The window grain is a range mark, which is what the four sentences it
		// replaced could not be compared as.
		const low = Number(await track.getAttribute('data-memory-span-low'));
		expect(Number(await track.getAttribute('data-memory-span-high'))).toBeGreaterThanOrEqual(low);
	});

	test('the panel names its denominator and says what it cannot separate', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');

		// The denominator is on the panel as an attribute, so the drawn lengths
		// can be checked against the number they were drawn from.
		const ceiling = Number(await board.getAttribute('data-memory-ceiling'));
		expect(ceiling, 'the panel drew against no ceiling').toBeGreaterThan(0);
		const measuredTotal = measured(await board.getAttribute('data-memory-total-measured'));
		expect(ceiling).toBe(measuredTotal ?? RUNNER_MEMORY_BYTES);

		// The one thing this panel cannot answer is said on the panel rather than
		// left for the reader to assume it was answered.
		await expect(board.locator('[data-memory-cannot-separate]')).toBeAttached();
		await expect(board.locator('[data-memory-denominator]')).toBeAttached();
	});
});
