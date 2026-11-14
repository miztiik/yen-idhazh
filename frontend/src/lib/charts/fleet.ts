/** Which recorded jobs belong to each UTC day and machine kind? */

import type { LostDay } from '../console/recording';
import type { Row } from '../data/ledger';
import { normalizeHostRows } from '../data/host-fingerprint';
import { formatNumber, type NumberFormatConfig } from '../number-format';
import { dayTicks, type DayTick, type Frame } from './frame';
import {
	isUnrecorded,
	machineKeys,
	promptRate,
	rateWords,
	UNRECORDED_KEY,
	type MachineIdentity,
	type MachineKey,
	type MachineRamp
} from './machine-colour';
import { readoutOf, type Readout } from './readout';
import type { HoverReadout } from './readout-hover';
import type { ChartConfig } from '../server/config';
import { RESERVED_GREY_INK } from './d3/ordered-colour';
import type { FillGradient, SeriesInput } from './d3/dateSeries';
import { bandScale } from './d3/scale';
import { fleetIdentities, type FleetIdentity } from './fleet-identity';

/** The columns the panel reads, and the only ones: what a query for it names. */
export const FLEET_COLUMNS = [
	'version',
	'date',
	'run_id',
	'job',
	'pipeline_name',
	'task_name',
	'shard',
	'fingerprint',
	'fingerprint_version',
	'cpu_model',
	'l3_cache_bytes',
	'job_seconds',
	'server_prompt_tokens',
	'server_prompt_seconds',
	'cores',
	'threads',
	'mhz_max',
	'mhz_at_probe'
] as const;

/** One job as the panel reads it. */
export interface FleetJob {
	/** The UTC day the job ran, `YYYY-MM-DD`. */
	date: string;
	runId: string;
	/** The legacy job name. Null for a generic pipeline/task identity. */
	job: string | null;
	pipelineName: string | null;
	taskName: string | null;
	shard: number | null;
	fingerprint: string | null;
	fingerprintVersion: number | null;
	cpuModel: string | null;
	l3CacheBytes: number | null;
	/** The job's own clock, in seconds. */
	seconds: number | null;
	/** Prompt tokens its model server read a second. Only a job that served the
	 * summarizing model takes one. */
	rate: number | null;
}

/** How a row of the panel is drawn. */
export type FleetDrawing = 'step' | 'untimed' | 'unrecorded';

/** One row of the panel: a kind of machine, a fold of several, or no machine. */
export interface FleetRow {
	/** The kind's own key, or the fold's. Never shown. */
	key: string;
	/** What a reader reads. */
	label: string;
	/** Median-speed context retained for details, never a colour encoding. */
	note: string | null;
	colour: string;
	drawing: FleetDrawing;
	step: number | null;
	/** The slowest median the row stands for, which orders rows on one step. */
	rate: number | null;
	/** Placements a drawn day, in the order `FleetView.days` holds. */
	counts: number[];
	placements: number;
	/** The kinds a fold holds, in words. Empty on a kind's own row. */
	members: string[];
	/** Constituent identities retain exact counts inside this compact legend group. */
	parts: FleetPart[];
}

export interface FleetPart extends FleetIdentity {
	counts: number[];
	note: string | null;
}

/** One job of a day, as the list a pick opens names it. */
export interface FleetLine {
	runId: string;
	job: string | null;
	pipelineName: string | null;
	taskName: string | null;
	shard: number | null;
	/** The kind of machine in words, never a fold's name. */
	machine: string;
	l3Cache?: string;
	swatch: string;
	seconds: number | null;
	rate: number | null;
	/** The row this job is drawn in. */
	row: string;
}

export interface FleetView {
	/** The days that recorded a placement, ascending. One column each. */
	days: string[];
	/** Legend-group order; each day's drawn stack ranks its own counts separately. */
	rows: FleetRow[];
	/** Every job of each drawn day, in row order, for the list a pick opens. */
	lines: FleetLine[][];
	/** Job placements the count was made from. The denominator, printed. */
	placements: number;
	/** Days the open span covers. */
	windowDays: number;
	/** Days of the span that recorded no placement at all. */
	daysWithout: number;
	/** Bars at or above `minRows` placements, one square a job under it. */
	shape: 'bars' | 'dots';
	minRows: number;
	topKinds: number;
	numberFormat: NumberFormatConfig;
	/** The kind placed most in the span, or null where none was named. */
	mostPlaced: FleetRow | null;
	/** Why there is nothing to draw. Null where there is something.
	 *
	 * `record-lost` is a span whose every placement lost its machine on a day
	 * that published articles; `none` is a span the record had not reached. They
	 * send an operator to opposite places.
	 */
	nothing: 'recording-off' | 'record-lost' | 'none' | null;
}

export interface FleetOptions {
	/** Whole-record speed groups used only for the established ordering and folds. */
	ramp: MachineRamp;
	appearance: { gradients: boolean; floor: number; palette: ChartConfig['palette'] };
	/** The open span, inclusive UTC days. */
	start: string;
	end: string;
	/** How many days the span covers. */
	windowDays: number;
	/** `console.fleet_min_rows`. */
	minRows: number;
	/** `console.fleet_top_kinds`. */
	topKinds: number;
	numberFormat: NumberFormatConfig;
	/** False where the machine record is switched off. */
	recording: boolean;
	/** Days that published articles and kept no machine row. Only their presence
	 * in the span is read here; the sentence is the route's. */
	lost?: readonly LostDay[];
}

type Cell = Row[string] | undefined;

function text(cell: Cell): string | null {
	if (cell === null || cell === undefined || typeof cell === 'boolean') return null;
	const trimmed = String(cell).trim();
	return trimmed === '' ? null : trimmed;
}

function figure(cell: Cell): number | null {
	const raw = text(cell);
	if (raw === null) return null;
	const parsed = Number(raw);
	return Number.isFinite(parsed) ? parsed : null;
}

const DAY = /^\d{4}-\d{2}-\d{2}$/;

/** The jobs in the rows a query for `FLEET_COLUMNS` answered.
 *
 * A row with no day or no run id is skipped, because it can be neither drawn
 * on a day nor named in a list. A row with no machine is kept: the platform
 * handed that job a machine too, and nobody recorded which.
 */
export function fleetJobs(rows: readonly Row[]): FleetJob[] {
	const jobs: FleetJob[] = [];
	for (const row of normalizeHostRows(rows)) {
		const date = text(row.date);
		const runId = text(row.run_id);
		if (date === null || !DAY.test(date) || runId === null) continue;
		const pipeline = text(row.pipeline_name);
		const task = text(row.task_name);
		jobs.push({
			date,
			runId,
			job: text(row.job) ?? (pipeline !== null && task !== null ? null : 'work'),
			pipelineName: pipeline,
			taskName: task,
			shard: figure(row.shard),
			fingerprint: text(row.fingerprint),
			fingerprintVersion: figure(row.fingerprint_version),
			cpuModel: text(row.cpu_model),
			l3CacheBytes: figure(row.l3_cache_bytes),
			seconds: figure(row.job_seconds),
			rate: promptRate(figure(row.server_prompt_tokens), figure(row.server_prompt_seconds))
		});
	}
	return jobs;
}

function rangeNote(rates: readonly number[], numberFormat: NumberFormatConfig): string | null {
	if (rates.length === 0) return null;
	const low = Math.min(...rates);
	const high = Math.max(...rates);
	const lowWords = formatNumber(low, numberFormat);
	const highWords = formatNumber(high, numberFormat);
	return lowWords === highWords
		? rateWords(low, numberFormat)
		: `${lowWords} to ${rateWords(high, numberFormat)}`;
}

/** A known machine the ordering metadata has no speed reading for. */
function untimed(machine: MachineKey): MachineIdentity {
	return {
		key: machine.key,
		name: machine.name,
		fingerprintVersion: machine.fingerprintVersion,
		step: null,
		rate: null,
		colour: RESERVED_GREY_INK
	};
}

/** The kinds, folds and absence the open span draws, day by day. */
export function fleetView(jobs: readonly FleetJob[], options: FleetOptions): FleetView {
	const inSpan = jobs.filter((job) => job.date >= options.start && job.date <= options.end);
	const resolve = machineKeys(
		jobs.map((job) => ({
			fingerprint: job.fingerprint,
			fingerprintVersion: job.fingerprintVersion,
			cpuModel: job.cpuModel
		}))
	);
	const placed = inSpan.map((job) => {
		const machine = resolve({
			fingerprint: job.fingerprint,
			fingerprintVersion: job.fingerprintVersion,
			cpuModel: job.cpuModel
		});
		return { job, identity: options.ramp.at.get(machine.key) ?? untimed(machine) };
	});
	const days = [...new Set(inSpan.map((job) => job.date))].sort();
	const column = new Map(days.map((date, index) => [date, index]));
	const colours = fleetIdentities(options.ramp.rows, options.appearance);
	function paint(identity: MachineIdentity): FleetIdentity {
		const colour = colours.get(identity.key);
		if (colour === undefined) throw new Error(`The widest machine universe names no ${identity.key}.`);
		return colour;
	}
	function part(identity: MachineIdentity): FleetPart {
		return {
			...paint(identity),
			counts: days.map((date) => placed.filter((one) => one.job.date === date && one.identity.key === identity.key).length),
			note: isUnrecorded(identity) ? null : identity.rate === null
				? 'Speed not recorded' : rateWords(identity.rate, options.numberFormat)
		};
	}

	const lost = (options.lost ?? []).filter(
		(day) => day.date >= options.start && day.date <= options.end
	);
	const nothing: FleetView['nothing'] = !options.recording
		? 'recording-off'
		: inSpan.length === 0
			? lost.length > 0
				? 'record-lost'
				: 'none'
			: lost.length > 0 && placed.every((one) => isUnrecorded(one.identity))
				? 'record-lost'
				: null;

	// Window frequency selects named groups; full identity selects paint.
	const kinds = new Map<string, { identity: MachineIdentity; placements: number; newest: string }>();
	for (const { job, identity } of placed) {
		const held = kinds.get(identity.key) ?? { identity, placements: 0, newest: job.date };
		held.placements += 1;
		if (job.date > held.newest) held.newest = job.date;
		kinds.set(identity.key, held);
	}
	const ranked = [...kinds.values()]
		.filter((kind) => !isUnrecorded(kind.identity))
		.sort(
			(a, b) =>
				b.placements - a.placements ||
				b.newest.localeCompare(a.newest) ||
				a.identity.key.localeCompare(b.identity.key)
		);
	const named = ranked.slice(0, Math.max(1, options.topKinds));
	const leftover = ranked.slice(named.length);

	// Which row each kind is drawn in: its own, or a fold of the leftovers on
	// its step. A step holding one leftover names it; so does a lone untimed one.
	const rowOf = new Map<string, string>();
	const folds = new Map<string, MachineIdentity[]>();
	for (const kind of named) rowOf.set(kind.identity.key, kind.identity.key);
	for (const kind of leftover) {
		const on = kind.identity.step === null ? 'fold:untimed' : `fold:step-${kind.identity.step}`;
		folds.set(on, [...(folds.get(on) ?? []), kind.identity]);
	}
	for (const [fold, members] of folds) {
		for (const member of members) rowOf.set(member.key, members.length === 1 ? member.key : fold);
	}

	const counts = (key: string): number[] => {
		const out = days.map(() => 0);
		for (const { job, identity } of placed) {
			if ((rowOf.get(identity.key) ?? identity.key) === key) out[column.get(job.date) ?? 0] += 1;
		}
		return out;
	};

	const rows: FleetRow[] = [];
	for (const kind of [...named, ...leftover.filter((one) => rowOf.get(one.identity.key) === one.identity.key)]) {
		const identity = kind.identity;
		rows.push({
			key: identity.key,
			label: paint(identity).label,
			note: identity.rate === null ? 'Speed not recorded' : rateWords(identity.rate, options.numberFormat),
			colour: paint(identity).colour,
			drawing: identity.step === null ? 'untimed' : 'step',
			step: identity.step,
			rate: identity.rate,
			counts: counts(identity.key),
			placements: kind.placements,
			members: [],
			parts: [part(identity)]
		});
	}
	for (const [fold, members] of folds) {
		if (members.length < 2) continue;
		const first = members[0];
		const rates = members.flatMap((member) => (member.rate === null ? [] : [member.rate]));
		const tally = counts(fold);
		rows.push({
			key: fold,
			label: `Other machines (${members.length})`,
			note: rangeNote(rates, options.numberFormat) ?? 'Speed not recorded',
			colour: paint(first).colour,
			drawing: first.step === null ? 'untimed' : 'step',
			step: first.step,
			rate: rates.length === 0 ? null : Math.min(...rates),
			counts: tally,
			placements: tally.reduce((sum, count) => sum + count, 0),
			members: members.map((member) => paint(member).label),
			parts: [...members].sort((a, b) => a.key < b.key ? -1 : a.key > b.key ? 1 : 0).map(part)
		});
	}
	// Slowest at the bottom of every bar and first in the strip, then the
	// machines with no reading, the most placed of them first.
	rows.sort(
		(a, b) =>
			(a.step === null ? 1 : 0) - (b.step === null ? 1 : 0) ||
			(a.step ?? 0) - (b.step ?? 0) ||
			(a.rate ?? 0) - (b.rate ?? 0) ||
			b.placements - a.placements ||
			a.key.localeCompare(b.key)
	);

	const unrecorded = kinds.get(UNRECORDED_KEY);
	if (unrecorded !== undefined) {
		rows.push({
			key: UNRECORDED_KEY,
			label: unrecorded.identity.name,
			note: null,
			colour: unrecorded.identity.colour,
			drawing: 'unrecorded',
			step: null,
			rate: null,
			counts: counts(UNRECORDED_KEY),
			placements: unrecorded.placements,
			members: [],
			parts: [part(unrecorded.identity)]
		});
	}

	const order = new Map(rows.map((row, index) => [row.key, index]));
	const lines: FleetLine[][] = days.map(() => []);
	for (const { job, identity } of placed) {
		const row = rowOf.get(identity.key) ?? identity.key;
		lines[column.get(job.date) ?? 0].push({
			runId: job.runId,
			job: job.job,
			pipelineName: job.pipelineName,
			taskName: job.taskName,
			shard: job.shard,
			machine: paint(identity).label,
			swatch: paint(identity).swatch,
			seconds: job.seconds,
			rate: job.rate,
			row
		});
	}
	for (const day of lines) {
		day.sort(
			(a, b) =>
				(order.get(a.row) ?? 0) - (order.get(b.row) ?? 0) ||
				a.runId.localeCompare(b.runId) ||
				(a.pipelineName !== null && a.taskName !== null
					? `${a.pipelineName}/${a.taskName}`
					: a.job ?? '').localeCompare(
					b.pipelineName !== null && b.taskName !== null
						? `${b.pipelineName}/${b.taskName}`
						: b.job ?? ''
				) ||
				(a.shard ?? -1) - (b.shard ?? -1)
		);
	}

	const mostPlaced = named.length === 0 ? null : (rows.find((row) => row.key === named[0].identity.key) ?? null);
	return {
		days,
		rows,
		lines,
		placements: inSpan.length,
		windowDays: options.windowDays,
		daysWithout: Math.max(0, options.windowDays - days.length),
		shape: inSpan.length >= options.minRows ? 'bars' : 'dots',
		minRows: options.minRows,
		topKinds: options.topKinds,
		numberFormat: options.numberFormat,
		mostPlaced,
		nothing
	};
}

/** Every machine's exact dated counts, independently of its position in a daily stack. */
export function fleetSeries(view: FleetView): SeriesInput[] {
	return view.rows.flatMap((row) => row.parts.map((part) => ({
		label: part.key,
		token: part.token,
		fill: part.colour,
		...(part.gradient === null ? {} : { gradient: part.gradient }),
		points: view.days.map((date, index) => ({ date, value: part.counts[index] ?? 0 }))
	})));
}

/** Full dated counts and speed context, reachable in the selected day's details. */
export function fleetReadout(view: FleetView): Readout {
	return readoutOf({
		type: 'dateSeries',
		columns: view.days.map((date) => `${date} UTC`),
		series: view.rows.flatMap((row) => row.parts.map((part) => ({
			label: part.label,
			swatch: part.swatch,
			values: part.counts,
			format: (value: number) => formatNumber(value, view.numberFormat, { exact: true, si: false }),
			...(part.note === null ? {} : { note: part.note })
		}))),
		notMeasured: 'No job was placed on this day',
		resting: 'last'
	});
}

/** Only the selected UTC day and its recorded job total belong below the plot. */
export function fleetSummary(view: FleetView): Readout {
	return readoutOf({
		type: 'dateSeries',
		columns: view.days.map((date) => `${date} UTC`),
		series: [{
			label: 'Recorded jobs', swatch: null,
			values: view.days.map((_, day) => view.rows.reduce((sum, row) => sum + row.counts[day], 0)),
			format: (value) => formatNumber(value, view.numberFormat, { exact: true, si: false })
		}],
		notMeasured: 'No recorded jobs', resting: 'last'
	});
}

/** Hover projects one actual machine mark, or just its day's total over empty day space. */
export function fleetHover(view: FleetView): HoverReadout {
	const summary = fleetSummary(view);
	return {
		name: 'machine-fleet', readout: summary, footnote: false,
		byMark: new Map(view.rows.flatMap((row) => row.parts.map((part) => [part.key, readoutOf({
			type: 'dateSeries', columns: summary.columns,
			series: [{
				label: part.label, swatch: part.swatch, values: part.counts,
				format: (count, day) => `${formatNumber(count, view.numberFormat, { exact: true, si: false })} of ${summary.series[0].values[day]} recorded jobs`
			}],
			notMeasured: 'No recorded jobs', resting: 'last'
		})] as const)))
	};
}

/** One job's square. */
export interface FleetSquare {
	x: number;
	y: number;
	size: number;
	colour: string;
	gradient: FillGradient | null;
	drawing: FleetDrawing;
	/** The column it stands in. */
	day: number;
	row: string;
}

export interface FleetDots {
	frame: Frame;
	/** Where each day's column is centred, in the chart's own pixels. */
	columns: number[];
	bandwidth: number;
	ticks: DayTick[];
	/** The side of every square. */
	size: number;
	squares: FleetSquare[];
	/** Each day's squares as one block, so the day held open is outlined at its own size. */
	blocks: FleetBlock[];
}

/** Where one day's squares stand: their left and right edges and the top of the highest. */
export interface FleetBlock {
	left: number;
	right: number;
	top: number;
}

/** One square a job, a column a day, largest machine count first from the bottom.
 *
 * A day's squares stand as a block no wider than the busiest day's is tall: as
 * many abreast as the square root of the busiest day's count, and never more
 * than the column holds. Every day is then one width and its height is its
 * count, and the most frequent machine stays at the bottom however wide the column.
 * The side is the largest up to `maxPx` that lets the busiest day fit the plot.
 * `gapPx` of ground parts every square from the next.
 */
export function fleetDots(
	view: FleetView,
	opts: { frame: Frame; density: number; padding: number; maxPx: number; gapPx: number }
): FleetDots | null {
	if (view.days.length === 0 || view.placements === 0) return null;
	const box = opts.frame;
	const band = bandScale(view.days, box, 'x', opts.padding);
	const width = band.bandwidth();
	const columns = view.days.map((date) => (band(date) ?? 0) + width / 2);
	const perDay = view.days.map((_, index) =>
		view.rows.reduce((sum, row) => sum + (row.counts[index] ?? 0), 0)
	);
	const busiest = Math.max(...perDay);
	const square = Math.max(1, Math.floor(Math.sqrt(busiest)));

	const abreast = (side: number): number =>
		Math.min(square, Math.max(1, Math.floor((width + opts.gapPx) / (side + opts.gapPx))));
	const fits = (side: number): boolean =>
		Math.ceil(busiest / abreast(side)) * (side + opts.gapPx) - opts.gapPx <= box.innerHeight;
	let size = Math.max(1, Math.floor(opts.maxPx));
	while (size > 1 && !fits(size)) size -= 1;
	const across = abreast(size);
	const step = size + opts.gapPx;

	const blocks: FleetBlock[] = view.days.map((_, day) => {
		const wide = Math.max(1, Math.min(across, perDay[day]));
		const left = columns[day] - (wide * step - opts.gapPx) / 2;
		const lines = Math.ceil(perDay[day] / across);
		return { left, right: left + wide * step - opts.gapPx, top: box.bottom - lines * step + opts.gapPx };
	});
	const squares: FleetSquare[] = [];
	view.days.forEach((_, day) => {
		const left = blocks[day].left;
		let at = 0;
		const parts = view.rows.flatMap((row) => row.parts).sort((a, b) =>
			b.counts[day] - a.counts[day] || a.key.localeCompare(b.key));
		for (const part of parts) {
			for (let count = 0; count < (part.counts[day] ?? 0); count += 1) {
				const line = Math.floor(at / across);
				squares.push({
					x: left + (at % across) * step,
					y: box.bottom - (line + 1) * step + opts.gapPx,
					size,
					colour: part.colour,
					gradient: part.gradient,
					drawing: part.key === UNRECORDED_KEY ? 'unrecorded' : 'step',
					day,
					row: part.key
				});
				at += 1;
			}
		}
	});
	return {
		frame: box,
		columns,
		bandwidth: width,
		ticks: dayTicks(view.days, { density: opts.density, columns, bounds: [box.left, box.right], labels: box.labels }),
		size,
		squares,
		blocks
	};
}
