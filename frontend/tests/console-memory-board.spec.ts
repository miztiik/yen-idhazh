/** Does the memory panel lead with how close one item took the machine to its
 * limit, and does it stay off the mark whose instrument is disputed?
 *
 * The panel used to lead with `llama_rss_peak_bytes`, a per-shard maximum of a
 * process high-water mark. That column is `VmHWM`: it covers the model server's
 * whole life rather than the item, and it reads lower than an earlier item's
 * whenever the kernel reclaims a page. It is still written to the ledger and it
 * is drawn nowhere on this panel.
 *
 * The lead is `os_mem_available_min_bytes` - the least the kernel had left at
 * one item's worst moment. That is the reading the question is about, and a
 * shard maximum cannot show it: one item can take the machine to its floor
 * while the shard it sits in reads as a normal shard.
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
		contextWindow: models.summarize.server['--ctx-size'],
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
		serverRssBytes: 10 * GIB,
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
		serverRssBytes: 12 * GIB,
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
		serverRssBytes: 11 * GIB,
		workerRssBytes: 1536 * MIB,
		memAvailableMin: 3 * GIB,
		memAvailable: 3 * GIB + 410 * MIB,
		load: 3.1,
		cpuBusyMin: 88,
		cpuBusyMax: 97
	})
];

test.describe('the memory board, at item grain', () => {
	test('THE ORACLE: the printed item minimum is the minimum over the item rows', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);

		// Recomputed from the fixture rows rather than read back off the view.
		const floors = health
			.filter((row) => row.run_id === RUN && row.os_mem_available_min_bytes !== '')
			.map((row) => Number(row.os_mem_available_min_bytes));
		expect(floors.length, 'the fixture recorded no kernel floor').toBe(3);
		expect(
			board.floorLowBytes,
			'the panel leads with something other than the item minimum'
		).toBe(Math.min(...floors));
		// A MINIMUM and not a maximum: the question is how little was left.
		expect(board.floorLowBytes).toBeLessThan(Math.max(...floors));
		// And it names the item that owns it, which is the whole reason the grain
		// exists: a per-shard figure is one number with no owner.
		expect(board.floorItemId).toBe('item-b');
		expect(board.items.filter((one) => one.tightest).map((one) => one.itemId)).toEqual([
			'item-b'
		]);
		// The share is of what was still FREE, against the denominator the board
		// drew against.
		expect(board.floorLowPct).toBe(
			Math.round((Math.min(...floors) / board.ceilingBytes) * 100)
		);
	});

	test('THE ORACLE: the disputed high-water mark reaches no figure on the board', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);

		// Every row carries it, and it is the largest byte figure in the fixture.
		const peaks = health.map((row) => Number(row.llama_rss_peak_bytes));
		expect(Math.max(...peaks), 'the fixture stopped carrying the disputed column').toBe(
			13 * GIB
		);

		// No figure the board hands the page equals it, and the item entries carry
		// no field for it at all. A caveat under a mark does not stop the mark
		// being read, so the mark is not built.
		const drawn = [
			board.floorLowBytes,
			board.serverEndHighWater,
			board.workerHighWater,
			board.bothHighWater,
			board.bracketScaleBytes,
			board.scaleBytes
		];
		expect(drawn, 'the disputed maximum is still a drawn figure').not.toContain(13 * GIB);
		expect(Object.keys(board.items[0])).not.toContain('peakBytes');
		// The byte domain is the kernel's, so a resident-set mark cannot widen it.
		expect(board.scaleBytes).toBe(board.ceilingBytes);
	});

	test('THE ORACLE: an item with no kernel reading is counted, never drawn at zero', () => {
		// item-c predates the kernel columns: it carries the process cells the
		// older run wrote and none of the three the kernel account added.
		const mixed = fixture(
			THREE_ITEMS.map((one) =>
				one.itemId === 'item-c'
					? { ...one, memTotal: '' as const, memAvailable: '' as const, memAvailableMin: '' as const }
					: one
			)
		);
		const board = memoryBoard(mixed.run, mixed.health);

		expect(board.from, 'the unrecorded item was dropped from the strip').toBe(3);
		expect(board.headroomFrom).toBe(2);
		expect(board.kernelSkipped, 'the skipped item was not counted').toBe(1);
		const gap = board.items.find((one) => one.itemId === 'item-c');
		expect(gap?.headroom.empty, 'an unmeasured kernel mark was drawn').toBe(true);
		expect(gap?.headroom.floorBytes).toBeNull();
		expect(gap?.headroom.floorBytes, 'absence was drawn as a measurement of zero').not.toBe(0);
		// The lead is still the minimum over the items that DID record one.
		expect(board.floorLowBytes).toBe(2 * GIB);

		// And the panel can say when the reading starts, off the rows it was
		// handed rather than off the archive.
		expect(board.kernelBeginsOn).toBe(DATE);
		expect(board.readFrom).toBe(DATE);
	});

	test('a run older than the kernel columns draws no mark and names the date', () => {
		// One run with the kernel account, one older run without. The older run is
		// the one drawn, so the track states its absence.
		const older = THREE_ITEMS.map((one) => ({
			...one,
			date: '2026-09-03',
			runId: '2026-09-03-1',
			memTotal: '' as const,
			memAvailable: '' as const,
			memAvailableMin: '' as const
		}));
		const { health } = ledgers(
			THREE_ITEMS.map((one) => ({ date: DATE, runId: RUN, ...one }))
		);
		const { hosts: oldHosts, health: oldHealth } = ledgers(older);
		const { runs, refused } = machineCounters(
			oldHosts,
			oldHealth,
			plan(['2026-09-03-1', 2]),
			limits()
		);
		expect(refused, 'the older fixture was refused').toEqual([]);
		expect(runs, 'the older fixture folded into no run').toHaveLength(1);
		const board = memoryBoard(runs[0], [...oldHealth, ...health]);

		expect(board.headroomFrom, 'a run with no kernel cells drew a mark').toBe(0);
		expect(board.floorLowBytes).toBeNull();
		expect(board.floorItemId).toBeNull();
		// The date the reading begins, taken from the rows in hand and bounded by
		// the earliest date among them - never a claim about the whole archive.
		expect(board.kernelBeginsOn).toBe(DATE);
		expect(board.readFrom).toBe('2026-09-03');
	});

	test('THE ORACLE: the two brackets run to the larger of themselves, not the machine', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);

		const servers = health.map((row) => Number(row.llama_rss_bytes));
		const workers = health.map((row) => Number(row.python_rss_bytes));
		expect(board.serverEndHighWater).toBe(Math.max(...servers));
		expect(board.workerHighWater).toBe(Math.max(...workers));
		// The bracket scale is the larger bracket and never the ceiling, so the
		// pair reads as two processes compared and never as a share of a budget.
		expect(board.bracketScaleBytes).toBe(Math.max(...servers, ...workers));
		expect(board.bracketScaleBytes).not.toBe(board.ceilingBytes);
		expect(board.bracketScaleBytes).toBeLessThan(board.ceilingBytes);
	});

	test('the two brackets added are an upper bound unless one item held both', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);
		// item-b holds the largest model-server figure and item-c the largest
		// worker figure, so no moment of this run held both.
		expect(board.coPeak).toBe(false);
		expect(board.serverEndHighWater).toBe(12 * GIB);
		expect(board.workerHighWater).toBe(1536 * MIB);
		expect(board.bothHighWater).toBe(12 * GIB + 1536 * MIB);

		// Move the worker maximum onto the item that owns the server maximum and
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
				serverRssBytes: 13 * GIB,
				memAvailableMin: 3 * GIB,
				memAvailable: 3 * GIB - 512 * MIB,
				load: 4
			})
		]);
		const mark = memoryBoard(leaking.run, leaking.health).items[0].headroom;
		expect(mark.recoveredBytes).toBe(-512 * MIB);
	});

	test('the load series is built from the same call', () => {
		const { run, health } = fixture(THREE_ITEMS);
		const board = memoryBoard(run, health);

		// One entry an item, in run order off the item's own clock.
		expect(board.items.map((one) => one.itemId)).toEqual(['item-a', 'item-b', 'item-c']);
		expect(board.loadHigh).toBe(6.5);
		expect(board.cores).toBe(4);
		expect(board.load.empty, 'load has no core count to be read against').toBe(false);
		// Busy runs near 100 on every row, which is why load is drawn beside it.
		expect(board.busySpan.median).toBe(88);
		expect(board.busySpan.max).toBe(100);
		expect(board.loadEmpty).toBe(false);
	});

	test('null machine columns are an empty panel, never a flat line at zero', () => {
		// Same three items, every machine cell blank. This is a day older than the
		// cells, which is a missing reading rather than an item that used none.
		const blank = THREE_ITEMS.map((one) => ({
			...one,
			peakRssBytes: '' as const,
			serverRssBytes: '' as const,
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
		expect(board.floorLowBytes).toBeNull();
		expect(board.floorLowBytes, 'absence was drawn as a measurement of zero').not.toBe(0);
		expect(board.bracketScaleBytes, 'an empty bracket drew a length').toBe(0);
		expect(board.loadHigh).toBeNull();
		expect(board.loadEmpty).toBe(true);
		expect(board.busySpan.empty).toBe(true);
		expect(board.empty).toBe(true);
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
				memAvailableMin: 5 * GIB,
				memAvailable: 5 * GIB,
				serverRssBytes: 7 * GIB,
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
		expect(board.floorLowBytes).toBeNull();
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
	test('THE ORACLE: the item minimum on the page recomputes from the canary ledger', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');
		await expect(board).toBeVisible();

		// A break panel, and it says so rather than leaving a reader to infer it.
		await expect(board).toHaveAttribute('data-panel-question', 'what is broken');
		const runId = await board.getAttribute('data-memory-board');
		expect(runId, 'the panel drew no run').not.toBe('empty');

		const floors = canaryRows('item-health')
			.filter((row) => row.run_id === runId)
			.map((row) => measured(row.os_mem_available_min_bytes))
			.filter((value): value is number => value !== null);
		expect(floors.length, 'the newest canary run records no kernel floor').toBeGreaterThan(0);

		// The figure the panel exists for, on an attribute rather than in prose:
		// a sentence can be renamed and a negative prose assertion then passes
		// while the page prints the wrong number.
		expect(Number(await board.getAttribute('data-memory-floor-low'))).toBe(Math.min(...floors));
		const owner = await board.getAttribute('data-memory-floor-item');
		expect(owner, 'the minimum reached the page with no item owning it').not.toBe('');

		// And exactly one mark is flagged, whatever ties behind it: "the item that
		// took the machine lowest" has to be an item a reader can go and look at,
		// so a tie is named once.
		const tightest = board.locator('[data-memory-item-tightest="true"]');
		await expect(tightest).toHaveCount(1);
		expect(await tightest.getAttribute('data-memory-item')).toBe(owner);
		expect(Number(await tightest.getAttribute('data-memory-item-floor'))).toBe(
			Math.min(...floors)
		);
	});

	test('THE ORACLE: an item with no kernel reading is hatched and its count printed', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');
		const runId = await board.getAttribute('data-memory-board');

		const rows = canaryRows('item-health').filter((row) => row.run_id === runId);
		// The canary's newest run carries one row the kernel account never
		// reached, beside rows it did.
		const drawn = rows.filter(
			(row) =>
				measured(row.llama_rss_bytes) !== null ||
				measured(row.python_rss_bytes) !== null ||
				measured(row.os_mem_available_min_bytes) !== null ||
				measured(row.os_mem_available_bytes) !== null
		);
		const without = drawn.filter((row) => measured(row.os_mem_available_min_bytes) === null);
		expect(without.length, 'the canary run has no item missing the kernel reading').toBe(1);

		expect(Number(await board.getAttribute('data-memory-kernel-skipped'))).toBe(without.length);
		expect(Number(await board.getAttribute('data-memory-kernel-from'))).toBe(
			drawn.length - without.length
		);
		// Printed, not only drawn: a hatched mark a reader cannot count is not a
		// count. And the sentence names the date the reading begins.
		const gap = board.locator('[data-memory-kernel-gap]');
		await expect(gap).toBeVisible();
		await expect(gap).toContainText('no kernel reading');
		const begins = await board.getAttribute('data-memory-kernel-begins');
		expect(begins, 'the page names no date for the start of the reading').not.toBe('');
		await expect(gap).toContainText(begins!);
		// The sentence is bounded by what the page read, not by the archive.
		const from = await board.getAttribute('data-memory-read-from');
		expect(from, 'the page bounds its sentence to nothing').not.toBe('');
		await expect(gap).toContainText(from!);
	});

	test('THE ORACLE: the disputed mark is off the page and the page says so', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');
		const runId = await board.getAttribute('data-memory-board');

		const peaks = canaryRows('item-health')
			.filter((row) => row.run_id === runId)
			.map((row) => measured(row.llama_rss_peak_bytes))
			.filter((value): value is number => value !== null);
		expect(peaks.length, 'the canary stopped writing the disputed column').toBeGreaterThan(0);

		// It stays in the ledger and it reaches no attribute the panel publishes.
		const drawnValues = await board.evaluate((node) =>
			[...node.attributes]
				.filter((one) => one.name.startsWith('data-memory-'))
				.map((one) => one.value)
		);
		expect(drawnValues, 'the disputed maximum is on the panel').not.toContain(
			String(Math.max(...peaks))
		);
		// And the surface that would have drawn it is where the reason is said.
		await expect(board.locator('[data-memory-not-drawn]')).toContainText(
			'not drawn here'
		);
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
				['data-memory-item-server-end', 'llama_rss_bytes'],
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

	test('the brackets are labelled at most and drawn against the larger of themselves', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-memory-board]');

		const server = measured(await board.getAttribute('data-memory-server-end-high-water'));
		const worker = measured(await board.getAttribute('data-memory-worker-high-water'));
		const scale = Number(await board.getAttribute('data-memory-bracket-scale'));
		expect(server, 'the model server bracket has no figure').not.toBeNull();
		expect(worker, 'the worker bracket has no figure').not.toBeNull();
		// Against the larger of the two and never against the machine, so the pair
		// cannot be read as a share of a budget.
		expect(scale).toBe(Math.max(server!, worker!));
		expect(scale).not.toBe(Number(await board.getAttribute('data-memory-ceiling')));
		await expect(board.locator('[data-memory-figure="server-end"]')).toContainText('at most');
		await expect(board.locator('[data-memory-figure="worker-end"]')).toContainText('at most');
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
