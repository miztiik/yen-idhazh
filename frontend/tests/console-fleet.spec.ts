/** When does a count of machines become a chart, and what may it never print?
 *
 * The panel answers "what are we actually being given". It is a count of what
 * happened and it must never become a rate: what the next job will draw is
 * exactly the thing a lottery refuses to quote.
 *
 * The gate is the other half. Bars over a handful of placements read as a
 * distribution and it is not one, so under `console.fleet_min_rows` the panel
 * lists the counts in words and draws no bar at all. The threshold is read from
 * the committed config here, so a test cannot pass against a number the page
 * does not use.
 *
 * Over the gate the count is a trend, because the title asks what has been
 * given lately. The fold past `console.fleet_top_kinds` is what keeps a day's
 * band to bars wide enough to paint, and the fold bar has to equal the kinds it
 * folded - in the window and on every day of it - or the panel has lost a
 * placement and says nothing about where.
 *
 * Every case is built. Nothing reads the committed machine record, which held
 * zero rows on the day this was written and would have made every assertion
 * here vacuous.
 */

import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fleetChart, fleetOverWindow } from '../src/lib/charts/fleet';
import { FOLDED_KEY, UNRECORDED_STOP } from '../src/lib/charts/machine-colour';
import type { HostFingerprint } from '../src/lib/server/host-fingerprint';

/** `config/appearance.json` read off disk, so the gate is the page's own gate. */
const APPEARANCE = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as {
	console: {
		fleet_min_rows: number;
		fleet_top_kinds: number;
		machine_colour_stops: number;
		bandwidth_min_kinds: number;
	};
};

const MIN_ROWS = APPEARANCE.console.fleet_min_rows;
const STOPS = APPEARANCE.console.machine_colour_stops;
const TOP_KINDS = APPEARANCE.console.fleet_top_kinds;

function row(over: Partial<HostFingerprint>): HostFingerprint {
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
		l3_cache_bytes: 33_554_432,
		mhz_max: null,
		mhz_at_probe: null,
		flags: 'avx2',
		boot_seconds: null,
		memcpy_gib_s: 12.4,
		memcpy_probe_mib: 512,
		vm_size: null,
		vm_location: null,
		vm_zone: null,
		vm_fault_domain: null,
		runner_name: null,
		measured_at: null,
		model_load_ms: null,
		job_seconds: null,
		server_prompt_tokens: null,
		server_prompt_seconds: null,
		...over
	};
}

/** `count` placements of one machine, dated inside the window. */
function draws(count: number, over: Partial<HostFingerprint>): HostFingerprint[] {
	return Array.from({ length: count }, (_, index) => row({ ...over, shard: index }));
}

const XEON = {
	fingerprint: 'c81d9e0a1b2c3d4e',
	cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C'
};

function view(rows: HostFingerprint[], recording = true) {
	return fleetOverWindow(rows, {
		days: 30,
		minRows: MIN_ROWS,
		colourStops: STOPS,
		topKinds: TOP_KINDS,
		recording
	});
}

test.describe('the threshold the panel draws at', () => {
	test('the committed config is what the page reads, and it is 160', () => {
		// Derived 2026-09-17: the rarest of six machine kinds held 11 of 356
		// committed counter rows, 3.1 percent, and 5 of those - the floor
		// `console.min_attempts_for_rate` already sets - needs about 162 rows.
		expect(MIN_ROWS).toBe(160);
		expect(STOPS).toBe(7);
		expect(TOP_KINDS).toBe(4);
		expect(APPEARANCE.console.bandwidth_min_kinds).toBe(3);
	});

	test('one row under the threshold draws no bar', () => {
		const under = view([...draws(MIN_ROWS - 1, {})]);
		expect(under.placements).toBe(MIN_ROWS - 1);
		expect(under.drawBars).toBe(false);
		expect(under.kinds).toHaveLength(1);
	});

	test('at the threshold it draws bars', () => {
		const at = view([...draws(MIN_ROWS, {})]);
		expect(at.placements).toBe(MIN_ROWS);
		expect(at.drawBars).toBe(true);
		expect(at.trend.series).toHaveLength(1);
		expect(at.trend.series[0].placements).toBe(MIN_ROWS);
	});
});

test.describe('what the count is', () => {
	const counted = view([...draws(120, {}), ...draws(60, XEON)]);

	test('counts descend, and every row prints a whole placement count', () => {
		expect(counted.kinds.map((kind) => kind.placements)).toEqual([120, 60]);
		expect(counted.trend.series.map((one) => one.placements)).toEqual([120, 60]);
	});

	test('nothing in the panel is a share, a rate or a probability', () => {
		const printed = counted.trend.series
			.map((one) => `${one.identity.name} ${one.placements} ${one.identity.folded.join(', ')}`)
			.join(' ');
		expect(printed).not.toMatch(/%|percent|probability|chance|likely/i);
	});

	test('each row keeps its machine name and the colour the ramp gave it', () => {
		expect(counted.kinds.map((kind) => kind.identity.name)).toEqual([
			'AMD EPYC 7763',
			'Intel Xeon Platinum 8573C'
		]);
		// Ascending by key: `3a7f...` before `c81d...`.
		expect(counted.kinds.map((kind) => kind.identity.colourStop).sort()).toEqual([1, 2]);
	});

	test('the denominator is the placements, not the machines', () => {
		expect(counted.placements).toBe(180);
	});
});

test.describe('the window and the switch', () => {
	test('a placement outside the open span is not counted', () => {
		const spanned = fleetOverWindow(
			[row({ date: '2026-09-01' }), row({ date: '2026-09-12' }), row({ date: '2026-09-20' })],
			{
				days: 7,
				minRows: MIN_ROWS,
				colourStops: STOPS,
				topKinds: TOP_KINDS,
				recording: true,
				start: '2026-09-10',
				end: '2026-09-16'
			}
		);
		expect(spanned.placements).toBe(1);
		expect(spanned.trend.days).toEqual(['2026-09-12']);
	});

	test('recording switched off is a different state from nothing recorded', () => {
		expect(view([], false).nothing).toBe('recording-off');
		expect(view([], true).nothing).toBe('none');
		expect(view([...draws(3, {})]).nothing).toBeNull();
	});

	test('a window that lost its rows is a different state from one waiting for its first', () => {
		// "This starts counting on the first run after the record ships" is the
		// sentence a window before the record gets, and until 2026-09-17 it was
		// also the sentence a window that lost every row got. They send an
		// operator to opposite places.
		const lost = fleetOverWindow([], {
			days: 30,
			minRows: MIN_ROWS,
			colourStops: STOPS,
			topKinds: TOP_KINDS,
			recording: true,
			lost: [{ date: '2026-09-16', articles: 431 }]
		});
		expect(lost.nothing).toBe('record-lost');
		// A loss never outranks a count: a window with rows in it has something to
		// draw whatever an earlier day did.
		const counted = fleetOverWindow([...draws(3, {})], {
			days: 30,
			minRows: MIN_ROWS,
			colourStops: STOPS,
			topKinds: TOP_KINDS,
			recording: true,
			lost: [{ date: '2026-09-16', articles: 431 }]
		});
		expect(counted.nothing).toBeNull();
	});

	test('a job that recorded no processor name still counts as a placement', () => {
		// Its fingerprint is what the record was built for, and a machine with no
		// name is still a machine the platform gave us.
		const unnamed = view([row({ cpu_model: null, fingerprint: '0000111122223333' })]);
		expect(unnamed.placements).toBe(1);
		expect(unnamed.kinds[0].identity.colourStop).not.toBe(UNRECORDED_STOP);
	});
});

test.describe('the count as a trend, and the fold past the top kinds', () => {
	/** Six machines over three days, every one of them a different kind.
	 *
	 * Built rather than read: the committed machine record held 40 placements
	 * over two days on 2026-09-20, which is a quarter of the list floor, so a
	 * trend taken off it would be a trend nothing draws.
	 */
	const SIX = [
		{ fingerprint: 'aaaa0000aaaa0000', cpu_model: 'AMD EPYC 7763 64-Core Processor', on: 30 },
		{ fingerprint: 'bbbb1111bbbb1111', cpu_model: 'AMD EPYC 9V74 80-Core Processor', on: 20 },
		{ fingerprint: 'cccc2222cccc2222', cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C', on: 12 },
		{ fingerprint: 'dddd3333dddd3333', cpu_model: 'Intel(R) Xeon(R) 6973P-C', on: 9 },
		{ fingerprint: 'eeee4444eeee4444', cpu_model: 'Intel(R) Xeon(R) Platinum 8370C CPU', on: 5 },
		{ fingerprint: 'ffff5555ffff5555', cpu_model: 'AMD EPYC 7B13 64-Core Processor', on: 3 }
	];
	const DAYS = ['2026-09-10', '2026-09-11', '2026-09-12'];

	/** Every kind spread over the three days, so each one has a bar in each. */
	function window(): HostFingerprint[] {
		return SIX.flatMap((kind) =>
			Array.from({ length: kind.on }, (_, index) =>
				row({
					fingerprint: kind.fingerprint,
					cpu_model: kind.cpu_model,
					date: DAYS[index % DAYS.length],
					shard: index
				})
			)
		);
	}

	const rows = window();
	const trend = view(rows).trend;

	test('six kinds draw the top K and one fold bar, and nothing else', () => {
		expect(SIX).toHaveLength(6);
		expect(trend.series).toHaveLength(TOP_KINDS + 1);
		expect(trend.folded).toBe(SIX.length - TOP_KINDS);
		expect(trend.series.at(-1)?.identity.key).toBe(FOLDED_KEY);
		// The fold row names its members, because colour is never the only carrier.
		expect(trend.series.at(-1)?.identity.folded).toHaveLength(SIX.length - TOP_KINDS);
	});

	test('the fold bar is the sum of the kinds it folded, over the window', () => {
		const other = trend.series.at(-1);
		const outside = SIX.slice(TOP_KINDS).reduce((carry, kind) => carry + kind.on, 0);
		expect(other?.placements).toBe(outside);
	});

	test('the fold bar is the sum of the kinds it folded, day by day', () => {
		const other = trend.series.at(-1);
		const outside = new Set(SIX.slice(TOP_KINDS).map((kind) => kind.fingerprint));
		const byDay = DAYS.map(
			(date) =>
				rows.filter((one) => one.date === date && outside.has(one.fingerprint ?? '')).length
		);
		expect(other?.counts).toEqual(byDay);
	});

	test('the fold bar takes a colour no drawn kind is holding', () => {
		const kept = trend.series.slice(0, TOP_KINDS).map((one) => one.identity.colourStop);
		const other = trend.series.at(-1)?.identity.colourStop ?? 0;
		expect(kept).not.toContain(other);
		expect(other).not.toBe(UNRECORDED_STOP);
	});

	test('every group is a day that recorded something, and the counts add up', () => {
		expect(trend.days).toEqual(DAYS);
		const drawn = trend.series.reduce(
			(carry, one) => carry + one.counts.reduce((sum, count) => sum + count, 0),
			0
		);
		expect(drawn).toBe(SIX.reduce((carry, kind) => carry + kind.on, 0));
	});

	test('a day the record never reached is counted, not drawn as a zero', () => {
		// Three days recorded out of a thirty-day window. A zero-height group
		// would say the platform gave us nothing that day; it says nothing.
		expect(trend.daysWithout).toBe(30 - DAYS.length);
	});

	test('the chart is one adaptive axis, one bar a kind, and a day category', () => {
		const plot = fleetChart(trend);
		expect(plot.empty).toBe(false);
		const series = plot.option.series as { type: string; data: number[] }[];
		expect(series).toHaveLength(TOP_KINDS + 1);
		expect(series.every((one) => one.type === 'bar')).toBe(true);
		// One quantity, so one shared domain and no ceiling to fix it against.
		expect(Array.isArray(plot.option.yAxis)).toBe(false);
		expect((plot.option.yAxis as { max?: number }).max).toBeUndefined();
		expect((plot.option.xAxis as { data: string[] }).data).toHaveLength(DAYS.length);
	});

	test('a window with nothing in it draws no chart at all', () => {
		const plot = fleetChart(view([]).trend);
		expect(plot.empty).toBe(true);
	});
});
