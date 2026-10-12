/** Deterministic article cost rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { articleCost, costTrack, runnerHourSeconds } from '../src/lib/console/machine/article-cost';
import { textRows } from '../src/lib/console/machine/records';
function itemRow(cells: Partial<Record<string, string | number>>): Record<string, string> {
	const row: Record<string, string> = {};
	for (const [key, value] of Object.entries(cells)) row[key] = String(value);
	return row;
}
test.describe('the three costs, as arithmetic', () => {
	test('processor and memory readings never cross a job or invent an unknown shard', () => {
		const base = { date: '2026-08-20', run_id: '2026-08-20-1', cpu_busy_pct: 50, item_total_ms: 1000 };
		const health = [
			itemRow({ ...base, machine_job: 'work', machine_shard: 0, item_index: 0, llama_rss_bytes: 100 }),
			itemRow({ ...base, machine_job: 'assemble', machine_shard: 0, item_index: 1, llama_rss_bytes: 300 }),
			itemRow({ ...base, item_index: 2, llama_rss_bytes: 600 }),
			itemRow({ ...base, item_index: 3, llama_rss_bytes: 900 })
		];
		const cost = articleCost(health, [{ date: base.date, run_id: base.run_id, job: 'assemble', shard: 0, cpu_logical_processors: 8 }]);
		expect(cost.processorSeconds).toMatchObject({ from: 1, outOf: 4, mid: 4 });
		expect(cost.addedBytes).toMatchObject({ from: 0, mid: null });
	});
	test('processor time is the busy share across measured logical processors', () => {
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 50, item_total_ms: 1000 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 25, item_total_ms: 2000 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 25, item_total_ms: 1000 })
		];
		const cost = articleCost(health, [{ date: '2026-08-20', run_id: 'r1', shard: 0, cpu_logical_processors: 8 }]);
		expect(cost.processorSeconds.from, 'not every offered article was measured').toBe(3);
		expect(cost.processorSeconds.outOf).toBe(3);
		expect(cost.processorSeconds.low).toBeCloseTo(2, 6);
		expect(cost.processorSeconds.mid).toBeCloseTo(4, 6);
		expect(cost.processorSeconds.high).toBeCloseTo(4, 6);
		expect(cost.processors).toEqual([8]);
	});
	test('THE ORACLE: a run whose machine record names no processor count is a dash', () => {
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 80, item_total_ms: 1000 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 40, item_total_ms: 2000 })
		];
		const blind = articleCost(health, [{ date: '2026-08-20', run_id: 'r1', shard: 0, cpu_logical_processors: null }]);
		expect(blind.processorSeconds.mid, 'a processor count was assumed from nothing').toBeNull();
		expect(blind.processorSeconds.low).toBeNull();
		expect(blind.processorSeconds.high).toBeNull();
		expect(blind.processorSeconds.from).toBe(0);
		expect(blind.processorSeconds.outOf).toBe(2);
		expect(blind.processors).toEqual([]);
		const seen = articleCost(health, [{ date: '2026-08-20', run_id: 'r1', shard: 0, cpu_logical_processors: 4 }]);
		expect(seen.processorSeconds.low).toBeCloseTo(3.2, 6);
		expect(seen.processorSeconds.high).toBeCloseTo(3.2, 6);
		expect(seen.processorSeconds.from).toBe(2);
		expect(seen.processors).toEqual([4]);
	});
	test('articles no machine record answered for are counted, not dropped', () => {
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'blind', machine_shard: 0, cpu_busy_pct: 80, item_total_ms: 1000 }),
			itemRow({ date: '2026-08-20', run_id: 'seen', machine_shard: 0, cpu_busy_pct: 50, item_total_ms: 1000 }),
			itemRow({ date: '2026-08-20', run_id: 'untimed', machine_shard: 0, cpu_busy_pct: 90 })
		];
		const cost = articleCost(health, [
			{ date: '2026-08-20', run_id: 'blind', shard: 0, cpu_logical_processors: null },
			{ date: '2026-08-20', run_id: 'seen', shard: 0, cpu_logical_processors: 4 }
		]);
		expect(cost.processorSeconds.outOf, 'the unanswered article was dropped').toBe(2);
		expect(cost.processorSeconds.from, 'an unanswered article was treated as measured').toBe(1);
		expect(cost.processorSeconds.mid).toBeCloseTo(2, 6);
	});
	test('agreeing duplicates count once and conflicting logical counts withhold the same key in both orders', () => {
		const health = [itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 50, item_total_ms: 2000 })];
		const host = { date: '2026-08-20', run_id: 'r1', shard: 0, cpu_logical_processors: 4 };
		const agreeing = articleCost(health, [host, host]);
		expect(agreeing.processorSeconds.from).toBe(1);
		expect(agreeing.processorSeconds.mid).toBeCloseTo(4, 6);
		expect(agreeing.processors).toEqual([4]);
		const other = { ...host, cpu_logical_processors: 8 };
		for (const rows of [[host, other], [other, host]]) {
			const cost = articleCost(health, rows);
			expect(cost.processorSeconds.from).toBe(0);
			expect(cost.processorSeconds.mid).toBeNull();
			expect(cost.processorSeconds.outOf).toBe(1);
			expect(cost.processors).toEqual([]);
		}
	});
	test('all four key cells matter, historical job means work only and blank or null shard never means zero', () => {
		const base = { date: '2026-08-20', run_id: 'r1', cpu_busy_pct: '50', item_total_ms: '2000' };
		const work = { date: base.date, run_id: base.run_id, job: 'work', shard: 0, cpu_logical_processors: 8 };
		const health = [{ ...base, machine_shard: '0' }];
		const cost = articleCost(health, [work, { ...work, job: 'plan', cpu_logical_processors: 4 },
			{ ...work, job: 'assemble', cpu_logical_processors: 16 }]);
		expect(cost.processorSeconds).toMatchObject({ from: 1, outOf: 1, mid: 8 });
		expect(runnerHourSeconds(cost.processors)).toBe(28800);
		for (const changed of [{ date: '2026-08-21' }, { run_id: 'r2' }, { job: 'plan' }]) {
			expect(articleCost(health, [{ ...work, ...changed }]).processorSeconds).toMatchObject({ from: 0, outOf: 1, mid: null });
		}
		for (const shard of [null, '', ' ', '-1', '0.5', 'bad']) {
			expect(articleCost(health, [{ ...work, shard }]).processorSeconds.from).toBe(0);
			// Raw native nulls also exercise the actual text adapter's empty representation.
			const [unknown] = textRows([{ ...base, machine_shard: shard }]);
			expect(articleCost([unknown], [work]).processorSeconds).toMatchObject({ from: 0, outOf: 1 });
			expect(articleCost([{ ...unknown, item_index: '0', llama_rss_bytes: '100' },
				{ ...unknown, item_index: '1', llama_rss_bytes: '200' }], []).addedBytes.from).toBe(0);
		}
	});
	test('recorded busy zero is a measured zero, not a missing reading', () => {
		const cost = articleCost([itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0,
			cpu_busy_pct: 0, item_total_ms: 2000 })], [
			{ date: '2026-08-20', run_id: 'r1', shard: 0, cpu_logical_processors: 8 }
		]);
		expect(cost.processorSeconds).toEqual({ low: 0, mid: 0, high: 0, from: 1, outOf: 1 });
	});
	test('model time is reading the prompt and writing the reply, added up', () => {
		const cost = articleCost([
			itemRow({ date: '2026-08-20', run_id: 'r1', prefill_ms: 1200, decode_ms: 800 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', prefill_ms: 100, decode_ms: 300 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', prefill_ms: 1000 })
		], []);
		expect(cost.modelSeconds.from).toBe(2);
		expect(cost.modelSeconds.outOf).toBe(2);
		expect(cost.modelSeconds.low).toBeCloseTo(0.4, 6);
		expect(cost.modelSeconds.mid).toBeCloseTo(1.2, 6);
		expect(cost.modelSeconds.high).toBeCloseTo(2, 6);
	});
	test('added memory is a signed step between neighbours of ONE shard', () => {
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 0, llama_rss_bytes: 100 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 1, llama_rss_bytes: 160 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 2, llama_rss_bytes: 140 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 4, llama_rss_bytes: 900 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 1, item_index: 0, llama_rss_bytes: 500 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 1, item_index: 1, llama_rss_bytes: 510 })
		];
		const cost = articleCost(health, []);
		expect(cost.addedBytes.from, 'a gap or a shard boundary was counted as a step').toBe(3);
		expect(cost.shards).toBe(2);
		expect(cost.addedBytes.low).toBe(-20);
		expect(cost.addedBytes.mid).toBe(10);
		expect(cost.addedBytes.high).toBe(60);
	});
	test('a shard with one article has no step, not zero', () => {
		const cost = articleCost([itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 0, llama_rss_bytes: 100 })], []);
		expect(cost.addedBytes.from).toBe(0);
		expect(cost.addedBytes.mid).toBeNull();
		expect(cost.shards).toBe(0);
	});
	test('the track holds zero, so returned memory is on the giving side', () => {
		const track = costTrack({ low: -100, mid: -50, high: 300, from: 3, outOf: 3 }, 400);
		expect(track).not.toBeNull();
		expect(track!.floor).toBe(-100);
		expect(track!.ceiling).toBe(300);
		expect(track!.zero).toBe('25.0000%');
		expect(track!.at).toBe('12.5000%');
		expect(track!.drawn).toBe(true);
	});
	test('agreeing readings draw no band, not a line too thin to see', () => {
		const track = costTrack({ low: 10, mid: 10, high: 10, from: 4, outOf: 4 }, 400);
		expect(track!.drawn).toBe(false);
		expect(track!.length).toBe('0.0000%');
	});
	test('a runner-hour is quoted on the smallest measured machine', () => {
		expect(runnerHourSeconds([4])).toBe(14400);
		expect(runnerHourSeconds([8, 4])).toBe(14400);
		expect(runnerHourSeconds([])).toBeNull();
	});
});
test.describe('the panel', () => {
	test('a figure no written row can fill is absent, not zero', () => {
		const cost = articleCost([itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 0 })], []);
		expect(cost.addedBytes.from).toBe(0);
		expect(cost.addedBytes.outOf).toBe(0);
		expect(cost.addedBytes.mid, 'the missing memory step was reported as zero').toBeNull();
	});
});
