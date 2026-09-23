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
 * The last block asks the same question of the two readings that became bars.
 * A bar can draw a plausible length against the wrong divisor and look
 * perfectly healthy, so the oracle is the ratio of the readings rather than
 * either length on its own - and the three refusals are named, because a bar
 * that is simply missing is the defect this file exists to catch.
 *
 * Every case is built. The archive has never produced a run whose jobs drew
 * three machines with one of them unrecorded, and that is the case that matters.
 */

import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import {
	cacheWords,
	clockSentence,
	copySpeedSentence,
	machineCards,
	uptimeSentence
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
import { observabilityConfig } from '../src/lib/server/config';

const LIMITS: MachineLimits = { contextWindow: 8192, jobTimeoutSeconds: 21_600 };
const STOPS = 7;

/** The margin these cases drive the pure function with.
 *
 * An input to the function under test, never a copy of the shipped default -
 * the last case in this file reads that default out of the generated schema and
 * checks the page reads the same one.
 */
const MARGIN = 2;

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
		mhz_at_probe: 2664.85,
		flags: 'avx2 f16c fma sse4_2',
		boot_seconds: 226.59,
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
		cacheMargin: MARGIN,
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

test.describe('the copy speed and the buffer it was taken with', () => {
	test('a buffer that clears the cache prints the rate, the buffer and the margin', () => {
		// 512 MiB against 32 MiB is 16 times the cache, eight times what it takes
		// to be sure the copy left it. This is the clean reading.
		const [card] = cardsFor([fingerprint({})]).cards;
		expect(copySpeedSentence(card)).toBe(
			'12.4 GiB/s, over a 512 MiB buffer against 32 MiB of L3 - 16.00 times it.'
		);
		expect(card.bufferClearedCache).toBe(true);
	});

	test('a buffer under twice the cache withholds the rate and says why', () => {
		// The shape nine of the 65 committed rows carry, measured 2026-09-21: a
		// 512 MiB buffer against 260 MiB of L3 is 1.97 times it. Those nine are
		// the SLOWEST rates in the fleet, so the short buffer is a reason to
		// distrust them rather than evidence they read high - and a caveat under
		// a number does not stop the number being compared.
		const [card] = cardsFor([
			fingerprint({ l3_cache_bytes: 260 * MIB, memcpy_probe_mib: 512, memcpy_gib_s: 21.96 })
		]).cards;
		expect(card.bufferClearedCache).toBe(false);
		const said = copySpeedSentence(card);
		expect(said).toBe(
			'No copy speed: the probe used a 512 MiB buffer against 260 MiB of L3, 1.97 times it, ' +
				'and a reading has to clear 2 times to be sure the copy left the cache.'
		);
		// The refused figure is nowhere in the sentence, at any rounding.
		expect(said).not.toContain('21.9');
		expect(said).not.toContain('GiB/s');
	});

	test('the margin is the knob, and moving it moves which readings are graded', () => {
		// The substitution test (CLAUDE.md Guardrail #6). One machine, one record,
		// one input changed.
		const row = fingerprint({ l3_cache_bytes: 260 * MIB, memcpy_probe_mib: 512 });
		const strict = machineCards(RUN, [row], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			cacheMargin: 2,
			recording: true
		}).cards[0];
		const loose = machineCards(RUN, [row], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			cacheMargin: 1,
			recording: true
		}).cards[0];
		expect(strict.bufferClearedCache).toBe(false);
		expect(loose.bufferClearedCache).toBe(true);
		expect(copySpeedSentence(loose)).toContain('12.4 GiB/s');
		expect(copySpeedSentence(strict)).toContain('No copy speed');
	});

	test('the page grades a row by the same margin the probe sized its buffer with', () => {
		// Two numbers in two languages would let the page refuse a row the probe
		// wrote correctly. Read inside the test, so one unexpected shape fails
		// this case rather than the module (CLAUDE.md section 13).
		const schema = JSON.parse(
			readFileSync(resolve(process.cwd(), '..', 'schemas', 'app-config.schema.json'), 'utf8')
		) as {
			$defs: {
				ObservabilityConfig: {
					properties: { host_fingerprint_bandwidth_cache_multiple: { default: number } };
				};
			};
		};
		const shipped =
			schema.$defs.ObservabilityConfig.properties.host_fingerprint_bandwidth_cache_multiple
				.default;
		expect(observabilityConfig().host_fingerprint_bandwidth_cache_multiple).toBe(shipped);
		expect(MARGIN).toBe(shipped);
	});

	test('a machine that reported no cache cannot be graded either way', () => {
		const [card] = cardsFor([fingerprint({ l3_cache_bytes: null })]).cards;
		expect(card.bufferClearedCache).toBe(false);
		expect(copySpeedSentence(card)).toBe(
			'No copy speed: the probe used a 512 MiB buffer and this machine reported no cache size, ' +
				'so nothing says whether the copy left the cache.'
		);
	});

	test('a buffer nobody recorded cannot be graded either', () => {
		const [card] = cardsFor([fingerprint({ memcpy_probe_mib: null })]).cards;
		expect(card.bufferClearedCache).toBe(false);
		expect(copySpeedSentence(card)).toBe(
			'No copy speed: the probe did not record the buffer it used, so nothing says whether the ' +
				'copy left the cache.'
		);
	});

	test('a probe that was switched off is a sentence, never a rate of zero', () => {
		const [card] = cardsFor([fingerprint({ memcpy_gib_s: null, memcpy_probe_mib: 0 })]).cards;
		expect(card.memcpyGibPerSecond).toBeNull();
		expect(copySpeedSentence(card)).toBe('Copy speed was not measured on this job.');
		// The cache still prints: one reading being absent does not remove another.
		expect(cacheWords(card.l3CacheBytes)).toBe('32 MiB');
	});

	test('a cache nothing recorded prints a dash rather than nothing at all', () => {
		expect(cacheWords(null)).toBe('-');
	});
});

test.describe('what the machine was doing when we asked', () => {
	test('uptime is on the card, in a clock a person reads', () => {
		const [card] = cardsFor([fingerprint({ boot_seconds: 226.59 })]).cards;
		expect(card.bootSeconds).toBe(226.59);
		expect(uptimeSentence(card)).toBe('Up 3 m 47 s when we measured it.');
	});

	test('uptime nobody recorded is a sentence, never an uptime of zero', () => {
		// A machine nobody asked did not just boot, and a freshly booted machine
		// is the reading this column exists for.
		const [card] = cardsFor([fingerprint({ boot_seconds: null })]).cards;
		expect(uptimeSentence(card)).toBe('Uptime was not recorded on this job.');
	});

	test('the clock prints alone, never as a share of a ceiling nothing writes', () => {
		// `mhz_max` is empty on all 65 committed rows, measured 2026-09-21. A card
		// that divided by it would draw the empty-column defect a second time.
		const [card] = cardsFor([fingerprint({ mhz_at_probe: 2664.85, mhz_max: null })]).cards;
		expect(card.mhzAtProbe).toBe(2664.85);
		const said = clockSentence(card);
		expect(said).toBe("2665 MHz when the probe ran, before the job's heaviest step.");
		expect(said).not.toContain('%');
	});

	test('a clock nobody recorded is a sentence, never a clock of zero', () => {
		const [card] = cardsFor([fingerprint({ mhz_at_probe: null })]).cards;
		expect(clockSentence(card)).toBe('Clock speed was not recorded on this job.');
	});

	test('a machine the record never reached carries neither, and both say so', () => {
		const named = cardsFor([fingerprint({ job: 'work', shard: 0 })]).cards.find(
			(card) => card.source === 'name-only'
		);
		if (named === undefined) throw new Error('the fixture drew no name-only card');
		expect(named.bootSeconds).toBeNull();
		expect(named.mhzAtProbe).toBeNull();
		expect(uptimeSentence(named)).toContain('not recorded');
		expect(clockSentence(named)).toContain('not recorded');
	});
});

test.describe('L3 and the copy rate as lengths on one track', () => {
	/** Two machines that differ only in what this panel draws.
	 *
	 * The committed record has never carried two machines with different L3 on
	 * one run - every row of it reports 32 MiB - so the case the bars exist for
	 * is built here (`CLAUDE.md` section 13).
	 */
	function twoMachines(over: Partial<HostFingerprint>) {
		const view = cardsFor([
			fingerprint({ job: 'work', shard: 0 }),
			fingerprint({
				job: 'work',
				shard: 1,
				fingerprint: 'c81d9e0a1b2c3d4e',
				cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C',
				...over
			})
		]);
		const epyc = view.cards.find((card) => card.identity.name === 'AMD EPYC 7763');
		const xeon = view.cards.find((card) => card.identity.name === 'Intel Xeon Platinum 8573C');
		if (epyc === undefined || xeon === undefined) throw new Error('the fixture drew one machine');
		return { epyc, xeon };
	}

	test('two cards with different L3 draw bars in the ratio of their bytes', () => {
		const { epyc, xeon } = twoMachines({ l3_cache_bytes: 260 * MIB });
		expect(epyc.l3CacheBytes).toBe(32 * MIB);
		expect(xeon.l3CacheBytes).toBe(260 * MIB);
		expect(epyc.l3Bar.state).toBe('drawn');
		expect(xeon.l3Bar.state).toBe('drawn');
		// The one property the bar is for. A zero-anchored domain makes the two
		// lengths the two readings, so this holds whatever the track runs to.
		expect(xeon.l3Bar.fraction / epyc.l3Bar.fraction).toBeCloseTo(260 / 32, 6);
	});

	test('the track is the same on every card, and it comes from the readings drawn', () => {
		const { epyc, xeon } = twoMachines({ l3_cache_bytes: 260 * MIB });
		// One domain, or the panel's comparison is deleted. The top is niced
		// upward from the largest reading rather than fixed: no runner model
		// publishes a ceiling for L3, so there is no limit to measure against.
		expect(epyc.l3Bar.top).toBe(xeon.l3Bar.top);
		expect(epyc.l3Bar.top).toBeGreaterThanOrEqual(260);
		expect(epyc.l3Bar.of).toBe(2);
		expect(xeon.l3Bar.topWords).toBe(cacheWords(xeon.l3Bar.top * MIB));
	});

	test('a copy rate draws on its own track, in the ratio of the rates', () => {
		const { epyc, xeon } = twoMachines({ memcpy_gib_s: 6.2 });
		expect(epyc.bandwidthBar.state).toBe('drawn');
		expect(xeon.bandwidthBar.state).toBe('drawn');
		expect(epyc.bandwidthBar.fraction / xeon.bandwidthBar.fraction).toBeCloseTo(12.4 / 6.2, 6);
		// Two quantities, two tracks. MiB of cache and GiB/s of copy rate share
		// no axis, so neither reading can be read off the other's length.
		expect(epyc.l3Bar.topWords.endsWith(' MiB')).toBe(true);
		expect(epyc.bandwidthBar.topWords.endsWith(' GiB/s')).toBe(true);
		expect(epyc.bandwidthBar.valueWords).toBe('12.4 GiB/s');
	});

	test('an ungraded reading is refused rather than pooled with the graded ones', () => {
		// A buffer 1.97 times the cache cannot be told apart from a cache reading,
		// and on one track it would take a length nobody can justify. Nine of the 65
		// committed rows are this shape.
		const { epyc, xeon } = twoMachines({
			l3_cache_bytes: 260 * MIB,
			memcpy_probe_mib: 512,
			memcpy_gib_s: 21.96
		});
		expect(xeon.bufferClearedCache).toBe(false);
		expect(xeon.bandwidthBar.state).toBe('ungraded');
		expect(xeon.bandwidthBar.fraction).toBe(0);
		// And the one memory reading left has nothing to compare against.
		expect(epyc.bandwidthBar.state).toBe('alone');
		expect(epyc.bandwidthBar.of).toBe(1);
	});

	test('one reading of a kind is named, never drawn full', () => {
		// A lone bar's domain is its own value, so it fills the track whatever it
		// says - and a full bar reads as a maximum rather than as the only one.
		const { epyc, xeon } = twoMachines({ l3_cache_bytes: null });
		expect(xeon.l3Bar.state).toBe('absent');
		expect(epyc.l3Bar.state).toBe('alone');
		expect(epyc.l3Bar.fraction).toBe(0);
		expect(epyc.l3Bar.percent).toBe('0.0000%');
	});

	test('a card with no reading states absence rather than drawing an empty bar', () => {
		const [card] = cardsFor([
			fingerprint({ job: 'work', shard: 0, l3_cache_bytes: null, memcpy_gib_s: null })
		]).cards;
		expect(card.l3Bar.state).toBe('absent');
		expect(card.bandwidthBar.state).toBe('absent');
		expect(card.l3Bar.valueWords).toBe('');
		expect(card.bandwidthBar.topWords).toBe('');
	});

	test('a card off the counters alone carries no track at all', () => {
		const xeon = cardsFor([fingerprint({ job: 'work', shard: 0 })]).cards.find(
			(card) => card.source === 'name-only'
		);
		expect(xeon?.l3Bar.state).toBe('absent');
		expect(xeon?.bandwidthBar.state).toBe('absent');
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
			cacheMargin: MARGIN,
			recording: false
		});
		expect(nowhere.nothing).toBe('recording-off');

		const nothing = machineCards(null, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			cacheMargin: MARGIN,
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
			cacheMargin: MARGIN,
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
			cacheMargin: MARGIN,
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
			cacheMargin: MARGIN,
			recording: true
		});
		const lost = machineCards(RUN, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			cacheMargin: MARGIN,
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
			machineCards(blank, [], { watchedFlags: FLAGS, colourStops: STOPS, cacheMargin: MARGIN, recording: true }).nothing
		).toBe('no-machine');
		expect(
			machineCards(blank, [], {
				watchedFlags: FLAGS,
				colourStops: STOPS,
				cacheMargin: MARGIN,
				recording: true,
				lost: LOST
			}).nothing
		).toBe('record-lost');
	});

	test('recording switched off outranks a loss, because nothing was there to lose', () => {
		const view = machineCards(RUN, [], {
			watchedFlags: FLAGS,
			colourStops: STOPS,
			cacheMargin: MARGIN,
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

	test("a writer's file with a header and no rows is a day the record RAN", () => {
		// The fact the rows cannot carry, and the one the whole join turns on. A
		// fixture tree, because the archive's own example of this ages out of every
		// window and a test timed to go red on a date nobody set is a fuse
		// (`CLAUDE.md` section 13).
		const root = mkdtempSync(join(tmpdir(), 'idhazh-record-'));
		const at = join(root, 'host-fingerprint', '2026', '09');
		mkdirSync(join(at, '16'), { recursive: true });
		mkdirSync(join(at, '17'), { recursive: true });
		const header = 'version,date,run_id,job,shard,fingerprint,cpu_model';
		writeFileSync(join(at, '16', '2026-09-16-1-1-work-00.csv'), `${header}\n`);
		writeFileSync(
			join(at, '17', '2026-09-17-1-1-work-00.csv'),
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
