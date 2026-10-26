/** Native machine cards preserve measured flags, clocks and independent host ratios. */
import { expect, test } from './support/door-page';
import { WATCHED_FLAG, type HostFingerprint } from '../src/lib/console/machine/host-types';
import { machineCounters, type MachineLimits, type MachineRun } from '../src/lib/console/machine/counters';
import { copySpeedSentence, clockSentence, machineCards, uptimeSentence } from '../src/lib/charts/machine-cards';
import { ledgers, plan, type ShardReading } from './support/machine-rows';
import { numberFormat } from './support/number-format';
/** The flags a card has to draw a chip for.
 *
 * The one copy, bound to the Python enum by
 * `backend/tests/contracts/test_frontend_vocabularies.py`, so this is the
 * contract's list and not a second one typed here.
 */
const WATCHED: readonly string[] = WATCHED_FLAG;
const DATE = '2026-09-18';
const RUN = '2026-09-18-1';
const MIB = 1024 * 1024;
const TEST_LIMITS: MachineLimits = {
    contextWindow: 8192,
    jobTimeoutSeconds: 3600
};
function foldedRun(readings: ShardReading[], shards = readings.length): MachineRun {
    const stamped = readings.map((reading) => ({ date: DATE, runId: RUN, ...reading }));
    const { hosts, health } = ledgers(stamped);
    const { runs, refused } = machineCounters(hosts, health, plan([RUN, shards]), TEST_LIMITS);
    expect(refused, 'the fixture was refused').toEqual([]);
    expect(runs, 'the fixture folded into no run').toHaveLength(1);
    return runs[0];
}
function machineShard(over: ShardReading): ShardReading {
    return {
        cachedTokens: 0,
        jobSeconds: 100,
        longestSequence: 1000,
        ...over
    };
}
function host(over: Partial<HostFingerprint>): HostFingerprint {
	const row = {
		version: '2026-10-10',
		date: DATE,
		run_id: RUN,
		job: 'work',
		pipeline_name: null,
		task_name: null,
		shard: 0,
		fingerprint: 'machine-a',
		fingerprint_version: 2,
		cpu_model: 'AMD EPYC 7763 64-Core Processor',
		cpu_vendor: 'AuthenticAMD',
		cpu_family: 25,
		cpu_model_number: 1,
		cpu_stepping: 1,
		microcode: '0x1',
		cpu_physical_cores: 4,
		cpu_logical_processors: 8,
		cpu_allowed_processors: null,
		cpu_quota_cores: null,
		cpu_quota_state: null,
		cpu_target_measured_at: null,
		l3_cache_bytes: 32 * MIB,
		machine_memory_total_mib: null,
		cpu_observed_mhz: 2800,
		cpu_reported_max_mhz: null,
		flags: '',
		boot_seconds: 125,
		memcpy_gib_s: 10,
		memcpy_probe_mib: 128,
		vm_size: 'Standard_D4s_v5',
		vm_location: 'eastus',
		vm_zone: '1',
		vm_fault_domain: '0',
		runner_name: 'runner-a',
		measured_at: `${DATE}T00:00:00Z`,
		model_load_ms: 400,
		job_seconds: 100,
		server_prompt_tokens: 200,
		server_prompt_seconds: 10,
		...over
	};
	return {
		...row,
		job: row.job === undefined ? 'work' : row.job,
		pipeline_name: row.pipeline_name ?? null,
		task_name: row.task_name ?? null
	};
}
test.describe('the machines this run drew', () => {
	test('machine cards preserve flags, copy speed, clocks and L3 ratios on written rows', () => {
		const run = foldedRun([
			machineShard({
				shard: 0,
				cpuModel: 'AMD EPYC 7763 64-Core Processor',
				fingerprint: 'full',
				serverPromptTokens: 200,
				serverPromptSeconds: 10,
				writtenTokens: 90,
				writeSeconds: 9
			}),
			machineShard({
				shard: 1,
				cpuModel: 'Intel Xeon Platinum 8370C CPU @ 2.80GHz',
				fingerprint: 'empty',
				serverPromptTokens: 50,
				serverPromptSeconds: 10,
				writtenTokens: 100,
				writeSeconds: 25
			})
		]);
		const cards = machineCards(
			run,
			[
				host({
					fingerprint: 'full',
					shard: 0,
					cpu_model: 'AMD EPYC 7763 64-Core Processor',
					flags: WATCHED.join(' '),
					l3_cache_bytes: 64 * MIB,
					memcpy_gib_s: 12,
					memcpy_probe_mib: 256,
					cpu_observed_mhz: 2750,
					boot_seconds: 125
				}),
				host({
					fingerprint: 'empty',
					shard: 1,
					cpu_model: 'Intel Xeon Platinum 8370C CPU @ 2.80GHz',
					flags: '',
					l3_cache_bytes: 32 * MIB,
					memcpy_gib_s: 6,
					memcpy_probe_mib: 32,
					cpu_observed_mhz: null,
					boot_seconds: null
				})
			],
			{
				watchedFlags: WATCHED,
				colour: { stops: 4, floor: 0.35 },
				numberFormat,
				recording: true,
				cacheMargin: 2
			}
		);

		expect(cards.record).toBe('recorded');
		expect(cards.cards).toHaveLength(2);
		const byName = new Map(cards.cards.map((card) => [card.identity.name, card]));
		const full = byName.get('AMD EPYC 7763');
		const empty = byName.get('Intel Xeon Platinum 8370C');
		expect(full?.flags).toEqual(WATCHED.map((name) => ({ name, present: true })));
		expect(empty?.flags).toEqual(WATCHED.map((name) => ({ name, present: false })));
		expect(full?.l3Bar.state).toBe('drawn');
		expect(empty?.l3Bar.state).toBe('drawn');
		expect((full?.l3Bar.fraction ?? 0) / (empty?.l3Bar.fraction ?? 1)).toBeCloseTo(2, 4);
		expect(copySpeedSentence(full!, numberFormat)).toBe(
			'12 GiB/s, over a 256 MiB buffer against 64 MiB of L3 - 4 times it.'
		);
		expect(copySpeedSentence(empty!, numberFormat)).toBe(
			'No copy speed: the probe used a 32 MiB buffer against 32 MiB of L3, 1 times it, and a reading has to clear 2 times to be sure the copy left the cache.'
		);
		expect(clockSentence(full!)).toBe(
			'Observed sample average 2750 MHz; reported hardware maximum unknown. The sample is not a sustained rate.'
		);
		expect(clockSentence(empty!)).toBe('Observed and reported maximum frequencies are unknown.');
		expect(uptimeSentence(full!, numberFormat)).toBe('Up 2 m 5 s when we measured it.');
		expect(uptimeSentence(empty!, numberFormat)).toBe('Uptime was not recorded on this job.');
	});

});
/** Which of the record's states the page is in, said in an attribute.
 *
 * **The assertion may not be a negative one about prose.** "The page contains
 * no sentence claiming the record starts later" passes the day somebody renames
 * that sentence, while the page goes on printing the lie - so the state is an
 * attribute that is always set, and every sentence the panel can print is tied
 * to the value it belongs to. A state that stops being set takes this red with
 * it.
 *
 * The three states themselves are asserted over built rows in
 * `console-machine-cards.spec.ts`. The canary holds one of them - a day the
 * record answered for - and it is the check that proves the binding.
 */
test.describe('the machine record names which state it is in', () => {
    test('a recorded row names the record state, so a loss is never claimed', () => {
        const run = foldedRun([
            machineShard({
                shard: 0,
                cpuModel: 'AMD EPYC 7763 64-Core Processor',
                fingerprint: 'recorded',
                serverPromptTokens: 200,
                serverPromptSeconds: 10,
                writtenTokens: 90,
                writeSeconds: 9
            })
        ]);
        const cards = machineCards(run, [
            host({
                fingerprint: 'recorded',
                shard: 0,
                cpu_model: 'AMD EPYC 7763 64-Core Processor',
                flags: WATCHED.join(' ')
            })
        ], {
            watchedFlags: WATCHED,
            colour: { stops: 4, floor: 0.35 },
            numberFormat,
            recording: true,
            cacheMargin: 2
        });
        expect(cards.record).toBe('recorded');
        expect(cards.lost).toBeNull();
        expect(cards.lostNote).toBeNull();
        expect(cards.nothing).toBeNull();
        expect(cards.cards).toHaveLength(1);
    });
});
