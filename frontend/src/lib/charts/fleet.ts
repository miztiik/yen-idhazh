/** Which machines ran our jobs, day by day: the rows a panel draws, and where.
 *
 * One stacked bar a day and one segment a kind of machine, counted over the job
 * placements the machine record holds for the open span. A count of what
 * happened and never a rate of what will: what the next job draws is precisely
 * what the processor lottery refuses to quote, so no share, no probability and
 * no pie belongs here.
 *
 * **A machine's colour is its speed** (`machine-colour.ts`), so the segments of
 * a day are stacked slowest at the bottom, where every day shares a baseline and
 * the slow machines the panel exists to show compare exactly day to day.
 *
 * **Placements pick which kinds get a row of their own; speed only sets the
 * colour.** The `topKinds` kinds placed most in the span are named, a tie going
 * to the kind placed most recently. The rest fold only with kinds on their own
 * speed step, because a fold that crossed a step would say two speeds were one,
 * and a step holding one of them names it. Known machines with no speed reading
 * fold into one hatched row, since none of them has a speed a merge could
 * misstate. No machine recorded is always its own row, last, and never folded.
 *
 * **Under `minRows` placements the panel draws one square a job, not a bar a
 * day.** A bar over a small count reads as "this much" and invites a rate the
 * count cannot support; a square a job reads as "these ones", because every
 * mark is a job a reader can point at.
 *
 * **The rows are the query door's own shape.** `fleetJobs` takes the rows a
 * query for `FLEET_COLUMNS` answers, whether the build read them off disk or a
 * browser fetched them, so where they come from can move without anything here
 * moving.
 *
 * Pure. Every threshold, colour and size arrives as an argument.
 */

import type { LostDay } from '../console/recording';
import { nameSpan } from '../console/span-words';
import type { Row } from '../data/ledger';
import { plural, shortDate } from '../format';
import { dayTicks, type DayTick, type Frame } from './frame';
import {
	isUnrecorded,
	machineKeys,
	MACHINE_HUE,
	promptRate,
	rateWords,
	UNRECORDED_KEY,
	type MachineIdentity,
	type MachineKey,
	type MachineRamp
} from './machine-colour';
import { readoutOf, type Readout } from './readout';
import { RESERVED_GREY_INK, type AbsentHatch } from './d3/ordered-colour';
import type { SeriesInput } from './d3/dateSeries';
import { bandScale } from './d3/scale';

/** The columns the panel reads, and the only ones: what a query for it names. */
export const FLEET_COLUMNS = [
	'date',
	'run_id',
	'job',
	'shard',
	'fingerprint',
	'cpu_model',
	'job_seconds',
	'server_prompt_tokens',
	'server_prompt_seconds'
] as const;

/** One job as the panel reads it. */
export interface FleetJob {
	/** The UTC day the job ran, `YYYY-MM-DD`. */
	date: string;
	runId: string;
	/** Which workflow job it was: `work`, `plan`, `assemble` and the rest. */
	job: string;
	shard: number | null;
	fingerprint: string | null;
	cpuModel: string | null;
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
	/** The speed the row's colour stands for: the kind's median, the range of a
	 * fold's medians, or `no speed reading`. Null for no machine recorded. */
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
}

/** One job of a day, as the list a pick opens names it. */
export interface FleetLine {
	runId: string;
	job: string;
	shard: number | null;
	/** The kind of machine in words, never a fold's name. */
	machine: string;
	seconds: number | null;
	rate: number | null;
	/** The row this job is drawn in. */
	row: string;
}

export interface FleetView {
	/** The days that recorded a placement, ascending. One column each. */
	days: string[];
	/** Slowest first, then the machines with no speed reading, then no machine. */
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
	/** The page's one ramp, cut over every machine the page holds. */
	ramp: MachineRamp;
	/** The open span, inclusive UTC days. */
	start: string;
	end: string;
	/** How many days the span covers. */
	windowDays: number;
	/** `console.fleet_min_rows`. */
	minRows: number;
	/** `console.fleet_top_kinds`. */
	topKinds: number;
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
	for (const row of rows) {
		const date = text(row.date);
		const runId = text(row.run_id);
		if (date === null || !DAY.test(date) || runId === null) continue;
		jobs.push({
			date,
			runId,
			job: text(row.job) ?? 'work',
			shard: figure(row.shard),
			fingerprint: text(row.fingerprint),
			cpuModel: text(row.cpu_model),
			seconds: figure(row.job_seconds),
			rate: promptRate(figure(row.server_prompt_tokens), figure(row.server_prompt_seconds))
		});
	}
	return jobs;
}

/** A step of the ramp in words, for the fold that stands on it. */
export function stepWords(step: number, stops: number): string {
	if (stops <= 1) return 'only';
	if (step <= 1) return 'slowest';
	if (step >= stops) return 'fastest';
	if (stops % 2 === 1 && step === (stops + 1) / 2) return 'middle';
	if (step === 2) return 'second slowest';
	if (step === stops - 1) return 'second fastest';
	return `step ${step} of ${stops}`;
}

/** The word that tells kinds of one name apart, fastest first. */
function speedRank(at: number, of: number): string {
	if (of === 2) return at === 0 ? 'faster' : 'slower';
	if (at === 0) return 'fastest';
	if (at === of - 1) return 'slowest';
	const place = at + 1;
	const suffix = place === 2 ? 'nd' : place === 3 ? 'rd' : 'th';
	return `${place}${suffix} fastest`;
}

function rangeNote(rates: readonly number[]): string | null {
	if (rates.length === 0) return null;
	const low = Math.min(...rates);
	const high = Math.max(...rates);
	return low.toFixed(1) === high.toFixed(1)
		? rateWords(low)
		: `${low.toFixed(1)} to ${rateWords(high)}`;
}

/** A known machine the ramp has no identity for: a machine with no reading. */
function untimed(machine: MachineKey): MachineIdentity {
	return { key: machine.key, name: machine.name, step: null, rate: null, colour: RESERVED_GREY_INK };
}

/** The kinds, folds and absence the open span draws, day by day. */
export function fleetView(jobs: readonly FleetJob[], options: FleetOptions): FleetView {
	const inSpan = jobs.filter((job) => job.date >= options.start && job.date <= options.end);
	const resolve = machineKeys(
		jobs.map((job) => ({ fingerprint: job.fingerprint, cpuModel: job.cpuModel }))
	);
	const placed = inSpan.map((job) => {
		const machine = resolve({ fingerprint: job.fingerprint, cpuModel: job.cpuModel });
		return { job, identity: options.ramp.at.get(machine.key) ?? untimed(machine) };
	});
	const days = [...new Set(inSpan.map((job) => job.date))].sort();
	const column = new Map(days.map((date, index) => [date, index]));

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

	// Each kind in the span: its placements, its newest day, and its jobs.
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
			label: identity.name,
			note: identity.rate === null ? 'no speed reading' : rateWords(identity.rate),
			colour: identity.colour,
			drawing: identity.step === null ? 'untimed' : 'step',
			step: identity.step,
			rate: identity.rate,
			counts: counts(identity.key),
			placements: kind.placements,
			members: []
		});
	}
	for (const [fold, members] of folds) {
		if (members.length < 2) continue;
		const first = members[0];
		const rates = members.flatMap((member) => (member.rate === null ? [] : [member.rate]));
		const tally = counts(fold);
		rows.push({
			key: fold,
			label:
				first.step === null
					? 'Other machines with no speed reading'
					: `Other machines at the ${stepWords(first.step, options.ramp.steps.length)} speed`,
			note: rangeNote(rates) ?? 'no speed reading',
			colour: first.colour,
			drawing: first.step === null ? 'untimed' : 'step',
			step: first.step,
			rate: rates.length === 0 ? null : Math.min(...rates),
			counts: tally,
			placements: tally.reduce((sum, count) => sum + count, 0),
			members: members.map((member) => member.name)
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

	// Two kinds of one name are two machines: each takes a word saying which.
	const byName = new Map<string, FleetRow[]>();
	for (const row of rows) {
		if (row.members.length > 0 || row.rate === null) continue;
		byName.set(row.label, [...(byName.get(row.label) ?? []), row]);
	}
	for (const same of byName.values()) {
		if (same.length < 2) continue;
		[...same]
			.sort((a, b) => (b.rate ?? 0) - (a.rate ?? 0))
			.forEach((row, at, all) => (row.label = `${row.label}, ${speedRank(at, all.length)}`));
	}

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
			members: []
		});
	}

	const order = new Map(rows.map((row, index) => [row.key, index]));
	const labelOf = new Map(rows.map((row) => [row.key, row.label]));
	const lines: FleetLine[][] = days.map(() => []);
	for (const { job, identity } of placed) {
		const row = rowOf.get(identity.key) ?? identity.key;
		lines[column.get(job.date) ?? 0].push({
			runId: job.runId,
			job: job.job,
			shard: job.shard,
			machine: row === identity.key ? (labelOf.get(row) ?? identity.name) : identity.name,
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
				a.job.localeCompare(b.job) ||
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
		mostPlaced,
		nothing
	};
}

/** The rows as `dateSeries` stacks them, slowest at the bottom.
 *
 * Keyed by the row's own key, which no two rows share, because two kinds of one
 * name are two series.
 */
export function fleetSeries(view: FleetView): SeriesInput[] {
	return view.rows.map((row) => ({
		label: row.key,
		token: MACHINE_HUE,
		fill: row.colour,
		hatched: row.drawing === 'untimed',
		points: view.days.map((date, index) => ({ date, value: row.counts[index] ?? 0 }))
	}));
}

/** A square's outline and nothing inside: a known machine with no reading, as
 * a square the size of a job's mark shows it. Stripes on a square this small are
 * one or two lines and read as the flat grey of no machine recorded. */
export function hollowSwatch(ink: string): string {
	const side = (at: string, size: string) => `linear-gradient(${ink} 0 0) ${at} / ${size} no-repeat`;
	return [
		side('top', '100% 2px'),
		side('bottom', '100% 2px'),
		side('left', '2px 100%'),
		side('right', '2px 100%')
	].join(', ');
}

/** The strip under the plot: a day a column, every row at that day.
 *
 * It is the key as well, so every row drawn is named and swatched here and no
 * second key is drawn. Each row carries the speed its colour stands for.
 */
export function fleetReadout(view: FleetView, hatch: AbsentHatch): Readout {
	return readoutOf({
		type: 'dateSeries',
		columns: view.days.map(shortDate),
		series: view.rows.map((row) => ({
			label: row.label,
			swatch:
				row.drawing !== 'untimed'
					? row.colour
					: view.shape === 'bars'
						? hatch.background
						: hollowSwatch(hatch.ink),
			values: row.counts,
			format: (value: number) => `${value}`,
			...(row.note === null ? {} : { note: row.note })
		})),
		notMeasured: 'No job was placed on this day',
		resting: 'last'
	});
}

/** One job's square. */
export interface FleetSquare {
	x: number;
	y: number;
	size: number;
	colour: string;
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

/** One square a job, a column a day, filled from the bottom in row order.
 *
 * A day's squares stand as a block no wider than the busiest day's is tall: as
 * many abreast as the square root of the busiest day's count, and never more
 * than the column holds. Every day is then one width and its height is its
 * count, and the slowest machine stays at the bottom however wide the column.
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
		for (const row of view.rows) {
			for (let count = 0; count < (row.counts[day] ?? 0); count += 1) {
				const line = Math.floor(at / across);
				squares.push({
					x: left + (at % across) * step,
					y: box.bottom - (line + 1) * step + opts.gapPx,
					size,
					colour: row.colour,
					drawing: row.drawing,
					day,
					row: row.key
				});
				at += 1;
			}
		}
	});
	return {
		frame: box,
		columns,
		bandwidth: width,
		ticks: dayTicks(view.days, { density: opts.density, columns, bounds: [box.left, box.right] }),
		size,
		squares,
		blocks
	};
}

/** The sentence above the plot: the count, its days, and the kind given most. */
export function fleetSentence(view: FleetView): string {
	const ran = `${plural(view.placements, 'job', 'jobs')} ran in ${nameSpan(view.windowDays)}`;
	const on =
		view.days.length === view.windowDays ? '' : `, on ${plural(view.days.length, 'day', 'days')} of them`;
	const counted = `${ran}${on}.`;
	if (view.mostPlaced === null) return counted;
	return `${counted} The kind we are given most is ${view.mostPlaced.label}, ${view.mostPlaced.placements} of them.`;
}

/** What each fold row holds, in words, or nothing where no row folds. */
export function foldSentences(view: FleetView): string[] {
	return view.rows
		.filter((row) => row.members.length > 0)
		.map((row) => {
			const names = row.members;
			const listed =
				names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
			return `The ${row.label} row holds ${names.length} kinds: ${listed}.`;
		});
}
