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
 * Every case is built. Nothing reads the committed machine record, which held
 * zero rows on the day this was written and would have made every assertion
 * here vacuous.
 */

import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fleetOverWindow } from '../src/lib/charts/fleet';
import { UNRECORDED_STOP } from '../src/lib/charts/machine-colour';
import type { HostFingerprint } from '../src/lib/server/host-fingerprint';

/** `config/appearance.json` read off disk, so the gate is the page's own gate. */
const APPEARANCE = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as { console: { fleet_min_rows: number; machine_colour_stops: number; bandwidth_min_kinds: number } };

const MIN_ROWS = APPEARANCE.console.fleet_min_rows;
const STOPS = APPEARANCE.console.machine_colour_stops;

function row(over: Partial<HostFingerprint>): HostFingerprint {
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
		l3CacheBytes: 33_554_432,
		flags: ['avx2'],
		memcpyGibPerSecond: 12.4,
		memcpyProbeMib: 512,
		vmSize: null,
		vmLocation: null,
		vmZone: null,
		vmFaultDomain: null,
		...over
	};
}

/** `count` placements of one machine, dated inside the window. */
function draws(count: number, over: Partial<HostFingerprint>): HostFingerprint[] {
	return Array.from({ length: count }, (_, index) => row({ ...over, shard: index }));
}

const XEON = {
	fingerprint: 'c81d9e0a1b2c3d4e',
	cpuModel: 'INTEL(R) XEON(R) PLATINUM 8573C'
};

function view(rows: HostFingerprint[], recording = true) {
	return fleetOverWindow(rows, {
		days: 30,
		minRows: MIN_ROWS,
		colourStops: STOPS,
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
		expect(at.ranked.rows).toHaveLength(1);
		expect(at.ranked.max).toBe(MIN_ROWS);
	});
});

test.describe('what the count is', () => {
	const counted = view([...draws(120, {}), ...draws(60, XEON)]);

	test('counts descend, and every row prints a whole placement count', () => {
		expect(counted.kinds.map((kind) => kind.placements)).toEqual([120, 60]);
		expect(counted.ranked.rows.map((r) => r.row.value)).toEqual(['120', '60']);
	});

	test('nothing in the panel is a share, a rate or a probability', () => {
		const printed = [
			...counted.ranked.rows.map((r) => `${r.row.label} ${r.row.value} ${r.row.context ?? ''}`)
		].join(' ');
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
			{ days: 7, minRows: MIN_ROWS, colourStops: STOPS, recording: true, start: '2026-09-10', end: '2026-09-16' }
		);
		expect(spanned.placements).toBe(1);
	});

	test('recording switched off is a different state from nothing recorded', () => {
		expect(view([], false).nothing).toBe('recording-off');
		expect(view([], true).nothing).toBe('none');
		expect(view([...draws(3, {})]).nothing).toBeNull();
	});

	test('a job that recorded no processor name still counts as a placement', () => {
		// Its fingerprint is what the record was built for, and a machine with no
		// name is still a machine the platform gave us.
		const unnamed = view([row({ cpuModel: null, fingerprint: '0000111122223333' })]);
		expect(unnamed.placements).toBe(1);
		expect(unnamed.kinds[0].identity.colourStop).not.toBe(UNRECORDED_STOP);
	});
});
