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
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
	bandwidthSentence,
	cacheWords,
	machineCards
} from '../src/lib/charts/machine-cards';
import { UNRECORDED_STOP } from '../src/lib/charts/machine-colour';
import { watchedFlags } from '../src/lib/server/host-fingerprint';
import type { HostFingerprint } from '../src/lib/server/host-fingerprint';
import {
	machineCounters,
	type MachineLimits,
	type RunCounters
} from '../src/lib/server/runtime-counters';

const LIMITS: MachineLimits = { contextWindow: 8192, jobTimeoutSeconds: 21_600 };
const STOPS = 7;

/** The twelve, read where the page reads them: the generated schema. */
const FLAGS = watchedFlags();

const MIB = 1024 * 1024;

function counterRow(cells: Partial<Record<string, string | number>>): Record<string, string> {
	const blank: Record<string, string> = {
		version: '2026-08-31',
		date: '2026-09-12',
		run_id: '2026-09-12-1',
		shard: '0',
		shards: '2',
		scraped_at: '2026-09-12T10:00:00Z',
		prompt_tokens_total: '',
		prompt_tokens_cached_total: '',
		prompt_seconds_total: '',
		tokens_predicted_total: '',
		tokens_predicted_seconds_total: '',
		n_decode_total: '',
		n_tokens_max: '',
		n_busy_slots_per_decode: '',
		job_seconds: '',
		cpu_model: '',
		cpu_busy_pct: '',
		peak_rss_bytes: '',
		model_load_ms: ''
	};
	for (const [name, value] of Object.entries(cells)) blank[name] = String(value);
	return blank;
}

function fingerprint(over: Partial<HostFingerprint>): HostFingerprint {
	return {
		date: '2026-09-12',
		runId: '2026-09-12-1',
		job: 'work',
		shard: 0,
		fingerprint: '3a7f0b1c2d4e5f60',
		cpuModel: 'AMD EPYC 7763 64-Core Processor',
		cpuFamily: 25,
		cpuModelNumber: 1,
		cpuStepping: 1,
		microcode: '0xa0011d3',
		l3CacheBytes: 32 * MIB,
		flags: ['avx2', 'f16c', 'fma', 'sse4_2'],
		memcpyGibPerSecond: 12.4,
		memcpyProbeMib: 512,
		vmSize: 'Standard_D4ads_v5',
		vmLocation: 'eastus',
		vmZone: '1',
		vmFaultDomain: '0',
		...over
	};
}

function onlyRun(rows: Record<string, string>[]): RunCounters {
	const { runs, refused } = machineCounters(rows, [], LIMITS);
	expect(refused, 'the fixture was refused').toEqual([]);
	expect(runs).toHaveLength(1);
	return runs[0];
}

const RUN = onlyRun([
	counterRow({ shard: 0, cpu_model: 'AMD EPYC 7763 64-Core Processor' }),
	counterRow({ shard: 1, cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C' })
]);

function cardsFor(rows: HostFingerprint[], recording = true) {
	return machineCards(RUN, rows, {
		watchedFlags: FLAGS,
		colourStops: STOPS,
		recording
	});
}

test.describe('the flag vocabulary', () => {
	test('the twelve come from the generated schema, so no copy can drift', () => {
		const schema = JSON.parse(
			readFileSync(resolve(process.cwd(), '..', 'schemas', 'machine-panels.schema.json'), 'utf8')
		) as { $defs: { WatchedFlag: { enum: string[] } } };
		expect(FLAGS).toEqual(schema.$defs.WatchedFlag.enum);
		expect(FLAGS).toHaveLength(12);
	});

	test('an unreadable schema draws no chip rather than twelve absent ones', () => {
		// Nothing recorded and reported none of them are different facts, and only
		// one of them is a machine with no AVX-512.
		expect(watchedFlags(resolve(process.cwd(), 'no-such-schema.json'))).toEqual([]);
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
		expect(view.cards.every((card) => card.source === 'counters')).toBe(true);
		expect(view.cards.every((card) => card.flags.length === 0)).toBe(true);
		expect(view.cards.every((card) => card.flagsRecorded === false)).toBe(true);
	});

	test('family, model and stepping are one string, and absent where any is', () => {
		expect(cardsFor([fingerprint({})]).cards[0].part).toBe('25/1/1');
		expect(cardsFor([fingerprint({ cpuStepping: null })]).cards[0].part).toBeNull();
	});

	test('the heading is the name a person reads and the raw string survives behind it', () => {
		const [card] = cardsFor([
			fingerprint({ cpuModel: 'INTEL(R) XEON(R) PLATINUM 8573C', fingerprint: 'c81d9e0a1b2c3d4e' })
		]).cards;
		expect(card.identity.name).toBe('Intel Xeon Platinum 8573C');
		expect(card.where?.cpuModelRaw).toBe('INTEL(R) XEON(R) PLATINUM 8573C');
	});

	test('a job the record missed joins the machine of its own name, not a card of its own', () => {
		// The record reached work shard 0 and reported a Xeon; shard 1 reported the
		// same processor name and nothing else. One machine, one card - two cards
		// under one heading reads as a defect rather than as the absence it is.
		const view = cardsFor([
			fingerprint({ cpuModel: 'INTEL(R) XEON(R) PLATINUM 8573C', fingerprint: 'c81d9e0a1b2c3d4e' })
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
		const [card] = cardsFor([fingerprint({ l3CacheBytes: 480 * MIB, memcpyProbeMib: 480 })]).cards;
		expect(card.measuredCache).toBe(true);
		expect(bandwidthSentence(card)).toContain('this measured cache, not memory');
	});

	test('a probe that was switched off is a sentence, never a rate of zero', () => {
		const [card] = cardsFor([fingerprint({ memcpyGibPerSecond: null, memcpyProbeMib: 0 })]).cards;
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
				cpuModel: 'INTEL(R) XEON(R) PLATINUM 8573C'
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
		expect(xeon?.source).toBe('counters');
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
		const blank = onlyRun([counterRow({ shard: 0 }), counterRow({ shard: 1 })]);
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
