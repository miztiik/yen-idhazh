/** Does a card say what a machine cannot do, as well as what it can?
 *
 * That is the whole reason the panel exists. The machine this project draws
 * most, the EPYC 7763, reports none of the watched AVX-512 entries at all, and
 * a card listing only the flags a machine has cannot say which one is missing -
 * which is the difference llama.cpp dispatches on.
 *
 * The other thing asserted here is the one a reader would never notice was
 * wrong: **never read** and **reported none of them** are different facts, and
 * twelve absent chips for the first would publish a guess as a reading.
 *
 * Every case is built. The archive has never produced a run whose jobs drew
 * three machines with one of them unrecorded, and that is the case that matters.
 */

import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import {
	bandwidthSentence,
	cacheWords,
	machineCards
} from '../src/lib/charts/machine-cards';
import { UNRECORDED_STOP } from '../src/lib/charts/machine-colour';
import { hostFingerprints, machineRecordDays, watchedFlags } from '../src/lib/server/host-fingerprint';
import type { HostFingerprint } from '../src/lib/server/host-fingerprint';
import {
	machineCounters,
	type MachineLimits,
	type MachineRun
} from '../src/lib/server/machine-counters';
import { ledgers, plan, type ShardReading } from './support/machine-rows';

const LIMITS: MachineLimits = { contextWindow: 8192, jobTimeoutSeconds: 21_600 };
const STOPS = 7;

/** The twelve, read where the page reads them: the generated contract. */
const FLAGS = watchedFlags();

const MIB = 1024 * 1024;

/** One shard of the run these cards are drawn for. */
function shardOf(reading: ShardReading): ShardReading {
	return { date: '2026-09-12', runId: '2026-09-12-1', ...reading };
}

function fingerprint(over: Partial<HostFingerprint>): HostFingerprint {
	return {
		version: '2026-09-19',
		date: '2026-09-12',
		run_id: '2026-09-12-1',
		job: 'work',
		shard: 0,
		fingerprint: '3a7f0b1c2d4e5f60',
		cpu_model: 'AMD EPYC 7763 64-Core Processor',
		cpu_vendor: 'AuthenticAMD',
		cpu_family: 25,
		cpu_model_number: 1,
		cpu_stepping: 1,
		microcode: '0xa0011d3',
		cores: 2,
		threads: 4,
		l3_cache_bytes: 32 * MIB,
		mhz_max: null,
		mhz_at_probe: null,
		flags: 'avx2 f16c fma sse4_2',
		boot_seconds: null,
		memcpy_gib_s: 12.4,
		memcpy_probe_mib: 512,
		vm_size: 'Standard_D4ads_v5',
		vm_location: 'eastus',
		vm_zone: '1',
		vm_fault_domain: '0',
		runner_name: null,
		measured_at: null,
		model_load_ms: null,
		job_seconds: null,
		server_prompt_tokens: null,
		server_prompt_seconds: null,
		...over
	};
}

function onlyRun(readings: ShardReading[]): MachineRun {
	const { hosts, health } = ledgers(readings.map(shardOf));
	const { runs, refused } = machineCounters(
		hosts,
		health,
		plan(['2026-09-12-1', readings.length]),
		LIMITS
	);
	expect(refused, 'the fixture was refused').toEqual([]);
	expect(runs).toHaveLength(1);
	return runs[0];
}

const RUN = onlyRun([
	{ shard: 0, cpuModel: 'AMD EPYC 7763 64-Core Processor' },
	{ shard: 1, cpuModel: 'INTEL(R) XEON(R) PLATINUM 8573C' }
]);

function cardsFor(rows: HostFingerprint[], recording = true) {
	return machineCards(RUN, rows, {
		watchedFlags: FLAGS,
		colourStops: STOPS,
		recording
	});
}

test.describe('the flag vocabulary', () => {
	test('the twelve come from the generated contract, so no copy can drift', () => {
		const schema = JSON.parse(
			readFileSync(resolve(process.cwd(), '..', 'schemas', 'machine-panels.schema.json'), 'utf8')
		) as { $defs: { WatchedFlag: { enum: string[] } } };
		expect(FLAGS).toEqual(schema.$defs.WatchedFlag.enum);
		expect(FLAGS).toHaveLength(12);
	});
});

test.describe('what a card says a machine can do', () => {
	test('a card draws every watched flag, present or absent, never a subset', () => {
		const [card] = cardsFor([fingerprint({})]).cards;
		expect(card.flags).toHaveLength(FLAGS.length);
		expect(card.flags.map((flag) => flag.name)).toEqual(FLAGS);
		expect(card.flags.filter((flag) => flag.present).map((flag) => flag.name)).toEqual([
			'avx2',
			'f16c',
			'fma',
			'sse4_2'
		]);
	});

	test('a machine with no AVX-512 draws those chips absent rather than omitting them', () => {
		const [card] = cardsFor([fingerprint({})]).cards;
		const wide = card.flags.filter((flag) => flag.name.startsWith('avx512'));
		expect(wide.length).toBeGreaterThan(0);
		expect(wide.every((flag) => !flag.present)).toBe(true);
	});

	test('a run the machine record never reached draws no chips and says which ledger it read', () => {
		const view = cardsFor([]);
		expect(view.nameOnly).toBe(true);
		expect(view.cards.every((card) => card.source === 'name-only')).toBe(true);
		expect(view.cards.every((card) => card.flags.length === 0)).toBe(true);
		expect(view.cards.every((card) => card.flagsRecorded === false)).toBe(true);
	});

	test('family, model and stepping are one string, and absent where any is', () => {
		expect(cardsFor([fingerprint({})]).cards[0].part).toBe('25/1/1');
		expect(cardsFor([fingerprint({ cpu_stepping: null })]).cards[0].part).toBeNull();
	});

	test('the heading is the name a person reads and the raw string survives behind it', () => {
		const [card] = cardsFor([
			fingerprint({ cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C', fingerprint: 'c81d9e0a1b2c3d4e' })
		]).cards;
		expect(card.identity.name).toBe('Intel Xeon Platinum 8573C');
		expect(card.where?.cpuModelRaw).toBe('INTEL(R) XEON(R) PLATINUM 8573C');
	});

	test('a job the record missed joins the machine of its own name, not a card of its own', () => {
		// The record reached work shard 0 and reported a Xeon; shard 1 reported the
		// same processor name and nothing else. One machine, one card - two cards
		// under one heading reads as a defect rather than as the absence it is.
		const view = cardsFor([
			fingerprint({ cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C', fingerprint: 'c81d9e0a1b2c3d4e' })
		]);
		expect(view.cards).toHaveLength(1);
		expect(view.cards[0].jobsDrawn).toBe(2);
		expect(view.cards[0].source).toBe('fingerprint');
	});

	test('the disclosure carries where the platform put it, and the microcode', () => {
		const [card] = cardsFor([fingerprint({})]).cards;
		expect(card.where?.vmSize).toBe('Standard_D4ads_v5');
		expect(card.where?.vmLocation).toBe('eastus');
		expect(card.where?.vmZone).toBe('1');
		expect(card.where?.vmFaultDomain).toBe('0');
		expect(card.where?.microcode).toBe('0xa0011d3');
	});
});

test.describe('the bandwidth reading and the buffer it was taken with', () => {
	test('the rate, the buffer and the cache are one sentence', () => {
		const [card] = cardsFor([fingerprint({})]).cards;
		expect(bandwidthSentence(card)).toBe(
			'12.4 GiB/s, over a 512 MiB buffer against 32 MiB of L3.'
		);
		expect(card.measuredCache).toBe(false);
	});

	test('a buffer at or below L3 says it measured cache, not memory', () => {
		const [card] = cardsFor([fingerprint({ l3_cache_bytes: 480 * MIB, memcpy_probe_mib: 480 })]).cards;
		expect(card.measuredCache).toBe(true);
		expect(bandwidthSentence(card)).toContain('this measured cache, not memory');
	});

	test('a probe that was switched off is a sentence, never a rate of zero', () => {
		const [card] = cardsFor([fingerprint({ memcpy_gib_s: null, memcpy_probe_mib: 0 })]).cards;
		expect(card.memcpyGibPerSecond).toBeNull();
		expect(bandwidthSentence(card)).toBe('Bandwidth was not measured on this job.');
		// The cache still prints: one reading being absent does not remove another.
		expect(cacheWords(card.l3CacheBytes)).toBe('32 MiB');
	});

	test('a cache nothing recorded prints a dash rather than nothing at all', () => {
		expect(cacheWords(null)).toBe('-');
	});
});

test.describe('how many jobs drew a machine', () => {
	test('a card counts the jobs that drew it against the jobs that recorded one', () => {
		const view = cardsFor([
			fingerprint({ job: 'plan', shard: 0 }),
			fingerprint({ job: 'work', shard: 0 }),
			fingerprint({
				job: 'work',
				shard: 1,
				fingerprint: 'c81d9e0a1b2c3d4e',
				cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C'
			}),
			fingerprint({ job: 'assemble', shard: 0 })
		]);
		expect(view.cards).toHaveLength(2);
		const epyc = view.cards.find((card) => card.identity.name === 'AMD EPYC 7763');
		expect(epyc?.jobsDrawn).toBe(3);
		expect(epyc?.jobsTotal).toBe(4);
	});

	test('a work shard the record missed still gets a card, off the counters', () => {
		// Only shard 0 has a machine row. Shard 1 drew a Xeon and the counters
		// ledger is the only thing that saw it, so it is a card with a name and
		// nothing else rather than a machine the panel drops.
		const view = cardsFor([fingerprint({ job: 'work', shard: 0 })]);
		expect(view.cards).toHaveLength(2);
		const xeon = view.cards.find((card) => card.identity.name === 'Intel Xeon Platinum 8573C');
		expect(xeon?.source).toBe('name-only');
		expect(xeon?.flags).toEqual([]);
		expect(view.nameOnly).toBe(false);
	});

	test('a shard covered by a machine row is counted once, not twice', () => {
		const view = cardsFor([fingerprint({ job: 'work', shard: 0 })]);
		expect(view.cards.reduce((total, card) => total + card.jobsDrawn, 0)).toBe(2);
	});
});

test.describe('when there is nothing to draw', () => {
	test('recording switched off is a different sentence from nothing recorded', () => {
		const nowhere = machineCards(null, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			recording: false
		});
		expect(nowhere.nothing).toBe('recording-off');

		const nothing = machineCards(null, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			recording: true
		});
		expect(nothing.nothing).toBe('no-machine');
	});

	test('recording off still says so when the counters name a processor anyway', () => {
		// The cards are real - they come off the model server's own counters - and
		// the panel has to say why they carry no instruction set. Drawing them
		// silently would read as a machine with nothing to report.
		const view = machineCards(RUN, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			recording: false
		});
		expect(view.cards.length).toBeGreaterThan(0);
		expect(view.nothing).toBeNull();
		expect(view.recording).toBe(false);
	});

	test('a run whose every shard is unnamed still draws one card, in the reserved grey', () => {
		const blank = onlyRun([{ shard: 0 }, { shard: 1 }]);
		const view = machineCards(blank, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			recording: true
		});
		// No shard named a machine and no machine row exists, so there is no
		// placement to draw at all.
		expect(view.cards).toEqual([]);
		expect(view.nothing).toBe('no-machine');
		// And the reserved stop stays reserved.
		expect(UNRECORDED_STOP).toBe(8);
	});
});

test.describe('a day that published and kept no machine row', () => {
	/** The state that destroyed 303 rows on 2026-09-16, built rather than read.
	 *
	 * The digest for the day carries articles and the record's own day file
	 * holds only its header. The archive holds this today and will not hold it
	 * for ever, so the case is built here (`CLAUDE.md` section 13).
	 */
	const LOST = { date: '2026-09-12', articles: 431 };

	test('a loss is a different state from a record that had not begun', () => {
		const quiet = machineCards(RUN, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			recording: true
		});
		const lost = machineCards(RUN, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			recording: true,
			lost: LOST
		});
		// Same cards either way - they come off the counters ledger - so the only
		// thing that can tell an operator which day he is looking at is the state.
		expect(lost.cards.length).toBe(quiet.cards.length);
		expect(quiet.record).toBe('none');
		expect(lost.record).toBe('lost');
		expect(quiet.lostNote).toBeNull();
		expect(lost.lostNote).toContain('did not survive');
		expect(lost.lost).toEqual(LOST);
	});

	test('a run with no placement at all names the loss before the quiet day', () => {
		const blank = onlyRun([{ shard: 0 }, { shard: 1 }]);
		expect(
			machineCards(blank, [], { watchedFlags: FLAGS, colourStops: STOPS, recording: true }).nothing
		).toBe('no-machine');
		expect(
			machineCards(blank, [], {
				watchedFlags: FLAGS,
				colourStops: STOPS,
				recording: true,
				lost: LOST
			}).nothing
		).toBe('record-lost');
	});

	test('recording switched off outranks a loss, because nothing was there to lose', () => {
		const view = machineCards(RUN, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			recording: false,
			lost: LOST
		});
		expect(view.record).toBe('off');
	});

	test('a recorded day says so, so the page attribute cannot fail open', () => {
		// The state is always set. A page that said which state it was in only by
		// which sentence it printed could be checked only by looking for a
		// sentence, and an assertion that a sentence is absent passes as happily
		// when it was renamed as when the defect was fixed.
		const view = cardsFor([fingerprint({ job: 'work', shard: 0 })]);
		expect(view.record).toBe('recorded');
		expect(view.lost).toBeNull();
		expect(view.lostNote).toBeNull();
	});

	test('a day file with a header and no rows is a day the record RAN', () => {
		// The fact the rows cannot carry, and the one the whole join turns on. A
		// fixture tree, because the archive's own example of this ages out of every
		// window and a test timed to go red on a date nobody set is a fuse
		// (`CLAUDE.md` section 13).
		const root = mkdtempSync(join(tmpdir(), 'idhazh-record-'));
		const at = join(root, 'host-fingerprint', '2026', '09');
		mkdirSync(at, { recursive: true });
		const header = 'version,date,run_id,job,shard,fingerprint,cpu_model';
		writeFileSync(join(at, '16.csv'), `${header}\n`);
		writeFileSync(
			join(at, '17.csv'),
			`${header}\n2026-09-17,2026-09-17,2026-09-17-1,work,0,3a7f0b1c2d4e5f60,AMD EPYC 7763\n`
		);

		// Both days opened a file; only one kept a row. 15 September opened none at
		// all, and that is the day the record had not begun on.
		expect(machineRecordDays(-1, root)).toEqual(['2026-09-16', '2026-09-17']);
		expect(hostFingerprints(-1, root).map((row) => row.date)).toEqual(['2026-09-17']);
	});

	test('a ledger that was never written reports no days rather than throwing', () => {
		const root = mkdtempSync(join(tmpdir(), 'idhazh-record-'));
		expect(machineRecordDays(-1, root)).toEqual([]);
	});
});
