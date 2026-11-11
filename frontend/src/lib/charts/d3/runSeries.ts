/** What changes between recorded runs, with sequence spacing rather than elapsed time. */
import { curveMonotoneX, line } from 'd3-shape';
import { compareRuns } from '../../console/queries/shared';
import { firstOfDay, MARK_PAD, runTicks } from '../../console/machine/run-axis';
import { isDay } from '../../data/slice-shapes';
import { dayColumns, type DayTick, type Frame } from '../frame';
import { readoutOf, type Readout, type ReadoutLine } from '../readout';
import type { ChartToken } from '../theme';
import type { NumberFormatConfig } from '../../number-format';
import { valueAxis, type ValueAxis } from './axis';
import { completeModelRule, ruleBoundaries, ruleEvents, type ModelRule, type RuleBoundary } from './model-rule';

export interface RunColumn {
	runId: string;
	date: string;
	events?: readonly ReadoutLine[];
}

export interface RunTrace {
	label: string;
	token: ChartToken;
	dashed: boolean;
	/** One reading per supplied run, with known unmeasured runs left null. */
	values: readonly (number | null)[];
	format: (value: number) => string;
}

export interface RunPoint {
	column: number;
	value: number;
	x: number;
	y: number;
	alone: boolean;
}

export interface RunLine {
	label: string;
	token: ChartToken;
	dashed: boolean;
	path: string;
	points: RunPoint[];
}

export interface RunSeriesOptions {
	frame: Frame;
	density: number;
	valueTicks: number;
	number_format: NumberFormatConfig;
	rule: ModelRule;
	notMeasured: string;
}

export interface RunSeriesGeometry {
	frame: Frame;
	runs: RunColumn[];
	columns: number[];
	ticks: DayTick[];
	axis: ValueAxis;
	lines: RunLine[];
	readout: Readout;
	rule: ModelRule;
	boundaries: RuleBoundary[];
}

export function runSeries(
	runs: readonly RunColumn[],
	series: readonly RunTrace[],
	opts: RunSeriesOptions
): RunSeriesGeometry | null {
	const identities = new Set<string>();
	for (const run of runs) {
		if (!isDay(run.date)) throw new Error('A run column needs a UTC date.');
		// Sorting alone cannot validate a chart with just one run.
		compareRuns(run.runId, run.runId);
		const key = `${run.date}/${run.runId}`;
		if (identities.has(key)) throw new Error(`The run series repeats ${key}.`);
		identities.add(key);
	}
	const names = new Set<string>();
	for (const trace of series) {
		if (!trace.label.trim() || names.has(trace.label)) throw new Error('Run series labels must be distinct and nonempty.');
		names.add(trace.label);
		if (trace.values.length !== runs.length) throw new Error(`"${trace.label}" needs one reading per run.`);
		if (trace.values.some((value) => value !== null && !Number.isFinite(value))) {
			throw new Error(`"${trace.label}" needs finite readings or null.`);
		}
	}
	const values = series.flatMap((trace) => trace.values.filter((value): value is number => value !== null));
	if (values.length === 0) return null;
	const order = runs.map((_, index) => index).sort((a, b) =>
		runs[a].date.localeCompare(runs[b].date) || compareRuns(runs[a].runId, runs[b].runId));
	const ordered = order.map((index) => runs[index]);
	const box = opts.frame;
	const columns = dayColumns(ordered.length, box, MARK_PAD);
	const dates = ordered.map((run) => run.date);
	const axis = valueAxis(values, box, { along: 'y', ticks: opts.valueTicks, number_format: opts.number_format });
	const rule = completeModelRule(opts.rule, dates);
	const events = ruleEvents(rule, dates);
	const lines = series.map((trace): RunLine => {
		const segments: RunPoint[][] = [];
		let segment: RunPoint[] = [];
		for (const [column, index] of order.entries()) {
			const value = trace.values[index];
			if (value === null) {
				if (segment.length) segments.push(segment);
				segment = [];
			} else {
				segment.push({ column, value, x: columns[column], y: axis.scale(value), alone: false });
			}
		}
		if (segment.length) segments.push(segment);
		const draw = line<RunPoint>().x((point) => point.x).y((point) => point.y).curve(curveMonotoneX);
		return {
			label: trace.label, token: trace.token, dashed: trace.dashed,
			path: segments.filter((part) => part.length > 1).map((part) => draw(part) ?? '').join(''),
			points: segments.flatMap((part) => part.map((point) => ({ ...point, alone: part.length === 1 })))
		};
	});
	return {
		frame: box, runs: ordered, columns, axis, lines, rule,
		ticks: runTicks(dates, columns, opts.density, box.labels),
		boundaries: ruleBoundaries(rule, firstOfDay(ordered), columns, box.left),
		readout: readoutOf({
			type: 'runSeries',
			columns: ordered.map((run) => `${run.runId} | ${run.date} UTC`),
			series: series.map((trace) => ({
				label: trace.label, swatch: `var(${trace.token})`, note: trace.dashed ? 'dashed' : 'solid',
				values: order.map((index) => trace.values[index]), format: trace.format
			})),
			events: { lines: ordered.map((run, index) => [...(run.events ?? []), ...events.lines[index]]) },
			notMeasured: opts.notMeasured,
			resting: 'last'
		})
	};
}
