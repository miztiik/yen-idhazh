/** THE ORACLE for the machine-kinds panel: what it draws from the rows the query door answers.
 *
 * Given the door's answer for the panel's columns - one row a job, as the
 * compaction packs the machine record - the panel draws one stacked bar a day
 * and one segment a machine kind, slowest at the bottom; a job whose machine
 * nobody recorded is the last segment and is never part of a fold; and every
 * machine keeps its own categorical paint and complete dated counts in details.
 *
 * The fixture is the door's own answer, recorded once through `sliceFromDisk`
 * over the packed machine record for 26 to 28 September 2026 with
 * `FLEET_COLUMNS`: `tests/fixtures/platform-mix/door-answer-26-to-28-september.json`.
 * A copy fixed in size, so this file costs the same however much the archive
 * holds (`CLAUDE.md` section 13). The record held no job without a machine on
 * those days, so that case, the folds and the ties are built below from rows
 * in the same shape - each is a case the archive has not produced.
 *
 * Every expectation is worked out here from the rows, never read back off the
 * module under test.
 */

import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { dateSeries, formatNumber, numberFormat } from './support/number-format';
import {
	FLEET_COLUMNS,
	fleetDots,
	fleetJobs,
	fleetHover,
	fleetReadout,
	fleetSummary,
	fleetSeries,
	fleetView,
	type FleetJob,
	type FleetOptions
} from '../src/lib/charts/fleet';
import { frame } from '../src/lib/charts/frame';
import { fleetCacheView } from '../src/lib/charts/fleet-cache';
import {
	machineKeys,
	machineRamp,
	UNRECORDED_KEY,
	UNRECORDED_NAME,
	type MachineRamp
} from '../src/lib/charts/machine-colour';
import { hoverReading } from '../src/lib/charts/readout-hover';
import { PALETTE } from '../src/lib/charts/theme';
import { schemePiYG } from 'd3-scale-chromatic';
import type { Row, SliceResult } from '../src/lib/data/slice-shapes';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '..', '..');

/** `config/appearance.json` read off disk, so every knob is the page's own. */
function knobs(): {
	machine_colour_stops: number;
	machine_colour_floor_share: number;
	fleet_min_rows: number;
	fleet_top_kinds: number;
	fleet_dot_max_px: number;
	absent_hatch_degrees: number;
} {
	return JSON.parse(readFileSync(path.join(repo, 'config', 'appearance.json'), 'utf8')).console;
}

/** The door's recorded answer, read inside the test that needs it. */
function recorded(): Row[] {
	const answer = JSON.parse(
		readFileSync(path.join(repo, 'tests', 'fixtures', 'platform-mix', 'door-answer-26-to-28-september.json'), 'utf8')
	) as SliceResult;
	expect(answer.state, 'the recorded answer is a door answer with rows').toBe('ok');
	return answer.rows.map((row) => ({ version: '2026-09-20', ...row }));
}

/** The page's one ramp, cut over every job handed in. */
function rampOf(jobs: readonly FleetJob[]): MachineRamp {
	const config = knobs();
	const keys = machineKeys(
		jobs.map((job) => ({
			fingerprint: job.fingerprint,
			fingerprintVersion: job.fingerprintVersion,
			cpuModel: job.cpuModel
		}))
	);
	return machineRamp(
		jobs.map((job) => ({
			machine: keys({
				fingerprint: job.fingerprint,
				fingerprintVersion: job.fingerprintVersion,
				cpuModel: job.cpuModel
			}),
			rate: job.rate
		})),
		{ stops: config.machine_colour_stops, floor: config.machine_colour_floor_share }
	);
}

function options(jobs: readonly FleetJob[], over: Partial<FleetOptions> = {}): FleetOptions {
	const config = knobs();
	return {
		ramp: rampOf(jobs),
		appearance: { gradients: true, floor: config.machine_colour_floor_share, palette: 'piyg' },
		start: '2026-09-26',
		end: '2026-09-28',
		windowDays: 3,
		minRows: config.fleet_min_rows,
		topKinds: config.fleet_top_kinds,
		numberFormat,
		recording: true,
		...over
	};
}

/** One job row in the door's shape. Every cell may be left to its default. */
function job(over: Partial<Record<(typeof FLEET_COLUMNS)[number], string | number | null>>): Row {
	return {
		version: '2026-09-20',
		date: '2026-09-12',
		run_id: '2026-09-12-1',
		job: 'work',
		pipeline_name: null,
		task_name: null,
		shard: 0,
		fingerprint: 'aaaa000000000000',
		cpu_model: 'AMD EPYC 7763 64-Core Processor',
		job_seconds: 800,
		server_prompt_tokens: 1000,
		server_prompt_seconds: 100,
		...over
	};
}

/** `count` jobs of one machine reading at `rate` tokens a second, on one day. */
function jobsOf(count: number, fingerprint: string | null, cpu: string | null, rate: number | null, date = '2026-09-12'): Row[] {
	return Array.from({ length: count }, (_, index) =>
		job({
			date,
			shard: index,
			fingerprint,
			cpu_model: cpu,
			server_prompt_tokens: rate === null ? null : rate * 100,
			server_prompt_seconds: rate === null ? null : 100
		})
	);
}

test('L3 groups combine vendors, count jobs rather than fingerprints, and preserve unknown and measured zero', () => {
	const jobs = fleetJobs([
		job({ date: '2026-09-26', l3_cache_bytes: 32 * 2 ** 20 }),
		job({ date: '2026-09-26', l3_cache_bytes: 32 * 2 ** 20 }),
		job({ date: '2026-09-26', cpu_model: 'Intel Xeon', fingerprint: 'bbbb000000000000', l3_cache_bytes: 32 * 2 ** 20 }),
		job({ date: '2026-09-27', l3_cache_bytes: 64 * 2 ** 20 }),
		job({ date: '2026-09-27', l3_cache_bytes: 0 }),
		job({ date: '2026-09-27', l3_cache_bytes: null })
	]);
	const view = fleetCacheView(jobs, options(jobs));
	expect(view.rows.map((row) => [row.label, row.counts])).toEqual([
		['64 MiB L3', [0, 1]], ['32 MiB L3', [3, 0]],
		['0 MiB L3', [0, 1]], ['L3 not measured', [0, 1]]
	]);
	expect(view.placements).toBe(6);
	const colours = view.rows.slice(0, -1).map((row) => row.colour);
	expect(new Set(colours).size).toBe(3);
	expect(colours[0]).toBe(schemePiYG[11][0]);
	expect(colours.at(-1)).toBe(schemePiYG[11].at(-1));
	expect(view.rows.at(-1)?.parts[0].gradient).toBeNull();
	expect(fleetSummary(view).series[0].values).toEqual(['3', '3']);
	expect(view.lines[0].map((line) => line.machine)).toContain('Intel Xeon');
	expect(view.lines[0].map((line) => line.l3Cache)).toEqual(['32 MiB L3', '32 MiB L3', '32 MiB L3']);
	expect(fleetSeries(view).map((series) => series.points.map((point) => point.value)))
		.toEqual([[0, 1], [3, 0], [0, 1], [0, 1]]);
	const narrow = fleetCacheView(jobs, options(jobs, { end: '2026-09-26', windowDays: 1 }));
	expect(narrow.rows[0].parts[0].swatch).toBe(view.rows[1].parts[0].swatch);
	const flat = fleetCacheView(jobs, options(jobs, {
		appearance: { ...options(jobs).appearance, gradients: false }
	}));
	expect(flat.rows.every((row) => row.parts[0].gradient === null)).toBe(true);
	const unnamed = fleetJobs([job({
		date: '2026-09-26', fingerprint: null, cpu_model: null, l3_cache_bytes: 32 * 2 ** 20
	})]);
	const reported = fleetCacheView(unnamed, options(unnamed, { lost: [{ date: '2026-09-27', articles: 1 }] }));
	expect(reported.nothing).toBeNull();
	expect(reported.rows[0].counts).toEqual([1]);
});

test.describe('THE ORACLE: the recorded door answer, drawn', () => {
	test('one stacked bar a day, one segment a kind, largest daily count at the bottom', () => {
		const rows = recorded();
		const jobs = fleetJobs(rows);
		expect(jobs, 'every recorded row is a job with a day and a run').toHaveLength(rows.length);
		const view = fleetView(jobs, options(jobs));
		const bars = dateSeries(fleetSeries(view), {
			frame: frame(760, 220),
			stacked: true,
			stackOrder: 'descending',
			density: 6,
			valueTicks: 4,
			padding: 0.2
		});
		expect(bars).not.toBeNull();
		if (bars === null) return;

		// The days and the kinds, worked out by hand off the rows.
		const days = [...new Set(rows.map((row) => String(row.date)))].sort();
		expect(bars.dates).toEqual(days);
		const byKind = new Map<string, { rates: number[]; perDay: Map<string, number> }>();
		for (const row of rows) {
			const kind = `v1:${String(row.fingerprint)}`;
			const held: { rates: number[]; perDay: Map<string, number> } = byKind.get(kind) ?? {
				rates: [],
				perDay: new Map()
			};
			const tokens = row.server_prompt_tokens;
			const seconds = row.server_prompt_seconds;
			if (typeof tokens === 'number' && typeof seconds === 'number' && seconds > 0) held.rates.push(tokens / seconds);
			held.perDay.set(String(row.date), (held.perDay.get(String(row.date)) ?? 0) + 1);
			byKind.set(kind, held);
		}
		// Every kind here is its own row: none shares a step with another leftover.
		expect(view.rows.map((row) => row.key).sort()).toEqual([...byKind.keys()].sort());

		for (const date of days) {
			// Bottom to top: the segment whose foot is lowest on the page first.
			const segments = bars.bars.filter((bar) => bar.date === date).sort((a, b) => b.y - a.y);
			const drawn = [...byKind].filter(([, held]) => (held.perDay.get(date) ?? 0) > 0).map(([key]) => key);
			expect(segments.map((bar) => bar.label).sort(), `${date}: one segment a kind`).toEqual(drawn.sort());
			for (const bar of segments) {
				expect(bar.value, `${date} ${bar.label}`).toBe(byKind.get(bar.label)?.perDay.get(date));
			}
			const counts = segments.map((bar) => bar.value);
			expect(counts, `${date}: largest count at the bottom`).toEqual([...counts].sort((a, b) => b - a));
		}
	});

	test('complete details retain exact dated counts and speed context without encoding speed in colour', () => {
		const jobs = fleetJobs(recorded());
		const view = fleetView(jobs, options(jobs));
		const readout = fleetReadout(view);
		expect(readout.columns).toEqual(view.days.map((date) => `${date} UTC`));
		expect(readout.series).toHaveLength(view.rows.length);
		const largeCountView = {
			...view,
			rows: view.rows.map((row, index) =>
				index === 0 ? { ...row, parts: row.parts.map((part) => ({ ...part, counts: [12_345, ...part.counts.slice(1)] })) } : row
			)
		};
		const largeCountReadout = fleetReadout(largeCountView);
		expect(largeCountReadout.series[0].values[0]).toBe(formatNumber(12_345, { exact: true, si: false }));
		for (const series of readout.series) {
			expect(series.note, series.label).toMatch(/^\d+(?:\.\d+)?(?: to \d+(?:\.\d+)?)? tokens a second$/);
		}
		// Full-identity ordering qualifies equal CPU names, not speed ranking.
		const labels = readout.series.map((series) => series.label);
		expect(labels).toContain('AMD EPYC 9V74 (kind 1)');
		expect(labels).toContain('AMD EPYC 9V74 (kind 2)');
		expect(new Set(labels).size).toBe(labels.length);
	});

	test('the rows name the most placed, and under the floor the panel draws a square a job', () => {
		const jobs = fleetJobs(recorded());
		const view = fleetView(jobs, options(jobs));
		// 90 jobs, under the 160 the panel needs for bars.
		expect(view.placements).toBe(90);
		expect(view.shape).toBe('dots');
		expect(fleetView(jobs, options(jobs, { minRows: 90 })).shape).toBe('bars');
		expect(view.mostPlaced?.label).toBe('AMD EPYC 7763');
		expect(fleetSummary(view).series[0].values).toEqual(
			view.days.map((date) => String(jobs.filter((job) => job.date === date).length)));
		const dots = fleetDots(view, { frame: frame(760, 220), density: 6, padding: 0.2, maxPx: knobs().fleet_dot_max_px, gapPx: 1 });
		expect(dots?.squares).toHaveLength(90);
		expect(dots?.size).toBeLessThanOrEqual(knobs().fleet_dot_max_px);
	});
});

test.describe('which kinds get a row of their own', () => {
	test('the most placed are named, and a tie goes to the kind placed most recently', () => {
		// Six kinds, top four named. The fourth and fifth tie at 3 placements; the
		// fifth was placed a day later, so it takes the named row and the fourth
		// folds with the sixth, which reads at the same speed.
		const rows = [
			...jobsOf(9, 'k1', 'Machine A', 10),
			...jobsOf(7, 'k2', 'Machine B', 20),
			...jobsOf(5, 'k3', 'Machine C', 30),
			...jobsOf(3, 'k4', 'Machine D', 50, '2026-09-11'),
			...jobsOf(3, 'k5', 'Machine E', 50, '2026-09-12'),
			...jobsOf(2, 'k6', 'Machine F', 50, '2026-09-12')
		];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-11', end: '2026-09-12', windowDays: 2, topKinds: 4 }));
		const own = view.rows.filter((row) => row.members.length === 0).map((row) => row.key);
		expect(own).toEqual(['v1:k1', 'v1:k2', 'v1:k3', 'v1:k5']);
		const fold = view.rows.find((row) => row.members.length > 0);
		expect(fold?.members.sort()).toEqual(['Machine D', 'Machine F']);
		expect(fold?.placements).toBe(5);
		expect(view.mostPlaced?.key).toBe('v1:k1');
	});

	test('leftovers fold once per step they share, and a step holding one leftover names it', () => {
		// Three kinds named; of the four leftovers two share the slowest step and
		// the other two stand alone on theirs. Cut over the seven kinds' medians,
		// the slowest step ends at 14.8, so 10 and 11 share it.
		const rows = [
			...jobsOf(20, 'n1', 'Named One', 30),
			...jobsOf(15, 'n2', 'Named Two', 40),
			...jobsOf(10, 'n3', 'Named Three', 70),
			...jobsOf(3, 'l1', 'Left One', 10),
			...jobsOf(2, 'l2', 'Left Two', 11),
			...jobsOf(2, 'l3', 'Left Three', 60),
			...jobsOf(1, 'l4', 'Left Four', 50)
		];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1, topKinds: 3 }));
		const fold = view.rows.find((row) => row.members.length > 0);
		expect(fold?.label).toBe('Other machines (2)');
		expect(fold?.members.sort()).toEqual(['Left One', 'Left Two']);
		expect(fold?.placements).toBe(5);
		expect(fold?.note).toBe('10 to 11 tokens a second');
		// The two lone leftovers keep rows of their own, named; Left Three shares
		// its step with a named kind, which is no fold.
		expect(view.rows.filter((row) => row.members.length === 0).map((row) => row.key).sort()).toEqual([
			'v1:l3',
			'v1:l4',
			'v1:n1',
			'v1:n2',
			'v1:n3'
		]);
		// The fold stands on its step: first, because step 1 is the slowest.
		expect(view.rows[0]).toBe(fold);
		expect(fold?.parts.map((part) => part.key)).toEqual(['v1:l1', 'v1:l2']);
		expect(new Set(fold?.parts.map((part) => part.colour)).size).toBe(2);
		for (const row of view.rows) for (let day = 0; day < view.days.length; day++) {
			expect(row.parts.reduce((sum, part) => sum + part.counts[day], 0)).toBe(row.counts[day]);
		}
		expect(fleetSeries(view).reduce((sum, series) =>
			sum + series.points.reduce((count, point) => count + (point.value ?? 0), 0), 0)).toBe(53);
		// The list a pick opens names each folded job's own machine, never the fold.
		expect(view.lines[0].filter((line) => line.row === fold?.key).map((line) => line.machine).sort()).toEqual([
			'Left One',
			'Left One',
			'Left One',
			'Left Two',
			'Left Two'
		]);
	});

	test('machines without speed keep their own identity fills inside the existing untimed fold', () => {
		const rows = [
			...jobsOf(10, 't1', 'Timed One', 20),
			...jobsOf(2, 'u1', 'Untimed One', null),
			...jobsOf(1, 'u2', 'Untimed Two', null)
		];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1, topKinds: 1 }));
		expect(view.rows.map((row) => row.label)).toEqual(['Timed One', 'Other machines (2)']);
		const untimed = view.rows[1];
		expect(untimed.drawing).toBe('untimed');
		expect(untimed.note).toBe('Speed not recorded');
		expect(untimed.members.sort()).toEqual(['Untimed One', 'Untimed Two']);
		expect(fleetSeries(view).map((series) => series.label)).toEqual(['v1:t1', 'v1:u1', 'v1:u2']);
		expect(fleetSeries(view).every((series) => series.gradient !== undefined && !series.hatched)).toBe(true);
	});
});

test.describe('a job whose machine nobody recorded', () => {
	test('is the last row, drawn in the grey, and never part of a fold', () => {
		const rows = [
			...jobsOf(6, 'k1', 'Machine A', 10),
			...jobsOf(4, 'k2', 'Machine B', 11),
			...jobsOf(3, 'k3', 'Machine C', 12),
			// Neither a digest nor a name: the platform gave the job a machine and
			// nobody wrote down which. It read prompts all the same.
			...jobsOf(5, null, null, 15)
		];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1, topKinds: 1 }));
		const last = view.rows.at(-1);
		expect(last?.key).toBe(UNRECORDED_KEY);
		expect(last?.label).toBe(UNRECORDED_NAME);
		expect(last?.drawing).toBe('unrecorded');
		expect(last?.note).toBeNull();
		expect(last?.placements).toBe(5);
		for (const row of view.rows) expect(row.members).not.toContain(UNRECORDED_NAME);
		// The bar stacks it last, on top of every kind.
		const series = fleetSeries(view);
		expect(series.at(-1)?.label).toBe(UNRECORDED_KEY);
	});

	test('a span whose every job lost its machine on a day that published says so rather than draws grey', () => {
		const jobs = fleetJobs(jobsOf(4, null, null, null));
		const lost = [{ date: '2026-09-12', articles: 431 }];
		const view = fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1, lost }));
		expect(view.nothing).toBe('record-lost');
		// Without the loss, those jobs are grey placements a reader can count.
		expect(fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1 })).nothing).toBeNull();
	});
});

test('categorical identity and qualified names survive presets, row order, speed and palette reuse', () => {
	const rows = [
		...jobsOf(3, 'same', 'Twin', 10, '2026-09-11'),
		job({ date: '2026-09-12', fingerprint: 'same', cpu_model: 'Twin', version: '2026-10-10', fingerprint_version: 2 }),
		job({ date: '2026-09-12', fingerprint: null, cpu_model: 'Twin' }),
		...jobsOf(1, 'untimed', 'Untimed', null),
		...jobsOf(1, 'zero', 'Zero', 0),
		...jobsOf(1, 'named-unknown', 'Machine not recorded', null),
		...jobsOf(1, null, null, null),
		...Array.from({ length: PALETTE.length }, (_, index) =>
			job({ date: '2026-09-12', fingerprint: `extra-${index}`, cpu_model: `Extra ${index}` }))
	];
	const jobs = fleetJobs(rows);
	const full = options(jobs, { start: '2026-09-11', end: '2026-09-12', windowDays: 2, topKinds: rows.length });
	const wide = fleetView(jobs, full);
	const narrow = fleetView([...jobs].reverse(), { ...full, start: '2026-09-12', windowDays: 1 });
	const changed = jobs.map((job) => ({ ...job, rate: job.rate === null ? null : 100 - job.rate }));
	const faster = fleetView(changed, { ...full, ramp: rampOf(changed) });
	const paints = (view: ReturnType<typeof fleetView>) =>
		new Map(view.rows.flatMap((row) => row.parts.map(({ key, label, colour, gradient }) =>
			[key, { label, colour, gradient }] as const)));
	const known = paints(wide);
	for (const [key, paint] of paints(narrow)) expect(paint, key).toEqual(known.get(key));
	for (const [key, paint] of paints(faster)) expect(paint, key).toEqual(known.get(key));
	expect([...known.keys()]).toEqual(expect.arrayContaining(['name:Twin', 'v1:same', 'v2:same', UNRECORDED_KEY]));
	expect(['name:Twin', 'v1:same', 'v2:same'].map((key) => known.get(key)?.label))
		.toEqual(['Twin (kind 1)', 'Twin (kind 2)', 'Twin (kind 3)']);
	const parts = wide.rows.flatMap((row) => row.parts);
	expect(parts.filter((part) => part.key !== UNRECORDED_KEY).every((part) =>
		schemePiYG[schemePiYG.length - 1].includes(part.colour))).toBe(true);
	expect(parts.filter((part) => part.key !== UNRECORDED_KEY).every((part) =>
		part.token !== '--chart-8' && part.gradient !== null)).toBe(true);
	expect(parts.find((part) => part.key === UNRECORDED_KEY)).toMatchObject({
		token: '--chart-8', gradient: null, colour: 'var(--chart-8)'
	});
	expect(parts.find((part) => part.key === 'v1:untimed')?.note).toBe('Speed not recorded');
	expect(parts.find((part) => part.key === 'v1:zero')?.note).toBe('0 tokens a second');
	expect(parts.find((part) => part.key === 'v1:named-unknown')?.label).toBe('Machine not recorded (kind 1)');
	expect(new Set(parts.map((part) => part.label)).size).toBe(parts.length);
	expect(new Set(parts.map((part) => part.colour)).size).toBeLessThan(parts.length);
	expect(fleetSeries(wide)).toHaveLength(parts.length);
	const flat = fleetView(jobs, { ...full, appearance: { ...full.appearance, gradients: false } });
	expect(fleetSeries(flat).every((series) => series.gradient === undefined)).toBe(true);
	expect(flat.rows.flatMap((row) => row.parts.map((part) => [part.key, part.colour])))
		.toEqual(wide.rows.flatMap((row) => row.parts.map((part) => [part.key, part.colour])));
});

test('compact mark hover and complete non-hover details quote the same machine-day counts, including zeros', () => {
	const jobs = fleetJobs([
		...jobsOf(2, 'a', 'Machine A', 0, '2026-09-11'),
		...jobsOf(1, 'b', 'Machine B', null, '2026-09-12'),
		...jobsOf(1, null, null, null, '2026-09-12')
	]);
	const view = fleetView(jobs, options(jobs, { start: '2026-09-11', end: '2026-09-12', windowDays: 2 }));
	const hover = fleetHover(view);
	const details = fleetReadout(view);
	expect(hoverReading(hover, 0)?.entries.map(({ label, value }) => [label, value])).toEqual([['Recorded jobs', '2']]);
	for (const row of view.rows) for (const part of row.parts) {
		for (let day = 0; day < view.days.length; day++) {
			const pointed = hoverReading(hover, day, part.key)!;
			expect(pointed.heading).toBe(`${view.days[day]} UTC`);
			expect(pointed.entries.map(({ label, value }) => [label, value]))
				.toEqual([[part.label, `${part.counts[day]} of 2 recorded jobs`]]);
			expect(pointed.entries[0].swatch).toBe(part.swatch);
			expect(details.series.find((series) => series.label === part.label)?.values[day])
				.toBe(String(part.counts[day]));
		}
	}
	expect(hoverReading(hover, 0, 'v1:b')?.entries[0].value).toBe('0 of 2 recorded jobs');
	expect(view.days).toEqual(['2026-09-11', '2026-09-12']);
	expect(details.series.find((series) => series.label === 'Machine B')?.note).toBe('Speed not recorded');
});

test('each day ranks its own counts while full-identity colours, zeros and unknown jobs remain exact', () => {
	const jobs = fleetJobs([
		...jobsOf(5, 'a', 'Machine A', 1, '2026-09-11'),
		...jobsOf(1, 'b', 'Machine B', 20, '2026-09-11'),
		...jobsOf(1, 'a', 'Machine A', 1, '2026-09-12'),
		...jobsOf(7, 'b', 'Machine B', 20, '2026-09-12'),
		...jobsOf(2, null, null, null, '2026-09-12')
	]);
	const view = fleetView(jobs, options(jobs, { start: '2026-09-11', end: '2026-09-12', windowDays: 2 }));
	const series = fleetSeries(view);
	const drawing = dateSeries(series, {
		frame: frame(760, 220), stacked: true, stackOrder: 'descending',
		density: 6, valueTicks: 4, padding: 0.2
	})!;
	const bottomFirst = (date: string) => drawing.bars.filter((bar) => bar.date === date)
		.sort((a, b) => b.y - a.y).map((bar) => [bar.label, bar.value]);
	expect(bottomFirst('2026-09-11')).toEqual([['v1:a', 5], ['v1:b', 1]]);
	expect(bottomFirst('2026-09-12')).toEqual([['v1:b', 7], [UNRECORDED_KEY, 2], ['v1:a', 1]]);
	const colourA = series.find((one) => one.label === 'v1:a')!.fill;
	expect(drawing.bars.filter((bar) => bar.label === 'v1:a').map((bar) => bar.fill)).toEqual([colourA, colourA]);
	const hover = fleetHover(view);
	expect(hoverReading(hover, 1, 'v1:a')?.entries[0].value).toBe('1 of 10 recorded jobs');
	expect(hoverReading(hover, 0, UNRECORDED_KEY)?.entries[0].value).toBe('0 of 6 recorded jobs');
	expect(fleetReadout(view).series.find((one) => one.label === UNRECORDED_NAME)?.values).toEqual(['0', '2']);
	const squares = fleetDots(view, { frame: frame(760, 220), density: 6, padding: 0.2, maxPx: 8, gapPx: 1 })!;
	expect(squares.squares.filter((square) => square.day === 0).map((square) => square.row))
		.toEqual([...Array(5).fill('v1:a'), 'v1:b']);
	expect(squares.squares.filter((square) => square.day === 1).map((square) => square.row))
		.toEqual([...Array(7).fill('v1:b'), UNRECORDED_KEY, UNRECORDED_KEY, 'v1:a']);
});

test.describe('the window, the states and the rows the door hands over', () => {
	test('a job outside the open span is not counted', () => {
		const rows = [job({ date: '2026-09-01' }), job({ date: '2026-09-12' }), job({ date: '2026-09-20' })];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-10', end: '2026-09-16', windowDays: 7 }));
		expect(view.placements).toBe(1);
		expect(view.days).toEqual(['2026-09-12']);
		expect(view.daysWithout).toBe(6);
		expect(fleetSummary(view).series[0].values).toEqual(['1']);
	});

	test('recording off, nothing recorded yet and a lost record are three states', () => {
		expect(fleetView([], options([], { recording: false })).nothing).toBe('recording-off');
		expect(fleetView([], options([])).nothing).toBe('none');
		expect(fleetView([], options([], { lost: [{ date: '2026-09-27', articles: 12 }] })).nothing).toBe('record-lost');
	});

	test('a cell read off disk as text and one handed back typed are the same job', () => {
		const typed = job({ shard: 3, job_seconds: 812.5, server_prompt_tokens: 950, server_prompt_seconds: 80.65 });
		const text: Row = Object.fromEntries(Object.entries(typed).map(([key, value]) => [key, value === null ? '' : String(value)]));
		expect(fleetJobs([text])).toEqual(fleetJobs([typed]));
		const [one] = fleetJobs([typed]);
		expect(one.rate).toBeCloseTo(950 / 80.65, 9);
		expect(one.shard).toBe(3);
		// A row that names no day or no run cannot be drawn or listed.
		expect(fleetJobs([job({ date: null }), job({ run_id: '' })])).toEqual([]);
	});

	test('pipeline and task identity stays separate in data and is named clearly in the list', () => {
		const jobs = fleetJobs([
			job({ job: null, pipeline_name: 'gardener', task_name: 'run-tasks' }),
			job({ job: null, pipeline_name: 'llm-council', task_name: 'settle' })
		]);
		expect(jobs.map((one) => [one.job, one.pipelineName, one.taskName])).toEqual([
			[null, 'gardener', 'run-tasks'],
			[null, 'llm-council', 'settle']
		]);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1 }));
		expect(view.lines[0].map(({ job, pipelineName, taskName }) =>
			job ?? `${pipelineName}/${taskName}`
		)).toEqual(['gardener/run-tasks', 'llm-council/settle']);
	});

	test('the list a pick opens is every job of that day, slowest machine first', () => {
		const rows = [...jobsOf(2, 'fast', 'Fast One', 40), ...jobsOf(1, 'slow', 'Slow One', 10)];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1 }));
		expect(view.lines[0].map((line) => [line.machine, line.rate])).toEqual([
			['Slow One', 10],
			['Fast One', 40],
			['Fast One', 40]
		]);
		expect(view.lines[0].every((line) => line.seconds === 800 && line.runId === '2026-09-12-1')).toBe(true);
	});

	test('one square a job, a day stacked bottom up in row order, and the busiest day fits', () => {
		const rows = [...jobsOf(30, 'slow', 'Slow One', 10), ...jobsOf(12, 'fast', 'Fast One', 40)];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1 }));
		const box = frame(390, 220);
		const dots = fleetDots(view, { frame: box, density: 6, padding: 0.2, maxPx: 8, gapPx: 1 });
		expect(dots).not.toBeNull();
		if (dots === null) return;
		expect(dots.squares).toHaveLength(42);
		expect(dots.squares.every((square) => square.y >= box.top && square.y + square.size <= box.bottom)).toBe(true);
		// The more frequent machine's squares sit at or below the less frequent one's.
		const lowestFast = Math.max(...dots.squares.filter((square) => square.row === 'v1:fast').map((square) => square.y));
		const highestSlow = Math.min(...dots.squares.filter((square) => square.row === 'v1:slow').map((square) => square.y));
		expect(Number.isFinite(lowestFast) && Number.isFinite(highestSlow)).toBe(true);
		expect(highestSlow).toBeGreaterThanOrEqual(lowestFast);
	});

	test('a day stands as a block no wider than the busiest day is tall, and its outline is that block', () => {
		// One day in a wide plot, where the column could hold all thirty in a row.
		const rows = [...jobsOf(18, 'slow', 'Slow One', 10), ...jobsOf(12, 'fast', 'Fast One', 40)];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1 }));
		const dots = fleetDots(view, { frame: frame(1400, 220), density: 6, padding: 0.2, maxPx: 8, gapPx: 1 });
		expect(dots).not.toBeNull();
		if (dots === null) return;
		// Thirty jobs: five abreast and six high, the square root rounded down.
		const across = new Set(dots.squares.map((square) => square.x)).size;
		const high = new Set(dots.squares.map((square) => square.y)).size;
		expect([across, high]).toEqual([5, 6]);
		// The more frequent machine fills the bottom lines.
		const lowestFast = Math.max(...dots.squares.filter((square) => square.row === 'v1:fast').map((square) => square.y));
		const highestSlow = Math.min(...dots.squares.filter((square) => square.row === 'v1:slow').map((square) => square.y));
		expect(Number.isFinite(lowestFast) && Number.isFinite(highestSlow)).toBe(true);
		expect(highestSlow).toBeGreaterThanOrEqual(lowestFast);
		// The outline of the day held open is the extent of its squares.
		expect(dots.blocks).toHaveLength(1);
		const [block] = dots.blocks;
		expect(block.left).toBeCloseTo(Math.min(...dots.squares.map((square) => square.x)), 6);
		expect(block.right).toBeCloseTo(Math.max(...dots.squares.map((square) => square.x + square.size)), 6);
		expect(block.top).toBeCloseTo(Math.min(...dots.squares.map((square) => square.y)), 6);
	});
});
