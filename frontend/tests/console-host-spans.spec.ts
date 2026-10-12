/** Native host measurements keep their own clocks, logical processors and four-cell joins. */
import { expect, test } from '@playwright/test';
import { articleCost } from '../src/lib/console/machine/article-cost';
import { countersFrom, processors, textRows } from '../src/lib/console/machine/records';
import type { Row } from '../src/lib/data/ledger';

const DATE = '2030-06-15';
const RUN = '2030-06-15-1';
const LIMITS = { contextWindow: 8192, jobTimeoutSeconds: 9000 };

function host(cells: Row = {}): Row {
	return {
		version: '2026-10-10', date: DATE, run_id: RUN, job: 'work', shard: 0,
		cpu_logical_processors: 4, ...cells
	};
}

function item(cells: Row = {}): Row {
	return {
		date: DATE, run_id: RUN, machine_job: 'work', machine_shard: 0,
		item_total_ms: 1000, cpu_busy_pct: 50, ...cells
	};
}

test.describe('the actual native host and article readers', () => {
	test('whole-host logical processors and the two independent clocks survive the native adapter', () => {
		const hosts = [host({
			cpu_allowed_processors: 1, cpu_quota_cores: 0.5, cores: 128, threads: 256,
			server_prompt_tokens: 1000, server_prompt_seconds: 100
		})];
		const items = [item({
			input_tokens: 1100, cached_tokens: 100, prefill_ms: 200000,
			output_tokens: 10, decode_ms: 5000
		})];
		const counters = countersFrom(hosts, items, [{ run_id: RUN, shards: 4 }], LIMITS);
		expect(counters.refused).toEqual([]);
		expect(counters.runs).toHaveLength(1);
		const run = counters.runs[0];
		expect(run.reported[0].logicalProcessors).toBe(4);
		expect(run.readTokensPerSecond).toEqual({ value: 10, from: 1, outOf: 4 });
		expect(run.writeTokensPerSecond).toEqual({ value: 2, from: 1, outOf: 4 });
		expect(run.clocks.server).toEqual({ tokens: 1000, seconds: 100, parts: 1, rate: 10 });
		expect(run.clocks.ledger).toEqual({ tokens: 1000, seconds: 200, parts: 1, rate: 5 });
		expect(run.clocks.gapPct).toBe(50);
		expect(run.clocks.agrees).toBe(false);
		const cost = articleCost(textRows(items), processors(hosts));
		expect(cost.processors).toEqual([4]);
		expect(cost.processorSeconds).toEqual({ low: 2, mid: 2, high: 2, from: 1, outOf: 1 });
		expect(cost.modelSeconds).toEqual({ low: 205, mid: 205, high: 205, from: 1, outOf: 1 });
	});

	test('date, run, job and shard each remain part of the article-to-host join', () => {
		const hosts = [
			host(),
			host({ date: '2030-06-16', cpu_logical_processors: 8 }),
			host({ run_id: '2030-06-15-2', cpu_logical_processors: 12 }),
			host({ job: 'plan', cpu_logical_processors: 16 }),
			host({ shard: 1, cpu_logical_processors: 2 })
		];
		const items = [
			item(),
			item({ date: '2030-06-16' }),
			item({ run_id: '2030-06-15-2' }),
			item({ machine_job: 'plan' }),
			item({ machine_shard: 1 })
		];
		const named = processors(hosts);
		expect(items.map((row) => articleCost(textRows([row]), named).processorSeconds.mid))
			.toEqual([2, 4, 6, 8, 1]);
		const cost = articleCost(textRows(items), named);
		expect(cost.processors).toEqual([2, 4, 8, 12, 16]);
		expect(cost.processorSeconds).toEqual({ low: 1, mid: 4, high: 8, from: 5, outOf: 5 });
		// An absent historical job is work; an absent shard is never shard zero.
		expect(articleCost(textRows([item({ machine_job: '' })]), named).processorSeconds.mid).toBe(2);
	});

	test('invalid or unknown shard cells cannot join to shard zero', () => {
		const hosts = processors([host()]);
		for (const shard of ['', null, -1, 0.5, NaN, 'Infinity']) {
			const cost = articleCost(textRows([item({
				machine_shard: shard, prefill_ms: 0, decode_ms: 0
			})]), hosts);
			expect(cost.processorSeconds).toEqual({ low: null, mid: null, high: null, from: 0, outOf: 1 });
			expect(cost.modelSeconds).toEqual({ low: 0, mid: 0, high: 0, from: 1, outOf: 1 });
			expect(cost.processors).toEqual([]);
		}
	});

	test('the finite legacy versions preserve unknown logical counts instead of promoting threads', () => {
		for (const version of ['2026-09-16', '2026-09-17', '2026-09-18', '2026-09-19', '2026-09-20']) {
			const hosts = [host({
				version, cpu_logical_processors: 64, cores: 4, threads: 8,
				server_prompt_tokens: 1000, server_prompt_seconds: 100
			})];
			const named = processors(hosts);
			expect(named).toEqual([{ date: DATE, run_id: RUN, job: 'work', shard: 0, cpu_logical_processors: null }]);
			const cost = articleCost(textRows([item()]), named);
			expect(cost.processorSeconds).toEqual({ low: null, mid: null, high: null, from: 0, outOf: 1 });
			const counters = countersFrom(hosts, [], [{ run_id: RUN, shards: 1 }], LIMITS);
			expect(counters.refused).toEqual([]);
			expect(counters.runs[0].reported[0].logicalProcessors).toBeNull();
			expect(counters.runs[0].readTokensPerSecond).toEqual({ value: 10, from: 1, outOf: 1 });
		}
		expect(processors([host({ version: '2099-01-01' })])).toEqual([]);
	});

	test('repeated host readings count once and conflicting logical counts leave an offered article unmeasured', () => {
		const health = textRows([item()]);
		expect(articleCost(health, processors([host(), host()])).processorSeconds)
			.toEqual({ low: 2, mid: 2, high: 2, from: 1, outOf: 1 });
		for (const hosts of [
			[host(), host({ cpu_logical_processors: 8 })],
			[host({ cpu_logical_processors: 8 }), host()]
		]) {
			expect(articleCost(health, processors(hosts)).processorSeconds)
				.toEqual({ low: null, mid: null, high: null, from: 0, outOf: 1 });
			expect(countersFrom(hosts, [], [{ run_id: RUN, shards: 1 }], LIMITS).runs).toEqual([]);
		}
	});

	test('unknown or invalid logical counts are not zero processor cost, while measured idle time is zero', () => {
		for (const count of [null, '', 0, -1, 0.5, NaN, Infinity]) {
			const cost = articleCost(textRows([item()]), processors([host({ cpu_logical_processors: count })]));
			expect(cost.processorSeconds).toEqual({ low: null, mid: null, high: null, from: 0, outOf: 1 });
			expect(cost.processors).toEqual([]);
		}
		const idle = articleCost(textRows([item({ cpu_busy_pct: 0 })]), processors([host()]));
		expect(idle.processorSeconds).toEqual({ low: 0, mid: 0, high: 0, from: 1, outOf: 1 });
		expect(idle.processors).toEqual([4]);
	});
});
