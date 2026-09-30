/** THE ORACLE for the machine-kinds panel: what it draws from the rows the query door answers.
 *
 * Given the door's answer for the panel's columns - one row a job, as the
 * compaction packs the machine record - the panel draws one stacked bar a day
 * and one segment a machine kind, slowest at the bottom; a job whose machine
 * nobody recorded is the last segment and is never part of a fold; and every
 * row of the strip under the plot says the speed its colour stands for.
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

import { dateSeries } from '../src/lib/charts/d3/dateSeries';
import { absentHatch } from '../src/lib/charts/d3/ordered-colour';
import {
	FLEET_COLUMNS,
	fleetDots,
	fleetJobs,
	fleetReadout,
	fleetSentence,
	fleetSeries,
	fleetView,
	foldSentences,
	stepWords,
	type FleetJob,
	type FleetOptions
} from '../src/lib/charts/fleet';
import { frame } from '../src/lib/charts/frame';
import {
	machineKeys,
	machineRamp,
	UNRECORDED_KEY,
	UNRECORDED_NAME,
	type MachineRamp
} from '../src/lib/charts/machine-colour';
import { shortDate } from '../src/lib/format';
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
	return answer.rows;
}

/** The page's one ramp, cut over every job handed in. */
function rampOf(jobs: readonly FleetJob[]): MachineRamp {
	const config = knobs();
	const keys = machineKeys(jobs.map((job) => ({ fingerprint: job.fingerprint, cpuModel: job.cpuModel })));
	return machineRamp(
		jobs.map((job) => ({ machine: keys({ fingerprint: job.fingerprint, cpuModel: job.cpuModel }), rate: job.rate })),
		{ stops: config.machine_colour_stops, floor: config.machine_colour_floor_share }
	);
}

function options(jobs: readonly FleetJob[], over: Partial<FleetOptions> = {}): FleetOptions {
	const config = knobs();
	return {
		ramp: rampOf(jobs),
		start: '2026-09-26',
		end: '2026-09-28',
		windowDays: 3,
		minRows: config.fleet_min_rows,
		topKinds: config.fleet_top_kinds,
		recording: true,
		...over
	};
}

/** The middle reading, averaging the two middle ones of an even count. */
function middle(values: readonly number[]): number {
	const sorted = [...values].sort((a, b) => a - b);
	const at = sorted.length / 2;
	return sorted.length % 2 === 1 ? sorted[Math.floor(at)] : (sorted[at - 1] + sorted[at]) / 2;
}

/** One job row in the door's shape. Every cell may be left to its default. */
function job(over: Partial<Record<(typeof FLEET_COLUMNS)[number], string | number | null>>): Row {
	return {
		date: '2026-09-12',
		run_id: '2026-09-12-1',
		job: 'work',
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

test.describe('THE ORACLE: the recorded door answer, drawn', () => {
	test('one stacked bar a day, one segment a kind, slowest at the bottom', () => {
		const rows = recorded();
		const jobs = fleetJobs(rows);
		expect(jobs, 'every recorded row is a job with a day and a run').toHaveLength(rows.length);
		const view = fleetView(jobs, options(jobs));
		const bars = dateSeries(fleetSeries(view), {
			frame: frame(760, 220),
			stacked: true,
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
			const kind = String(row.fingerprint);
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

		const speedOf = (key: string) => middle(byKind.get(key)?.rates ?? []);
		for (const date of days) {
			// Bottom to top: the segment whose foot is lowest on the page first.
			const segments = bars.bars.filter((bar) => bar.date === date).sort((a, b) => b.y - a.y);
			const drawn = [...byKind].filter(([, held]) => (held.perDay.get(date) ?? 0) > 0).map(([key]) => key);
			expect(segments.map((bar) => bar.label).sort(), `${date}: one segment a kind`).toEqual(drawn.sort());
			for (const bar of segments) {
				expect(bar.value, `${date} ${bar.label}`).toBe(byKind.get(bar.label)?.perDay.get(date));
			}
			const speeds = segments.map((bar) => speedOf(bar.label));
			expect(speeds, `${date}: slowest at the bottom`).toEqual([...speeds].sort((a, b) => a - b));
		}
	});

	test('every row of the strip says the speed its colour stands for', () => {
		const jobs = fleetJobs(recorded());
		const view = fleetView(jobs, options(jobs));
		const config = knobs();
		const readout = fleetReadout(view, absentHatch({ degrees: config.absent_hatch_degrees, gapPx: 3, linePx: 1 }));
		expect(readout.columns).toEqual(view.days.map(shortDate));
		expect(readout.series).toHaveLength(view.rows.length);
		for (const series of readout.series) {
			expect(series.note, series.label).toMatch(/^\d+\.\d( to \d+\.\d)? tokens a second$/);
		}
		// Two kinds of one name are told apart by speed, in words.
		const labels = readout.series.map((series) => series.label);
		expect(labels).toContain('AMD EPYC 9V74, faster');
		expect(labels).toContain('AMD EPYC 9V74, slower');
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
		expect(fleetSentence(view)).toBe(
			'90 jobs ran in these 3 days. The kind we are given most is AMD EPYC 7763, 50 of them.'
		);
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
		expect(own).toEqual(['k1', 'k2', 'k3', 'k5']);
		const fold = view.rows.find((row) => row.members.length > 0);
		expect(fold?.members.sort()).toEqual(['Machine D', 'Machine F']);
		expect(fold?.placements).toBe(5);
		expect(view.mostPlaced?.key).toBe('k1');
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
		expect(fold?.label).toBe(`Other machines at the ${stepWords(1, knobs().machine_colour_stops)} speed`);
		expect(fold?.members.sort()).toEqual(['Left One', 'Left Two']);
		expect(fold?.placements).toBe(5);
		expect(fold?.note).toBe('10.0 to 11.0 tokens a second');
		// The two lone leftovers keep rows of their own, named; Left Three shares
		// its step with a named kind, which is no fold.
		expect(view.rows.filter((row) => row.members.length === 0).map((row) => row.key).sort()).toEqual([
			'l3',
			'l4',
			'n1',
			'n2',
			'n3'
		]);
		// The fold stands on its step: first, because step 1 is the slowest.
		expect(view.rows[0]).toBe(fold);
		expect(foldSentences(view)).toEqual([`The ${fold?.label} row holds 2 kinds: Left One and Left Two.`]);
		// The list a pick opens names each folded job's own machine, never the fold.
		expect(view.lines[0].filter((line) => line.row === fold?.key).map((line) => line.machine).sort()).toEqual([
			'Left One',
			'Left One',
			'Left One',
			'Left Two',
			'Left Two'
		]);
	});

	test('machines with no speed reading fold into one hatched row past the named ones', () => {
		const rows = [
			...jobsOf(10, 't1', 'Timed One', 20),
			...jobsOf(2, 'u1', 'Untimed One', null),
			...jobsOf(1, 'u2', 'Untimed Two', null)
		];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-12', end: '2026-09-12', windowDays: 1, topKinds: 1 }));
		expect(view.rows.map((row) => row.label)).toEqual(['Timed One', 'Other machines with no speed reading']);
		const untimed = view.rows[1];
		expect(untimed.drawing).toBe('untimed');
		expect(untimed.note).toBe('no speed reading');
		expect(untimed.members.sort()).toEqual(['Untimed One', 'Untimed Two']);
		expect(fleetSeries(view)[1].hatched).toBe(true);
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

test.describe('the window, the states and the rows the door hands over', () => {
	test('a job outside the open span is not counted', () => {
		const rows = [job({ date: '2026-09-01' }), job({ date: '2026-09-12' }), job({ date: '2026-09-20' })];
		const jobs = fleetJobs(rows);
		const view = fleetView(jobs, options(jobs, { start: '2026-09-10', end: '2026-09-16', windowDays: 7 }));
		expect(view.placements).toBe(1);
		expect(view.days).toEqual(['2026-09-12']);
		expect(view.daysWithout).toBe(6);
		expect(fleetSentence(view)).toBe(
			'1 job ran in these 7 days, on 1 day of them. The kind we are given most is AMD EPYC 7763, 1 of them.'
		);
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
		// The slow machine's squares sit at or below every fast machine's square.
		const lowestFast = Math.max(...dots.squares.filter((square) => square.row === 'fast').map((square) => square.y));
		const highestSlow = Math.min(...dots.squares.filter((square) => square.row === 'slow').map((square) => square.y));
		expect(highestSlow).toBeGreaterThanOrEqual(lowestFast);
	});
});
